# -*- coding: utf-8 -*-
"""无人机业务节点
健壮性设计：
- 分级降级策略：错误率高时自动降低非关键数据发送频率
- 背压控制：点云等大数据发送失败时自动降频
- 看门狗：工作线程异常退出自动重启
- 错误熔断：连续错误过多时熔断保护，避免雪崩
- 全局健康状态聚合
- 信号处理与优雅关闭
- 内存保护：大数据发送前二次检查
"""

import os
import sys
import time
import signal
import threading
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protocol import HeartbeatMessage, DataMessage, PointCloudMessage, SystemMetricsMessage
from transport.base_sender import TransportSender
from config.drone_config import DroneConfig
from .hardware.base_drone_hardware import DroneHardwareBase
from .hardware.system_metrics_collector import SystemMetricsCollector


class DroneNode:
    """无人机业务节点"""

    def __init__(
        self,
        config: DroneConfig,
        heartbeat_transport: TransportSender,
        data_transport: TransportSender,
        hardware: DroneHardwareBase,
        pointcloud_transport: TransportSender = None,
        metrics_transport: TransportSender = None,
        metrics_collector: SystemMetricsCollector = None
    ):
        self.config = config
        self.heartbeat_transport = heartbeat_transport
        self.data_transport = data_transport
        self.pointcloud_transport = pointcloud_transport
        self.metrics_transport = metrics_transport
        self.hardware = hardware

        # 从配置读取阈值 - 保守冗余版
        self.CIRCUIT_BREAKER_THRESHOLD = config.circuit_breaker_threshold
        self.CIRCUIT_BREAKER_RECOVERY = config.circuit_breaker_recovery
        self.MAX_POINTS = config.max_pointcloud_points
        self.MAX_PACKET_SIZE = config.max_packet_size

        # 系统性能采集器（外部传入，支持硬件看门狗等配置）
        self.metrics_collector = metrics_collector
        if self.metrics_collector is None and config.enable_system_metrics:
            self.metrics_collector = SystemMetricsCollector()

        # 序列号
        self._seq = 0
        self._pc_seq = 0
        self._metrics_seq = 0

        # 运行状态
        self._running = False
        self._shutting_down = False
        self._shutdown_event = threading.Event()
        self._threads: Dict[str, threading.Thread] = {}
        self._thread_watchdogs: Dict[str, int] = {}
        self._lock = threading.RLock()

        # 错误计数与熔断
        self._error_counts: Dict[str, int] = {
            "heartbeat": 0, "data": 0, "pointcloud": 0, "metrics": 0
        }
        self._circuit_breakers: Dict[str, bool] = {
            "heartbeat": False, "data": False, "pointcloud": False, "metrics": False
        }
        self._circuit_breaker_open_time: Dict[str, float] = {}

        # 通道状态
        self._channel_status: Dict[str, str] = {
            "heartbeat": "starting",
            "data": "starting",
            "pointcloud": "disabled" if not config.enable_pointcloud else "starting",
            "metrics": "disabled" if not config.enable_system_metrics else "starting"
        }

        # 降级状态 - 保守阈值，提前降载留冗余
        self._degraded_mode = False
        self._degraded_reason = ""
        self._cpu_throttle_threshold = config.cpu_throttle_threshold
        self._memory_throttle_threshold = config.memory_throttle_threshold

        # 性能参数 - 从配置读取（保守值）
        self._max_pointcloud_points = config.max_pointcloud_points
        self._max_packet_size = config.max_packet_size

        # ========== 资源冗余保护：主动限流状态 ==========
        self._system_cpu_high = False       # 系统CPU超过阈值
        self._memory_pressure = False       # 内存超过阈值
        self._last_resource_check = 0.0

        # 注册信号处理
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """注册优雅关闭信号处理"""
        def _signal_handler(signum, frame):
            if self._shutting_down:
                # 第二次按 Ctrl+C，强制退出
                print("\n[系统] 强制退出...")
                import os
                os._exit(1)
            print(f"\n[系统] 收到信号 {signum}，开始优雅关闭...（再按一次强制退出）")
            self._shutting_down = True
            # 在新线程中执行关闭，避免阻塞信号处理
            import threading
            threading.Thread(target=self.stop, daemon=True).start()
        try:
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)
        except (ValueError, AttributeError):
            # Windows或非主线程可能无法注册信号
            pass

    def _is_circuit_open(self, channel: str) -> bool:
        """检查通道熔断器是否打开"""
        if not self._circuit_breakers.get(channel, False):
            return False
        # 检查是否到了恢复时间
        open_time = self._circuit_breaker_open_time.get(channel, 0)
        if time.time() - open_time > self.CIRCUIT_BREAKER_RECOVERY:
            # 尝试半开状态
            self._circuit_breakers[channel] = False
            self._error_counts[channel] = 0
            print(f"[熔断器] {channel} 通道尝试恢复")
            return False
        return True

    def _record_channel_success(self, channel: str) -> None:
        """记录通道发送成功"""
        self._error_counts[channel] = 0
        self._channel_status[channel] = "healthy"
        if self._circuit_breakers.get(channel, False):
            self._circuit_breakers[channel] = False
            print(f"[熔断器] {channel} 通道恢复正常")

    def _record_channel_error(self, channel: str, error: Exception) -> None:
        """记录通道发送错误，触发熔断"""
        self._error_counts[channel] = self._error_counts.get(channel, 0) + 1
        self._channel_status[channel] = "error"

        if self._error_counts[channel] >= self.CIRCUIT_BREAKER_THRESHOLD:
            if not self._circuit_breakers.get(channel, False):
                self._circuit_breakers[channel] = True
                self._circuit_breaker_open_time[channel] = time.time()
                print(f"[熔断器] {channel} 通道连续错误{self.CIRCUIT_BREAKER_THRESHOLD}次，熔断保护{self.CIRCUIT_BREAKER_RECOVERY}秒")

    def _get_adaptive_interval(self, base_interval: float, channel: str) -> float:
        """根据错误率自适应调整发送间隔（背压控制）"""
        errors = self._error_counts.get(channel, 0)
        if errors < 3:
            return base_interval
        elif errors < 10:
            return base_interval * 2
        else:
            return base_interval * 5

    def _watchdog_loop(self) -> None:
        """看门狗线程：监控工作线程存活，异常退出自动重启"""
        while self._running and not self._shutdown_event.is_set():
            try:
                for name, thread in list(self._threads.items()):
                    if not thread.is_alive() and self._running:
                        print(f"[看门狗] {name} 线程异常退出，正在重启...")
                        self._restart_thread(name)
                time.sleep(2)
            except Exception as e:
                print(f"[看门狗] 异常: {e}")
                time.sleep(1)

    def _restart_thread(self, name: str) -> None:
        """重启指定工作线程"""
        thread_funcs = {
            "heartbeat": self._heartbeat_loop,
            "data": self._data_loop,
            "pointcloud": self._pointcloud_loop,
            "metrics": self._metrics_loop
        }
        if name in thread_funcs:
            t = threading.Thread(target=thread_funcs[name], daemon=True, name=name)
            t.start()
            self._threads[name] = t
            print(f"[看门狗] {name} 线程已重启")

    def _heartbeat_loop(self) -> None:
        """心跳发送循环 - 带熔断保护"""
        while self._running and not self._shutdown_event.is_set():
            try:
                if self._is_circuit_open("heartbeat"):
                    time.sleep(1.0)
                    continue

                msg = HeartbeatMessage.create(drone_id=self.config.drone_id)
                self.heartbeat_transport.send(msg.to_json().encode("utf-8"))
                self._record_channel_success("heartbeat")

            except Exception as e:
                self._record_channel_error("heartbeat", e)
                if self._error_counts["heartbeat"] % 10 == 1:
                    print(f"[心跳] 发送失败: {e}")

            interval = self._get_adaptive_interval(self.config.heartbeat_interval, "heartbeat")
            self._shutdown_event.wait(interval)

    def _data_loop(self) -> None:
        """飞控数据发送循环 - 带降级策略"""
        while self._running and not self._shutdown_event.is_set():
            try:
                if self._is_circuit_open("data"):
                    time.sleep(1.0)
                    continue

                # 硬件连接检查
                if not self.hardware.is_connected():
                    flight_mode = "DISCONNECTED"
                    battery = {"percent": 0.0, "voltage": 0.0, "current": 0.0}
                    position = {}
                    attitude = {}
                    velocity = {}
                    sensors = {}
                else:
                    # 单项读取异常隔离，单个传感器失败不影响其他
                    try:
                        flight_mode = self.hardware.get_flight_mode() or "UNKNOWN"
                    except Exception as e:
                        flight_mode = "ERROR"
                        print(f"[数据] 飞行模式读取失败: {e}")

                    try:
                        battery = self.hardware.get_battery_detail()
                        if not battery or "percent" not in battery:
                            battery = {"percent": 0.0, "voltage": 0.0, "current": 0.0}
                    except Exception as e:
                        battery = {"percent": 0.0, "voltage": 0.0, "current": 0.0}
                        print(f"[数据] 电池数据读取失败: {e}")

                    try:
                        position = self.hardware.get_position() or {}
                    except Exception:
                        position = {}
                    try:
                        attitude = self.hardware.get_attitude() or {}
                    except Exception:
                        attitude = {}
                    try:
                        velocity = self.hardware.get_velocity() or {}
                    except Exception:
                        velocity = {}
                    try:
                        sensors = self.hardware.get_sensors() or {}
                    except Exception:
                        sensors = {}

                # 组装报文
                msg = DataMessage.create(
                    drone_id=self.config.drone_id,
                    seq=self._seq,
                    mode=flight_mode,
                    battery=battery,
                    attitude=attitude,
                    position=position,
                    velocity=velocity,
                    sensors=sensors
                )
                self.data_transport.send(msg.to_json().encode("utf-8"))
                self._record_channel_success("data")

                if self._seq % 50 == 0:
                    gps_status = "有定位" if position and "lat" in position else "无GPS"
                    print(f"[数据] seq={self._seq} 模式={flight_mode} 电量={battery.get('percent', 0)}% {gps_status}")
                self._seq += 1

            except ConnectionError as e:
                self._record_channel_error("data", e)
            except TimeoutError as e:
                self._record_channel_error("data", e)
            except Exception as e:
                self._record_channel_error("data", e)
                if self._error_counts["data"] % 10 == 1:
                    print(f"[数据] 发送异常: {e}")

            interval = self._get_adaptive_interval(self.config.data_interval, "data")
            self._shutdown_event.wait(interval)

    def _pointcloud_loop(self) -> None:
        """点云数据发送循环 - 轻量版，多留资源给SLAM/导航
        资源紧张时主动暂停点云发送，不抢CPU/内存/带宽
        """
        if not self.config.enable_pointcloud or self.pointcloud_transport is None:
            return

        print("[点云] 点云发送线程启动（轻量预览模式，资源紧张时自动暂停）")
        while self._running and not self._shutdown_event.is_set():
            try:
                if self._is_circuit_open("pointcloud"):
                    time.sleep(2.0)
                    continue

                # ========== 资源检查：CPU/内存紧张时主动暂停点云 ==========
                if self._system_cpu_high or self._memory_pressure:
                    # CPU或内存紧张，暂停点云发送，把资源让给核心算法
                    self._channel_status["pointcloud"] = "throttled"
                    self._shutdown_event.wait(2.0)
                    continue

                # 熔断器打开或降级模式，直接跳过
                if self._degraded_mode:
                    self._shutdown_event.wait(self.config.pointcloud_interval * 3)
                    continue

                if not self.hardware.has_pointcloud():
                    self._shutdown_event.wait(self.config.pointcloud_interval)
                    continue

                points = self.hardware.get_pointcloud()
                if not points:
                    self._shutdown_event.wait(self.config.pointcloud_interval)
                    continue

                # 自适应降采样：正常模式传完整点云，错误率高时降采样
                max_points = self.config.max_pointcloud_points
                if self._error_counts["pointcloud"] > 5:
                    max_points = max_points // 2
                if self._error_counts["pointcloud"] > 10:
                    max_points = max_points // 3

                if len(points) > max_points:
                    # 均匀降采样，而不是只取前N个
                    step = len(points) / max_points
                    points = [points[int(i * step)] for i in range(max_points)]

                msg = PointCloudMessage.create(
                    drone_id=self.config.drone_id,
                    seq=self._pc_seq,
                    frame_id="velodyne",
                    points=points,
                    compression="zlib",
                    compression_level=self.config.pointcloud_compression_level
                )

                # 二次检查报文大小
                msg_data = msg.to_json().encode("utf-8")
                if len(msg_data) > self.config.max_packet_size:
                    if self._pc_seq % 20 == 0:
                        print(f"[点云] 帧过大({len(msg_data)//1024}KB)，跳过发送")
                    self._shutdown_event.wait(self.config.pointcloud_interval)
                    continue

                self.pointcloud_transport.send(msg_data)
                self._record_channel_success("pointcloud")

                if self._pc_seq % 30 == 0:
                    print(f"[点云] seq={self._pc_seq} 点数={len(points)} 大小={len(msg_data)//1024}KB")
                self._pc_seq += 1

                # 发送完主动让出CPU，给其他进程机会
                time.sleep(0.001)

            except ConnectionError as e:
                self._record_channel_error("pointcloud", e)
            except TimeoutError as e:
                self._record_channel_error("pointcloud", e)
            except MemoryError:
                print("[点云] 内存不足，跳过大帧点云")
                self._channel_status["pointcloud"] = "memory_pressure"
                self._shutdown_event.wait(5.0)
            except Exception as e:
                self._record_channel_error("pointcloud", e)
                if self._error_counts["pointcloud"] % 10 == 1:
                    print(f"[点云] 发送异常: {e}")

            interval = self._get_adaptive_interval(self.config.pointcloud_interval, "pointcloud")
            self._shutdown_event.wait(interval)

    def _metrics_loop(self) -> None:
        """系统性能数据发送循环"""
        if not self.config.enable_system_metrics or self.metrics_transport is None:
            return
        if self.metrics_collector is None:
            print("[系统监控] psutil未安装，系统性能采集已禁用")
            return

        print("[系统监控] 系统性能监控线程启动")
        while self._running and not self._shutdown_event.is_set():
            try:
                if self._is_circuit_open("metrics"):
                    time.sleep(2.0)
                    continue

                # 收集所有通道的健康状态
                channel_health = {
                    name: {
                        "status": status,
                        "errors": self._error_counts.get(name, 0),
                        "circuit_open": self._circuit_breakers.get(name, False)
                    }
                    for name, status in self._channel_status.items()
                }

                metrics = self.metrics_collector.collect(channel_health)

                # 添加硬件健康状态
                try:
                    metrics["hardware_health"] = self.hardware.get_hardware_health()
                except Exception:
                    metrics["hardware_health"] = {}

                # 添加传输层健康状态
                try:
                    metrics["transport_health"] = {
                        "heartbeat": self.heartbeat_transport.get_health_status(),
                        "data": self.data_transport.get_health_status(),
                    }
                    if self.pointcloud_transport:
                        metrics["transport_health"]["pointcloud"] = self.pointcloud_transport.get_health_status()
                    if self.metrics_transport:
                        metrics["transport_health"]["metrics"] = self.metrics_transport.get_health_status()
                except Exception:
                    metrics["transport_health"] = {}

                msg = SystemMetricsMessage.create(
                    drone_id=self.config.drone_id,
                    seq=self._metrics_seq,
                    cpu=metrics["cpu"],
                    memory=metrics["memory"],
                    disk=metrics["disk"],
                    network=metrics["network"],
                    comm_channels=metrics["comm_channels"],
                    process=metrics["process"],
                    uptime_seconds=metrics["uptime_seconds"],
                    temperature=metrics.get("temperature")
                )
                self.metrics_transport.send(msg.to_json().encode("utf-8"))
                self._record_channel_success("metrics")

                # 检查是否进入降级模式（香橙派资源预留策略）
                cpu_percent = metrics["cpu"]["percent"]
                mem_percent = metrics["memory"]["percent"]
                mem_available_mb = metrics["memory"]["available_mb"]
                cpu_throttle = self.config.cpu_throttle_threshold
                mem_throttle = self.config.memory_throttle_threshold
                low_mem_mb = self.config.memory_low_mb

                # CPU过高：非关键数据降频
                cpu_high = cpu_percent > cpu_throttle
                # 内存过高：主动降级
                mem_high = mem_percent > mem_throttle or mem_available_mb < low_mem_mb

                # 更新限流状态，供其他线程使用
                self._system_cpu_high = cpu_high
                self._memory_pressure = mem_high

                if (cpu_high or mem_high) and not self._degraded_mode:
                    reasons = []
                    if cpu_high:
                        reasons.append(f"CPU使用率{cpu_percent}%>{cpu_throttle}%")
                    if mem_high:
                        reasons.append(f"内存不足(使用率{mem_percent}%, 可用{mem_available_mb}MB)")
                    self._degraded_mode = True
                    self._degraded_reason = ", ".join(reasons)
                    print(f"[资源保护] 进入降级模式: {self._degraded_reason}，暂停非关键数据发送")
                elif not cpu_high and not mem_high and self._degraded_mode:
                    self._degraded_mode = False
                    self._degraded_reason = ""
                    print("[资源保护] 系统资源恢复，退出降级模式")

                if self._metrics_seq % 15 == 0:
                    cpu_pct = metrics["cpu"]["percent"]
                    mem_pct = metrics["memory"]["percent"]
                    print(f"[系统监控] seq={self._metrics_seq} CPU={cpu_pct}% 内存={mem_pct}%")
                self._metrics_seq += 1

            except ConnectionError as e:
                self._record_channel_error("metrics", e)
            except TimeoutError as e:
                self._record_channel_error("metrics", e)
            except Exception as e:
                self._record_channel_error("metrics", e)
                if self._error_counts["metrics"] % 10 == 1:
                    print(f"[系统监控] 发送异常: {e}")

            interval = self._get_adaptive_interval(self.config.metrics_interval, "metrics")
            self._shutdown_event.wait(interval)

    def start(self) -> None:
        """启动无人机节点"""
        print("=" * 70)
        print(f"  无人机 {self.config.drone_id} 启动（高可靠模式）")
        print(f"  目标地址: {self.config.target_ip}")
        print(f"  心跳端口(UDP): {self.config.heartbeat_port}")
        print(f"  数据端口(TCP): {self.config.data_port}")
        if self.config.enable_pointcloud and self.pointcloud_transport:
            print(f"  点云端口(TCP): {self.config.pointcloud_port} (LiDAR点云)")
        if self.config.enable_system_metrics and self.metrics_transport:
            print(f"  监控端口(TCP): {self.config.metrics_port} (系统性能)")
        print(f"  健壮性: 自动重连+熔断保护+看门狗+降级策略")
        print("=" * 70)

        if not self.hardware.is_connected():
            print("[初始化] 警告：当前未检测到无人机硬件连接，等待连接...")

        self._running = True
        self._shutdown_event.clear()

        # 启动工作线程
        thread_configs = [
            ("heartbeat", self._heartbeat_loop),
            ("data", self._data_loop),
        ]
        if self.config.enable_pointcloud and self.pointcloud_transport:
            thread_configs.append(("pointcloud", self._pointcloud_loop))
        if self.config.enable_system_metrics and self.metrics_transport:
            thread_configs.append(("metrics", self._metrics_loop))

        for name, func in thread_configs:
            t = threading.Thread(target=func, daemon=True, name=name)
            t.start()
            self._threads[name] = t

        # 启动看门狗
        watchdog = threading.Thread(target=self._watchdog_loop, daemon=True, name="watchdog")
        watchdog.start()
        self._threads["watchdog"] = watchdog

    def stop(self) -> None:
        """优雅关闭节点"""
        if not self._running:
            return

        print("[系统] 正在停止...")
        self._running = False
        self._shutdown_event.set()

        # 先关闭传输，让发送线程快速退出
        for transport, name in [
            (self.heartbeat_transport, "heartbeat"),
            (self.data_transport, "data"),
            (self.pointcloud_transport, "pointcloud"),
            (self.metrics_transport, "metrics")
        ]:
            if transport:
                try:
                    transport.close()
                except Exception as e:
                    print(f"[关闭] {name}传输关闭异常: {e}")

        # 等待线程结束（缩短超时时间）
        for name, t in self._threads.items():
            if t.is_alive():
                t.join(timeout=1.0)

        # 关闭硬件
        try:
            self.hardware.close()
        except Exception as e:
            print(f"[关闭] 硬件关闭异常: {e}")

        print("[系统] 无人机节点已安全退出")

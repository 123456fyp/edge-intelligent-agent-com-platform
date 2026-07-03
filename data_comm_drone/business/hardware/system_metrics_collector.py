# -*- coding: utf-8 -*-
"""系统性能监控采集器
适配ARM64架构，支持RK3588特有温度传感器（CPU大核/小核/GPU/NPU）
"""
import os
import time
import threading
from typing import Dict, Any, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[系统监控] 警告: psutil未安装，系统性能采集功能不可用")
    print("[系统监控] 请执行: pip3 install psutil")


class SystemMetricsCollector:
    """系统性能采集器 - Orange Pi 5 Max优化版"""

    # RK3588 sysfs温度传感器路径
    RK3588_THERMAL_PATHS = {
        "cpu_big": "/sys/class/thermal/thermal_zone0/temp",      # CPU大核 A76
        "cpu_little": "/sys/class/thermal/thermal_zone1/temp",   # CPU小核 A55
        "gpu": "/sys/class/thermal/thermal_zone2/temp",          # GPU Mali-G610
        "npu": "/sys/class/thermal/thermal_zone3/temp",          # NPU RKNN
        "soc": "/sys/class/thermal/thermal_zone4/temp",          # SOC整体
    }

    def __init__(self):
        self._lock = threading.Lock()
        self._process = psutil.Process(os.getpid()) if PSUTIL_AVAILABLE else None
        self._last_net_io = None
        self._boot_time = psutil.boot_time() if PSUTIL_AVAILABLE else time.time()
        self._is_rk3588 = self._detect_rk3588()

        if self._is_rk3588:
            print("[系统监控] 检测到RK3588平台，启用硬件温度监控")

        # 缓存
        self._metrics_cache: Optional[Dict[str, Any]] = None
        self._last_collect_time = 0

    def _detect_rk3588(self) -> bool:
        """检测是否运行在RK3588平台"""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().lower()
                    if "rk3588" in model or "orange pi 5" in model:
                        return True
            # 检查CPU信息
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read().lower()
                    if "rk3588" in cpuinfo:
                        return True
        except Exception:
            pass
        return False

    def _read_rk3588_temp(self, path: str) -> Optional[float]:
        """读取RK3588 sysfs温度传感器"""
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    temp_milli = int(f.read().strip())
                    return round(temp_milli / 1000.0, 1)
        except Exception:
            pass
        return None

    def _get_rk3588_temperatures(self) -> Dict[str, float]:
        """读取RK3588所有温度传感器"""
        temps = {}
        for name, path in self.RK3588_THERMAL_PATHS.items():
            temp = self._read_rk3588_temp(path)
            if temp is not None:
                temps[name] = temp
        return temps if temps else None

    def _get_cpu_freqs(self) -> Dict[str, Any]:
        """获取RK3588大小核频率信息"""
        freqs = {}
        try:
            # RK3588: 0-3是A55小核，4-7是A76大核
            little_freqs = []
            big_freqs = []
            for cpu_id in range(8):
                cpufreq_path = f"/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_cur_freq"
                if os.path.exists(cpufreq_path):
                    with open(cpufreq_path, "r") as f:
                        freq_khz = int(f.read().strip())
                        freq_mhz = freq_khz / 1000
                        if cpu_id < 4:
                            little_freqs.append(freq_mhz)
                        else:
                            big_freqs.append(freq_mhz)
            if little_freqs:
                freqs["little_core_mhz"] = round(max(little_freqs))
            if big_freqs:
                freqs["big_core_mhz"] = round(max(big_freqs))
        except Exception:
            pass
        return freqs

    def collect(self, comm_channel_status: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """采集一次系统性能数据"""
        if not PSUTIL_AVAILABLE:
            return self._get_empty_metrics()

        with self._lock:
            now = time.time()
            # 500ms缓存，避免频繁采集
            if self._metrics_cache and (now - self._last_collect_time) < 0.5:
                result = dict(self._metrics_cache)
                if comm_channel_status is not None:
                    result["comm_channels"] = comm_channel_status
                return result

            # ========== CPU ==========
            cpu_percent = psutil.cpu_percent(interval=0.05)  # 缩短采样间隔
            cpu = {
                "percent": cpu_percent,
                "core_count_physical": psutil.cpu_count(logical=False),
                "core_count_logical": psutil.cpu_count(logical=True),
            }
            try:
                freq = psutil.cpu_freq()
                if freq:
                    cpu["freq_mhz"] = round(freq.current)
            except Exception:
                pass
            # RK3588大小核频率
            cpu.update(self._get_cpu_freqs())

            # ========== 内存 - 16G内存优化 ==========
            mem = psutil.virtual_memory()
            memory = {
                "total_mb": round(mem.total / 1024 / 1024, 1),
                "used_mb": round(mem.used / 1024 / 1024, 1),
                "available_mb": round(mem.available / 1024 / 1024, 1),
                "percent": mem.percent,
                "total_gb": round(mem.total / 1024 / 1024 / 1024, 1),
            }
            # Swap
            try:
                swap = psutil.swap_memory()
                memory["swap_used_mb"] = round(swap.used / 1024 / 1024, 1)
                memory["swap_percent"] = swap.percent
            except Exception:
                pass

            # ========== 磁盘 ==========
            disk = psutil.disk_usage("/")
            disk_info = {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 1),
                "percent": round(disk.percent, 1)
            }
            # 磁盘IO
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    disk_info["read_mb"] = round(disk_io.read_bytes / 1024 / 1024, 1)
                    disk_info["write_mb"] = round(disk_io.write_bytes / 1024 / 1024, 1)
            except Exception:
                pass

            # ========== 网络 ==========
            current_net = psutil.net_io_counters()
            network = {}
            if self._last_net_io is not None:
                time_delta = now - self._last_collect_time if self._last_collect_time > 0 else 1.0
                network["send_rate_bps"] = round((current_net.bytes_sent - self._last_net_io.bytes_sent) / time_delta, 1)
                network["recv_rate_bps"] = round((current_net.bytes_recv - self._last_net_io.bytes_recv) / time_delta, 1)
            network["total_sent_mb"] = round(current_net.bytes_sent / 1024 / 1024, 1)
            network["total_recv_mb"] = round(current_net.bytes_recv / 1024 / 1024, 1)
            self._last_net_io = current_net

            # ========== 当前进程 ==========
            process_info = {}
            try:
                with self._process.oneshot():
                    process_info = {
                        "pid": self._process.pid,
                        "cpu_percent": round(self._process.cpu_percent(), 1),
                        "memory_mb": round(self._process.memory_info().rss / 1024 / 1024, 1),
                        "num_threads": self._process.num_threads(),
                        "create_time": self._process.create_time(),
                        "cpu_num": self._process.cpu_num()
                    }
            except Exception:
                pass

            # ========== 运行时间 ==========
            uptime = round(now - self._boot_time, 1)

            # ========== 温度 - RK3588优先 ==========
            temperature = None
            if self._is_rk3588:
                temperature = self._get_rk3588_temperatures()
            # fallback到psutil
            if temperature is None:
                try:
                    temps = psutil.sensors_temperatures()
                    if temps:
                        temperature = {}
                        for name, entries in temps.items():
                            for entry in entries:
                                temperature[f"{name}_{entry.label or 'core'}"] = round(entry.current, 1)
                except Exception:
                    pass

            # ========== 通信通道状态 ==========
            if comm_channel_status is None:
                comm_channel_status = {}

            # ========== 平台信息 ==========
            platform_info = {
                "arch": os.uname().machine,
                "platform": "RK3588" if self._is_rk3588 else "generic",
                "hostname": os.uname().nodename
            }

            result = {
                "cpu": cpu,
                "memory": memory,
                "disk": disk_info,
                "network": network,
                "comm_channels": comm_channel_status,
                "process": process_info,
                "uptime_seconds": uptime,
                "temperature": temperature,
                "platform": platform_info
            }

            self._metrics_cache = result
            self._last_collect_time = now
            return result

    def _get_empty_metrics(self) -> Dict[str, Any]:
        """psutil不可用时返回空数据"""
        return {
            "cpu": {"percent": 0, "core_count_physical": 0, "core_count_logical": 0},
            "memory": {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0},
            "disk": {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0},
            "network": {},
            "comm_channels": {},
            "process": {},
            "uptime_seconds": 0,
            "temperature": None,
            "platform": {"arch": "unknown", "platform": "unknown"}
        }

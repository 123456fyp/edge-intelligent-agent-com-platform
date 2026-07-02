# -*- coding: utf-8 -*-
"""??????? - ???
?????????????????UI?????
"""
import json
import time
import threading
from typing import Dict, Set, Tuple, Optional

from PyQt5.QtCore import QObject, pyqtSignal, QTimer  # ?????QTimer

from config.ground_station_config import GroundStationConfig
from transport.base_receiver import TransportReceiver
from protocol import HeartbeatMessage, DataMessage
from utils import quaternion_to_euler


class GroundStation(QObject):
    """????????????Qt??????"""
    # ???????????????????
    sig_drone_online = pyqtSignal(str)
    sig_drone_offline = pyqtSignal(str)
    sig_data_updated = pyqtSignal(str)  # ??????ID

    def __init__(
        self,
        config: GroundStationConfig,
        heartbeat_receiver: TransportReceiver,
        data_receiver: TransportReceiver,
        parent=None
    ):
        super().__init__(parent)
        self.config = config
        self.heartbeat_receiver = heartbeat_receiver
        self.data_receiver = data_receiver

        # ???????
        self._last_heartbeat: Dict[str, float] = {}
        self._drone_status: Dict[str, dict] = {}

        self._running = False
        self._lock = threading.Lock()

        # ========== ???1??????????????????==========
        self._offline_check_timer = QTimer(self)
        self._offline_check_timer.timeout.connect(self.check_offline_drones)
        # ????????????????
        self._offline_check_timer.setInterval(1000)

    # ========== ???? ==========
    def _on_heartbeat_message(self, raw_data: bytes, addr: Tuple[str, int]) -> None:
        if not self._is_allowed_drone(addr):
            return

        """??????????????"""
        try:
            msg = HeartbeatMessage.from_json(raw_data.decode("utf-8"))
            is_new = False

            with self._lock:
                self._last_heartbeat[msg.drone_id] = time.time()
                if msg.drone_id not in self._drone_status:
                    self._drone_status[msg.drone_id] = {}
                    is_new = True

            # ???????????
            if is_new:
                self.sig_drone_online.emit(msg.drone_id)
                print(f"[??] ??????: {msg.drone_id} ??:{addr[0]}:{addr[1]}")

        except Exception as e:
            print(f"[????] ??: {e}")

    def _on_data_message(self, raw_data: bytes, addr: Tuple[str, int]) -> None:
        if not self._is_allowed_drone(addr):
            return

        """?????????????????????"""
        try:
            raw_json = raw_data.decode("utf-8")
            msg = DataMessage.from_json(raw_json)

            # ??????????
            attitude = self._normalize_attitude(msg.attitude)

            is_new = False
            with self._lock:
                # ========== ???2????????????????????????==========
                self._last_heartbeat[msg.drone_id] = time.time()

                # ========== ???3??????????????????????????????==========
                if msg.drone_id not in self._drone_status:
                    is_new = True

                # ?????????
                self._drone_status[msg.drone_id] = {
                    "seq": msg.seq,
                    "timestamp": msg.timestamp,
                    "mode": msg.mode,
                    "battery": msg.battery,
                    "position": msg.position,
                    "attitude": attitude,
                    "velocity": msg.velocity,
                    "sensors": msg.sensors
                }

            # ?????????????
            if is_new:
                self.sig_drone_online.emit(msg.drone_id)
                print(f"[??] ??????(????): {msg.drone_id} ??:{addr[0]}:{addr[1]}")

            # ?????????UI????
            self.sig_data_updated.emit(msg.drone_id)

            # ??????????????????????
            alt = msg.position.get("alt", "N/A")
            bat = msg.battery.get("percent", "N/A")
            print(f"[??] {msg.drone_id} seq={msg.seq} ??={msg.mode} ??={alt}m ??={bat}%")

        except Exception as e:
            print(f"[????] ??: {e}")

    def _normalize_attitude(self, atti_raw: dict) -> dict:
        """????????????????????"""
        if "x" in atti_raw and "w" in atti_raw:
            try:
                roll, pitch, yaw = quaternion_to_euler(
                    float(atti_raw.get("x", 0)),
                    float(atti_raw.get("y", 0)),
                    float(atti_raw.get("z", 0)),
                    float(atti_raw.get("w", 1))
                )
                return {
                    "roll": round(roll, 2),
                    "pitch": round(pitch, 2),
                    "yaw": round(yaw, 2)
                }
            except Exception:
                return atti_raw
        return atti_raw

    def _is_allowed_drone(self, addr: Tuple[str, int]) -> bool:
        allowed_ip = getattr(self.config, "allowed_drone_ip", "").strip()
        if not allowed_ip:
            return True
        return addr[0] == allowed_ip

    # ========== ?????? ==========
    def get_online_ids(self) -> list:
        """?????????ID??"""
        with self._lock:
            return list(self._last_heartbeat.keys())

    def get_drone_status(self, drone_id: str) -> Optional[dict]:
        """???????????"""
        with self._lock:
            data = self._drone_status.get(drone_id)
            return data.copy() if data else None

    def check_offline_drones(self) -> Set[str]:
        """?????????????????????"""
        now = time.time()
        offline = set()
        timeout = self.config.heartbeat_timeout

        with self._lock:
            for drone_id, last_time in self._last_heartbeat.items():
                if now - last_time > timeout:
                    offline.add(drone_id)

            for drone_id in offline:
                self._last_heartbeat.pop(drone_id, None)
                self._drone_status.pop(drone_id, None)

        # ??????
        for drone_id in offline:
            self.sig_drone_offline.emit(drone_id)
            print(f"[??] ???????: {drone_id}")

        return offline

    def get_all_status_json(self, indent: int = 2) -> str:
        """???????? JSON??????"""
        with self._lock:
            return json.dumps(self._drone_status, indent=indent, ensure_ascii=False)

    def get_drone_status_json(self, drone_id: str, indent: int = 2) -> str:
        """???????? JSON??????"""
        with self._lock:
            status = self._drone_status.get(drone_id, {})
            return json.dumps(status, indent=indent, ensure_ascii=False)

    def start(self) -> None:
        """?????????????????????"""
        print("=" * 50)
        print("  ?????")
        print(f"  ??????(UDP): {self.config.heartbeat_port}")
        print(f"  ??????(TCP): {self.config.data_port}")
        print(f"  ??????: {self.config.heartbeat_timeout}s")
        print("=" * 50)

        self._running = True
        self.heartbeat_receiver.start(on_message=self._on_heartbeat_message)
        self.data_receiver.start(on_message=self._on_data_message)

        # ========== ???4??????????????==========
        self._offline_check_timer.start()

    def stop(self) -> None:
        """?????????"""
        self._running = False
        # ?????????
        self._offline_check_timer.stop()
        self.heartbeat_receiver.close()
        self.data_receiver.close()
        print("??????")

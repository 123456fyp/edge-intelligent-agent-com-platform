# -*- coding: utf-8 -*-
"""数据消息 - 协议层（接收端）
全量核心飞控数据报文，纯数据结构与编解码
"""
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class DataMessage:
    drone_id: str
    seq: int
    timestamp: str
    mode: str
    battery: Dict[str, float]
    attitude: Dict[str, float]
    position: Dict[str, float]
    velocity: Dict[str, float]
    sensors: Dict[str, Any]

    @classmethod
    def create(
        cls,
        drone_id: str,
        seq: int,
        mode: str,
        battery: Dict[str, float],
        attitude: Optional[Dict[str, float]] = None,
        position: Optional[Dict[str, float]] = None,
        velocity: Optional[Dict[str, float]] = None,
        sensors: Optional[Dict[str, Any]] = None
    ) -> "DataMessage":
        return cls(
            drone_id=drone_id,
            seq=seq,
            timestamp=datetime.now().isoformat(),
            mode=mode,
            battery=battery,
            attitude=attitude if attitude is not None else {},
            position=position if position is not None else {},
            velocity=velocity if velocity is not None else {},
            sensors=sensors if sensors is not None else {}
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "DataMessage":
        data = json.loads(raw)
        return cls(**data)
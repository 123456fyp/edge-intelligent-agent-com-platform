# -*- coding: utf-8 -*-
"""心跳消息 - 协议层（接收端）
极简保活报文，仅用于链路连通性检测与离线判断
"""
import json
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class HeartbeatMessage:
    drone_id: str
    timestamp: str

    @classmethod
    def create(cls, drone_id: str) -> "HeartbeatMessage":
        return cls(
            drone_id=drone_id,
            timestamp=datetime.now().isoformat()
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "HeartbeatMessage":
        data = json.loads(raw)
        return cls(**data)
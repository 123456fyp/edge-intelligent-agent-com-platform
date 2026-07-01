# -*- coding: utf-8 -*-
"""心跳消息 - 协议层
极简保活报文，仅用于测试链路连通性
"""
import json
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class HeartbeatMessage:
    """极简心跳：仅做链路保活"""
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
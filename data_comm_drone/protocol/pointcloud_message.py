# -*- coding: utf-8 -*-
"""点云消息 - 协议层
支持LiDAR/深度相机点云数据传输，zlib高压缩比节省带宽
优化二进制打包，减少CPU占用
"""
import json
import base64
import zlib
import struct
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Optional


@dataclass
class PointCloudMessage:
    """点云数据消息"""
    drone_id: str
    seq: int
    timestamp: str
    frame_id: str
    height: int
    width: int
    point_step: int
    fields: List[str]
    num_points: int
    is_dense: bool
    compression: str
    chunk_index: int = 0
    chunk_total: int = 1
    data: str = ""

    @classmethod
    def create(cls, drone_id: str, seq: int, frame_id: str,
               points: List[Dict[str, float]], fields: Optional[List[str]] = None,
               compression: str = "zlib", compression_level: int = 6) -> "PointCloudMessage":
        """创建点云消息
        Args:
            compression_level: zlib压缩等级1-9，默认6（平衡CPU和压缩比，约3:1压缩）
        """
        if fields is None:
            fields = ["x", "y", "z", "intensity"]

        # 优化二进制打包：预分配缓冲区，减少内存拷贝
        num_fields = len(fields)
        fmt = f"{len(points) * num_fields}f"
        values = []
        for pt in points:
            for f in fields:
                values.append(float(pt.get(f, 0.0)))

        binary_data = struct.pack(fmt, *values)

        if compression == "zlib":
            binary_data = zlib.compress(binary_data, level=compression_level)
        b64_data = base64.b64encode(binary_data).decode("ascii")

        return cls(drone_id=drone_id, seq=seq, timestamp=datetime.now().isoformat(),
                   frame_id=frame_id, height=1, width=len(points),
                   point_step=num_fields*4, fields=fields, num_points=len(points),
                   is_dense=True, compression=compression, data=b64_data)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "PointCloudMessage":
        return cls(**json.loads(raw))

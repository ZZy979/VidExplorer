import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from videxplorer.utils.file import format_duration, format_file_size


@dataclass
class Video:
    """视频数据模型"""
    id: Optional[int] = None
    file_path: str = ""
    title: str = ""
    duration: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    created_at: Optional[datetime] = None
    last_played: Optional[datetime] = None
    play_count: int = 0
    thumbnail_path: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    @property
    def duration_str(self):
        """格式化时长"""
        if not self.duration:
            return '00:00'
        return format_duration(self.duration)

    @property
    def file_name(self):
        """文件名（不含扩展名）"""
        base = os.path.basename(self.file_path)
        return os.path.splitext(base)[0]

    @property
    def file_size_str(self):
        """格式化文件大小"""
        if not self.file_size:
            return '未知大小'
        return format_file_size(self.file_size)

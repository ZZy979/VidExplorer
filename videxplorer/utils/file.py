"""文件处理工具"""

import logging
import os

import cv2
from PySide6.QtGui import QPixmap, QImage

from videxplorer.core.library import VideoLibrary


def get_file_name(file_path):
    """获取文件名（不含扩展名）"""
    return os.path.splitext(os.path.basename(file_path))[0]


def get_file_extension(file_path):
    """获取文件扩展名（小写）"""
    return os.path.splitext(file_path)[1].lower()


def get_file_size(file_path):
    """获取文件大小（字节）"""
    try:
        return os.path.getsize(file_path)
    except:
        return None


def get_file_size_readable(file_path):
    """获取文件大小（可读格式）"""
    try:
        return format_file_size(os.path.getsize(file_path))
    except:
        return '未知大小'

def format_file_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f'{size:.1f} {unit}'
        size /= 1024.0
    return f'{size:.1f} PB'


def get_video_duration(file_path):
    """获取视频时长（秒）"""
    try:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return None

        # 获取总帧数和帧率
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        cap.release()
        if fps <= 0:
            return None
        return int(total_frames / fps)
    except Exception as e:
        logging.error(e)
        return None

def get_video_dimensions(file_path: str):
    """获取视频尺寸 (width, height)"""
    try:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return None, None

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cap.release()

        if width > 0 and height > 0:
            return width, height
        return None, None
    except Exception as e:
        logging.error(e)
        return None, None


def format_duration(seconds):
    """格式化时长"""
    hours, minutes = divmod(seconds, 3600)
    minutes, seconds = divmod(minutes, 60)
    if hours > 0:
        return f'{hours}:{minutes:02d}:{seconds:02d}'
    else:
        return f'{minutes:02d}:{seconds:02d}'


def get_thumbnail(file_path, width=320, height=180):
    """获取视频缩略图"""
    try:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return None

        # 尝试读取中间帧
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 10)

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return None

        # 转换颜色空间 BGR -> RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 缩放
        h, w = frame_rgb.shape[:2]
        if w > width or h > height:
            # 计算缩放比例，保持宽高比
            ratio = min(width / w, height / h)
            new_w = int(w * ratio)
            new_h = int(h * ratio)
            frame_rgb = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # 转换为 QImage
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

        return QPixmap.fromImage(qt_image)
    except Exception as e:
        logging.error(e)
        return None


def is_video_file(file_path):
    """判断是否为视频文件"""
    ext = get_file_extension(file_path)
    return ext in VideoLibrary.VIDEO_EXTENSIONS

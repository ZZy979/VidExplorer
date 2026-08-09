"""视频信息异步加载器"""
from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

from videxplorer.utils.file import get_video_duration, format_duration


class VideoMetadata:
    """视频元数据"""

    def __init__(self, file_path):
        self.file_path = file_path
        self.duration = None
        self.duration_str = ""
        self.thumbnail_loaded = False


class VideoLoaderThread(QThread):
    """视频加载线程"""

    # 信号：单个视频加载完成
    video_loaded = Signal(str, object)  # file_path, VideoMetadata

    # 信号：所有视频加载完成
    all_loaded = Signal()

    # 信号：进度更新
    progress = Signal(int, int)  # current, total

    def __init__(self):
        super().__init__()
        self.video_paths = []
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self._stop = False

    def set_videos(self, paths):
        """设置要加载的视频列表"""
        self.mutex.lock()
        self.video_paths = paths[:]
        self._stop = False
        self.mutex.unlock()

    def stop(self):
        """停止加载"""
        self.mutex.lock()
        self._stop = True
        self.condition.wakeAll()
        self.mutex.unlock()

    def run(self):
        """后台线程运行"""
        self.mutex.lock()
        paths = self.video_paths[:]
        total = len(paths)
        self.mutex.unlock()

        if not paths:
            self.all_loaded.emit()
            return

        for idx, file_path in enumerate(paths):
            # 检查是否停止
            self.mutex.lock()
            if self._stop:
                self.mutex.unlock()
                break
            self.mutex.unlock()

            # 创建元数据对象
            metadata = VideoMetadata(file_path)

            # 获取时长
            if duration := get_video_duration(file_path):
                metadata.duration = duration
                metadata.duration_str = format_duration(duration)

            # 发送加载完成信号
            self.video_loaded.emit(file_path, metadata)

            # 发送进度
            self.progress.emit(idx + 1, total)

        self.all_loaded.emit()

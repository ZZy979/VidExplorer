import os.path


class VideoLibrary:
    """视频库管理"""

    # 支持的视频扩展名
    VIDEO_EXTENSIONS = {
        '.mp4', '.avi', '.mkv', '.mov', '.wmv',
        '.flv', '.webm', '.m4v', '.mpg', '.mpeg',
        '.3gp', '.ogv', '.ts', '.mts', '.m2ts'
    }

    def __init__(self):
        self._stop_scan = False

    def stop_scan(self):
        """停止扫描"""
        self._stop_scan = True

    def scan_folder(self, path, callback=None):
        """扫描文件夹，返回所有视频文件的完整路径列表"""
        video_files = []

        if not os.path.exists(path):
            return video_files

        self._stop_scan = False

        for root, dirs, files in os.walk(path):
            if self._stop_scan:
                break
            for file in files:
                if self._stop_scan:
                    break
                ext = os.path.splitext(file)[1].lower()
                if ext in self.VIDEO_EXTENSIONS:
                    full_path = os.path.join(root, file)
                    video_files.append(full_path)

            # 回调检查是否停止
            if callback and callback(len(video_files)):
                break

        # 按文件名排序
        video_files.sort(key=lambda x: os.path.basename(x).lower())

        return video_files

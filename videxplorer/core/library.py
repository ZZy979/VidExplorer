import os.path

from videxplorer.utils.path import normalize_path


class VideoLibrary:
    """视频库管理。

    对外返回的所有路径都经过 ``normalize_path`` 规范化，
    保证整个应用使用同一种路径写法（Windows 下形如 ``H:\\dir\\file.mp4``）。
    """

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

    def list_folder(self, path):
        """列出文件夹下的子文件夹和视频文件（不递归）。

        返回 (folder_items, video_files)：
        - folder_items: [(子文件夹完整路径, 其中直接包含的视频数量), ...]
        - video_files: [视频文件完整路径, ...]
        返回的路径均已规范化。
        """
        folders = []  # [(path, video_count)]
        videos = []

        # 先规范化入参，之后 join 出来的子路径才不会再混入正斜杠
        path = normalize_path(path)
        if not os.path.exists(path):
            return folders, videos

        try:
            entries = os.listdir(path)
        except OSError:
            return folders, videos

        for name in entries:
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path):
                folders.append((full_path, self._count_direct_videos(full_path)))
            elif os.path.isfile(full_path):
                ext = os.path.splitext(name)[1].lower()
                if ext in self.VIDEO_EXTENSIONS:
                    videos.append(full_path)

        # 按名称排序
        folders.sort(key=lambda x: os.path.basename(x[0]).lower())
        videos.sort(key=lambda x: os.path.basename(x).lower())

        return folders, videos

    @staticmethod
    def _count_direct_videos(folder_path):
        """统计文件夹内直接包含的视频文件数量（不递归）"""
        count = 0
        folder_path = normalize_path(folder_path)
        try:
            for name in os.listdir(folder_path):
                full_path = os.path.join(folder_path, name)
                ext = os.path.splitext(name)[1].lower()
                if os.path.isfile(full_path) and ext in VideoLibrary.VIDEO_EXTENSIONS:
                    count += 1
        except OSError:
            pass
        return count

    def list_videos_recursive(self, path):
        """递归获取文件夹下所有视频文件的完整路径（已规范化）"""
        videos = []
        path = normalize_path(path)
        if not os.path.exists(path):
            return videos

        for root, dirs, files in os.walk(path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in self.VIDEO_EXTENSIONS:
                    videos.append(os.path.join(root, file))

        videos.sort(key=lambda x: os.path.basename(x).lower())
        return videos

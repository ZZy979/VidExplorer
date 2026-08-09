"""缩略图缓存管理"""

import hashlib
import os

from PySide6.QtGui import QPixmap

from videxplorer.utils.file import get_thumbnail


class ThumbnailCache:
    """缩略图缓存管理器"""

    def __init__(self, cache_dir='data/thumbnails'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_path(self, file_path, size=320):
        """生成缓存文件路径"""
        # 使用文件路径 + 修改时间 + 尺寸生成唯一哈希
        stat = os.stat(file_path)
        key = f'{file_path}_{stat.st_mtime}_{size}'
        hash_val = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f'{hash_val}.jpg')

    def get_or_create(self, file_path, width=320, height=180):
        """获取缩略图（如有缓存则直接返回，否则生成并缓存）"""
        cache_path = self._get_cache_path(file_path, width)

        # 尝试从缓存加载
        if os.path.exists(cache_path):
            pixmap = QPixmap(cache_path)
            if not pixmap.isNull():
                return pixmap

        # 生成新的缩略图
        pixmap = get_thumbnail(file_path, width, height)
        if pixmap and not pixmap.isNull():
            # 保存到缓存
            pixmap.save(cache_path, 'JPEG', 85)
            return pixmap

        return None

    def clear_cache(self):
        """清空所有缓存"""
        for file in os.listdir(self.cache_dir):
            if file.endswith('.jpg'):
                os.remove(os.path.join(self.cache_dir, file))

    def get_cache_size(self):
        """获取缓存总大小（字节）"""
        total = 0
        for file in os.listdir(self.cache_dir):
            if file.endswith('.jpg'):
                total += os.path.getsize(os.path.join(self.cache_dir, file))
        return total


# 全局缓存实例
thumbnail_cache = ThumbnailCache()

"""视频合集（collection）管理。

每个合集有独立的数据库文件（data/<slug>.db）与缩略图目录
（data/thumbnails/<slug>），合集信息统一登记在 data/collections.db 中。
"""
import logging
import os
import re

from PySide6.QtSql import QSqlQuery

from videxplorer.models.database import SqliteDatabase, VideoDatabase
from videxplorer.utils.path import normalize_path

DATA_DIR = 'data'


def slugify(name):
    """把合集名称转换成可安全用作文件名的形式。

    例如 'Film' -> 'film'，'Short video' -> 'short-video'。
    """
    slug = re.sub(r'[^\w\s-]', '', (name or '').strip().lower(), flags=re.UNICODE)
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')
    return slug or 'collection'


class CollectionStore(SqliteDatabase):
    """合集注册表（默认 data/collections.db）"""

    def __init__(self, db_path=os.path.join(DATA_DIR, 'collections.db')):
        super().__init__(db_path, os.path.join(DATA_DIR, 'collections.sql'))

    def list_collections(self):
        """获取所有合集（按名称排序）"""
        db = self.get_connection()
        query = QSqlQuery(db)
        if not query.exec('SELECT * FROM collections ORDER BY name COLLATE NOCASE'):
            logging.error(f'list_collections 失败: {query.lastError().text()}')
            return []

        results = []
        while query.next():
            results.append(self._row_to_dict(query))
        return results

    def get_collection(self, collection_id):
        """根据 ID 获取合集信息"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare('SELECT * FROM collections WHERE id = ?')
        query.addBindValue(collection_id)
        if query.exec() and query.next():
            return self._row_to_dict(query)
        return None

    def get_collection_by_name(self, name):
        """根据名称获取合集信息（名称不区分大小写）"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare('SELECT * FROM collections WHERE name = ? COLLATE NOCASE')
        query.addBindValue(name)
        if query.exec() and query.next():
            return self._row_to_dict(query)
        return None

    def get_recent_collections(self, limit=5):
        """获取最近打开的合集（未打开过则按创建时间）"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT * FROM collections
            ORDER BY COALESCE(last_opened_at, created_at) DESC, id DESC
            LIMIT ?
        """)
        query.addBindValue(limit)
        if not query.exec():
            logging.error(f'get_recent_collections 失败: {query.lastError().text()}')
            return []

        results = []
        while query.next():
            results.append(self._row_to_dict(query))
        return results

    def add_collection(self, name, folder_path, db_path, thumbnail_dir):
        """登记新合集，返回合集 ID；失败返回 None"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO collections (name, folder_path, db_path, thumbnail_dir, last_opened_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """)
        query.addBindValue(name)
        query.addBindValue(folder_path)
        query.addBindValue(db_path)
        query.addBindValue(thumbnail_dir)
        if not query.exec():
            logging.error(f'add_collection 失败: {query.lastError().text()}')
            return None
        return query.lastInsertId()

    def mark_opened(self, collection_id):
        """记录合集最近打开时间"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare('UPDATE collections SET last_opened_at = CURRENT_TIMESTAMP WHERE id = ?')
        query.addBindValue(collection_id)
        if not query.exec():
            logging.error(f'mark_opened 失败: {query.lastError().text()}')
            return False
        return True


class CollectionManager:
    """合集的创建与查询，以及合集数据库/缩略图目录的分配"""

    # 不能用作合集数据库文件名的保留名称（与注册表/旧版数据库重名）
    _RESERVED_SLUGS = {'collections', 'videos'}

    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        self.thumbnail_root = os.path.join(data_dir, 'thumbnails')
        self.store = CollectionStore(os.path.join(data_dir, 'collections.db'))

    def list_collections(self):
        """获取所有合集"""
        return self.store.list_collections()

    def get_collection(self, collection_id):
        """根据 ID 获取合集"""
        return self.store.get_collection(collection_id)

    def recent_collections(self, limit=5):
        """获取最近打开的合集"""
        return self.store.get_recent_collections(limit)

    def mark_opened(self, collection_id):
        """记录合集最近打开时间"""
        return self.store.mark_opened(collection_id)

    def create_collection(self, name, folder_path):
        """创建合集：登记信息、初始化合集数据库与缩略图目录，返回合集记录。

        校验失败时抛出 ValueError，写入失败时抛出 RuntimeError。
        """
        name = (name or '').strip()
        if not name:
            raise ValueError('合集名称不能为空')
        if self.store.get_collection_by_name(name):
            raise ValueError(f'已存在同名合集：{name}')

        folder_path = normalize_path(folder_path or '')
        if not folder_path or not os.path.isdir(folder_path):
            raise ValueError('请选择有效的根文件夹')

        slug = self._unique_slug(name)
        db_path = normalize_path(os.path.join(self.data_dir, f'{slug}.db'))
        thumbnail_dir = normalize_path(os.path.join(self.thumbnail_root, slug))

        # 使用 data/videos.sql 初始化合集数据库表结构
        VideoDatabase(db_path).close_connection()
        os.makedirs(thumbnail_dir, exist_ok=True)

        collection_id = self.store.add_collection(name, folder_path, db_path, thumbnail_dir)
        if collection_id is None:
            self._cleanup_failed_create(db_path, thumbnail_dir)
            raise RuntimeError('保存合集信息失败')

        collection = self.store.get_collection(collection_id)
        if collection is None:
            raise RuntimeError('读取新建合集信息失败')
        return collection

    def _unique_slug(self, name):
        """生成不与现有数据库文件/已登记合集冲突的 slug"""
        base = slugify(name)
        occupied = {os.path.normcase(os.path.abspath(c['db_path']))
                    for c in self.store.list_collections()}
        slug = base
        index = 2
        while True:
            db_path = normalize_path(os.path.join(self.data_dir, f'{slug}.db'))
            if (slug not in self._RESERVED_SLUGS
                    and not os.path.exists(db_path)
                    and os.path.normcase(os.path.abspath(db_path)) not in occupied):
                return slug
            slug = f'{base}-{index}'
            index += 1

    def _cleanup_failed_create(self, db_path, thumbnail_dir):
        """创建合集失败时清理已产生的空数据库与缩略图目录"""
        for suffix in ('', '-wal', '-shm'):
            try:
                os.remove(db_path + suffix)
            except OSError:
                pass
        try:
            os.rmdir(thumbnail_dir)
        except OSError:
            pass

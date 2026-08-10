"""SQLite数据库操作"""
import atexit
import logging
import os
import threading

from PySide6.QtSql import QSqlDatabase, QSqlQuery


class VideoDatabase:
    """基于 QtSql 的数据库访问类。

    连接管理策略：线程局部变量。
    - Qt 要求 QSqlDatabase 只能在创建它的线程中使用，因此为每个线程维护
      一个命名唯一的连接，同一线程内所有查询复用该连接。
    - 不再每次查询都新建连接。
    """

    def __init__(self, db_path='data/videos.db'):
        self.db_path = db_path
        self._local = threading.local()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_tables()
        self._enable_wal()
        atexit.register(self.close_connection)

    def _enable_wal(self):
        """启用 WAL 模式并设置 busy timeout，降低读写并发时的锁冲突"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.exec('PRAGMA journal_mode=WAL')
        query = QSqlQuery(db)
        query.exec('PRAGMA busy_timeout=10000')

    def get_connection(self):
        """获取当前线程的数据库连接（线程局部，同线程内复用）"""
        conn = getattr(self._local, 'connection', None)
        if conn is not None and conn.isOpen():
            return conn

        conn_name = getattr(self._local, 'connection_name', None)
        if conn_name is None or not QSqlDatabase.contains(conn_name):
            conn_name = f'videxplorer_{id(self)}_{threading.get_ident()}'
            self._local.connection_name = conn_name
            conn = QSqlDatabase.addDatabase('QSQLITE', conn_name)
            conn.setDatabaseName(self.db_path)
        else:
            conn = QSqlDatabase.database(conn_name)

        if not conn.isOpen():
            if not conn.open():
                raise RuntimeError(f'无法打开数据库: {conn.lastError().text()}')

        self._local.connection = conn
        return conn

    def close_connection(self):
        """关闭并移除当前线程的数据库连接"""
        conn = getattr(self._local, 'connection', None)
        conn_name = getattr(self._local, 'connection_name', None)
        self._local.connection = None
        self._local.connection_name = None

        if conn is not None:
            conn.close()
            del conn
        if conn_name is not None and QSqlDatabase.contains(conn_name):
            QSqlDatabase.removeDatabase(conn_name)

    def init_tables(self):
        """初始化数据库表"""
        db = self.get_connection()
        with open('data/videos.sql', encoding='utf-8') as f:
            script = f.read()

        # QSqlQuery.exec 一次只能执行一条语句，需将脚本拆分后逐条执行
        for statement in self._split_sql_script(script):
            query = QSqlQuery(db)
            if not query.exec(statement):
                raise RuntimeError(f'初始化数据库表失败: {query.lastError().text()}')

    @staticmethod
    def _split_sql_script(script):
        """将 SQL 脚本按分号拆分为单条语句，忽略空行与注释"""
        statements = []
        current = []
        for line in script.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('--'):
                continue
            current.append(line)
            if stripped.endswith(';'):
                statements.append('\n'.join(current))
                current = []
        if current:
            statements.append('\n'.join(current))
        return statements

    @staticmethod
    def _row_to_dict(query):
        """将 QSqlQuery 当前行转换为 dict"""
        record = query.record()
        return {record.fieldName(i): query.value(i) for i in range(record.count())}

    def _get_video_id(self, file_path):
        """根据路径获取视频ID"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare('SELECT id FROM videos WHERE file_path = ?')
        query.addBindValue(file_path)
        if query.exec() and query.next():
            return query.value(0)
        return None

    def add_or_update_video(self, file_path, metadata):
        """添加或更新视频信息"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO videos (file_path, title, duration, width, height, file_size)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (file_path) DO UPDATE SET
                title = excluded.title,
                duration = excluded.duration,
                width = excluded.width,
                height = excluded.height,
                file_size = excluded.file_size
            RETURNING id
        """)
        query.addBindValue(file_path)
        query.addBindValue(metadata.get('title', os.path.basename(file_path)))
        query.addBindValue(metadata.get('duration'))
        query.addBindValue(metadata.get('width'))
        query.addBindValue(metadata.get('height'))
        query.addBindValue(metadata.get('file_size'))

        if not query.exec():
            logging.error(f'add_or_update_video 失败: {query.lastError().text()}')
            return None

        video_id = None
        if query.next():
            video_id = query.value(0)

        # 兼容不支持 RETURNING 的 SQLite/Qt 版本
        if video_id is None:
            video_id = self._get_video_id(file_path)

        return video_id

    def get_video_by_path(self, file_path):
        """根据路径获取视频信息"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare('SELECT * FROM videos WHERE file_path = ?')
        query.addBindValue(file_path)
        if query.exec() and query.next():
            return self._row_to_dict(query)
        return None

    def get_all_videos(self):
        """获取所有视频"""
        db = self.get_connection()
        query = QSqlQuery(db)
        if not query.exec('SELECT * FROM videos ORDER BY title'):
            logging.error(f'get_all_videos 失败: {query.lastError().text()}')
            return []

        results = []
        while query.next():
            results.append(self._row_to_dict(query))
        return results

    def update_play_count(self, file_path: str):
        """更新播放次数"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare("""
            UPDATE videos
            SET play_count = play_count + 1, last_played = CURRENT_TIMESTAMP
            WHERE file_path = ?
        """)
        query.addBindValue(file_path)
        if not query.exec():
            logging.error(f'update_play_count 失败: {query.lastError().text()}')

    def get_or_create_tag(self, tag_name):
        """获取或创建标签"""
        db = self.get_connection()
        return self._get_or_create_tag_in_conn(db, tag_name)

    def _get_or_create_tag_in_conn(self, db, tag_name):
        """在指定的连接/事务上获取或创建标签。

        不额外打开新连接，避免在已有写事务中嵌套连接导致 'database is locked'。
        """
        query = QSqlQuery(db)
        query.prepare('SELECT id FROM tags WHERE name = ?')
        query.addBindValue(tag_name)
        if query.exec() and query.next():
            return query.value(0)

        query = QSqlQuery(db)
        query.prepare('INSERT INTO tags (name) VALUES (?)')
        query.addBindValue(tag_name)
        if query.exec():
            return query.lastInsertId()

        # 插入失败（如并发创建了同名标签），重新查询
        logging.error(f'创建标签失败: {query.lastError().text()}')
        query = QSqlQuery(db)
        query.prepare('SELECT id FROM tags WHERE name = ?')
        query.addBindValue(tag_name)
        if query.exec() and query.next():
            return query.value(0)
        return None

    def get_all_tags(self):
        """获取所有标签"""
        db = self.get_connection()
        query = QSqlQuery(db)
        if not query.exec("""
            SELECT tags.*, ifnull(t.video_count, 0) as video_count
            FROM tags
            LEFT JOIN (
                SELECT tag_id, COUNT(*) AS video_count
                FROM video_tags
                GROUP BY tag_id
            ) AS t
            ON t.tag_id = tags.id
            ORDER BY tags.name
        """):
            logging.error(f'get_all_tags 失败: {query.lastError().text()}')
            return []

        results = []
        while query.next():
            results.append(self._row_to_dict(query))
        return results

    def rename_tag(self, tag_id, new_name):
        """重命名标签"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare('UPDATE tags SET name = ? WHERE id = ?')
        query.addBindValue(new_name)
        query.addBindValue(tag_id)
        if not query.exec():
            logging.error(f'重命名标签失败: {query.lastError().text()}')
            return False
        return query.numRowsAffected() > 0

    def delete_tag(self, tag_id):
        """删除标签"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare('DELETE FROM tags WHERE id = ?')
        query.addBindValue(tag_id)
        if not query.exec():
            logging.error(f'删除标签失败: {query.lastError().text()}')
            return False
        return query.numRowsAffected() > 0

    def add_tag_to_video(self, video_path, tag_name):
        """为视频添加标签"""
        db = self.get_connection()

        video = self.get_video_by_path(video_path)
        if not video:
            return False

        if not db.transaction():
            logging.error(f'开启事务失败: {db.lastError().text()}')
            return False

        try:
            tag_id = self._get_or_create_tag_in_conn(db, tag_name)
            if tag_id is None:
                raise RuntimeError('创建标签失败')

            query = QSqlQuery(db)
            query.prepare('INSERT INTO video_tags (video_id, tag_id) VALUES (?, ?)')
            query.addBindValue(video['id'])
            query.addBindValue(tag_id)
            if not query.exec():
                # 主键冲突说明关联已存在，仅记录日志
                logging.error(f'添加视频标签失败: {query.lastError().text()}')

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logging.error(f'add_tag_to_video 失败: {e}')
            return False

    def remove_tag_from_video(self, video_path, tag_name):
        """从视频移除标签"""
        db = self.get_connection()

        video = self.get_video_by_path(video_path)
        if not video:
            return False

        query = QSqlQuery(db)
        query.prepare('SELECT id FROM tags WHERE name = ?')
        query.addBindValue(tag_name)
        if not (query.exec() and query.next()):
            return False
        tag_id = query.value(0)

        query = QSqlQuery(db)
        query.prepare('DELETE FROM video_tags WHERE video_id = ? AND tag_id = ?')
        query.addBindValue(video['id'])
        query.addBindValue(tag_id)
        if not query.exec():
            logging.error(f'移除视频标签失败: {query.lastError().text()}')
            return False
        return query.numRowsAffected() > 0

    def get_tags_for_video(self, video_path):
        """获取视频的所有标签"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT t.name
            FROM tags t
            JOIN video_tags vt ON vt.tag_id = t.id
            JOIN videos v ON vt.video_id = v.id
            WHERE v.file_path = ?
            ORDER BY t.name
        """)
        query.addBindValue(video_path)
        if not query.exec():
            logging.error(f'get_tags_for_video 失败: {query.lastError().text()}')
            return []

        tags = []
        while query.next():
            tags.append(query.value(0))
        return tags

    def get_videos_by_tag(self, tag_name):
        """根据标签获取视频路径列表"""
        db = self.get_connection()
        query = QSqlQuery(db)
        query.prepare("""
            SELECT v.file_path
            FROM videos v
            JOIN video_tags vt ON vt.video_id = v.id
            JOIN tags t ON vt.tag_id = t.id
            WHERE t.name = ?
            ORDER BY v.title
        """)
        query.addBindValue(tag_name)
        if not query.exec():
            logging.error(f'get_videos_by_tag 失败: {query.lastError().text()}')
            return []

        paths = []
        while query.next():
            paths.append(query.value(0))
        return paths

    def set_video_tags(self, video_path, tag_names):
        """设置视频的标签（覆盖）"""
        db = self.get_connection()

        video = self.get_video_by_path(video_path)
        if not video:
            return False

        if not db.transaction():
            logging.error(f'开启事务失败: {db.lastError().text()}')
            return False

        try:
            # 删除所有现有标签
            query = QSqlQuery(db)
            query.prepare('DELETE FROM video_tags WHERE video_id = ?')
            query.addBindValue(video['id'])
            if not query.exec():
                raise RuntimeError(f'删除原标签失败: {query.lastError().text()}')

            # 添加新标签（同一连接/事务内完成，避免嵌套连接导致 database locked）
            for tag_name in tag_names:
                if tag_name.strip():
                    tag_id = self._get_or_create_tag_in_conn(db, tag_name.strip())
                    if tag_id is None:
                        continue
                    query = QSqlQuery(db)
                    query.prepare('INSERT INTO video_tags (video_id, tag_id) VALUES (?, ?)')
                    query.addBindValue(video['id'])
                    query.addBindValue(tag_id)
                    if not query.exec():
                        logging.error(f'添加视频标签失败: {query.lastError().text()}')

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logging.error(f'set_video_tags 失败: {e}')
            return False

    def _get_or_create_video_id_in_conn(self, db, file_path):
        """在指定连接/事务中获取或创建视频ID（用于批量操作）"""
        query = QSqlQuery(db)
        query.prepare('SELECT id FROM videos WHERE file_path = ?')
        query.addBindValue(file_path)
        if query.exec() and query.next():
            return query.value(0)

        query = QSqlQuery(db)
        query.prepare('INSERT INTO videos (file_path, title) VALUES (?, ?)')
        query.addBindValue(file_path)
        query.addBindValue(os.path.basename(file_path))
        if query.exec():
            return query.lastInsertId()
        logging.error(f'创建视频记录失败: {query.lastError().text()}')
        return None

    def add_tags_to_videos(self, video_paths, tag_names):
        """为多个视频批量添加标签（只添加，不覆盖已有标签）"""
        if not video_paths or not tag_names:
            return True

        db = self.get_connection()
        if not db.transaction():
            logging.error(f'开启事务失败: {db.lastError().text()}')
            return False

        try:
            for file_path in video_paths:
                video_id = self._get_or_create_video_id_in_conn(db, file_path)
                if video_id is None:
                    continue
                for tag_name in tag_names:
                    if not tag_name.strip():
                        continue
                    tag_id = self._get_or_create_tag_in_conn(db, tag_name.strip())
                    if tag_id is None:
                        continue
                    query = QSqlQuery(db)
                    query.prepare('INSERT OR IGNORE INTO video_tags (video_id, tag_id) VALUES (?, ?)')
                    query.addBindValue(video_id)
                    query.addBindValue(tag_id)
                    if not query.exec():
                        logging.error(f'批量添加标签失败: {query.lastError().text()}')

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logging.error(f'add_tags_to_videos 失败: {e}')
            return False

    def get_videos_with_tags(self):
        """获取所有视频及其标签"""
        db = self.get_connection()
        query = QSqlQuery(db)
        if not query.exec("""
            SELECT v.file_path, t.name
            FROM videos v
            LEFT JOIN video_tags vt ON vt.video_id = v.id
            LEFT JOIN tags t ON vt.tag_id = t.id
            ORDER BY v.file_path, t.name
        """):
            logging.error(f'get_videos_with_tags 失败: {query.lastError().text()}')
            return {}

        result = {}
        while query.next():
            path = query.value(0)
            tag = query.value(1)
            if path not in result:
                result[path] = []
            if tag:
                result[path].append(tag)
        return result

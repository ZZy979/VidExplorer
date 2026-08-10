"""SQLite数据库操作"""
import logging
import os
import sqlite3


class VideoDatabase:

    def __init__(self, db_path='data/videos.db'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_tables()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        with open('data/videos.sql', encoding='utf-8') as f:
            cursor.executescript(f.read())
        conn.commit()
        conn.close()

    def add_or_update_video(self, file_path, metadata):
        """添加或更新视频信息"""
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = """
            INSERT INTO videos (file_path, title, duration, width, height, file_size)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (file_path) DO UPDATE SET
                title = excluded.title,
                duration = excluded.duration,
                width = excluded.width,
                height = excluded.height,
                file_size = excluded.file_size
            RETURNING id
        """
        params = (
            file_path,
            metadata.get('title', os.path.basename(file_path)),
            metadata.get('duration'),
            metadata.get('width'),
            metadata.get('height'),
            metadata.get('file_size')
        )
        cursor.execute(sql, params)

        result = cursor.fetchone()
        video_id = result[0] if result else None

        conn.commit()
        conn.close()
        return video_id

    def get_video_by_path(self, file_path):
        """根据路径获取视频信息"""
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = 'SELECT * FROM videos WHERE file_path = ?'
        cursor.execute(sql, (file_path,))

        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None

    def get_all_videos(self):
        """获取所有视频"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM videos ORDER BY title')

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def update_play_count(self, file_path: str):
        """更新播放次数"""
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = """
            UPDATE videos
            SET play_count  = play_count + 1, last_played = CURRENT_TIMESTAMP
            WHERE file_path = ?
        """
        cursor.execute(sql, (file_path,))

        conn.commit()
        conn.close()

    def get_or_create_tag(self, tag_name):
        """获取或创建标签"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 尝试获取已存在的标签
        cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
        result = cursor.fetchone()

        if result:
            tag_id = result[0]
        else:
            # 创建新标签
            cursor.execute('INSERT INTO tags (name) VALUES (?)', (tag_name,))
            tag_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return tag_id

    def get_all_tags(self):
        """获取所有标签"""
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT tags.*, ifnull(t.video_count, 0) as video_count
            FROM tags
            LEFT JOIN (
                SELECT tag_id, COUNT(*) AS video_count
                FROM video_tags
                GROUP BY tag_id
            ) AS t
            ON t.tag_id = tags.id
            ORDER BY tags.name
        """
        cursor.execute(sql)

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def rename_tag(self, tag_id, new_name):
        """重命名标签"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('UPDATE tags SET name = ? WHERE id = ?', (new_name, tag_id))
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            return affected > 0
        except sqlite3.IntegrityError as e:
            logging.error(e)
            conn.close()
            return False

    def delete_tag(self, tag_id):
        """删除标签"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM tags WHERE id = ?', (tag_id,))
        affected = cursor.rowcount

        conn.commit()
        conn.close()
        return affected > 0

    def add_tag_to_video(self, video_path, tag_name):
        """为视频添加标签"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 获取视频ID
        video = self.get_video_by_path(video_path)
        if not video:
            conn.close()
            return False

        # 获取或创建标签
        tag_id = self.get_or_create_tag(tag_name)

        # 获取或创建标签
        try:
            sql = 'INSERT INTO video_tags (video_id, tag_id) VALUES (?, ?)'
            cursor.execute(sql, (video['id'], tag_id))
            conn.commit()
            success = True
        except sqlite3.IntegrityError as e:
            logging.error(e)
            success = False

        conn.close()
        return success

    def remove_tag_from_video(self, video_path, tag_name):
        """从视频移除标签"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 获取视频ID
        video = self.get_video_by_path(video_path)
        if not video:
            conn.close()
            return False

        # 获取标签ID
        cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False

        tag_id = result[0]

        # 删除关联
        sql = 'DELETE FROM video_tags WHERE video_id = ? AND tag_id = ?'
        cursor.execute(sql, (video['id'], tag_id))

        conn.commit()
        conn.close()
        return True

    def get_tags_for_video(self, video_path):
        """获取视频的所有标签"""
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT t.name
            FROM tags t
            JOIN video_tags vt ON vt.tag_id = t.id
            JOIN videos v ON vt.video_id = v.id
            WHERE v.file_path = ?
            ORDER BY t.name
        """
        cursor.execute(sql, (video_path,))

        tags = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tags

    def get_videos_by_tag(self, tag_name):
        """根据标签获取视频路径列表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT v.file_path
            FROM videos v
            JOIN video_tags vt ON vt.video_id = v.id
            JOIN tags t ON vt.tag_id = t.id
            WHERE t.name = ?
            ORDER BY v.title
        """
        cursor.execute(sql, (tag_name,))

        paths = [row[0] for row in cursor.fetchall()]
        conn.close()
        return paths

    def set_video_tags(self, video_path, tag_names):
        """设置视频的标签（覆盖）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 获取视频ID
        video = self.get_video_by_path(video_path)
        if not video:
            conn.close()
            return False

        # 删除所有现有标签
        cursor.execute('DELETE FROM video_tags WHERE video_id = ?', (video['id'],))

        # 添加新标签
        for tag_name in tag_names:
            if tag_name.strip():
                tag_id = self.get_or_create_tag(tag_name.strip())
                try:
                    sql = 'INSERT INTO video_tags (video_id, tag_id) VALUES (?, ?)'
                    cursor.execute(sql, (video['id'], tag_id))
                except sqlite3.IntegrityError as e:
                    logging.error(e)

        conn.commit()
        conn.close()
        return True

    def get_videos_with_tags(self):
        """获取所有视频及其标签"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT v.file_path, t.name
            FROM videos v
            LEFT JOIN video_tags vt ON vt.video_id = v.id
            LEFT JOIN tags t ON vt.tag_id = t.id
            ORDER BY v.file_path, t.name
        """)

        result = {}
        for row in cursor.fetchall():
            path = row[0]
            tag = row[1]
            if path not in result:
                result[path] = []
            if tag:
                result[path].append(tag)

        conn.close()
        return result

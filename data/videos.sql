BEGIN;

-- 视频表
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    title TEXT,
    duration INTEGER,
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_played TIMESTAMP,
    play_count INTEGER DEFAULT 0,
    thumbnail_path TEXT
);

-- 标签表
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    color TEXT DEFAULT '#666666',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 视频-标签关联表
CREATE TABLE IF NOT EXISTS video_tags (
    video_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY (video_id, tag_id),
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_videos_path ON videos(file_path);
CREATE INDEX IF NOT EXISTS idx_video_tags_video ON video_tags(video_id);
CREATE INDEX IF NOT EXISTS idx_video_tags_tag ON video_tags(tag_id);

COMMIT;

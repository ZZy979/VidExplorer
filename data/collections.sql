BEGIN;

-- 视频合集表
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    folder_path TEXT NOT NULL,
    db_path TEXT NOT NULL,
    thumbnail_dir TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_opened_at TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_collections_last_opened ON collections(last_opened_at);

COMMIT;

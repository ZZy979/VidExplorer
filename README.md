# VidExplorer
视频库管理软件

## 功能
* **加载视频列表**：打开文件夹，扫描目录下所有视频文件，以网格卡片显示。
* **显示缩略图**：从视频中提取一帧，如果没有则显示默认图标。
* **播放视频**：点击卡片，调用系统默认播放器。
* **标签系统**：为视频添加、编辑、删除标签。
* **标签管理器**：查看所有标签、重命名、删除。
* **搜索功能**：按文件名或标签搜索视频。

## 安装与运行
1.安装依赖

```shell
pip install -r requirements.txt
```

2.运行

```shell
python -m videxplorer
```

## 代码目录结构

```
VidExplorer/
    videxplorer/        # 主包目录
        __init__.py
        __main__.py     # 应用入口
        core/           # 核心业务逻辑
        models/         # 数据模型
        ui/             # UI 相关
        utils/          # 工具函数
    data/               # 运行时数据
        videos.db       # SQLite数据库
        thumbnails/     # 缩略图缓存
    requirements.txt    # Python依赖
```

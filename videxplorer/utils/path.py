"""路径规范化工具"""
import os


def normalize_path(path):
    """把路径统一规范为本地格式（Windows 下形如 'H:\\dir\\file.mp4'）。

    统一分隔符，避免同一个文件因为 'H:/dir\\file.mp4' 与 'H:\\dir\\file.mp4'
    两种写法被当成不同路径（会导致数据库出现重复记录）。

    说明：
    - 空值原样返回（``os.path.normpath('')`` 会得到 ``'.'``，不可用于空路径）。
    - 使用 ``os.path.normpath``，只统一分隔符与合并冗余片段，
      不解析符号链接、不转换大小写（比较路径时应再叠加 ``os.path.normcase``）。
    """
    if not path:
        return path
    return os.path.normpath(path)

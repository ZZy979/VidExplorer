"""搜索引擎。

支持的语法（各条件之间取交集）：
- ``tag:xxx``  搜索具有指定标签的视频，可重复多次；标签名含空格时用引号：``tag:"xx xx"``
- ``tag:none`` 搜索没有任何标签的视频
- 其他字符串   搜索标题（文件名）中包含该字符串的视频

例如 ``tag:foo tag:bar baz`` 表示「同时具有标签 foo 和 bar，且标题包含 baz」。
"""
import os
import re

# 依次匹配：tag:"..." / tag:... / "..."（带引号的普通短语）/ 普通词
_TOKEN_RE = re.compile(r'tag:"[^"]*"|tag:\S+|"[^"]*"|\S+', re.IGNORECASE)

_TAG_PREFIX = 'tag:'
_NONE_KEYWORD = 'none'


def _is_quoted(text):
    """判断是否被成对的英文双引号包裹"""
    return len(text) >= 2 and text.startswith('"') and text.endswith('"')


def _unquote(text):
    """去掉首尾成对的英文双引号"""
    return text[1:-1] if _is_quoted(text) else text


def parse_query(text):
    """解析搜索串。

    返回 (tags, none_tag, words)：
    - tags: 必须同时具备的标签名列表
    - none_tag: 是否要求「没有任何标签」
    - words: 标题必须同时包含的关键词列表
    """
    tags = []
    none_tag = False
    words = []

    for token in _TOKEN_RE.findall(text or ''):
        if token[:len(_TAG_PREFIX)].lower() == _TAG_PREFIX:
            raw_value = token[len(_TAG_PREFIX):]
            value = _unquote(raw_value).strip()
            if not value:
                continue
            # 只有不加引号的 none 才表示「没有标签」，
            # 加引号的 tag:"none" 用于精确搜索名字就叫 none 的标签
            if not _is_quoted(raw_value) and value.lower() == _NONE_KEYWORD:
                none_tag = True
            elif value not in tags:
                tags.append(value)
        else:
            word = _unquote(token).strip()
            if word and word not in words:
                words.append(word)

    return tags, none_tag, words


def match_paths(video_paths, tags_map, text):
    """按搜索条件过滤候选视频，返回命中的完整路径列表（已按文件名排序）。

    video_paths: 候选视频的完整路径（已规范化）
    tags_map: {视频路径: [标签名, ...]}
    """
    tags, none_tag, words = parse_query(text)
    tags_lower = [tag.lower() for tag in tags]
    words_lower = [word.lower() for word in words]

    matched = []
    for path in video_paths:
        path_tags = tags_map.get(path, [])

        # 标签条件：指定标签必须全部具备（不区分大小写）
        path_tags_lower = {tag.lower() for tag in path_tags}
        if any(tag not in path_tags_lower for tag in tags_lower):
            continue
        # tag:none：必须一个标签都没有
        if none_tag and path_tags:
            continue

        # 标题条件：关键词必须全部出现（不区分大小写）
        title = os.path.basename(path).lower()
        if any(word not in title for word in words_lower):
            continue

        matched.append(path)

    matched.sort(key=lambda p: os.path.basename(p).lower())
    return matched


def build_tag_search(tag):
    """把标签名转成可直接放进搜索框的搜索串（含空格时自动加引号）"""
    return f'{_TAG_PREFIX}"{tag}"' if ' ' in tag else f'{_TAG_PREFIX}{tag}'

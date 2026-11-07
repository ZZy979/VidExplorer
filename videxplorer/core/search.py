"""搜索引擎。

支持的语法（各条件之间取交集）：
- ``tag:xxx``  搜索具有指定标签的视频，可重复多次；标签名含空格时用引号：``tag:"xx xx"``
- ``tag:none`` 搜索没有任何标签的视频
- ``date:YYYY-MM-DD`` 搜索修改日期为该日期的视频，也支持 ``>`` ``>=`` ``<`` ``<=``
- ``play:n``   搜索播放次数为 n 的视频，也支持 ``>`` ``>=`` ``<`` ``<=``
- 其他字符串   搜索标题（文件名）中包含该字符串的视频

例如 ``tag:foo play:>0 date:>=2024-01-01 baz`` 表示「同时具有标签 foo、
播放过、修改日期不早于 2024-01-01，且标题包含 baz」。

带冒号但不是已知字段（tag/date/play）的文字仍按标题关键词处理，
例如 ``star:wars`` 搜索标题中包含 ``star:wars`` 的视频。
"""
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

# 依次匹配：field:"..." / field:... / "..."（带引号的普通短语）/ 普通词
_TOKEN_RE = re.compile(r'[^\s:"]+:"[^"]*"|[^\s:"]+:\S+|"[^"]*"|\S+')

_TAG_FIELD = 'tag'
_DATE_FIELD = 'date'
_PLAY_FIELD = 'play'
_FIELDS = (_TAG_FIELD, _DATE_FIELD, _PLAY_FIELD)

_NONE_KEYWORD = 'none'

# 比较运算符，先匹配两个字符的运算符
_OPS = ('>=', '<=', '>', '<', '=')
_EQUAL_OP = '='

# 日期形如 2024-01-31；播放量必须是非负整数
_DATE_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})$')
_COUNT_RE = re.compile(r'^\d+$')


@dataclass(frozen=True)
class VideoInfo:
    """参与搜索的视频信息（播放量、日期条件会用到）"""
    play_count: int = 0
    modified_date: Optional[date] = None


@dataclass
class SearchQuery:
    """解析后的搜索条件"""
    tags: List[str] = field(default_factory=list)
    none_tag: bool = False
    words: List[str] = field(default_factory=list)
    dates: List[Tuple[str, date]] = field(default_factory=list)
    plays: List[Tuple[str, int]] = field(default_factory=list)


def _is_quoted(text):
    """判断是否被成对的英文双引号包裹"""
    return len(text) >= 2 and text.startswith('"') and text.endswith('"')


def _unquote(text):
    """去掉首尾成对的英文双引号"""
    return text[1:-1] if _is_quoted(text) else text


def _split_comparison(text):
    """把 ``>=2024-01-01`` 拆成 ``('>=', '2024-01-01')``，没有运算符时视为相等匹配"""
    for op in _OPS:
        if text.startswith(op):
            return op, text[len(op):]
    return _EQUAL_OP, text


def _parse_date(text):
    """解析日期条件，格式非法时返回 None"""
    op, value = _split_comparison(text)
    match = _DATE_RE.match(value)
    if not match:
        return None
    try:
        return op, date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def _parse_play(text):
    """解析播放量条件，格式非法时返回 None"""
    op, value = _split_comparison(text)
    if not _COUNT_RE.match(value):
        return None
    return op, int(value)


def _parse_field(name, raw_value, query):
    """把 ``field:query`` 形式的条件加入 query"""
    value = _unquote(raw_value).strip()
    if not value:
        return

    if name == _TAG_FIELD:
        # 只有不加引号的 none 才表示「没有标签」，
        # 加引号的 tag:"none" 用于精确搜索名字就叫 none 的标签
        if not _is_quoted(raw_value) and value.lower() == _NONE_KEYWORD:
            query.none_tag = True
        elif value not in query.tags:
            query.tags.append(value)
    elif name == _DATE_FIELD:
        condition = _parse_date(value)
        if condition and condition not in query.dates:
            query.dates.append(condition)
    else:
        condition = _parse_play(value)
        if condition and condition not in query.plays:
            query.plays.append(condition)


def parse_query(text):
    """解析搜索串，返回 SearchQuery。

    - tags: 必须同时具备的标签名列表
    - none_tag: 是否要求「没有任何标签」
    - words: 标题必须同时包含的关键词列表
    - dates: [(运算符, 日期), ...]
    - plays: [(运算符, 播放次数), ...]
    """
    query = SearchQuery()

    for token in _TOKEN_RE.findall(text or ''):
        name, sep, raw_value = token.partition(':')
        if sep and name.lower() in _FIELDS:
            _parse_field(name.lower(), raw_value, query)
            continue
        word = _unquote(token).strip()
        if word and word not in query.words:
            query.words.append(word)

    return query


def _matches(actual, op, expected):
    """按运算符比较实际值；actual 未知（None）时一律不匹配"""
    if actual is None:
        return False
    if op == '>':
        return actual > expected
    if op == '>=':
        return actual >= expected
    if op == '<':
        return actual < expected
    if op == '<=':
        return actual <= expected
    return actual == expected


def match_paths(video_paths, tags_map, text, info_map=None):
    """按搜索条件过滤候选视频，返回命中的完整路径列表（已按文件名排序）。

    video_paths: 候选视频的完整路径（已规范化）
    tags_map: {视频路径: [标签名, ...]}
    info_map: {视频路径: VideoInfo}，播放量/日期条件会用到；
              缺失的项按「播放 0 次、日期未知」处理
    """
    query = parse_query(text)
    tags_lower = [tag.lower() for tag in query.tags]
    words_lower = [word.lower() for word in query.words]
    info_map = info_map or {}

    matched = []
    for path in video_paths:
        path_tags = tags_map.get(path, [])

        # 标签条件：指定标签必须全部具备（不区分大小写）
        path_tags_lower = {tag.lower() for tag in path_tags}
        if any(tag not in path_tags_lower for tag in tags_lower):
            continue
        # tag:none：必须一个标签都没有
        if query.none_tag and path_tags:
            continue

        # 标题条件：关键词必须全部出现（不区分大小写）
        title = os.path.basename(path).lower()
        if any(word not in title for word in words_lower):
            continue

        # 播放量 / 日期条件
        if query.plays or query.dates:
            info = info_map.get(path) or VideoInfo()
            if any(not _matches(info.play_count, op, count)
                   for op, count in query.plays):
                continue
            if any(not _matches(info.modified_date, op, day)
                   for op, day in query.dates):
                continue

        matched.append(path)

    matched.sort(key=lambda p: os.path.basename(p).lower())
    return matched


def build_tag_search(tag):
    """把标签名转成可直接放进搜索框的搜索串（含空格时自动加引号）"""
    return f'{_TAG_FIELD}:"{tag}"' if ' ' in tag else f'{_TAG_FIELD}:{tag}'

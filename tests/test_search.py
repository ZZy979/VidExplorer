"""videxplorer.core.search 的单元测试。

search.py 是纯逻辑模块，不依赖 PySide6 / OpenCV，因此可以直接运行：

    python -m unittest discover -v
    python -m unittest discover -s tests -t . -v
    python -m unittest tests.test_search -v
"""
import os
import unittest
from datetime import date

from videxplorer.core.search import (
    SearchQuery, VideoInfo, build_tag_search, match_paths, parse_query
)


def names(paths):
    """把完整路径列表转成文件名列表，便于断言"""
    return [os.path.basename(p) for p in paths]


def make_query(tags=(), none_tag=False, words=(), dates=(), plays=()):
    """构造期望的 SearchQuery，便于在表格里书写"""
    return SearchQuery(list(tags), none_tag, list(words), list(dates), list(plays))


class ParseQueryTests(unittest.TestCase):
    """parse_query：搜索串 -> SearchQuery"""

    def test_table(self):
        cases = [
            # 需求里的例子
            ('tag:foo tag:bar baz',
             make_query(tags=['foo', 'bar'], words=['baz'])),
            # 标签名含空格：必须加引号
            ('tag:"xx xx"', make_query(tags=['xx xx'])),
            # tag:none 表示「没有任何标签」
            ('tag:none', make_query(none_tag=True)),
            # 前缀不区分大小写，标签名本身保留原样
            ('TAG:Foo', make_query(tags=['Foo'])),
            ('Tag:foo tAg:bar', make_query(tags=['foo', 'bar'])),
            # 加引号的 none 是字面标签名，不是「没有标签」
            ('tag:"none"', make_query(tags=['none'])),
            # 没有 tag: 前缀的文字只作为标题关键词
            ('baz', make_query(words=['baz'])),
            ('"baz qux" simple', make_query(words=['baz qux', 'simple'])),
            # tag:none 与标题关键词可以共存
            ('tag:none 2019', make_query(none_tag=True, words=['2019'])),
            # 多个条件混合
            ('tag:foo bar tag:"a b"',
             make_query(tags=['foo', 'a b'], words=['bar'])),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_query(text), expected)

    def test_empty_or_incomplete_input(self):
        """空串 / None / 只有字段前缀时不产生任何条件"""
        for text in ('', '   ', None, 'tag:', 'tag:""', 'tag:   ',
                     'date:', 'play:', 'date:""', 'play:""'):
            with self.subTest(text=text):
                self.assertEqual(parse_query(text), make_query())

    def test_duplicates_are_deduped(self):
        """重复出现的同一条件只保留一份"""
        self.assertEqual(parse_query('tag:foo tag:foo'),
                         make_query(tags=['foo']))
        self.assertEqual(parse_query('baz baz'), make_query(words=['baz']))
        self.assertEqual(parse_query('play:>0 play:>0'),
                         make_query(plays=[('>', 0)]))
        self.assertEqual(parse_query('date:2024-01-01 date:2024-01-01'),
                         make_query(dates=[('=', date(2024, 1, 1))]))

    def test_same_name_as_tag_and_as_word(self):
        """同一个词分别出现在 tag: 和普通位置时，两种条件都会生效"""
        self.assertEqual(parse_query('tag:foo foo'),
                         make_query(tags=['foo'], words=['foo']))


class ParseDatePlayTests(unittest.TestCase):
    """parse_query：date: / play: 条件"""

    def test_date_conditions(self):
        cases = [
            ('date:2024-01-31', [('=', date(2024, 1, 31))]),
            ('date:>2024-01-31', [('>', date(2024, 1, 31))]),
            ('date:>=2024-01-31', [('>=', date(2024, 1, 31))]),
            ('date:<2024-01-31', [('<', date(2024, 1, 31))]),
            ('date:<=2024-01-31', [('<=', date(2024, 1, 31))]),
            # 字段名不区分大小写，闰年日期有效
            ('DATE:2024-02-29', [('=', date(2024, 2, 29))]),
            # 值可以加引号
            ('date:">=2024-01-01"', [('>=', date(2024, 1, 1))]),
            # 同一天可以叠加多个条件
            ('date:>=2024-01-01 date:<2024-02-01',
             [('>=', date(2024, 1, 1)), ('<', date(2024, 2, 1))]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_query(text), make_query(dates=expected))

    def test_invalid_date_conditions_are_ignored(self):
        for text in ('date:abc', 'date:2024-13-01', 'date:2024-02-30',
                     'date:2024-1-1', 'date:20240101', 'date:>', 'date:-2024-01-01'):
            with self.subTest(text=text):
                self.assertEqual(parse_query(text), make_query())

    def test_play_conditions(self):
        cases = [
            ('play:5', [('=', 5)]),
            ('play:0', [('=', 0)]),
            ('play:>0', [('>', 0)]),
            ('play:>=10', [('>=', 10)]),
            ('play:<3', [('<', 3)]),
            ('play:<=3', [('<=', 3)]),
            # 字段名不区分大小写，值可以加引号
            ('Play:>2', [('>', 2)]),
            ('play:">=2"', [('>=', 2)]),
            # 多个条件叠加
            ('play:>0 play:<=10', [('>', 0), ('<=', 10)]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_query(text), make_query(plays=expected))

    def test_invalid_play_conditions_are_ignored(self):
        for text in ('play:abc', 'play:-1', 'play:1.5', 'play:>', 'play:+3'):
            with self.subTest(text=text):
                self.assertEqual(parse_query(text), make_query())

    def test_unknown_field_is_title_word(self):
        """带冒号但不是已知字段时，整段文字仍按标题关键词搜索"""
        self.assertEqual(parse_query('star:wars'),
                         make_query(words=['star:wars']))
        self.assertEqual(parse_query('http://example.com'),
                         make_query(words=['http://example.com']))

    def test_all_conditions_combined(self):
        self.assertEqual(
            parse_query('tag:foo play:>0 date:>=2024-01-01 baz'),
            make_query(tags=['foo'], words=['baz'],
                       dates=[('>=', date(2024, 1, 1))], plays=[('>', 0)]))


class BuildTagSearchTests(unittest.TestCase):
    """build_tag_search：标签名 -> 搜索串"""

    def test_table(self):
        cases = [
            ('foo', 'tag:foo'),
            ('a-b', 'tag:a-b'),
            # 含空格必须加引号，否则会被拆成两个条件
            ('xx xx', 'tag:"xx xx"'),
        ]
        for tag, expected in cases:
            with self.subTest(tag=tag):
                self.assertEqual(build_tag_search(tag), expected)

    def test_round_trip(self):
        """生成出的搜索串再解析回来，应还原成同一个标签条件"""
        for tag in ('foo', 'xx xx', 'a-b', 'x y z'):
            with self.subTest(tag=tag):
                query = parse_query(build_tag_search(tag))
                self.assertEqual(query.tags, [tag])
                self.assertEqual(query.words, [])
                self.assertFalse(query.none_tag)


class MatchPathsTests(unittest.TestCase):
    """match_paths：各条件取交集"""

    def setUp(self):
        videos = os.path.join('videos')
        self.a = os.path.join(videos, 'a.mp4')
        self.b = os.path.join(videos, 'b.mp4')
        self.c = os.path.join(videos, 'c baz.mp4')      # 标题含 baz
        self.d = os.path.join(videos, 'd.mp4')          # 无标签
        self.paths = [self.a, self.b, self.c, self.d]
        self.tags_map = {
            self.a: ['foo', 'bar'],
            self.b: ['foo'],
            self.c: ['foo', 'bar'],
            self.d: [],
        }

    def match(self, text):
        return names(match_paths(self.paths, self.tags_map, text))

    def test_intersection_of_tags_and_title(self):
        """需求示例：tag:foo tag:bar baz -> 同时有 foo、bar 且标题含 baz"""
        self.assertEqual(self.match('tag:foo tag:bar baz'), ['c baz.mp4'])

    def test_single_tag(self):
        self.assertEqual(self.match('tag:foo'), ['a.mp4', 'b.mp4', 'c baz.mp4'])

    def test_multiple_tags_are_intersected(self):
        self.assertEqual(self.match('tag:foo tag:bar'), ['a.mp4', 'c baz.mp4'])

    def test_tag_none(self):
        self.assertEqual(self.match('tag:none'), ['d.mp4'])

    def test_tag_none_combined_with_title_word(self):
        self.assertEqual(self.match('tag:none baz'), [])
        self.assertEqual(self.match('tag:none d'), ['d.mp4'])

    def test_title_only(self):
        self.assertEqual(self.match('baz'), ['c baz.mp4'])
        self.assertEqual(self.match('a.mp4'), ['a.mp4'])

    def test_multiple_words_are_intersected(self):
        """标题必须同时包含所有关键词"""
        self.assertEqual(self.match('c baz'), ['c baz.mp4'])
        self.assertEqual(self.match('baz nope'), [])

    def test_no_conditions_matches_all(self):
        self.assertEqual(self.match(''), ['a.mp4', 'b.mp4', 'c baz.mp4', 'd.mp4'])

    def test_tag_matching_is_case_insensitive(self):
        self.assertEqual(self.match('tag:FOO'), ['a.mp4', 'b.mp4', 'c baz.mp4'])

    def test_title_matching_is_case_insensitive(self):
        self.assertEqual(self.match('BAZ'), ['c baz.mp4'])

    def test_unknown_tag_matches_nothing(self):
        self.assertEqual(self.match('tag:nope'), [])

    def test_contradictory_conditions_match_nothing(self):
        """tag:none 与 tag:foo 互相矛盾，交集为空"""
        self.assertEqual(self.match('tag:none tag:foo'), [])

    def test_video_missing_from_tags_map_counts_as_untagged(self):
        """还没入库、不在 tags_map 里的视频视为没有标签"""
        new_video = os.path.join('videos', 'new.mp4')
        paths = [new_video]
        self.assertEqual(names(match_paths(paths, {}, 'tag:none')), ['new.mp4'])
        self.assertEqual(names(match_paths(paths, {}, 'tag:foo')), [])

    def test_quoted_tag_needed_for_names_with_spaces(self):
        videos = os.path.join('videos')
        path = os.path.join(videos, 'x.mp4')
        tags_map = {path: ['xx xx', 'yy']}

        # 加引号 -> 一个完整标签名
        self.assertEqual(match_paths([path], tags_map, 'tag:"xx xx"'), [path])
        # 不加引号 -> 变成「标签 xx」+「标题含 xx」两个条件，都匹配不上
        self.assertEqual(match_paths([path], tags_map, 'tag:xx xx'), [])
        # 用 build_tag_search 生成则不会有这个问题
        self.assertEqual(
            match_paths([path], tags_map, build_tag_search('xx xx')), [path])

    def test_results_sorted_by_name_ignoring_case(self):
        videos = os.path.join('videos')
        paths = [
            os.path.join(videos, 'z.mp4'),
            os.path.join(videos, 'A.mp4'),
            os.path.join(videos, 'm.mp4'),
        ]
        self.assertEqual(
            names(match_paths(paths, {}, '')), ['A.mp4', 'm.mp4', 'z.mp4'])

    def test_empty_candidate_list(self):
        self.assertEqual(match_paths([], self.tags_map, 'tag:foo'), [])

    def test_search_scope_is_not_modified(self):
        """match_paths 不应修改传入的参数"""
        paths = list(self.paths)
        tags_map = {k: list(v) for k, v in self.tags_map.items()}
        match_paths(paths, tags_map, 'tag:foo tag:bar baz')

        self.assertEqual(paths, self.paths)
        self.assertEqual(tags_map, self.tags_map)


class MatchPathInfoTests(unittest.TestCase):
    """match_paths：按播放量 / 日期条件过滤"""

    def setUp(self):
        videos = os.path.join('videos')
        self.a = os.path.join(videos, 'a.mp4')
        self.b = os.path.join(videos, 'b.mp4')
        self.c = os.path.join(videos, 'c.mp4')
        self.paths = [self.a, self.b, self.c]
        self.info_map = {
            self.a: VideoInfo(play_count=0, modified_date=date(2024, 1, 1)),
            self.b: VideoInfo(play_count=3, modified_date=date(2024, 6, 15)),
            self.c: VideoInfo(play_count=10, modified_date=date(2023, 12, 31)),
        }

    def match(self, text, info_map=None):
        if info_map is None:
            info_map = self.info_map
        return names(match_paths(self.paths, {}, text, info_map))

    def test_play_equal(self):
        self.assertEqual(self.match('play:3'), ['b.mp4'])
        self.assertEqual(self.match('play:0'), ['a.mp4'])
        self.assertEqual(self.match('play:4'), [])

    def test_play_comparisons(self):
        self.assertEqual(self.match('play:>0'), ['b.mp4', 'c.mp4'])
        self.assertEqual(self.match('play:>=3'), ['b.mp4', 'c.mp4'])
        self.assertEqual(self.match('play:<3'), ['a.mp4'])
        self.assertEqual(self.match('play:<=3'), ['a.mp4', 'b.mp4'])

    def test_play_conditions_are_intersected(self):
        self.assertEqual(self.match('play:>0 play:<=3'), ['b.mp4'])
        self.assertEqual(self.match('play:>0 play:<3'), [])

    def test_date_equal(self):
        self.assertEqual(self.match('date:2024-01-01'), ['a.mp4'])
        self.assertEqual(self.match('date:2024-01-02'), [])

    def test_date_comparisons(self):
        # 相同日期的边界：>= 与 <= 都包含当天
        self.assertEqual(self.match('date:>2024-01-01'), ['b.mp4'])
        self.assertEqual(self.match('date:>=2024-01-01'), ['a.mp4', 'b.mp4'])
        self.assertEqual(self.match('date:<2024-01-01'), ['c.mp4'])
        self.assertEqual(self.match('date:<=2024-01-01'), ['a.mp4', 'c.mp4'])

    def test_date_range(self):
        self.assertEqual(
            self.match('date:>=2024-01-01 date:<2024-06-15'), ['a.mp4'])

    def test_info_combined_with_tags_and_title(self):
        tags_map = {self.a: ['foo'], self.b: ['foo'], self.c: ['foo']}
        self.assertEqual(
            names(match_paths(self.paths, tags_map, 'tag:foo play:>0 b',
                              self.info_map)),
            ['b.mp4'])

    def test_missing_info_means_unplayed_and_unknown_date(self):
        video = os.path.join('videos', 'new.mp4')
        self.assertEqual(names(match_paths([video], {}, 'play:0')), ['new.mp4'])
        self.assertEqual(names(match_paths([video], {}, 'play:>0')), [])
        self.assertEqual(
            names(match_paths([video], {}, 'date:>=2000-01-01')), [])
        self.assertEqual(names(match_paths([video], {}, 'play:<=0')), ['new.mp4'])

    def test_info_map_is_not_modified(self):
        info_map = dict(self.info_map)
        match_paths(self.paths, {}, 'play:>0 date:<2024-06-01', info_map)
        self.assertEqual(info_map, self.info_map)


class NonAsciiSearchTests(unittest.TestCase):
    """中文/含空格的标签与标题"""

    def setUp(self):
        videos = os.path.join('视频')
        self.trip = os.path.join(videos, '欧洲旅行.mp4')
        self.doc = os.path.join(videos, '纪录片 4K.mp4')
        self.plain = os.path.join(videos, '未分类.mp4')
        self.paths = [self.trip, self.doc, self.plain]
        self.tags_map = {
            self.trip: ['旅行', '收藏'],
            self.doc: ['旅行'],
            self.plain: [],
        }

    def match(self, text):
        return names(match_paths(self.paths, self.tags_map, text))

    def test_chinese_tag(self):
        self.assertEqual(self.match('tag:旅行'), ['欧洲旅行.mp4', '纪录片 4K.mp4'])

    def test_intersection_of_chinese_tags(self):
        self.assertEqual(self.match('tag:旅行 tag:收藏'), ['欧洲旅行.mp4'])

    def test_chinese_title_word(self):
        self.assertEqual(self.match('欧洲'), ['欧洲旅行.mp4'])

    def test_chinese_tag_and_title_word(self):
        self.assertEqual(self.match('tag:旅行 4K'), ['纪录片 4K.mp4'])

    def test_tag_none_among_chinese_titles(self):
        self.assertEqual(self.match('tag:none'), ['未分类.mp4'])

    def test_quoted_tag_matches(self):
        self.assertEqual(self.match('tag:"旅行"'), ['欧洲旅行.mp4', '纪录片 4K.mp4'])


if __name__ == '__main__':
    unittest.main()

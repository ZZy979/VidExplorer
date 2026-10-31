import os
import platform
import shutil
import subprocess

from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QStatusBar, QProgressBar, QMenu
)

from videxplorer.core.library import VideoLibrary
from videxplorer.core.loader import VideoLoaderThread
from videxplorer.core.search import build_tag_search, match_paths
from videxplorer.models.collection import CollectionManager
from videxplorer.models.database import VideoDatabase
from videxplorer.ui.batch_tag_dialog import BatchTagDialog
from videxplorer.ui.clean_missing_dialog import CleanMissingDialog
from videxplorer.ui.collection_dialogs import CreateCollectionDialog, OpenCollectionDialog
from videxplorer.ui.rename_dialog import RenameDialog
from videxplorer.ui.tag_dialog import TagDialog
from videxplorer.ui.tag_manager_dialog import TagManagerDialog
from videxplorer.ui.video_grid import VideoGrid
from videxplorer.utils.file import get_file_size, get_video_dimensions
from videxplorer.utils.path import normalize_path
from videxplorer.utils.thumbnail_cache import DEFAULT_CACHE_DIR, thumbnail_cache


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.library = VideoLibrary()
        self.collection_manager = CollectionManager()
        self.collection = None  # 当前打开的合集
        self.db = None  # 合集数据库（打开合集后创建）
        self.current_folder = ''
        self.folder_stack = []  # 文件夹导航栈（用于返回上级）
        self.video_paths = []
        self.loader_thread = None
        self._load_session = 0  # 加载会话编号，用于忽略旧线程的延迟信号
        self.sort_mode = 'name'  # 排序方式：name / mtime / play_count
        self.current_selected_path = ''
        self.video_tags_cache = {}  # 缓存视频标签

        self.setWindowTitle('VidExplorer - 视频合集')
        self.setMinimumSize(1200, 700)

        # 创建菜单栏
        self.create_menu_bar()

        # 创建中央部件
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 顶部工具栏
        self.toolbar = self.create_toolbar()
        main_layout.addWidget(self.toolbar)

        # 统计信息栏
        self.stats_label = QLabel('未打开合集')
        main_layout.addWidget(self.stats_label)

        # 视频网格
        self.video_grid = VideoGrid()
        self.video_grid.video_clicked.connect(self.on_video_clicked)
        self.video_grid.video_tag_clicked.connect(self.on_tag_clicked)
        self.video_grid.video_context_menu_requested.connect(self.show_video_context_menu)
        self.video_grid.folder_context_menu_requested.connect(self.show_folder_context_menu)
        self.video_grid.folder_opened.connect(self.on_folder_opened)
        self.video_grid.collection_opened.connect(self.open_collection)
        main_layout.addWidget(self.video_grid, stretch=1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel('就绪')
        self.status_bar.addWidget(self.status_label)

        # 初始界面：显示最近打开的合集
        self._update_ui_state()
        self.show_recent_collections()

    def create_toolbar(self):
        """创建顶部工具栏"""
        toolbar = QWidget(self)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 新建合集按钮
        create_btn = QPushButton('➕新建合集')
        create_btn.clicked.connect(self.create_collection)
        layout.addWidget(create_btn)

        # 打开合集按钮
        open_btn = QPushButton('📂打开合集')
        open_btn.clicked.connect(self.show_open_collection_dialog)
        layout.addWidget(open_btn)

        # 关闭合集按钮
        self.close_collection_btn = QPushButton('🔒关闭合集')
        self.close_collection_btn.clicked.connect(self.close_collection)
        layout.addWidget(self.close_collection_btn)

        # 刷新按钮
        self.refresh_btn = QPushButton('🔄刷新')
        self.refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_btn)

        # 返回上级按钮
        self.up_btn = QPushButton('⬆返回上级')
        self.up_btn.setEnabled(False)
        self.up_btn.clicked.connect(self.go_up)
        layout.addWidget(self.up_btn)

        # 标签管理按钮
        self.tag_manager_btn = QPushButton("🏷️标签管理")
        self.tag_manager_btn.clicked.connect(self.open_tag_manager)
        layout.addWidget(self.tag_manager_btn)

        # 搜索框（支持 tag: 语法，搜索当前文件夹及子文件夹，占据剩余空间）
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('搜索标题，或 tag:标签名 ...')
        self.search_input.setToolTip(
            '搜索语法（多个条件之间取交集）：\n'
            '  • tag:标签名 —— 具有该标签的视频，可重复使用\n'
            '      标签名含空格时加引号，例如 tag:"xx xx"\n'
            '  • tag:none —— 没有任何标签的视频\n'
            '  • 其他文字 —— 标题中包含该文字的视频\n'
            '\n'
            '例如：tag:foo tag:bar baz\n'
            '表示「同时具有标签 foo 和 bar，且标题包含 baz 的视频」\n'
            '\n'
            '搜索范围为当前文件夹及其所有子文件夹。'
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._run_search_from_box)
        layout.addWidget(self.search_input, stretch=1)

        # 搜索按钮（点击或按回车触发搜索）
        self.search_btn = QPushButton('🔍搜索')
        self.search_btn.clicked.connect(self._run_search_from_box)
        layout.addWidget(self.search_btn)

        return toolbar

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu('文件(&F)')
        create_action = file_menu.addAction('新建合集...')
        create_action.triggered.connect(self.create_collection)
        open_collection_action = file_menu.addAction('打开合集...')
        open_collection_action.triggered.connect(self.show_open_collection_dialog)
        self.close_collection_action = file_menu.addAction('关闭合集')
        self.close_collection_action.triggered.connect(self.close_collection)
        self.close_collection_action.setEnabled(False)
        file_menu.addSeparator()
        self.up_action = file_menu.addAction('返回上级')
        self.up_action.triggered.connect(self.go_up)
        self.up_action.setEnabled(False)
        file_menu.addSeparator()
        exit_action = file_menu.addAction('退出(&X)')
        exit_action.triggered.connect(self.close)

        # 视图菜单（排序方式）
        view_menu = menubar.addMenu('视图(&V)')
        self.sort_group = QActionGroup(self)
        self.sort_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.Exclusive)

        self.sort_name_action = view_menu.addAction('按文件名')
        self.sort_name_action.setCheckable(True)
        self.sort_name_action.setChecked(True)
        self.sort_name_action.triggered.connect(lambda: self.set_sort_mode('name'))

        self.sort_mtime_action = view_menu.addAction('按修改时间')
        self.sort_mtime_action.setCheckable(True)
        self.sort_mtime_action.triggered.connect(lambda: self.set_sort_mode('mtime'))

        self.sort_play_action = view_menu.addAction('按播放次数')
        self.sort_play_action.setCheckable(True)
        self.sort_play_action.triggered.connect(lambda: self.set_sort_mode('play_count'))

        for action in (self.sort_name_action, self.sort_mtime_action, self.sort_play_action):
            self.sort_group.addAction(action)

        # 工具菜单
        tools_menu = menubar.addMenu('工具(&T)')
        self.clear_cache_action = tools_menu.addAction('清空缩略图缓存')
        self.clear_cache_action.triggered.connect(self.clear_thumbnail_cache)
        self.clean_missing_action = tools_menu.addAction('清理已失效文件')
        self.clean_missing_action.triggered.connect(self.clean_missing_files)
        tools_menu.addSeparator()
        self.tag_manager_action = tools_menu.addAction('标签管理')
        self.tag_manager_action.triggered.connect(self.open_tag_manager)

    def load_videos(self, folder):
        """加载当前文件夹中的子文件夹和视频（不递归）"""
        # 清空搜索框（blockSignals 避免触发其他信号）
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)

        # 停止之前的加载线程
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait()
            self.loader_thread = None

        # 清空当前显示
        self.video_grid.clear_cards()
        self.video_paths = []
        self.video_tags_cache.clear()

        # 列出当前文件夹下的子文件夹和视频（不递归）
        folder_items, self.video_paths = self.library.list_folder(folder)
        folder_count = len(folder_items)
        video_count = len(self.video_paths)

        # 更新统计信息（未打开合集时不显示合集名）
        title = f'{self.collection["name"]}  -  ' if self.collection else ''
        self.stats_label.setText(
            f'{title}{folder}  -  {folder_count}个文件夹 / {video_count}个视频')

        # 加载视频标签
        self.load_video_tags(self.video_paths)

        # 加载播放次数
        play_count_cache = self.load_video_play_counts(self.video_paths)

        # 应用排序（子文件夹始终排在视频之前）
        folder_items = self._sort_folders(folder_items)
        self.video_paths = self._sort_videos(self.video_paths, play_count_cache)

        # 显示文件夹和视频卡片
        self.video_grid.set_entries(
            folder_items, self.video_paths, self.video_tags_cache, play_count_cache)

        if video_count == 0:
            self.status_label.setText('此文件夹下没有视频文件')
            self.progress_bar.setVisible(False)
            return

        self.status_label.setText(f'正在加载 {video_count} 个视频的缩略图...')

        # 启动后台加载线程
        self._start_loader(self.video_paths)

    def _start_loader(self, paths):
        """启动后台加载线程。

        每次加载分配新的会话编号，并用 lambda 把编号传给回调；
        旧线程延迟到达的信号会因会话编号不匹配而被忽略，
        避免它在切换文件夹后误清空正在运行的新线程导致崩溃。
        """
        # 停止并等待之前的加载线程
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait()
            self.loader_thread = None

        self._load_session += 1
        session = self._load_session

        thread = VideoLoaderThread()
        thread.set_videos(paths)
        thread.video_loaded.connect(
            lambda path, meta, s=session: self.on_video_metadata_loaded(path, meta, s))
        thread.all_loaded.connect(lambda s=session: self.on_all_videos_loaded(s))
        thread.progress.connect(
            lambda cur, tot, s=session: self.on_loading_progress(cur, tot, s))
        self.loader_thread = thread
        thread.start()

    def save_video_to_database(self, file_path, metadata):
        """保存视频信息到数据库"""
        # 检查是否已存在
        if self.db.get_video_by_path(file_path):
            return

        # 获取视频信息
        duration = metadata.duration
        width, height = get_video_dimensions(file_path)
        file_size = get_file_size(file_path)

        # 保存到数据库
        metadata = {
            'title': os.path.basename(file_path),
            'duration': duration,
            'width': width,
            'height': height,
            'file_size': file_size
        }
        self.db.add_or_update_video(file_path, metadata)

    def load_video_tags(self, video_paths: list):
        """批量加载视频标签"""
        for path in video_paths:
            tags = self.db.get_tags_for_video(path)
            self.video_tags_cache[path] = tags

    def load_video_play_counts(self, video_paths: list) -> dict:
        """批量加载视频播放次数"""
        counts = {}
        for path in video_paths:
            video = self.db.get_video_by_path(path)
            if video and video.get('play_count') is not None:
                counts[path] = video['play_count']
        return counts

    def set_sort_mode(self, mode):
        """设置排序方式并刷新当前视图"""
        self.sort_mode = mode
        # 同步勾选状态
        self.sort_name_action.setChecked(mode == 'name')
        self.sort_mtime_action.setChecked(mode == 'mtime')
        self.sort_play_action.setChecked(mode == 'play_count')
        if self.current_folder:
            self.load_videos(self.current_folder)

    @staticmethod
    def _mtime(path):
        """获取路径修改时间（不存在时返回 0）"""
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0

    def _sort_folders(self, folder_items):
        """对子文件夹排序：按文件名升序（默认）或修改时间降序。

        播放次数排序对子文件夹不生效，仍按文件名升序。
        """
        if self.sort_mode == 'mtime':
            return sorted(folder_items, key=lambda item: self._mtime(item[0]), reverse=True)
        return sorted(folder_items, key=lambda item: os.path.basename(item[0]).lower())

    def _sort_videos(self, video_paths, play_count_cache):
        """对视频排序：文件名升序（默认）/ 修改时间降序 / 播放次数降序"""
        if self.sort_mode == 'mtime':
            return sorted(video_paths, key=self._mtime, reverse=True)
        if self.sort_mode == 'play_count':
            return sorted(video_paths, key=lambda p: play_count_cache.get(p, 0), reverse=True)
        return sorted(video_paths, key=lambda p: os.path.basename(p).lower())

    def on_video_metadata_loaded(self, file_path, metadata, session=None):
        """单个视频元数据加载完成"""
        # 忽略旧加载会话延迟到达的信号
        if session is not None and session != self._load_session:
            return
        # 更新对应卡片的时长显示
        self.video_grid.update_card_metadata(file_path, metadata)
        self.save_video_to_database(file_path, metadata)
        # 更新播放次数显示（新入库视频为 0）
        video = self.db.get_video_by_path(file_path)
        if video:
            self.video_grid.update_card_play_count(file_path, video.get('play_count'))

    def on_all_videos_loaded(self, session=None):
        """所有视频加载完成"""
        # 忽略旧加载会话延迟到达的信号
        if session is not None and session != self._load_session:
            return
        self.status_label.setText(f'加载完成，共{len(self.video_paths)}个视频')
        self.progress_bar.setVisible(False)
        self.loader_thread = None

    def on_loading_progress(self, current, total, session=None):
        """更新进度"""
        # 忽略旧加载会话延迟到达的信号
        if session is not None and session != self._load_session:
            return
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f'加载缩略图{current}/{total}')

    def on_tag_clicked(self, tag):
        """点击视频卡片上的标签 - 搜索该标签"""
        if not self.current_folder:
            self.status_label.setText(f'搜索标签: {tag}')
            return

        # 转成 tag: 语法（标签名含空格时自动加引号）
        query = build_tag_search(tag)

        # 在搜索框中显示当前条件（blockSignals 避免触发搜索框自身的搜索逻辑）
        self.search_input.blockSignals(True)
        self.search_input.setText(query)
        self.search_input.blockSignals(False)

        self._run_search_from_box()

    def _run_search_from_box(self):
        """执行搜索框搜索（搜索按钮 / 回车触发）"""
        query = self.search_input.text().strip()
        if not query:
            self._exit_search()
            return
        self._apply_search(query)

    def _exit_search(self):
        """清空搜索，回到当前文件夹视图"""
        if self.current_folder:
            self.load_videos(self.current_folder)

    def _apply_search(self, query):
        """在「当前文件夹 + 子文件夹」范围内按搜索条件取交集"""
        if not self.current_folder:
            return

        # 停止之前的加载线程
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait()
            self.loader_thread = None

        # 当前文件夹范围内（含子文件夹）的所有视频
        all_paths = self.library.list_videos_recursive(self.current_folder)

        # 标签一次取全表，再在内存中与其它条件取交集
        tags_map = {normalize_path(path): tags
                    for path, tags in self.db.get_videos_with_tags().items()}

        matched_paths = match_paths(all_paths, tags_map, query)
        self._show_search_results(matched_paths, query)

    def _show_search_results(self, matched_paths, query):
        """显示搜索结果"""
        self.video_tags_cache.clear()
        self.video_paths = matched_paths

        self.load_video_tags(matched_paths)
        play_count_cache = self.load_video_play_counts(matched_paths)

        # 按当前排序方式排列搜索结果
        matched_paths = self._sort_videos(matched_paths, play_count_cache)
        self.video_paths = matched_paths

        self.stats_label.setText(f'搜索结果: "{query}"  -  共{len(matched_paths)}个视频')
        self.video_grid.set_entries([], matched_paths, self.video_tags_cache, play_count_cache)

        if not matched_paths:
            self.status_label.setText('未找到匹配的视频')
            self.progress_bar.setVisible(False)
            return

        self.status_label.setText(f'正在加载 {len(matched_paths)} 个视频的缩略图...')
        self._start_loader(matched_paths)

    def show_video_context_menu(self, file_path, pos):
        """显示视频右键菜单"""
        self.current_selected_path = file_path

        menu = QMenu(self)

        play_action = menu.addAction('播放')
        play_action.triggered.connect(lambda: self.on_video_clicked(file_path))

        menu.addSeparator()

        edit_tags_action = menu.addAction('编辑标签')
        edit_tags_action.triggered.connect(lambda: self.edit_video_tags(file_path))

        move_action = menu.addAction('移动')
        move_action.triggered.connect(lambda: self.move_video(file_path))

        rename_action = menu.addAction('重命名')
        rename_action.triggered.connect(lambda: self.rename_video(file_path))

        delete_action = menu.addAction('删除')
        delete_action.triggered.connect(lambda: self.delete_video(file_path))

        menu.exec(pos)

    def show_folder_context_menu(self, folder_path, pos):
        """显示文件夹右键菜单"""
        menu = QMenu(self)

        open_action = menu.addAction('打开')
        open_action.triggered.connect(lambda: self.on_folder_opened(folder_path))

        rename_action = menu.addAction('重命名')
        rename_action.triggered.connect(lambda: self.rename_folder(folder_path))

        batch_action = menu.addAction('批量添加标签')
        batch_action.triggered.connect(lambda: self.batch_add_tags_to_folder(folder_path))

        menu.exec(pos)

    def rename_folder(self, folder_path):
        """重命名文件夹：更新磁盘上的文件夹名，并同步数据库中的视频路径"""
        folder_path = normalize_path(folder_path)
        old_name = os.path.basename(folder_path)

        dialog = RenameDialog(
            folder_path, self,
            title='重命名文件夹',
            path_label='当前文件夹：',
            name_label='新文件夹名：',
            placeholder='输入新文件夹名')
        if not dialog.exec():
            return  # 点击取消，不做任何修改

        new_name = dialog.get_new_name()
        if new_name == old_name:
            return

        # 新文件夹名不能包含路径分隔符，也不能是 . / ..
        if os.sep in new_name or (os.altsep and os.altsep in new_name):
            QMessageBox.warning(self, '重命名失败', '文件夹名不能包含路径分隔符')
            return
        if new_name in ('.', '..'):
            QMessageBox.warning(self, '重命名失败', f'文件夹名无效: {new_name}')
            return

        new_path = os.path.join(os.path.dirname(folder_path), new_name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, '重命名失败', f'目标已存在: {new_name}')
            return

        # 记录各视频的修改时间，用于重命名后清理旧路径的缩略图缓存
        old_mtimes = {}
        for video_path in self.library.list_videos_recursive(folder_path):
            try:
                old_mtimes[video_path] = os.stat(video_path).st_mtime
            except OSError:
                pass

        try:
            os.rename(folder_path, new_path)
        except OSError as e:
            QMessageBox.warning(self, '重命名失败', f'无法重命名文件夹:\n{e}')
            return

        new_path = normalize_path(new_path)

        # 同步数据库中的视频路径与标题
        if self.db.update_folder_path(folder_path, new_path) is None:
            QMessageBox.warning(
                self, '警告',
                '文件夹已重命名，但更新数据库中的视频路径失败，可能需要手动清理失效记录')

        # 清理旧路径的缩略图缓存
        for video_path, mtime in old_mtimes.items():
            thumbnail_cache.remove_cache(video_path, mtime)

        # 导航栈与当前文件夹若位于被重命名的文件夹内，同步更新
        self.folder_stack = [
            self._replace_folder_prefix(p, folder_path, new_path) for p in self.folder_stack]
        self.current_folder = self._replace_folder_prefix(
            self.current_folder, folder_path, new_path)

        self.status_label.setText(f'已重命名文件夹: {old_name} -> {new_name}')
        if self.current_folder:
            self.load_videos(self.current_folder)

    @staticmethod
    def _replace_folder_prefix(path, old_folder, new_folder):
        """把 path 中被重命名文件夹的路径前缀替换为新路径，无关路径原样返回"""
        if not path:
            return path

        old_key = os.path.normcase(old_folder.rstrip('\\/'))
        path_key = os.path.normcase(path.rstrip('\\/'))
        if path_key == old_key:
            return new_folder
        if path_key.startswith(old_key + os.sep):
            return new_folder + path[len(old_key):]
        return path

    def batch_add_tags_to_folder(self, folder_path):
        """为该文件夹中的所有视频批量添加标签（只添加，不覆盖）"""
        video_paths = self.library.list_videos_recursive(folder_path)
        if not video_paths:
            QMessageBox.information(self, '提示', '该文件夹下没有视频文件')
            return

        all_tags = [tag['name'] for tag in self.db.get_all_tags()]
        dialog = BatchTagDialog(folder_path, len(video_paths), all_tags, self)
        if not dialog.exec():
            return

        tag_names = dialog.get_tags()
        if not tag_names:
            QMessageBox.information(self, '提示', '未输入任何标签')
            return

        if self.db.add_tags_to_videos(video_paths, tag_names):
            self.status_label.setText(
                f'已为 {len(video_paths)} 个视频添加标签: {", ".join(tag_names)}')
            # 刷新当前视图以更新卡片上的标签显示
            if self.current_folder:
                self.load_videos(self.current_folder)
        else:
            QMessageBox.warning(self, '失败', '批量添加标签失败')

    def edit_video_tags(self, file_path):
        """编辑视频标签"""
        current_tags = self.db.get_tags_for_video(file_path)
        all_tags = [tag['name'] for tag in self.db.get_all_tags()]

        dialog = TagDialog(file_path, current_tags, all_tags, self.db, self)
        if dialog.exec():
            new_tags = dialog.get_tags()
            # 保存到数据库
            self.db.set_video_tags(file_path, new_tags)

            # 更新缓存
            self.video_tags_cache[file_path] = new_tags

            # 更新界面
            self.video_grid.update_card_tags(file_path, new_tags)

            self.status_label.setText(f'已更新标签: {file_path}')

    def open_tag_manager(self):
        """打开标签管理器"""
        if self.db is None:
            return
        dialog = TagManagerDialog(self.db, self)
        dialog.exec()
        # 关闭后刷新当前视图，以更新卡片上的标签显示
        if self.current_folder:
            self.load_videos(self.current_folder)

    def clear_thumbnail_cache(self):
        """清空当前合集的缩略图缓存"""
        if self.db is None:
            return
        name = self.collection['name'] if self.collection else ''
        reply = QMessageBox.question(
            self,
            '确认清空',
            f'确定要清空合集「{name}」的缩略图缓存吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            thumbnail_cache.clear_cache()
            QMessageBox.information(self, '完成', '缩略图缓存已清空')
            # 刷新当前视图
            if self.current_folder:
                self.load_videos(self.current_folder)

    def clean_missing_files(self):
        """清理已失效文件：从数据库中删除磁盘上已不存在的视频信息及标签信息"""
        if self.db is None:
            return
        missing_paths = []
        for video in self.db.get_all_videos():
            file_path = video.get('file_path')
            if not file_path:
                continue
            # 磁盘上已不再是该文件，视为失效
            if not os.path.isfile(file_path):
                missing_paths.append(file_path)

        if not missing_paths:
            QMessageBox.information(self, '提示', '没有已失效的文件')
            return

        missing_paths.sort(key=lambda p: p.lower())

        # 弹出确认窗口，列出所有待删除文件的完整路径
        dialog = CleanMissingDialog(missing_paths, self)
        if not dialog.exec():
            return  # 点击取消，不删除

        paths = dialog.get_paths()
        if self.db.delete_videos(paths):
            self.status_label.setText(f'已从数据库清理 {len(paths)} 个失效文件记录')
            # 刷新当前视图
            if self.current_folder:
                self.load_videos(self.current_folder)
        else:
            QMessageBox.warning(self, '失败', '清理失效文件失败')

    def create_collection(self):
        """新建合集：输入名称与根文件夹，初始化合集数据库后自动打开"""
        dialog = CreateCollectionDialog(self)
        if not dialog.exec():
            return

        try:
            collection = self.collection_manager.create_collection(
                dialog.get_name(), dialog.get_folder())
        except (ValueError, RuntimeError, OSError) as e:
            QMessageBox.warning(self, '新建合集失败', str(e))
            return

        self.status_label.setText(f'已创建合集: {collection["name"]}')
        self.open_collection(collection['id'])

    def show_open_collection_dialog(self):
        """弹出合集列表，选择要打开的合集"""
        collections = self.collection_manager.list_collections()
        if not collections:
            QMessageBox.information(self, '提示', '还没有合集，请先新建合集')
            return

        dialog = OpenCollectionDialog(collections, self)
        if not dialog.exec():
            return

        collection_id = dialog.get_selected_id()
        if collection_id is not None:
            self.open_collection(collection_id)

    def open_collection(self, collection_id):
        """打开合集：切换数据库与缩略图目录，并加载合集根文件夹"""
        collection = self.collection_manager.get_collection(collection_id)
        if not collection:
            QMessageBox.warning(self, '打开合集失败', '合集不存在或已被删除')
            return

        folder = normalize_path(collection['folder_path'])
        if not os.path.isdir(folder):
            QMessageBox.warning(self, '打开合集失败', f'合集根文件夹不存在:\n{folder}')
            return

        # 先创建新合集数据库，失败时保持当前合集不变
        try:
            db = VideoDatabase(collection['db_path'])
        except (RuntimeError, OSError) as e:
            QMessageBox.warning(self, '打开合集失败', f'无法打开合集数据库:\n{e}')
            return

        # 关闭当前合集，避免两套数据库/缩略图缓存同时生效
        if self.collection is not None:
            self._close_current_collection()

        self.db = db
        self.collection = collection
        self.collection_manager.mark_opened(collection_id)
        thumbnail_cache.set_cache_dir(normalize_path(collection['thumbnail_dir']))

        self.folder_stack.clear()
        self.current_folder = folder
        self.setWindowTitle(f'VidExplorer - {collection["name"]}')

        # 合集包含根文件夹及其子文件夹中的所有视频，打开时一次性登记到合集数据库
        self.db.add_missing_videos(self.library.list_videos_recursive(folder))

        self._update_ui_state()
        self.load_videos(folder)

    def close_collection(self):
        """关闭合集：保存改动到数据库并回到初始界面"""
        if self.collection is None:
            return

        name = self.collection['name']
        self._close_current_collection()
        self.current_folder = ''
        self.video_paths = []
        self.video_tags_cache.clear()

        # 清空搜索框（blockSignals 避免触发搜索）
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)

        self.setWindowTitle('VidExplorer - 视频合集')
        self._update_ui_state()
        self.show_recent_collections()
        self.status_label.setText(f'已关闭合集: {name}')

    def _close_current_collection(self):
        """停止加载线程并关闭当前合集数据库（所有改动已在操作时提交）"""
        # 递增会话编号，令已排队的加载回调失效（避免关闭后仍写入数据库/界面）
        self._load_session += 1
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait()
        self.loader_thread = None

        if self.db is not None:
            self.db.close_connection()
            self.db = None

        self.collection = None
        self.folder_stack.clear()
        # 回到缓存的根目录，避免继续写入已关闭合集的缩略图子目录
        thumbnail_cache.set_cache_dir(DEFAULT_CACHE_DIR)

    def show_recent_collections(self):
        """初始界面：显示最近打开的 5 个合集"""
        recent = self.collection_manager.recent_collections(5)
        self.video_grid.set_collections(recent)

        total = len(self.collection_manager.list_collections())
        self.stats_label.setText(f'未打开合集  -  共{total}个合集')
        self.progress_bar.setVisible(False)

    def _update_ui_state(self):
        """根据是否已打开合集，同步按钮/菜单/搜索框的可用状态"""
        opened = self.collection is not None

        for widget in (self.refresh_btn, self.tag_manager_btn,
                       self.search_input, self.search_btn):
            widget.setEnabled(opened)
        self.close_collection_btn.setEnabled(opened)

        for action in (self.close_collection_action, self.clear_cache_action,
                       self.clean_missing_action, self.tag_manager_action):
            action.setEnabled(opened)

        self.update_up_button_state()

    def on_folder_opened(self, folder_path):
        """双击文件夹卡片，进入子文件夹"""
        self.folder_stack.append(self.current_folder)
        self.current_folder = folder_path
        self.update_up_button_state()
        self.load_videos(folder_path)

    def go_up(self):
        """返回上级文件夹"""
        if not self.folder_stack:
            return
        parent = self.folder_stack.pop()
        self.current_folder = parent
        self.update_up_button_state()
        self.load_videos(parent)

    def update_up_button_state(self):
        """根据导航栈更新返回上级按钮/菜单状态"""
        has_parent = self.collection is not None and bool(self.folder_stack)
        if hasattr(self, 'up_btn'):
            self.up_btn.setEnabled(has_parent)
        if hasattr(self, 'up_action'):
            self.up_action.setEnabled(has_parent)

    def refresh(self):
        """刷新当前文件夹"""
        if self.current_folder:
            self.load_videos(self.current_folder)
        else:
            QMessageBox.information(self, '提示', '请先打开一个合集')

    def on_video_clicked(self, video_path):
        """播放视频"""
        # 更新播放计数
        self.db.update_play_count(video_path)
        # 更新卡片播放次数显示
        video = self.db.get_video_by_path(video_path)
        if video:
            self.video_grid.update_card_play_count(video_path, video.get('play_count'))

        try:
            if platform.system() == 'Windows':
                os.startfile(video_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', video_path])
            else:  # Linux
                subprocess.run(['xdg-open', video_path])
        except Exception as e:
            QMessageBox.warning(self, '播放失败', str(e))

    def move_video(self, file_path):
        """移动视频：将视频移动到指定文件夹，并更新数据库中的视频信息"""
        old_name = os.path.basename(file_path)
        src_dir = normalize_path(os.path.dirname(file_path))

        target_dir = QFileDialog.getExistingDirectory(
            self, '选择目标文件夹', src_dir, QFileDialog.Option.ShowDirsOnly)
        if not target_dir:
            return  # 点击取消，不移动

        # 统一分隔符后再比较，避免 'H:/a' 与 'H:\a' 被当成不同文件夹
        target_dir = normalize_path(target_dir)

        # 目标文件夹与视频所在文件夹相同，无需移动
        if os.path.normcase(target_dir) == os.path.normcase(src_dir):
            QMessageBox.information(self, '提示', '目标文件夹与视频所在文件夹相同')
            return

        new_path = os.path.join(target_dir, old_name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, '移动失败', f'目标文件夹中已存在同名文件: {old_name}')
            return

        # 记录原文件修改时间，用于清理旧路径的缩略图缓存
        try:
            old_mtime = os.stat(file_path).st_mtime
        except OSError:
            old_mtime = None

        # shutil.move 支持跨盘符移动（同盘符时退化为重命名）
        try:
            shutil.move(file_path, new_path)
        except (OSError, shutil.Error) as e:
            QMessageBox.warning(self, '移动失败', f'无法移动文件:\n{e}')
            return

        # 清理旧路径的缩略图缓存
        if old_mtime is not None:
            thumbnail_cache.remove_cache(file_path, old_mtime)

        # 更新数据库中的路径
        self.db.update_video_path(file_path, new_path)

        # 更新内存缓存
        if file_path in self.video_tags_cache:
            self.video_tags_cache[new_path] = self.video_tags_cache.pop(file_path)

        self.status_label.setText(f'已移动: {old_name} -> {target_dir}')
        if self.current_folder:
            self.load_videos(self.current_folder)

    def rename_video(self, file_path):
        """重命名视频：更新磁盘上的文件名和数据库中的视频信息"""
        dialog = RenameDialog(file_path, self)
        if not dialog.exec():
            return  # 点击取消，不做任何修改

        new_name = dialog.get_new_name()
        old_name = os.path.basename(file_path)
        if new_name == old_name:
            return

        # 新文件名不能包含路径分隔符
        if os.sep in new_name or (os.altsep and os.altsep in new_name):
            QMessageBox.warning(self, '重命名失败', '文件名不能包含路径分隔符')
            return

        # 扩展名必须仍为支持的视频格式
        new_ext = os.path.splitext(new_name)[1].lower()
        if new_ext not in VideoLibrary.VIDEO_EXTENSIONS:
            QMessageBox.warning(
                self, '重命名失败',
                f'扩展名必须为支持的视频格式: {", ".join(sorted(VideoLibrary.VIDEO_EXTENSIONS))}')
            return

        new_path = os.path.join(os.path.dirname(file_path), new_name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, '重命名失败', f'目标文件已存在: {new_name}')
            return

        # 记录原文件修改时间，用于清理旧路径的缩略图缓存
        try:
            old_mtime = os.stat(file_path).st_mtime
        except OSError:
            old_mtime = None

        try:
            os.rename(file_path, new_path)
        except OSError as e:
            QMessageBox.warning(self, '重命名失败', f'无法重命名文件:\n{e}')
            return

        # 清理旧路径的缩略图缓存
        if old_mtime is not None:
            thumbnail_cache.remove_cache(file_path, old_mtime)

        # 更新数据库中的路径与标题
        self.db.update_video_path(file_path, new_path)

        # 更新内存缓存
        if file_path in self.video_tags_cache:
            self.video_tags_cache[new_path] = self.video_tags_cache.pop(file_path)

        self.status_label.setText(f'已重命名: {old_name} -> {new_name}')
        if self.current_folder:
            self.load_videos(self.current_folder)

    def delete_video(self, file_path):
        """删除视频：删除磁盘文件、数据库记录与标签信息"""
        box = QMessageBox(self)
        box.setWindowTitle('确认删除')
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText('确定要删除以下视频吗？\n此操作将永久删除磁盘上的文件、数据库记录及标签信息，且无法恢复。')
        box.setInformativeText(file_path)
        confirm_btn = box.addButton('确认', QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = box.addButton('取消', QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.exec()
        if box.clickedButton() is not confirm_btn:
            return  # 点击取消，不删除

        # 记录原文件修改时间，用于清理缩略图缓存
        try:
            old_mtime = os.stat(file_path).st_mtime
        except OSError:
            old_mtime = None

        # 删除磁盘文件
        try:
            os.remove(file_path)
        except OSError as e:
            QMessageBox.warning(self, '删除失败', f'无法删除文件:\n{e}')
            return

        # 清理缩略图缓存
        if old_mtime is not None:
            thumbnail_cache.remove_cache(file_path, old_mtime)

        # 删除数据库记录与标签关联
        self.db.delete_video(file_path)

        # 更新内存缓存
        self.video_tags_cache.pop(file_path, None)

        self.status_label.setText(f'已删除: {os.path.basename(file_path)}')
        if self.current_folder:
            self.load_videos(self.current_folder)

    def closeEvent(self, event):
        """窗口关闭时停止加载线程并关闭合集数据库"""
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait()
        self._close_current_collection()
        event.accept()

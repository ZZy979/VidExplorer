import os
import platform
import subprocess

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QStatusBar, QProgressBar, QMenu
)

from videxplorer.core.library import VideoLibrary
from videxplorer.core.loader import VideoLoaderThread
from videxplorer.models.database import VideoDatabase
from videxplorer.ui.batch_tag_dialog import BatchTagDialog
from videxplorer.ui.tag_dialog import TagDialog
from videxplorer.ui.tag_manager_dialog import TagManagerDialog
from videxplorer.ui.video_grid import VideoGrid
from videxplorer.utils.file import get_file_size, get_video_dimensions
from videxplorer.utils.thumbnail_cache import thumbnail_cache


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.library = VideoLibrary()
        self.db = VideoDatabase()
        self.current_folder = ''
        self.folder_stack = []  # 文件夹导航栈（用于返回上级）
        self.video_paths = []
        self.loader_thread = None
        self.current_selected_path = ''
        self.video_tags_cache = {}  # 缓存视频标签

        self.setWindowTitle('VidExplorer - 视频库')
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
        self.stats_label = QLabel("未打开文件夹")
        main_layout.addWidget(self.stats_label)

        # 视频网格
        self.video_grid = VideoGrid()
        self.video_grid.video_clicked.connect(self.on_video_clicked)
        self.video_grid.video_tag_clicked.connect(self.on_tag_clicked)
        self.video_grid.video_context_menu_requested.connect(self.show_video_context_menu)
        self.video_grid.folder_context_menu_requested.connect(self.show_folder_context_menu)
        self.video_grid.folder_opened.connect(self.on_folder_opened)
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

    def create_toolbar(self):
        """创建顶部工具栏"""
        toolbar = QWidget(self)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 打开文件夹按钮
        open_btn = QPushButton('📁打开文件夹')
        open_btn.clicked.connect(self.open_folder)
        layout.addWidget(open_btn)

        # 刷新按钮
        refresh_btn = QPushButton('🔄刷新')
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

        # 返回上级按钮
        self.up_btn = QPushButton('⬆返回上级')
        self.up_btn.setEnabled(False)
        self.up_btn.clicked.connect(self.go_up)
        layout.addWidget(self.up_btn)

        # 标签管理按钮
        self.tag_manager_btn = QPushButton("🏷️标签管理")
        self.tag_manager_btn.clicked.connect(self.open_tag_manager)
        layout.addWidget(self.tag_manager_btn)

        # 当前路径显示
        self.path_display = QLineEdit()
        self.path_display.setPlaceholderText('当前打开的文件夹路径...')
        self.path_display.setReadOnly(True)
        layout.addWidget(self.path_display, stretch=1)

        # 视频数量
        self.count_label = QLabel('0个视频', parent=self)
        layout.addWidget(self.count_label)

        return toolbar

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu('文件(&F)')
        open_action = file_menu.addAction('打开文件夹...')
        open_action.triggered.connect(self.open_folder)
        self.up_action = file_menu.addAction('返回上级')
        self.up_action.triggered.connect(self.go_up)
        self.up_action.setEnabled(False)
        file_menu.addSeparator()
        exit_action = file_menu.addAction('退出(&X)')
        exit_action.triggered.connect(self.close)

        # 工具菜单
        tools_menu = menubar.addMenu('工具(&T)')
        clear_cache_action = tools_menu.addAction('清空缩略图缓存')
        clear_cache_action.triggered.connect(self.clear_thumbnail_cache)
        tools_menu.addSeparator()
        tag_manager_action = tools_menu.addAction('标签管理')
        tag_manager_action.triggered.connect(self.open_tag_manager)

    def load_videos(self, folder):
        """加载当前文件夹中的子文件夹和视频（不递归）"""
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

        # 更新统计信息
        self.count_label.setText(f'{video_count}个视频')
        self.stats_label.setText(f'{folder}  -  {folder_count}个文件夹 / {video_count}个视频')

        # 加载视频标签
        self.load_video_tags(self.video_paths)

        # 显示文件夹和视频卡片
        self.video_grid.set_entries(folder_items, self.video_paths, self.video_tags_cache)

        if video_count == 0:
            self.status_label.setText('此文件夹下没有视频文件')
            self.progress_bar.setVisible(False)
            return

        self.status_label.setText(f'正在加载 {video_count} 个视频的缩略图...')

        # 启动后台加载线程
        self.loader_thread = VideoLoaderThread()
        self.loader_thread.set_videos(self.video_paths)
        self.loader_thread.video_loaded.connect(self.on_video_metadata_loaded)
        self.loader_thread.all_loaded.connect(self.on_all_videos_loaded)
        self.loader_thread.progress.connect(self.on_loading_progress)
        self.loader_thread.start()

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

    def on_video_metadata_loaded(self, file_path, metadata):
        """单个视频元数据加载完成"""
        # 更新对应卡片的时长显示
        self.video_grid.update_card_metadata(file_path, metadata)
        self.save_video_to_database(file_path, metadata)

    def on_all_videos_loaded(self):
        """所有视频加载完成"""
        self.status_label.setText(f'加载完成，共{len(self.video_paths)}个视频')
        self.progress_bar.setVisible(False)
        self.loader_thread = None

    def on_loading_progress(self, current, total):
        """更新进度"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f'加载缩略图{current}/{total}')

    def on_tag_clicked(self, tag):
        """点击标签 - 搜索该标签"""
        self.status_label.setText(f'搜索标签: {tag}')
        # TODO: 实现搜索功能

    def show_video_context_menu(self, file_path, pos):
        """显示视频右键菜单"""
        self.current_selected_path = file_path

        menu = QMenu(self)
        edit_tags_action = menu.addAction('编辑标签')
        edit_tags_action.triggered.connect(lambda: self.edit_video_tags(file_path))

        menu.addSeparator()
        play_action = menu.addAction('播放')
        play_action.triggered.connect(lambda: self.on_video_clicked(file_path))

        menu.exec(pos)

    def show_folder_context_menu(self, folder_path, pos):
        """显示文件夹右键菜单"""
        menu = QMenu(self)

        open_action = menu.addAction('打开')
        open_action.triggered.connect(lambda: self.on_folder_opened(folder_path))

        batch_action = menu.addAction('批量添加标签')
        batch_action.triggered.connect(lambda: self.batch_add_tags_to_folder(folder_path))

        menu.exec(pos)

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
        dialog = TagManagerDialog(self.db, self)
        dialog.exec()
        # 关闭后刷新当前视图，以更新卡片上的标签显示
        if self.current_folder:
            self.load_videos(self.current_folder)

    def clear_thumbnail_cache(self):
        """清空缩略图缓存"""
        reply = QMessageBox.question(
            self,
            '确认清空',
            '确定要清空所有缩略图缓存吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            thumbnail_cache.clear_cache()
            QMessageBox.information(self, '完成', '缩略图缓存已清空')
            # 刷新当前视图
            if self.current_folder:
                self.load_videos(self.current_folder)

    def open_folder(self):
        """打开文件夹选择对话框"""
        folder = QFileDialog.getExistingDirectory(
            self, '选择视频文件夹', self.current_folder, QFileDialog.Option.ShowDirsOnly)
        if folder:
            self.folder_stack.clear()
            self.current_folder = folder
            self.path_display.setText(folder)
            self.update_up_button_state()
            self.load_videos(folder)

    def on_folder_opened(self, folder_path):
        """双击文件夹卡片，进入子文件夹"""
        self.folder_stack.append(self.current_folder)
        self.current_folder = folder_path
        self.path_display.setText(folder_path)
        self.update_up_button_state()
        self.load_videos(folder_path)

    def go_up(self):
        """返回上级文件夹"""
        if not self.folder_stack:
            return
        parent = self.folder_stack.pop()
        self.current_folder = parent
        self.path_display.setText(parent)
        self.update_up_button_state()
        self.load_videos(parent)

    def update_up_button_state(self):
        """根据导航栈更新返回上级按钮/菜单状态"""
        has_parent = bool(self.folder_stack)
        if hasattr(self, 'up_btn'):
            self.up_btn.setEnabled(has_parent)
        if hasattr(self, 'up_action'):
            self.up_action.setEnabled(has_parent)

    def refresh(self):
        """刷新当前文件夹"""
        if self.current_folder:
            self.load_videos(self.current_folder)
        else:
            QMessageBox.information(self, '提示', '请先打开一个视频文件夹')

    def on_video_clicked(self, video_path):
        """播放视频"""
        # 更新播放计数
        self.db.update_play_count(video_path)

        try:
            if platform.system() == 'Windows':
                os.startfile(video_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', video_path])
            else:  # Linux
                subprocess.run(['xdg-open', video_path])
        except Exception as e:
            QMessageBox.warning(self, '播放失败', str(e))

    def closeEvent(self, event):
        """窗口关闭时停止加载线程"""
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait()
        event.accept()

import os
import platform
import subprocess

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QStatusBar, QProgressBar
)

from videxplorer.core.library import VideoLibrary
from videxplorer.core.loader import VideoLoaderThread
from videxplorer.ui.video_grid import VideoGrid
from videxplorer.utils.thumbnail_cache import thumbnail_cache


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.library = VideoLibrary()
        self.current_folder = ''
        self.video_paths = []
        self.loader_thread = None

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
        self.video_grid.video_clicked.connect(self.play_video)
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

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu('文件')

        clear_cache_action = file_menu.addAction('清空缩略图缓存')
        clear_cache_action.triggered.connect(self.clear_thumbnail_cache)

        exit_action = file_menu.addAction('退出')
        exit_action.triggered.connect(self.close)

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

        # 当前路径显示
        self.path_display = QLineEdit()
        self.path_display.setPlaceholderText('当前打开的文件夹路径...')
        self.path_display.setReadOnly(True)
        layout.addWidget(self.path_display, stretch=1)

        # 视频数量
        self.count_label = QLabel('0个视频', parent=self)
        layout.addWidget(self.count_label)

        return toolbar

    def open_folder(self):
        """打开文件夹选择对话框"""
        folder = QFileDialog.getExistingDirectory(
            self, '选择视频文件夹', self.current_folder, QFileDialog.Option.ShowDirsOnly)
        if folder:
            self.current_folder = folder
            self.path_display.setText(folder)
            self.load_videos(folder)

    def load_videos(self, folder):
        """加载文件夹中的视频"""
        # 停止之前的加载线程
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait()
            self.loader_thread = None

        # 清空当前显示
        self.video_grid.clear_cards()
        self.video_paths = []

        # 扫描文件（主线程快速完成）
        self.video_paths = self.library.scan_folder(folder)

        # 更新统计信息
        count = len(self.video_paths)
        self.count_label.setText(f'{count}个视频')
        self.stats_label.setText(f'{folder}  -  共{count}个视频')

        if count == 0:
            self.video_grid.show_empty()
            self.status_label.setText('未找到视频文件')
            return

        # 先显示所有卡片（缩略图占位）
        self.video_grid.set_videos_with_placeholder(self.video_paths)
        self.status_label.setText(f'正在加载 {count} 个视频的缩略图...')

        # 启动后台加载线程
        self.loader_thread = VideoLoaderThread()
        self.loader_thread.set_videos(self.video_paths)
        self.loader_thread.video_loaded.connect(self.on_video_metadata_loaded)
        self.loader_thread.all_loaded.connect(self.on_all_videos_loaded)
        self.loader_thread.progress.connect(self.on_loading_progress)
        self.loader_thread.start()

    def on_video_metadata_loaded(self, file_path, metadata):
        """单个视频元数据加载完成"""
        # 更新对应卡片的时长显示
        self.video_grid.update_card_metadata(file_path, metadata)

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

    def refresh(self):
        """刷新当前文件夹"""
        if self.current_folder:
            self.load_videos(self.current_folder)
        else:
            QMessageBox.information(self, '提示', '请先打开一个视频文件夹')

    def play_video(self, video_path):
        """播放视频"""
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

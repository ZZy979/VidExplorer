import os
import platform
import subprocess

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QLineEdit,
    QFileDialog, QMessageBox
)

from videxplorer.core.library import VideoLibrary
from videxplorer.ui.video_grid import VideoGrid


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.library = VideoLibrary()
        self.current_folder = ''

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

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        exit_action = file_menu.addAction("退出")
        exit_action.triggered.connect(self.close)

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
        videos = self.library.scan_folder(folder)
        self.video_grid.set_videos(videos)

        # 更新统计信息
        count = len(videos)
        self.count_label.setText(f'{count}个视频')
        self.stats_label.setText(f'{folder}  -  共{count}个视频')

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

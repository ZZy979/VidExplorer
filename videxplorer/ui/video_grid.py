from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QScrollArea, QWidget, QGridLayout, QLabel

from .video_card import VideoCard


class VideoGrid(QScrollArea):
    """视频网格视图"""
    video_clicked = Signal(str)  # 发送视频路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_cards = []

        # 容器
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        # 空状态标签
        self.empty_label = QLabel('请打开视频文件夹\n\n支持格式: mp4, avi, mkv, mov, wmv, flv, webm')
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 14px; padding: 100px 0;")
        self.grid_layout.addWidget(self.empty_label, 0, 0)

        self.setWidget(self.container)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def set_videos(self, video_paths):
        """设置视频列表"""
        self.clear_cards()

        if not video_paths:
            self.empty_label.show()
            return

        self.empty_label.hide()

        # 计算列数（根据宽度动态调整，这里固定4列）
        cols = 4
        for idx, path in enumerate(video_paths):
            row, col = divmod(idx, cols)
            card = VideoCard(path)
            card.clicked.connect(self.video_clicked.emit)
            self.grid_layout.addWidget(card, row, col)
            self.video_cards.append(card)


    def clear_cards(self):
        """清空所有卡片"""
        for card in self.video_cards:
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        self.video_cards.clear()

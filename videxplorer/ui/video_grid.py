from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QScrollArea, QWidget, QGridLayout, QLabel

from .video_card import VideoCard


class VideoGrid(QScrollArea):
    """视频网格视图"""
    video_clicked = Signal(str)  # 发送视频路径
    video_tag_clicked = Signal(str)
    video_context_menu_requested = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 视频路径到卡片的映射
        self.card_map = {}

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

        # 启用右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_videos_with_placeholder(self, video_paths, tags_cache=None):
        """设置视频列表（先显示占位）"""
        self.clear_cards()

        if not video_paths:
            self.show_empty()
            return

        self.empty_label.hide()

        # 计算列数（根据宽度动态调整，这里固定4列）
        cols = 4
        self.card_map.clear()
        tags_cache = tags_cache or {}

        for idx, path in enumerate(video_paths):
            row, col = divmod(idx, cols)
            card = VideoCard(path, load_immediately=False)
            card.clicked.connect(self.video_clicked.emit)
            card.tag_clicked.connect(self.video_tag_clicked.emit)

            # 设置标签
            if path in tags_cache:
                card.set_tags(tags_cache[path])

            self.grid_layout.addWidget(card, row, col)
            self.card_map[path] = card

    def update_card_metadata(self, file_path, metadata):
        """更新卡片的元数据（时长）"""
        if card := self.card_map.get(file_path):
            card.update_metadata(metadata)

    def update_card_tags(self, file_path, tags):
        """更新卡片的标签"""
        card = self.card_map.get(file_path)
        if card:
            card.set_tags(tags)

    def show_context_menu(self, pos):
        """显示右键菜单"""
        # 获取点击位置对应的卡片
        widget = self.childAt(pos)
        while widget:
            if isinstance(widget, VideoCard):
                # 转换坐标到全局
                global_pos = self.mapToGlobal(pos)
                self.video_context_menu_requested.emit(widget.file_path, global_pos)
                return
            widget = widget.parent()

    def show_empty(self):
        """显示空状态"""
        self.clear_cards()
        self.empty_label.show()

    def clear_cards(self):
        """清空所有卡片"""
        for card in self.card_map.values():
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        self.card_map.clear()

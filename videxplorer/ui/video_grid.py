from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QScrollArea, QWidget, QGridLayout, QLabel

from .folder_card import FolderCard
from .video_card import VideoCard


class VideoGrid(QScrollArea):
    """视频网格视图"""
    video_clicked = Signal(str)  # 发送视频路径
    video_tag_clicked = Signal(str)
    video_context_menu_requested = Signal(str, object)
    folder_context_menu_requested = Signal(str, object)  # 文件夹右键菜单
    folder_opened = Signal(str)  # 双击文件夹，发送文件夹路径

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

    def set_entries(self, folders, video_paths, tags_cache=None, play_count_cache=None):
        """设置网格内容：文件夹卡片 + 视频卡片

        folders: [(文件夹路径, 视频数量), ...]
        video_paths: [视频文件路径, ...]
        play_count_cache: {视频路径: 播放次数}
        """
        self.clear_cards()
        self.empty_label.hide()
        tags_cache = tags_cache or {}

        # 计算列数
        # TODO 根据宽度动态调整
        cols = 4
        idx = 0

        # 文件夹卡片
        for folder_path, video_count in folders:
            row, col = divmod(idx, cols)
            card = FolderCard(folder_path, video_count)
            card.folder_opened.connect(self.folder_opened.emit)
            self.grid_layout.addWidget(card, row, col)
            self.card_map[f'folder:{folder_path}'] = card
            idx += 1

        # 视频卡片
        for path in video_paths:
            row, col = divmod(idx, cols)
            card = VideoCard(path, load_immediately=False)
            card.clicked.connect(self.video_clicked.emit)
            card.tag_clicked.connect(self.video_tag_clicked.emit)

            # 设置标签
            if path in tags_cache:
                card.set_tags(tags_cache[path])

            # 设置播放次数
            if play_count_cache and path in play_count_cache:
                card.set_play_count(play_count_cache[path])

            self.grid_layout.addWidget(card, row, col)
            self.card_map[path] = card
            idx += 1

        # 空状态
        if idx == 0:
            self.empty_label.setText('此文件夹为空\n\n没有找到视频文件或子文件夹')
            self.empty_label.show()

    def set_videos_with_placeholder(self, video_paths, tags_cache=None):
        """兼容旧接口：仅显示视频（无文件夹卡片）"""
        self.set_entries([], video_paths, tags_cache)

    def update_card_metadata(self, file_path, metadata):
        """更新卡片的元数据（时长）"""
        if card := self.card_map.get(file_path):
            card.update_metadata(metadata)

    def update_card_tags(self, file_path, tags):
        """更新卡片的标签"""
        card = self.card_map.get(file_path)
        if card:
            card.set_tags(tags)

    def update_card_play_count(self, file_path, count):
        """更新卡片的播放次数"""
        card = self.card_map.get(file_path)
        if card:
            card.set_play_count(count)

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
            if isinstance(widget, FolderCard):
                global_pos = self.mapToGlobal(pos)
                self.folder_context_menu_requested.emit(widget.folder_path, global_pos)
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

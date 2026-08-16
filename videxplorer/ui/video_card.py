import datetime
import os

from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget

from videxplorer.ui.tag_manager_widget import TagDisplayWidget
from videxplorer.utils.file import get_file_name, get_file_size_readable
from videxplorer.utils.thumbnail_cache import thumbnail_cache


class VideoCard(QFrame):
    """视频卡片组件"""
    clicked = Signal(str)
    tag_clicked = Signal(str)  # 点击标签

    def __init__(self, file_path, load_immediately=True, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.metadata = None
        self.tags = []
        self.play_count = None

        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ccc;
                border-radius: 8px;
                background: white;
            }
            QFrame:hover {
                border-color: #999;
                background: #f5f5f5;
            }
        """)
        self.setFixedWidth(220)
        self.setMinimumHeight(200)
        self.setCursor(Qt.PointingHandCursor)

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 缩略图区域
        self.thumb_container = QWidget()
        self.thumb_container.setFixedHeight(150)
        self.thumb_container.setStyleSheet("""
            QWidget {
                background: #f0f0f0;
                border-radius: 8px 8px 0 0;
            }
        """)
        thumb_layout = QVBoxLayout(self.thumb_container)
        thumb_layout.setContentsMargins(0, 0, 0, 0)

        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("background: transparent; font-size: 48px;")
        thumb_layout.addWidget(self.thumb_label)

        # 加载指示器
        self.loading_label = QLabel('⏳')
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("background: transparent; font-size: 32px;")
        thumb_layout.addWidget(self.loading_label)
        # 让 loading_label 覆盖在 thumb_label 上面（通过堆叠顺序）
        self.loading_label.raise_()

        # 时长标签（覆盖在缩略图右下角，与缩略图重叠）
        self.duration_label = QLabel(self.thumb_container)
        self.duration_label.setStyleSheet("""
            QLabel {
                color: white;
                background: rgba(0, 0, 0, 0.7);
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.duration_label.hide()

        layout.addWidget(self.thumb_container)

        # 信息区域
        info_widget = QWidget(self)
        info_widget.setStyleSheet('background: transparent;')
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(10, 8, 10, 8)
        info_layout.setSpacing(4)

        # 文件名
        name = get_file_name(file_path)
        name_label = QLabel(name)
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(40)
        font = name_label.font()
        font.setPointSize(10)
        name_label.setFont(font)
        info_layout.addWidget(name_label)

        # 元信息行：日期、大小、播放次数（同一行显示）
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        try:
            mtime = os.path.getmtime(file_path)
            date_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
        except OSError:
            date_str = ''

        date_label = QLabel(date_str)
        size_label = QLabel(get_file_size_readable(file_path))
        self.play_label = QLabel()
        for lbl in (date_label, size_label, self.play_label):
            lbl.setStyleSheet("font-size: 11px; color: #666;")

        meta_row.addWidget(date_label)
        meta_row.addWidget(size_label)
        meta_row.addStretch()
        meta_row.addWidget(self.play_label)
        info_layout.addLayout(meta_row)

        # 标签显示区域（过多时自动换行）
        self.tag_display = TagDisplayWidget()
        self.tag_display.tag_clicked.connect(self.tag_clicked.emit)
        info_layout.addWidget(self.tag_display)

        layout.addWidget(info_widget)

        # 如果立即加载，则加载缩略图
        if load_immediately:
            QTimer.singleShot(10, self.load_thumbnail)

    def set_tags(self, tags):
        """设置标签"""
        self.tags = tags
        self.tag_display.set_tags(tags)

    def set_play_count(self, count):
        """设置播放次数"""
        self.play_count = count
        if count is not None:
            self.play_label.setText(f'▶{count}')
        else:
            self.play_label.setText('')

    def update_metadata(self, metadata):
        """更新元数据（从后台线程接收）"""
        self.metadata = metadata
        if metadata.duration:
            self._set_duration(metadata.duration_str)

        if not self.thumb_label.pixmap():
            QTimer.singleShot(10, self.load_thumbnail)

    def _set_duration(self, duration_str):
        """设置时长并定位到缩略图右下角（与缩略图重叠）"""
        self.duration_label.setText(duration_str)
        self.duration_label.adjustSize()
        x = self.thumb_container.width() - self.duration_label.width() - 8
        y = self.thumb_container.height() - self.duration_label.height() - 8
        self.duration_label.move(max(0, x), max(0, y))
        self.duration_label.show()

    def resizeEvent(self, event):
        """卡片尺寸变化时，保持时长标签在缩略图右下角"""
        super().resizeEvent(event)
        if self.duration_label and self.duration_label.text():
            self.duration_label.adjustSize()
            x = self.thumb_container.width() - self.duration_label.width() - 8
            y = self.thumb_container.height() - self.duration_label.height() - 8
            self.duration_label.move(max(0, x), max(0, y))

    def load_thumbnail(self):
        """加载缩略图"""
        self.loading_label.setText('⏳')
        self.loading_label.show()

        # 从缓存获取缩略图
        thumb = thumbnail_cache.get_or_create(self.file_path, width=220, height=150)
        self.loading_label.hide()

        if thumb:
            # 缩放并居中裁剪到 220x150
            pixmap = thumb.scaled(
                220, 150,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            # 居中裁剪
            if pixmap.width() > 220 or pixmap.height() > 150:
                x = (pixmap.width() - 220) // 2
                y = (pixmap.height() - 150) // 2
                pixmap = pixmap.copy(x, y, 220, 150)
            self.thumb_label.setPixmap(pixmap)
            self.thumb_label.setStyleSheet("background: transparent; font-size: 48px;")
        else:
            # 显示默认图标
            self.thumb_label.setText("🎬")
            self.thumb_label.setStyleSheet("background: transparent; font-size: 48px;")

        # 如果有元数据，更新时长
        if self.metadata and self.metadata.duration:
            self._set_duration(self.metadata.duration_str)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.file_path)

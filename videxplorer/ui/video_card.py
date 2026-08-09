from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget

from videxplorer.utils.file import get_file_name, get_file_size
from videxplorer.utils.thumbnail_cache import thumbnail_cache


class VideoCard(QFrame):
    """视频卡片组件"""
    clicked = Signal(str)

    def __init__(self, file_path, load_immediately=True, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.metadata = None

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
        self.setFixedSize(220, 240)
        self.setCursor(Qt.PointingHandCursor)

        # 布局
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

        # 时长标签（覆盖在缩略图右下角）
        self.duration_label = QLabel()
        self.duration_label.setAlignment(Qt.AlignBottom | Qt.AlignRight)
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
        self.duration_label.setFixedHeight(24)
        thumb_layout.addWidget(self.duration_label)

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

        # 文件大小
        size_str = get_file_size(file_path)
        size_label = QLabel(size_str)
        size_label.setStyleSheet('color: #666; font-size: 11px;')
        info_layout.addWidget(size_label)

        layout.addWidget(info_widget)

        # 如果立即加载，则加载缩略图
        if load_immediately:
            QTimer.singleShot(10, self.load_thumbnail)

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
            self.duration_label.setText(self.metadata.duration_str)

    def update_metadata(self, metadata):
        """更新元数据（从后台线程接收）"""
        self.metadata = metadata
        if metadata.duration:
            self.duration_label.setText(metadata.duration_str)

        # 如果缩略图还没加载，现在加载
        if not self.thumb_label.pixmap():
            QTimer.singleShot(10, self.load_thumbnail)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.file_path)

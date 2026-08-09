from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget

from videxplorer.utils.file import *


class VideoCard(QFrame):
    """视频卡片组件"""
    clicked = Signal(str)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path

        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                background: #16213e;
                border-radius: 10px;
                border: 2px solid transparent;
            }
            QFrame:hover {
                border-color: #e94560;
                background: #1a2744;
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
                background: #0f1a30;
                border-radius: 10px 10px 0 0;
            }
        """)
        thumb_layout = QVBoxLayout(self.thumb_container)
        thumb_layout.setContentsMargins(0, 0, 0, 0)

        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("background: transparent; font-size: 48px;")
        thumb_layout.addWidget(self.thumb_label)

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
        name_label.setStyleSheet('color: #eee; font-weight: bold;')
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(40)
        font = name_label.font()
        font.setPointSize(10)
        name_label.setFont(font)
        info_layout.addWidget(name_label)

        # 文件大小
        size_str = get_file_size(file_path)
        size_label = QLabel(size_str)
        size_label.setStyleSheet('color: #888; font-size: 11px;')
        info_layout.addWidget(size_label)

        layout.addWidget(info_widget)

        # 异步加载缩略图和时长
        QTimer.singleShot(10, self.load_metadata)

    def load_metadata(self):
        """加载缩略图和时长"""
        # 加载缩略图
        thumb = get_thumbnail(self.file_path)
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

        # 加载时长
        duration = get_video_duration(self.file_path)
        if duration:
            self.duration_label.setText(format_duration(duration))
        else:
            self.duration_label.setText("")

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.file_path)

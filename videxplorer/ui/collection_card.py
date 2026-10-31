"""合集卡片组件（初始界面用于快速打开最近合集）"""
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget


class CollectionCard(QFrame):
    """合集卡片，双击打开该合集"""

    opened = Signal(int)  # 发送合集 ID

    def __init__(self, collection, parent=None):
        super().__init__(parent)
        self.collection_id = collection['id']
        self.collection_name = collection['name']
        self.folder_path = collection['folder_path']

        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #b8cde0;
                border-radius: 8px;
                background: #f3f8fd;
            }
            QFrame:hover {
                border-color: #4a8bc2;
                background: #e6f1fa;
            }
        """)
        self.setFixedSize(220, 280)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 图标区域
        icon_container = QWidget()
        icon_container.setFixedHeight(150)
        icon_container.setStyleSheet("""
            QWidget {
                background: #dcebf8;
                border-radius: 8px 8px 0 0;
            }
        """)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel('📚')
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet('background: transparent; font-size: 56px;')
        icon_layout.addWidget(icon_label)

        layout.addWidget(icon_container)

        # 信息区域
        info_widget = QWidget(self)
        info_widget.setStyleSheet('background: transparent;')
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(10, 8, 10, 8)
        info_layout.setSpacing(4)

        name_label = QLabel(self.collection_name)
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(40)
        font = name_label.font()
        font.setPointSize(10)
        font.setBold(True)
        name_label.setFont(font)
        info_layout.addWidget(name_label)

        path_label = QLabel(self._elided(self.folder_path))
        path_label.setToolTip(self.folder_path)
        path_label.setStyleSheet('font-size: 11px; color: #999;')
        info_layout.addWidget(path_label)

        hint_label = QLabel('双击打开')
        hint_label.setStyleSheet('font-size: 11px; color: #bbb;')
        info_layout.addWidget(hint_label)

        layout.addWidget(info_widget)
        layout.addStretch()

    def _elided(self, text):
        """按卡片宽度截断过长的文件夹路径"""
        metrics = QFontMetrics(self.font())
        return metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, 190)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if event.button() == Qt.LeftButton:
            self.opened.emit(self.collection_id)

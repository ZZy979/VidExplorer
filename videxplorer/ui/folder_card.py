import os

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget


class FolderCard(QFrame):
    """文件夹卡片组件，双击打开子文件夹"""

    folder_opened = Signal(str)  # 发送文件夹路径

    def __init__(self, folder_path, video_count=0, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path

        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ccc;
                border-radius: 8px;
                background: #fdfae8;
            }
            QFrame:hover {
                border-color: #d0a63c;
                background: #f8f0cf;
            }
        """)
        self.setFixedSize(220, 280)
        self.setCursor(Qt.PointingHandCursor)

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 图标区域
        icon_container = QWidget()
        icon_container.setFixedHeight(150)
        icon_container.setStyleSheet("""
            QWidget {
                background: #f7ecbd;
                border-radius: 8px 8px 0 0;
            }
        """)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel('📁')
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("background: transparent; font-size: 56px;")
        icon_layout.addWidget(icon_label)

        layout.addWidget(icon_container)

        # 信息区域
        info_widget = QWidget(self)
        info_widget.setStyleSheet('background: transparent;')
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(10, 8, 10, 8)
        info_layout.setSpacing(4)

        # 文件夹名
        name = os.path.basename(folder_path.rstrip('/\\'))
        name_label = QLabel(name)
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(40)
        font = name_label.font()
        font.setPointSize(10)
        font.setBold(True)
        name_label.setFont(font)
        info_layout.addWidget(name_label)

        # 视频数量
        count_label = QLabel(f'{video_count} 个视频')
        count_label.setStyleSheet("font-size: 11px; color: #999;")
        info_layout.addWidget(count_label)

        # 提示
        hint_label = QLabel('双击进入')
        hint_label.setStyleSheet("font-size: 11px; color: #bbb;")
        info_layout.addWidget(hint_label)

        layout.addWidget(info_widget)
        layout.addStretch()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if event.button() == Qt.LeftButton:
            self.folder_opened.emit(self.folder_path)

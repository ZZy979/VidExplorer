"""标签管理组件（显示视频的标签）"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from videxplorer.ui.flow_layout import FlowLayout


class TagDisplayWidget(QWidget):
    """标签显示组件"""

    tag_clicked = Signal(str)  # 点击标签信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tags = []
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        # 使用自动换行布局，标签过多时换行显示
        self.layout = FlowLayout(self.container, margin=0, spacing=5)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

    def set_tags(self, tags):
        """设置标签列表"""
        self.tags = tags[:]
        self.update_display()

    def update_display(self):
        """更新显示"""
        # 清空现有标签按钮
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        # 添加标签按钮
        for tag in sorted(self.tags):
            btn = QPushButton(tag)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #e3f2fd;
                    border: 1px solid #90caf9;
                    border-radius: 12px;
                    padding: 2px 12px;
                    font-size: 11px;
                    color: #1565c0;
                }}
                QPushButton:hover {{
                    background: #bbdefb;
                }}
            """)
            btn.clicked.connect(lambda checked, t=tag: self.tag_clicked.emit(t))
            self.layout.addWidget(btn)

    def add_tag(self, tag):
        """添加标签"""
        if tag not in self.tags:
            self.tags.append(tag)
            self.update_display()

    def remove_tag(self, tag):
        """移除标签"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.update_display()

    def get_tags(self):
        """获取当前标签列表"""
        return self.tags[:]

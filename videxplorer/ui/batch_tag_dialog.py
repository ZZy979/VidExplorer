"""批量添加标签对话框"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCompleter
)


class BatchTagDialog(QDialog):
    """批量添加标签对话框"""

    def __init__(self, folder_path, video_count, all_tags, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.video_count = video_count

        self.setWindowTitle('批量添加标签')
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f'文件夹：{folder_path}'))
        layout.addWidget(QLabel(
            f'将向 {video_count} 个视频添加以下标签（不影响已有标签）：'))

        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText('多个标签用逗号分隔，例如：电影, 动作, 收藏')
        self.tag_input.setFocus()

        completer = QCompleter(all_tags)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.tag_input.setCompleter(completer)
        self.tag_input.returnPressed.connect(self.accept)

        layout.addWidget(self.tag_input)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton('确定')
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def get_tags(self):
        """解析输入的标签列表"""
        raw = self.tag_input.text()
        tags = []
        for part in raw.replace('、', ',').replace('，', ',').split(','):
            tag = part.strip()
            if tag and tag not in tags:
                tags.append(tag)
        return tags

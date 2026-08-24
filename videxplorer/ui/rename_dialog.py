"""视频重命名对话框"""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel
)


class RenameDialog(QDialog):
    """输入新文件名（含扩展名）的对话框。

    点击「确认」接受（新文件名非空时），点击「取消」拒绝。
    """

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle('重命名视频')
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel('当前文件：'))
        self.old_path_label = QLabel(file_path)
        self.old_path_label.setWordWrap(True)
        self.old_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.old_path_label)

        layout.addWidget(QLabel('新文件名：'))
        self.name_input = QLineEdit()
        self.name_input.setText(os.path.basename(file_path))
        self.name_input.selectAll()
        self.name_input.setPlaceholderText('输入新文件名（含扩展名）')
        self.name_input.returnPressed.connect(self._on_confirm)
        layout.addWidget(self.name_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.confirm_btn = QPushButton('确认')
        self.confirm_btn.setDefault(True)
        self.confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)

        self.name_input.setFocus()

    def _on_confirm(self):
        """确认：新文件名非空时才接受"""
        if self.name_input.text().strip():
            self.accept()

    def get_new_name(self):
        """返回输入的新文件名（含扩展名）"""
        return self.name_input.text().strip()

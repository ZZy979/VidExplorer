"""重命名对话框（视频或文件夹）"""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel
)


class RenameDialog(QDialog):
    """输入新名称的对话框（默认用于重命名视频文件）。

    通过 title/path_label/name_label/placeholder 可复用于文件夹等场景。
    点击「确认」接受（新名称非空时），点击「取消」拒绝。
    """

    def __init__(self, file_path, parent=None, title='重命名视频',
                 path_label='当前文件：', name_label='新文件名：',
                 placeholder='输入新文件名（含扩展名）'):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel(path_label))
        self.old_path_label = QLabel(file_path)
        self.old_path_label.setWordWrap(True)
        self.old_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.old_path_label)

        layout.addWidget(QLabel(name_label))
        self.name_input = QLineEdit()
        self.name_input.setText(os.path.basename(file_path))
        self.name_input.selectAll()
        self.name_input.setPlaceholderText(placeholder)
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
        """确认：新名称非空时才接受"""
        if self.name_input.text().strip():
            self.accept()

    def get_new_name(self):
        """返回输入的新名称（视频场景下含扩展名）"""
        return self.name_input.text().strip()

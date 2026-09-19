"""清理已失效文件确认对话框"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget
)


class CleanMissingDialog(QDialog):
    """列出所有待清理文件的完整路径，供用户确认。

    点击「确认」接受，点击「取消」拒绝。
    """

    def __init__(self, missing_paths, parent=None):
        super().__init__(parent)
        self.missing_paths = list(missing_paths)

        self.setWindowTitle('清理已失效文件')
        self.setMinimumSize(720, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel(
            f'以下 {len(self.missing_paths)} 个文件在磁盘上已不存在，'
            '将从数据库中删除其视频信息和标签信息：'))

        self.path_list = QListWidget()
        self.path_list.addItems(self.missing_paths)
        self.path_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 4px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
                color: #000000;
            }
        """)
        layout.addWidget(self.path_list, stretch=1)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.confirm_btn = QPushButton('确认')
        self.confirm_btn.setDefault(True)
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_btn)

        self.cancel_btn = QPushButton('取消')
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        self.path_list.setFocus()

    def get_paths(self):
        """返回待清理的文件路径列表"""
        return self.missing_paths[:]

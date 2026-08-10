"""标签管理器对话框：查看所有标签、重命名、删除"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QInputDialog
)


class TagManagerDialog(QDialog):
    """标签管理器"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.tags = []  # 当前标签列表：[{id, name, video_count, ...}, ...]

        self.setWindowTitle('标签管理')
        self.setMinimumSize(420, 480)

        # 主布局
        layout = QVBoxLayout(self)

        # 提示
        hint = QLabel('双击标签可快速重命名')
        hint.setStyleSheet('color: #888; font-size: 12px;')
        layout.addWidget(hint)

        # 标签列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
                color: #000000;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self.rename_selected)
        layout.addWidget(self.list_widget, stretch=1)

        # 按钮区
        btn_layout = QHBoxLayout()

        self.rename_btn = QPushButton('✏️重命名')
        self.rename_btn.clicked.connect(self.rename_selected)
        btn_layout.addWidget(self.rename_btn)

        self.delete_btn = QPushButton('🗑️删除')
        self.delete_btn.clicked.connect(self.delete_selected)
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self.refresh()

    def refresh(self):
        """重新加载所有标签"""
        self.list_widget.clear()
        self.tags = self.db.get_all_tags()

        if not self.tags:
            empty_item = QListWidgetItem('（暂无标签）')
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            empty_item.setTextAlignment(Qt.AlignCenter)
            self.list_widget.addItem(empty_item)
            return

        for tag in self.tags:
            text = f"{tag['name']}　（{tag.get('video_count', 0)} 个视频）"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.list_widget.addItem(item)

    def current_tag(self):
        """获取当前选中的标签 dict"""
        item = self.list_widget.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def rename_selected(self):
        """重命名选中的标签"""
        tag = self.current_tag()
        if tag is None:
            QMessageBox.information(self, '提示', '请先选择一个标签')
            return

        new_name, ok = QInputDialog.getText(
            self, '重命名标签', '新名称：', text=tag['name'])
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()

        if new_name == tag['name']:
            return

        if self.db.rename_tag(tag['id'], new_name):
            self.refresh()
        else:
            QMessageBox.warning(self, '重命名失败', '重命名失败，可能存在同名标签')

    def delete_selected(self):
        """删除选中的标签"""
        tag = self.current_tag()
        if tag is None:
            QMessageBox.information(self, '提示', '请先选择一个标签')
            return

        reply = QMessageBox.question(
            self,
            '确认删除',
            f'确定要删除标签「{tag["name"]}」吗？\n'
            f'该标签将从 {tag.get("video_count", 0)} 个视频中移除。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.db.delete_tag(tag['id']):
            self.refresh()
        else:
            QMessageBox.warning(self, '删除失败', '删除标签失败')

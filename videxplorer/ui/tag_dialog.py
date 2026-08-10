"""标签编辑对话框"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QLabel,
    QMessageBox, QCompleter
)

class TagDialog(QDialog):
    """视频标签编辑对话框"""

    tags_changed = Signal(list)  # 标签列表变化

    def __init__(self, video_path, current_tags, all_tags, db, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.current_tags = current_tags[:]
        self.all_tags = all_tags[:]
        self.db = db

        self.setWindowTitle('编辑标签')
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        # 主布局
        layout = QVBoxLayout(self)

        # 当前标签显示
        layout.addWidget(QLabel('当前标签：'))
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.tag_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
                min-height: 100px;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
        """)
        self.refresh_tag_list()
        layout.addWidget(self.tag_list)

        # 标签操作按钮
        tag_btn_layout = QHBoxLayout()

        self.remove_btn = QPushButton('移除选中标签')
        self.remove_btn.clicked.connect(self.remove_selected_tag)
        tag_btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton('清空所有标签')
        self.clear_btn.clicked.connect(self.clear_tags)
        tag_btn_layout.addWidget(self.clear_btn)

        tag_btn_layout.addStretch()
        layout.addLayout(tag_btn_layout)

        # 添加标签区域
        layout.addWidget(QLabel('添加标签：'))
        add_layout = QHBoxLayout()

        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText('输入标签名称，按回车添加')
        self.tag_input.returnPressed.connect(self.add_tag)

        # 自动补全
        self.completer = QCompleter(self.all_tags)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.tag_input.setCompleter(self.completer)

        add_layout.addWidget(self.tag_input, stretch=1)

        self.add_btn = QPushButton('添加')
        self.add_btn.clicked.connect(self.add_tag)
        add_layout.addWidget(self.add_btn)

        layout.addLayout(add_layout)

        # 分隔线
        layout.addWidget(QLabel('─' * 40))

        # 所有标签列表
        layout.addWidget(QLabel('所有标签（双击添加）：'))
        self.all_tags_list = QListWidget()
        self.all_tags_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
                min-height: 100px;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 3px;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
        """)
        self.all_tags_list.itemDoubleClicked.connect(self.add_tag_from_list)
        self.refresh_all_tags_list()
        layout.addWidget(self.all_tags_list)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.ok_btn = QPushButton('确定')
        self.ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton('取消')
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def refresh_tag_list(self):
        """刷新当前标签列表"""
        self.tag_list.clear()
        for tag in sorted(self.current_tags):
            item = QListWidgetItem(tag)
            # 显示颜色标识
            color = self.get_tag_color(tag)
            item.setBackground(QColor(color).lighter(180))
            self.tag_list.addItem(item)

    def refresh_all_tags_list(self):
        """刷新所有标签列表"""
        self.all_tags_list.clear()
        for tag in sorted(self.all_tags):
            if tag not in self.current_tags:  # 只显示未添加的标签
                item = QListWidgetItem(tag)
                color = self.get_tag_color(tag)
                item.setBackground(QColor(color).lighter(180))
                self.all_tags_list.addItem(item)

    def get_tag_color(self, tag_name):
        """获取标签颜色"""
        for tag in self.db.get_all_tags():
            if tag['name'] == tag_name:
                return tag['color']
        return '#666666'

    def add_tag(self):
        """添加标签"""
        tag = self.tag_input.text().strip()
        if not tag:
            return

        if tag in self.current_tags:
            QMessageBox.information(self, '提示', f'标签 "{tag}" 已存在')
            self.tag_input.clear()
            return

        self.current_tags.append(tag)
        self.tag_input.clear()
        self.refresh_tag_list()
        self.refresh_all_tags_list()
        self.tags_changed.emit(self.current_tags)

    def add_tag_from_list(self, item):
        """从所有标签列表双击添加"""
        tag = item.text()
        if tag not in self.current_tags:
            self.current_tags.append(tag)
            self.refresh_tag_list()
            self.refresh_all_tags_list()
            self.tags_changed.emit(self.current_tags)

    def remove_selected_tag(self):
        """移除选中的标签"""
        current_row = self.tag_list.currentRow()
        if current_row < 0:
            QMessageBox.information(self, '提示', '请先选择一个标签')
            return

        tag = self.tag_list.item(current_row).text()
        self.current_tags.remove(tag)
        self.refresh_tag_list()
        self.refresh_all_tags_list()
        self.tags_changed.emit(self.current_tags)

    def clear_tags(self):
        """清空所有标签"""
        if not self.current_tags:
            return

        reply = QMessageBox.question(
            self,
            '确认清空',
            '确定要清空所有标签吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.current_tags.clear()
            self.refresh_tag_list()
            self.refresh_all_tags_list()
            self.tags_changed.emit(self.current_tags)

    def get_tags(self):
        """获取当前标签列表"""
        return self.current_tags[:]

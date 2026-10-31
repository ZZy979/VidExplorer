"""合集相关对话框：新建合集、打开合集"""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QFileDialog, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox
)

from videxplorer.utils.path import normalize_path


class CreateCollectionDialog(QDialog):
    """新建合集：输入合集名称并选择根文件夹"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('新建合集')
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('例如：Film、Short video')
        form.addRow('合集名称：', self.name_input)

        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText('选择合集根文件夹')
        folder_row.addWidget(self.folder_input)
        browse_btn = QPushButton('浏览...')
        browse_btn.clicked.connect(self._choose_folder)
        folder_row.addWidget(browse_btn)
        form.addRow('根文件夹：', folder_row)

        layout.addLayout(form)

        hint = QLabel('合集包含该文件夹及其所有子文件夹中的视频。')
        hint.setStyleSheet('color: #888;')
        layout.addWidget(hint)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton('确认')
        confirm_btn.setDefault(True)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

        self.name_input.setFocus()

    def _choose_folder(self):
        """选择合集根文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self, '选择合集根文件夹', self.folder_input.text(),
            QFileDialog.Option.ShowDirsOnly)
        if folder:
            self.folder_input.setText(normalize_path(folder))

    def _on_confirm(self):
        """确认：名称非空且根文件夹有效时才接受"""
        if not self.name_input.text().strip():
            QMessageBox.warning(self, '提示', '请输入合集名称')
            self.name_input.setFocus()
            return
        folder = normalize_path(self.folder_input.text().strip())
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, '提示', '请选择有效的根文件夹')
            return
        self.accept()

    def get_name(self):
        """返回输入的合集名称"""
        return self.name_input.text().strip()

    def get_folder(self):
        """返回选择的根文件夹"""
        return normalize_path(self.folder_input.text().strip())


class OpenCollectionDialog(QDialog):
    """打开合集：列出所有合集的名称与根文件夹"""

    def __init__(self, collections, parent=None):
        super().__init__(parent)
        self.setWindowTitle('打开合集')
        self.setMinimumSize(620, 360)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        hint = QLabel('选择要打开的合集（也可双击列表项）：')
        layout.addWidget(hint)

        self.table = QTableWidget(len(collections), 2, self)
        self.table.setHorizontalHeaderLabels(['合集名称', '根文件夹'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        for row, collection in enumerate(collections):
            name_item = QTableWidgetItem(collection['name'])
            name_item.setData(Qt.ItemDataRole.UserRole, collection['id'])
            path_item = QTableWidgetItem(collection['folder_path'])
            path_item.setToolTip(collection['folder_path'])
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, path_item)

        if collections:
            self.table.selectRow(0)
        self.table.doubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self.table, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        open_btn = QPushButton('打开')
        open_btn.setDefault(True)
        open_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(open_btn)

        layout.addLayout(btn_layout)

    def _on_double_clicked(self, index):
        """双击列表项直接打开"""
        if index.isValid():
            self.accept()

    def _on_confirm(self):
        """确认：选中了合集才接受"""
        if self.get_selected_id() is None:
            QMessageBox.information(self, '提示', '请先选择一个合集')
            return
        self.accept()

    def get_selected_id(self):
        """返回选中合集的 ID（未选中时返回 None）"""
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

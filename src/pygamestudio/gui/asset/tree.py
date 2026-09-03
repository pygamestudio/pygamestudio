import os
import shutil
import platform
import subprocess
from pathlib import Path
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.asset.type import *
from pygamestudio.gui.asset.model import *
from pygamestudio.gui.asset.menu import ContextMenu
from pygamestudio.gui.asset.delegate import AssetTreeWidgetDelegate
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.config import get_project_config, update_project_config
from pygamestudio.common.utils.system import send_to_trash
from pygamestudio.common.utils.path import RES_PATH


# File suffixes the built-in code editor can open as plain text.
TEXT_FILE_EXTENSIONS = {
    '.py', '.txt', '.json', '.md', '.pygs', '.qss', '.qrc', '.cfg', '.ini',
    '.toml', '.yaml', '.yml', '.log', '.html', '.css', '.js', '.ts', '.csv', '.xml', '.scene'
}

# Raster image suffixes the built-in image editor can open.
IMAGE_FILE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tga', '.tif',
    '.tiff', '.xpm', '.ico', '.ppm', '.pgm', '.pbm', '.svg'
}


class AssetTreeView(QTreeView):
    edit_file_signal = Signal(str)
    image_edit_signal = Signal(str)

    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._proxy_model = AssetSortFilterProxyModel(self)
        self._file_model = AssetFileSystemModel(self)
        self._context_menu = ContextMenu('', self)
        self._delegate = AssetTreeWidgetDelegate(self, self._proxy_model, self._file_model, game_manager)

        self._root_path = ''
        self._is_cut = False
        self._expand_state = {}
        self._is_connected = False
        self._clipboard_content = []
        self._highlight_indexes_paths = []
        self._sort_type = SORT_BY_NAME_ASC

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_object_name()

    def _set_widget(self):
        self._file_model.setReadOnly(False)
        self._file_model.setRootPath(self._root_path)
        self._file_model.setFilter(QDir.Filter.Dirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)

        self._proxy_model.setFilterKeyColumn(0)
        self._proxy_model.setDynamicSortFilter(True)
        self._proxy_model.setSourceModel(self._file_model)
        self._proxy_model.setRecursiveFilteringEnabled(True)
        self._proxy_model.sort(0, Qt.SortOrder.AscendingOrder)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        self.setModel(self._proxy_model)
        self.setRootIndex(self._proxy_model.mapFromSource(self._file_model.index(self._root_path)))
        for i in range(1, self._file_model.columnCount()):
            self.hideColumn(i)
        
        self.setItemDelegate(self._delegate)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setHeaderHidden(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                
    def _set_signal(self):
        self.selectionModel().selectionChanged.connect(self._clear_highlight_items)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._context_menu.add_signal.connect(self._add)
        self._context_menu.cut_signal.connect(self._cut)
        self._context_menu.copy_signal.connect(self._copy)
        self._context_menu.paste_signal.connect(self._paste)
        self._context_menu.delete_signal.connect(self._delete)
        self._context_menu.rename_signal.connect(self._rename)
        self._context_menu.duplicate_signal.connect(self._duplicate)
        self._context_menu.copy_path_signal.connect(self._copy_path)
        self._context_menu.copy_name_signal.connect(self._copy_name)
        self._context_menu.open_in_terminal_signal.connect(self._open_in_terminal)
        self._context_menu.open_externally_signal.connect(self._open_externally)
        self._context_menu.show_in_explorer_signal.connect(self._show_in_explorer)
        self._context_menu.open_signal.connect(self._open_file)
        self._context_menu.run_signal.connect(self._run_project)
        self.doubleClicked.connect(self._on_double_clicked)

    def _set_object_name(self):
        self.setObjectName('assetTreeView')

    def _show_context_menu(self, pos):
        index = self.indexAt(pos)
        global_pos = self.mapToGlobal(pos)

        if not index.isValid():
            index_type = INDEX_INVALID
            file_path = ''
        elif self._file_model.isDir(self._proxy_model.mapToSource(index)):
            index_type = INDEX_FOLDER
            file_path = ''
        else:
            index_type = INDEX_FILE
            file_path = self._file_model.filePath(self._proxy_model.mapToSource(index))

        self._context_menu.show(global_pos, index_type, file_path)

    def _get_parent_index_for_creation(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return self.rootIndex()
        
        parent_index = selected_indexes[-1]
        
        if not self._file_model.isDir(self._proxy_model.mapToSource(parent_index)):
            parent_index = parent_index.parent()
        
        return parent_index
        
    def get_ready_for_project(self):
        self._root_path = self._game_manager.get_project_path()
        self._file_model.setRootPath(self._root_path)
        self._sort_type = get_project_config()['asset']['sort_type']
        self.setRootIndex(self._proxy_model.mapFromSource(self._file_model.index(self._root_path)))

    def clean_up(self):
        self._clear_highlight_items()
        self._is_cut = False
        self._expand_state = {}
        self._is_connected = False
        self._clipboard_content = []
        self._highlight_indexes_paths = []
        self._sort_type = SORT_BY_NAME_ASC
        self._root_path = ''
        self._file_model.setRootPath(self._root_path)
        self.setRootIndex(self._proxy_model.mapFromSource(self._file_model.index(self._root_path)))

    def add(self, index_type):
        return self._add(index_type)
    
    def _add(self, index_type):
        self._highlight_indexes_paths = []

        if index_type == INDEX_FOLDER:
            item_path = self._add_folder()
        else:
            item_path = self._add_file(index_type)

        QTimer.singleShot(20, lambda: self._select_and_scroll_to_new_item(item_path, on_selected=self._rename))

    def _add_folder(self):
        parent_index = self._get_parent_index_for_creation()
        self.setExpanded(parent_index, True)
        parent_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(parent_index)))

        # Make sure the added folder name does not exist in the current directory.
        new_folder_name = INDEX_FOLDER
        folder_path = self._get_unique_path(new_folder_name, parent_path)
        folder_path.mkdir()

        self._highlight_indexes_paths.append(folder_path)
        return folder_path

    def _add_file(self, index_type):
        """Create a new file of the given type inside the current folder.

        Scene files are written with an empty JSON document, script files are
        filled with the object script template, and any other file is created
        empty via touch(). The new path is remembered so it can be selected
        and renamed after the file system finishes loading.
        """
        parent_index = self._get_parent_index_for_creation()
        self.setExpanded(parent_index, True)
        parent_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(parent_index)))

        # Make sure the added file name does not exist in the current directory.
        new_file_name = index_type
        file_path = self._get_unique_path(new_file_name, parent_path)

        if index_type == INDEX_SCENE:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('{}')
        elif index_type == INDEX_SCRIPT:
            # Fill the new script file with the object script template.
            template_path = RES_PATH / 'templates/object_script_template.py'
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
        else:
            file_path.touch()

        self._highlight_indexes_paths.append(file_path)
        return file_path

    def _select_and_scroll_to_new_item(self, item_path, retry_count=0, on_selected=None):
        """Select, scroll to, and optionally rename a just-created file.

        The file system model may still be loading the new entry when this is
        called, so if the index is not valid yet we retry a few times (25 ms
        apart) instead of giving up immediately.
        """
        source_index = self._file_model.index(str(item_path))
        index = self._proxy_model.mapFromSource(source_index)

        if index.isValid():
            self.setCurrentIndex(index)
            self.scrollTo(index)
            if on_selected:
                on_selected()
        elif retry_count < 40:
            # The directory is still loading; try again shortly.
            QTimer.singleShot(25, lambda: self._select_and_scroll_to_new_item(item_path, retry_count + 1, on_selected))

    def _delete(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        
        def is_to_delete(index, selected_indexes):
            """
            Check if the index needs to be deleted (no ancestor in the selected indexes).
            E.g., if a file-type index has a folder-type ancestor index, we only need to delete the folder index as the file in the folder will be deleted together.
            """
            current = index
            while current.parent() and current.parent() != self.rootIndex():
                if current.parent() in selected_indexes:
                    return False
                current = current.parent()
            return True
        
        indexes_to_delete = [index for index in selected_indexes if is_to_delete(index, selected_indexes)]
        index_names = [index.data(Qt.ItemDataRole.DisplayRole) for index in indexes_to_delete]

        content = T.tr('message_box.question_delete_asset_item_content', 'Delete {} item(s)?\n{}').format(str(len(indexes_to_delete)), ('\n').join(index_names))
        reply = QMessageBox.question(QApplication.activeWindow(), T.tr('message_box.question_title', 'Confirm'), content, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.No:
            return
        
        for index in indexes_to_delete:
            index_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(index)))
            if index_path.exists():
                # Move to the system recycle bin instead of deleting permanently.
                send_to_trash(index_path)

    def _cut(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
                
        self._is_cut = True
        self._clipboard_content = []
        QApplication.clipboard().clear()

        for index in selected_indexes:
            self._clipboard_content.append(Path(self._file_model.filePath(self._proxy_model.mapToSource(index))))
        
        # To show transparent effet when keys Ctrl+X are pressed.
        self.viewport().update()

    def _copy(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        
        self._is_cut = False
        self._clipboard_content = []
        QApplication.clipboard().clear()
            
        for index in selected_indexes:
            self._clipboard_content.append(Path(self._file_model.filePath(self._proxy_model.mapToSource(index))))

        # To remove transparent effet.
        self.viewport().update()

    def _paste(self):
        if not self._clipboard_content:
            return
        
        if not self._is_cut:
            self._paste_for_copy()
        else:
            self._paste_for_cut()

    def _paste_for_copy(self):
        self._highlight_indexes_paths = []

        parent_index = self._get_parent_index_for_creation()
        parent_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(parent_index)))
        self.setExpanded(parent_index, True)

        for source_path in self._clipboard_content:
            target_path = self._get_unique_path(source_path.name, parent_path)
            shutil.copytree(source_path, target_path) if source_path.is_dir() else shutil.copy2(source_path, target_path)
            self._highlight_indexes_paths.append(target_path)

    def _paste_for_cut(self):
        self._highlight_indexes_paths = []

        parent_index = self._get_parent_index_for_creation()
        parent_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(parent_index)))
        self.setExpanded(parent_index, True)
        self._is_cut = False

        repetitive_assets_paths = []
        for source_path in self._clipboard_content:
            target_path = parent_path / source_path.name
            if source_path == target_path:
                continue
            elif target_path.exists():
                repetitive_assets_paths.append((source_path, target_path))
            else:
                shutil.move(source_path, target_path)
                self._highlight_indexes_paths.append(target_path)

        if not repetitive_assets_paths:
            return
        
        repetitive_asset_names = [ele[0].name for ele in repetitive_assets_paths]
        content = T.tr('message_box.question_overwrite_content', 'Overwrite the following duplicate resources?\n{}').format(('\n').join(repetitive_asset_names))
        reply = QMessageBox.question(QApplication.activeWindow(), T.tr('message_box.question_title', 'Confirm'), content, QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.StandardButton.Yes:
            for ele in repetitive_assets_paths:
                source_path = ele[0]
                target_path = ele[1]
                shutil.copytree(source_path, target_path, dirs_exist_ok=True) if source_path.is_dir() else shutil.copy2(source_path, target_path)
                shutil.rmtree(source_path) if source_path.is_dir() else source_path.unlink()
                self._highlight_indexes_paths.append(target_path)

    def _rename(self):
        self.edit(self.currentIndex())

    def _get_unique_path(self, name, parent_item_path):
        num = 0
        new_name = name
        new_path = parent_item_path / new_name
        while new_path.exists():
            num += 1
            stem = Path(name).stem
            suffix = Path(name).suffix
            new_name = f"{stem}-{num}{suffix}"
            new_path = parent_item_path / new_name
        return new_path
    
    def _duplicate(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        
        self._highlight_indexes_paths = []
        
        for index in selected_indexes:
            index = self._proxy_model.mapToSource(index)
            index_name = self._file_model.fileName(index)
            source_path = Path(self._file_model.filePath(index))
            parent_path = Path(self._file_model.filePath(index.parent()))
            target_path = self._get_unique_path(index_name, parent_path)
            shutil.copytree(source_path, target_path) if source_path.is_dir() else shutil.copy2(source_path, target_path)
            self._highlight_indexes_paths.append(target_path)

    def _copy_path(self):
        index_path = self._file_model.filePath(self._proxy_model.mapToSource(self.currentIndex()))
        QApplication.clipboard().setText(index_path)

    def _copy_name(self):
        index_name = self.currentIndex().data(Qt.ItemDataRole.DisplayRole)
        QApplication.clipboard().setText(index_name)

    def _open_in_terminal(self):
        selected_indexes = self.selectedIndexes()
        target_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(selected_indexes[-1]))) if selected_indexes else Path(self._file_model.filePath(self._proxy_model.mapToSource(self.rootIndex())))
        if not target_path.is_dir():
            target_path = target_path.parent

        system = platform.system()
        if system == 'Windows':
            subprocess.Popen(f'start cmd /k "cd /d {target_path}"', shell=True)
        elif system == 'Darwin':
            subprocess.Popen(['open', '-a', 'Terminal', target_path])
        elif system == 'Linux':
            try:
                subprocess.Popen(['gnome-terminal', '--working-directory', target_path])
            except:
                QMessageBox.information(QApplication.activeWindow(), T.tr('message_box.information_title', 'Info'), T.tr('message_box.information_os_content', 'Unsupported Operating System'))
        else:
            QMessageBox.information(QApplication.activeWindow(), T.tr('message_box.information_title', 'Info'), T.tr('message_box.information_os_content', 'Unsupported Operating System'))

    def _open_externally(self):
        """Open the selected item with the operating system's default
        application: images with the default viewer, audio/video with the
        default player, folders in the file manager, etc."""
        selected_indexes = self.selectedIndexes()
        if selected_indexes:
            target_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(selected_indexes[-1])))
        else:
            target_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(self.rootIndex())))

        system = platform.system()
        if system == 'Windows':
            try:
                os.startfile(str(target_path))
            except OSError as e:
                QMessageBox.warning(QApplication.activeWindow(), T.tr('message_box.warning_title', 'Warning'), str(e))
        elif system == 'Darwin':
            subprocess.Popen(['open', str(target_path)])
        elif system == 'Linux':
            subprocess.Popen(['xdg-open', str(target_path)])
        else:
            QMessageBox.information(QApplication.activeWindow(), T.tr('message_box.information_title', 'Info'), T.tr('message_box.information_os_content', 'Unsupported Operating System'))

    def _get_selected_file_path(self):
        """Return the path of the currently selected file (or None)."""
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return None
        return Path(self._file_model.filePath(self._proxy_model.mapToSource(selected_indexes[-1])))

    @staticmethod
    def _is_text_file(path):
        return path.is_file() and path.suffix.lower() in TEXT_FILE_EXTENSIONS

    @staticmethod
    def _is_image_file(path):
        return path.is_file() and path.suffix.lower() in IMAGE_FILE_EXTENSIONS

    def _open_file(self):
        """Open the selected file: text files in the built-in code editor,
        images in the built-in image editor, everything else with the
        system's default application."""
        target_path = self._get_selected_file_path()
        if not target_path:
            return
        if self._is_text_file(target_path):
            self.edit_file_signal.emit(str(target_path))
        elif self._is_image_file(target_path):
            self.image_edit_signal.emit(str(target_path))
        else:
            self._open_externally()

    def _on_double_clicked(self, index):
        """Double-clicking a folder toggles expand/collapse, a text file
        opens in the code editor, an image opens in the built-in image
        editor, and any other file opens with the system's default
        application."""
        target_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(index)))
        if target_path.is_dir():
            # Let the tree's default behavior expand/collapse the folder.
            return
        if self._is_text_file(target_path):
            self.edit_file_signal.emit(str(target_path))
        elif self._is_image_file(target_path):
            self.image_edit_signal.emit(str(target_path))
        else:
            # Make sure the double-clicked item is the one that gets opened
            # (the default app opener reads the current selection).
            self.setCurrentIndex(index)
            self._open_externally()

    def _run_project(self):
        """Run the project (same as the Run Project button)."""
        self._game_manager.run_project()

    def _show_in_explorer(self):
        selected_indexes = self.selectedIndexes()
        target_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(selected_indexes[-1]))) if selected_indexes else Path(self._file_model.filePath(self._proxy_model.mapToSource(self.rootIndex())))

        system = platform.system()
        if system == 'Windows':
            subprocess.Popen(['explorer', '/select,', target_path])
        elif system == 'Darwin':
            subprocess.Popen(['open', target_path])
        elif system == 'Linux':
            subprocess.Popen(["xdg-open", target_path])
        else:
            QMessageBox.information(QApplication.activeWindow(), T.tr('message_box.information_title', 'Info'), T.tr('message_box.information_os_content', 'Unsupported Operating System'))

    def _drop_indexes(self, parent_path, source_paths, is_internal_drag):
        repetitive_assets_paths = []
        for source_path in source_paths:
            target_path = parent_path / source_path.name
            if source_path == target_path:
                continue
            elif target_path.exists():
                repetitive_assets_paths.append((source_path, target_path))
            else:
                if is_internal_drag:
                    shutil.move(source_path, target_path)
                else:
                    shutil.copytree(source_path, target_path, dirs_exist_ok=True) if source_path.is_dir() else shutil.copy2(source_path, target_path)

        if not repetitive_assets_paths:
            return
        
        repetitive_asset_names = [ele[0].name for ele in repetitive_assets_paths]
        content = T.tr('message_box.question_overwrite_content', 'Overwrite the following duplicate resources?\n{}').format(('\n').join(repetitive_asset_names))
        reply = QMessageBox.question(QApplication.activeWindow(), T.tr('message_box.question_title', 'Confirm'), content, QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.StandardButton.Yes:
            for ele in repetitive_assets_paths:
                source_path = ele[0]
                target_path = ele[1]
                shutil.copytree(source_path, target_path, dirs_exist_ok=True) if source_path.is_dir() else shutil.copy2(source_path, target_path)
                if is_internal_drag:
                    shutil.rmtree(source_path) if source_path.is_dir() else source_path.unlink()

    def _save_expand_state(self):
        def _save(parent_path):
            proxy_parent_index = self._proxy_model.mapFromSource(self._file_model.index(parent_path))
            child_count = self._proxy_model.rowCount(proxy_parent_index)
            if child_count <= 0:
                return
            
            for i in range(child_count):
                proxy_child_index = self._proxy_model.index(i, 0, proxy_parent_index)
                source_child_index = self._proxy_model.mapToSource(proxy_child_index)
                child_path = self._file_model.filePath(source_child_index)

                if not self._file_model.isDir(source_child_index):
                    continue

                if self.isExpanded(proxy_child_index):
                    _save(child_path)
                    self._expand_state[child_path] = True
                else:
                    self._expand_state[child_path] = False

        _save(self._root_path)

    def _restore_indexes_expand_state(self):
        for index_path in self._expand_state.keys():
            if not Path(index_path).exists():
                continue

            proxy_index = self._proxy_model.mapFromSource(self._file_model.index(index_path))
            self.setExpanded(proxy_index, self._expand_state[index_path])

        self._expand_state.clear()

    def search(self, keyword):
        return self._search(keyword)
    
    def _search(self, keyword):
        self._proxy_model.setFilterRegularExpression(QRegularExpression())
        self.setRootIndex(self._proxy_model.mapFromSource(self._file_model.index(self._root_path)))
        self._restore_indexes_expand_state()

        if not keyword:
            return
        
        self._save_expand_state()
        self._file_model.directoryLoaded.connect(self.expandAll)
        self.expandAll()

        QTimer.singleShot(0, lambda: self._proxy_model.setFilterRegularExpression(QRegularExpression(keyword)))

    def _count_folders_rglob(self, path):
        path_obj = Path(path)
        
        if not path_obj.exists():
            return 0
        
        folders = [p for p in path_obj.rglob("*") if p.is_dir()]
        
        return len(folders)

    def _clear_highlight_items(self):
        self._highlight_indexes_paths = []
        self.viewport().update()

    def refresh(self):
        self._file_model.setRootPath(self._root_path)
        self.setRootIndex(self._proxy_model.mapFromSource(self._file_model.index(self._root_path)))
        self._proxy_model.invalidate()

    def get_file_system_model(self):
        return self._file_model
    
    def get_sort_filter_proxy_model(self):
        return self._proxy_model
    
    def get_clipboard_content(self):
        return self._clipboard_content
    
    def get_sort_type(self):
        return self._sort_type
    
    def set_sort_type(self, sort_type):
        self._sort_type = sort_type
        self._proxy_model.invalidate()
        update_project_config('asset.sort_type', sort_type)

    def drawRow(self, painter, options, index):
        index_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(index)))

        painter.save()
        if self._is_cut:
            if index_path in self._clipboard_content:
                painter.setOpacity(0.5)
        
        if index_path in self._highlight_indexes_paths:
            painter.setPen(QPen(QColor(229, 243, 255, 255)))
            painter.setBrush(QColor(229, 243, 255, 255))
            painter.drawRect(options.rect)

        super().drawRow(painter, options, index)
        painter.restore()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        index = self.indexAt(event.pos())
        if not index.isValid():
            self._clear_highlight_items()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        
        index_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(index)))
        if index_path.suffix == '.scene':
            # Load the same scene.
            if index_path.as_posix() == self._game_manager.current_scene_file_path:
                self._game_manager.deselect_all()
                self._game_manager.select(self._game_manager.canvas_object_uuid)
                return
            
            # Load a different scene.
            self._game_manager.load_scene(index_path.as_posix())

    def dragEnterEvent(self, event):
        if event.source() != None and event.source() != self:
            event.ignore()
            return
        
        if event.mimeData().hasUrls():
            event.accept()

    def dropEvent(self, event):   
        parent_index = self.indexAt(event.pos())
        if not parent_index.isValid():
            parent_index = self.rootIndex()
        elif not self._file_model.isDir(self._proxy_model.mapToSource(parent_index)):
            parent_index = parent_index.parent()
        parent_path = Path(self._file_model.filePath(self._proxy_model.mapToSource(parent_index)))
        
        urls = event.mimeData().urls()
        source_paths = [Path(url.toLocalFile()) for url in urls]
        self._drop_indexes(parent_path, source_paths, event.source()==self)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_X:
                self._cut()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_C:
                self._copy()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_V:
                self._paste()
                event.accept()
                return
        
        elif event.key() == Qt.Key.Key_Delete:
            self._delete()
            event.accept()
            return
        
        super().keyPressEvent(event)
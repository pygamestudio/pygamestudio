# Source - https://stackoverflow.com/a/53773101
# Posted by eyllanesc
# Retrieved 2026-03-24, License - CC BY-SA 4.0

from PyQt5 import QtCore, QtGui, QtWidgets

class Widget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(Widget, self).__init__(parent)
        le = QtWidgets.QLineEdit(textChanged=self.on_textChanged)
        self.lv = QtWidgets.QTreeView()

        self._dirpath = QtCore.QDir.homePath()

        self.file_model = QtWidgets.QFileSystemModel()
        self.file_model.setRootPath(QtCore.QDir.rootPath())
        self.file_model.setFilter(QtCore.QDir.NoDotAndDotDot 
            | QtCore.QDir.AllEntries 
            | QtCore.QDir.Dirs 
            | QtCore.QDir.Files)
        self.proxy_model = QtCore.QSortFilterProxyModel(
            recursiveFilteringEnabled=True,
            filterRole=QtWidgets.QFileSystemModel.FileNameRole)
        self.proxy_model.setSourceModel(self.file_model)
        self.lv.setModel(self.proxy_model)
        self.adjust_root_index()

        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(le)
        lay.addWidget(self.lv)

    @QtCore.pyqtSlot(str)
    def on_textChanged(self, text):
        self.proxy_model.setFilterWildcard("*{}*".format(text))
        self.adjust_root_index()

    def adjust_root_index(self):
        root_index = self.file_model.index(self._dirpath)
        proxy_index = self.proxy_model.mapFromSource(root_index)
        self.lv.setRootIndex(proxy_index)

if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = Widget()
    w.show()
    sys.exit(app.exec_())

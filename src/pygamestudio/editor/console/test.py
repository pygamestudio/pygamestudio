import os
import re
import sys
from pathlib import Path
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

class ErrorTextBrowser(QTextBrowser):
    """支持错误行跳转的文本浏览器，支持Ctrl+点击跳转"""
    
    # 信号：请求打开文件
    fileOpenRequested = Signal(str, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)  # 禁用默认链接行为
        
        # 存储文件路径和行号的映射
        self._file_links = {}
        
        # 设置字体
        font = QFont("Consolas", 10)
        self.setFont(font)
        
        # 设置鼠标跟踪
        self.setMouseTracking(True)
        
        # 初始化样式
        self.setStyleSheet("""
            QTextBrowser {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
            }
        """)
        
        # 创建光标
        self._hand_cursor = QCursor(Qt.PointingHandCursor)
        self._default_cursor = QCursor(Qt.IBeamCursor)
        
        # 正则表达式模式用于匹配错误行
        self._error_patterns = [
            # Python: File "filename.py", line 123
            r'File\s+"([^"]+\.py)"(?:, line (\d+))',
            r"File\s+'([^']+\.py)'(?:, line (\d+))",
            # Python: File "filename.py", line 123, in function
            r'File\s+"([^"]+\.py)", line (\d+), in',
            # 通用: filename.py:123
            r'([a-zA-Z0-9_\-\./\\]+\.(?:py|txt|json|xml|html|css|js)):(\d+)',
            # Windows 完整路径
            r'([a-zA-Z]:[\\/][^:\n]+\.(?:py|txt|json|xml|html|css|js)):(\d+)',
        ]
        
        # 当前鼠标下的链接
        self._current_link = None
        
    def append_error(self, error_text):
        """添加错误文本并自动识别链接"""
        html_text = self._format_error_text(error_text)
        self.append(html_text)
        
    def _format_error_text(self, text):
        """格式化错误文本，识别并高亮文件路径"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            formatted_line = self._process_line(line)
            formatted_lines.append(formatted_line)
        
        return '<br>'.join(formatted_lines)
    
    def _process_line(self, line):
        """处理单行文本，识别文件路径"""
        # 转义HTML特殊字符
        line = self._escape_html(line)
        
        # 检查是否有匹配的错误模式
        for pattern in self._error_patterns:
            match = re.search(pattern, line)
            if match:
                file_path = match.group(1)
                line_num = int(match.group(2)) if match.group(2) else 1
                
                # 创建唯一标识符
                link_id = f"file_link_{len(self._file_links)}"
                self._file_links[link_id] = (file_path, line_num)
                
                # 替换为链接格式
                start, end = match.span()
                original_text = match.group(0)
                link_text = f'<span id="{link_id}" style="color: #0066CC; text-decoration: none;">{original_text}</span>'
                
                # 重构行
                line = line[:start] + link_text + line[end:]
                break
        
        return line
    
    def _escape_html(self, text):
        """转义HTML特殊字符"""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace(' ', '&nbsp;'))
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件处理"""
        # 获取鼠标位置
        pos = event.pos()
        
        # 检查是否在链接上
        link_text = self.anchorAt(pos)
        print(link_text)
        if link_text:
            self._current_link = link_text
            # 检查是否按下了Ctrl键
            if event.modifiers() & Qt.ControlModifier:
                self.viewport().setCursor(self._hand_cursor)
                # 添加下划线效果
                self._highlight_link(link_text, True)
            else:
                self.viewport().setCursor(self._default_cursor)
                self._highlight_link(link_text, False)
        else:
            self._current_link = None
            self.viewport().setCursor(self._default_cursor)
        
        super().mouseMoveEvent(event)
    
    def _highlight_link(self, link_id, highlight=True):
        """高亮或取消高亮链接"""
        if not link_id:
            return
            
        # 获取当前文档
        document = self.document()
        cursor = QTextCursor(document)
        
        # 查找包含该链接的元素
        html = self.toHtml()
        
        if highlight:
            # 添加下划线
            new_html = html.replace(f'id="{link_id}"', 
                                  f'id="{link_id}" style="color: #FF5500; text-decoration: underline;"')
        else:
            # 移除下划线
            new_html = html.replace(f'id="{link_id}" style="color: #FF5500; text-decoration: underline;"',
                                  f'id="{link_id}" style="color: #0066CC; text-decoration: none;"')
        
        self.setHtml(new_html)
    
    def mousePressEvent(self, event):
        """鼠标点击事件处理"""
        if event.button() == Qt.LeftButton:
            # 检查是否按下了Ctrl键
            if event.modifiers() & Qt.ControlModifier:
                # 获取点击位置的链接
                pos = event.pos()
                link_text = self.anchorAt(pos)
                
                if link_text and link_text in self._file_links:
                    file_path, line_num = self._file_links[link_text]
                    print(f"跳转到: {file_path}:{line_num}")
                    self.fileOpenRequested.emit(file_path, line_num)
                    return
        
        super().mousePressEvent(event)
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_Control:
            # Ctrl键按下时，如果鼠标在链接上，改变光标
            if self._current_link:
                self.viewport().setCursor(self._hand_cursor)
                self._highlight_link(self._current_link, True)
        
        super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        """键盘释放事件处理"""
        if event.key() == Qt.Key_Control:
            # Ctrl键释放时，恢复默认光标
            self.viewport().setCursor(self._default_cursor)
            if self._current_link:
                self._highlight_link(self._current_link, False)
        
        super().keyReleaseEvent(event)

class CodeEditor(QPlainTextEdit):
    """代码编辑器，支持行号高亮"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas", 11)
        self.setFont(font)
        
        # 设置只读
        self.setReadOnly(True)
        
        # 创建行号区域
        self.line_number_area = LineNumberArea(self)
        
        # 连接信号
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        
        # 初始化行号区域宽度
        self.update_line_number_area_width(0)
    
    def open_file(self, file_path, line_number=1):
        """打开文件并跳转到指定行"""
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                # 尝试在当前目录下查找
                current_dir = os.path.dirname(os.path.abspath(__file__))
                possible_paths = [
                    file_path,
                    os.path.join(current_dir, file_path),
                    os.path.join(current_dir, os.path.basename(file_path))
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        file_path = path
                        break
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 设置文本
            self.setPlainText(content)
            
            # 跳转到指定行
            self.highlight_line(line_number)
            
            return True
            
        except Exception as e:
            self.setPlainText(f"无法打开文件: {file_path}\n错误: {str(e)}")
            return False
    
    def highlight_line(self, line_number):
        """高亮显示指定行"""
        # 确保行号有效
        if line_number < 1:
            line_number = 1
        
        # 获取文档
        document = self.document()
        
        # 找到对应的块
        block = document.findBlockByLineNumber(line_number - 1)
        if not block.isValid():
            # 如果行号超出范围，跳转到最后一行
            block = document.lastBlock()
        
        # 创建光标并跳转
        cursor = QTextCursor(block)
        self.setTextCursor(cursor)
        
        # 确保光标可见
        self.centerCursor()
        
        # 创建高亮选择
        extra_selections = []
        
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(255, 255, 200))  # 浅黄色背景
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = QTextCursor(block)
        selection.cursor.movePosition(QTextCursor.StartOfBlock)
        selection.cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        
        extra_selections.append(selection)
        self.setExtraSelections(extra_selections)
    
    def line_number_area_width(self):
        """计算行号区域的宽度"""
        digits = 1
        count = max(1, self.blockCount())
        while count >= 10:
            count /= 10
            digits += 1
        
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    
    def update_line_number_area_width(self, new_block_count):
        """更新行号区域宽度"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect, dy):
        """更新行号区域"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), 
                                        self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
    
    def resizeEvent(self, event):
        """调整大小事件"""
        super().resizeEvent(event)
        
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), 
                  self.line_number_area_width(), cr.height()))
    
    def line_number_area_paint_event(self, event):
        """绘制行号区域"""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(240, 240, 240))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor(120, 120, 120))
                painter.drawText(0, top, self.line_number_area.width() - 3, 
                               self.fontMetrics().height(),
                               Qt.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

class LineNumberArea(QWidget):
    """行号区域部件"""
    
    def __init__(self, editor):
        super().__init__(editor)
        self._code_editor = editor
    
    def sizeHint(self):
        return QSize(self._code_editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self._code_editor.line_number_area_paint_event(event)

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 设置窗口属性
        self.setWindowTitle("错误跳转工具")
        self.setGeometry(100, 100, 1400, 900)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建提示标签
        hint_label = QLabel("提示: 按住 Ctrl 键并将鼠标悬停在错误行上，点击即可跳转")
        hint_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-style: italic;
                padding: 5px;
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
        """)
        main_layout.addWidget(hint_label)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧：错误显示区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        error_label = QLabel("错误信息")
        error_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        left_layout.addWidget(error_label)
        
        self.error_browser = ErrorTextBrowser()
        self.error_browser.fileOpenRequested.connect(self.open_file_in_editor)
        left_layout.addWidget(self.error_browser)
        
        # 右侧：代码编辑区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        code_label = QLabel("代码编辑器")
        code_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        right_layout.addWidget(code_label)
        
        self.code_editor = CodeEditor()
        right_layout.addWidget(self.code_editor)
        
        # 添加到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # 设置分割比例
        splitter.setSizes([500, 900])
        
        # 创建示例文件
        self._create_sample_files()
        
        # 添加示例错误
        self._add_sample_errors()
        
        # 状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")
    
    def _create_sample_files(self):
        """创建示例文件"""
        self.sample_dir = os.path.join(os.path.dirname(__file__), "sample_files")
        os.makedirs(self.sample_dir, exist_ok=True)
        
        # 创建示例 Python 文件
        python_code = '''#!/usr/bin/env python3
"""
示例 Python 文件
包含一些函数和类
"""

def calculate_sum(a, b):
    """计算两个数的和"""
    result = a + b
    return result

def calculate_product(x, y):
    """计算两个数的乘积"""
    # 第15行：这里可能有错误
    if y == 0:
        raise ValueError("除数不能为零")
    
    product = x * y
    return product

def process_data(data_list):
    """处理数据列表"""
    # 第25行：这里处理数据
    processed = []
    for item in data_list:
        # 检查是否为数字
        if isinstance(item, (int, float)):
            processed.append(item * 2)
        else:
            # 第31行：处理非数字数据
            processed.append(str(item).upper())
    
    return processed

class DataProcessor:
    """数据处理类"""
    
    def __init__(self, data):
        self.data = data
    
    def analyze(self):
        """分析数据"""
        # 第45行：这里进行数据分析
        if not self.data:
            return None
        
        # 计算统计信息
        stats = {
            'length': len(self.data),
            'sum': sum(self.data) if self.data else 0,
            'average': sum(self.data)/len(self.data) if self.data else 0
        }
        
        return stats

def main():
    """主函数"""
    # 第60行：程序入口
    print("程序开始运行...")
    
    try:
        # 测试函数
        result = calculate_sum(10, 20)
        print(f"10 + 20 = {result}")
        
        # 这里会产生除零错误
        result2 = calculate_product(5, 0)
        print(f"5 * 0 = {result2}")
        
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()
'''
        
        python_file = os.path.join(self.sample_dir, "example.py")
        with open(python_file, 'w', encoding='utf-8') as f:
            f.write(python_code)
    
    def _add_sample_errors(self):
        """添加示例错误信息"""
        # 创建示例错误跟踪
        example_errors = """Traceback (most recent call last):
  File "example.py", line 65, in <module>
    main()
  File "example.py", line 60, in main
    result2 = calculate_product(5, 0)
  File "example.py", line 15, in calculate_product
    raise ValueError("除数不能为零")
ValueError: 除数不能为零

另一个语法错误：
File "example.py", line 45
    def analyze(self):
        ^
IndentationError: expected an indented block

还有一个文件不存在的错误：
File "missing.py", line 10
    import unknown_module
ModuleNotFoundError: No module named 'unknown_module'

使用绝对路径的错误：
""" + f'File "{os.path.join(self.sample_dir, "example.py")}", line 25' + """
    processed.append(item * 2)
TypeError: can't multiply sequence by non-int of type 'float'
"""
        
        self.error_browser.append_error(example_errors)
        
        # 添加更多错误类型
        more_errors = """
常见错误格式：
utils.py:42 - 函数调用错误
config.json:10 - JSON解析错误
/data/project/main.py:156 - 权限错误
C:\\Users\\Admin\\project\\test.py:89 - Windows路径错误
"""
        self.error_browser.append_error(more_errors)
    
    def open_file_in_editor(self, file_path, line_number):
        """在编辑器中打开文件"""
        success = self.code_editor.open_file(file_path, line_number)
        
        if success:
            self.status_bar.showMessage(f"已打开: {file_path} (第{line_number}行)", 3000)
        else:
            self.status_bar.showMessage(f"无法打开文件: {file_path}", 3000)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 创建并显示窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class CodeHighlighter(QSyntaxHighlighter):
    """Theme-aware syntax highlighter for the built-in code editor.

    Supports Python, JSON, JavaScript, HTML, CSS and plain text. All
    highlight colors come from a light/dark palette so the editor stays in
    sync with the app theme.
    """

    # Palette per language token kind, as (light_color, dark_color).
    _PALETTE = {
        'keyword': ('#0000ff', '#569cd6'),
        'string': ('#a31515', '#ce9178'),
        'comment': ('#008000', '#6a9955'),
        'number': ('#098658', '#b5cea8'),
        'function': ('#795e26', '#dcdcaa'),
        'class': ('#267f99', '#4ec9b0'),
        'builtin': ('#000080', '#4fc1ff'),
        'self': ('#0000ff', '#569cd6'),
        'decorator': ('#af00db', '#d7ba7d'),
        'key': ('#0451a5', '#9cdcfe'),
        'constant': ('#0000ff', '#569cd6'),
    }

    _PY_KEYWORDS = (
        'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
        'def', 'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
        'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None',
        'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True', 'try',
        'while', 'with', 'yield',
    )

    _PY_BUILTINS = (
        'abs', 'all', 'any', 'bin', 'bool', 'bytearray', 'bytes', 'callable',
        'chr', 'classmethod', 'complex', 'dict', 'dir', 'divmod', 'enumerate',
        'eval', 'exec', 'filter', 'float', 'format', 'frozenset', 'getattr',
        'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int',
        'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals', 'map',
        'max', 'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord',
        'pow', 'print', 'property', 'range', 'repr', 'reversed', 'round',
        'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum',
        'super', 'tuple', 'type', 'vars', 'zip',
    )

    _JSON_CONSTANTS = ('true', 'false', 'null')

    _JS_KEYWORDS = (
        'as', 'async', 'await', 'break', 'case', 'catch', 'class', 'const',
        'continue', 'debugger', 'default', 'delete', 'do', 'else', 'export',
        'extends', 'finally', 'for', 'from', 'function', 'if', 'import',
        'in', 'instanceof', 'let', 'new', 'of', 'return', 'static', 'super',
        'switch', 'this', 'throw', 'try', 'typeof', 'var', 'void', 'while',
        'with', 'yield',
    )

    _JS_CONSTANTS = ('true', 'false', 'null', 'undefined', 'NaN', 'Infinity')

    _JS_BUILTINS = (
        'Array', 'Boolean', 'Date', 'Error', 'JSON', 'Map', 'Math', 'Number',
        'Object', 'Promise', 'RegExp', 'Set', 'String', 'Symbol', 'clearInterval',
        'clearTimeout', 'console', 'document', 'fetch', 'globalThis',
        'localStorage', 'parseFloat', 'parseInt', 'sessionStorage',
        'setInterval', 'setTimeout', 'window',
    )

    def __init__(self, document, is_dark=True):
        super().__init__(document)
        self._is_dark = is_dark
        self._language = 'py'
        self._formats = {}
        self._rebuild_formats()

    # ---------------------------------------------------------------- language
    def set_language(self, suffix):
        """Pick the highlighter rules from a file suffix (.py / .json / ...)."""
        self._language = suffix.lower().lstrip('.')
        self.rehighlight()

    def apply_theme(self, is_dark):
        """Switch the palette (dark / light) and re-apply the colors."""
        self._is_dark = is_dark
        self._rebuild_formats()
        self.rehighlight()

    # ------------------------------------------------------------------ internals
    def _rebuild_formats(self):
        self._formats = {}
        for kind, (light, dark) in self._PALETTE.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(dark if self._is_dark else light))
            if kind == 'comment':
                fmt.setFontItalic(True)
            elif kind in ('keyword', 'self', 'constant', 'key'):
                fmt.setFontWeight(QFont.Weight.Bold)
            self._formats[kind] = fmt

    def _fmt(self, kind):
        return self._formats.get(kind, QTextCharFormat())

    def _apply(self, text, pattern, kind):
        for match in re.finditer(pattern, text):
            self.setFormat(match.start(), match.end() - match.start(), self._fmt(kind))

    def _apply_group(self, text, pattern, kind, group):
        """Paint one capture group of every match.

        Used when the pattern has to anchor on surrounding syntax (an
        attribute value behind ``=``, a CSS selector in front of ``{``) but
        only the group itself must be colored.
        """
        for match in re.finditer(pattern, text):
            start, end = match.span(group)
            if start >= 0:
                self.setFormat(start, end - start, self._fmt(kind))

    def highlightBlock(self, text):
        if self._language in ('py', 'python'):
            self._highlight_python(text)
        elif self._language == 'json':
            self._highlight_json(text)
        elif self._language == 'js':
            self._highlight_js(text)
        elif self._language in ('html', 'htm'):
            self._highlight_html(text)
        elif self._language == 'css':
            self._highlight_css(text)

    def _highlight_python(self, text):
        # Secondary tokens first; string/comment regions override them below.
        self._apply(text, r'\b\d+(?:\.\d+)?\b', 'number')
        self._apply(text, r'@\w+', 'decorator')
        self._apply(text, r'\b(?:def|class)\s+([A-Za-z_]\w*)', 'function')
        self._apply(text, r'\b[A-Za-z_]\w*(?=\s*\()', 'function')
        self._apply(text, r'\bself\b', 'self')
        self._apply(text, r'\b(?:' + '|'.join(self._PY_BUILTINS) + r')\b', 'builtin')
        self._apply(text, r'\b(?:' + '|'.join(self._PY_KEYWORDS) + r')\b', 'keyword')
        self._apply(text, r'\bclass\s+([A-Za-z_]\w*)', 'class')
        # Scan for strings (incl. multi-line triple-quoted) and comments, which
        # must win over everything inside them.
        self._scan_strings_and_comments(text)

    def _scan_strings_and_comments(self, text):
        """Paint string and comment regions of one block.

        Uses the highlighter block state (1 = inside \"\"\", 2 = inside
        '''') so triple-quoted strings keep their color across lines and the
        closing triple quote is included.
        """
        string_fmt = self._fmt('string')
        comment_fmt = self._fmt('comment')
        state = self.previousBlockState()
        n = len(text)

        if state in (1, 2):
            # Block continues a multi-line string opened in a previous block.
            delim = '"""' if state == 1 else "'''"
            close = text.find(delim)
            if close == -1:
                self.setFormat(0, n, string_fmt)
                self.setCurrentBlockState(state)
                return
            self.setFormat(0, close + 3, string_fmt)
            i = close + 3
        else:
            i = 0

        while i < n:
            ch = text[i]
            if ch == '#':
                self.setFormat(i, n - i, comment_fmt)
                break
            if ch in ('"', "'"):
                triple = text[i:i + 3]
                if triple in ('"""', "'''"):
                    close = text.find(triple, i + 3)
                    if close == -1:
                        # String spans into the next block.
                        self.setFormat(i, n - i, string_fmt)
                        self.setCurrentBlockState(1 if triple == '"""' else 2)
                        return
                    self.setFormat(i, close + 3 - i, string_fmt)
                    i = close + 3
                    continue
                # Single-line string (handles backslash escapes).
                j = i + 1
                while j < n:
                    if text[j] == '\\':
                        j += 2
                        continue
                    if text[j] == ch:
                        j += 1
                        break
                    j += 1
                self.setFormat(i, min(j, n) - i, string_fmt)
                i = min(j, n)
                continue
            i += 1

        self.setCurrentBlockState(0)

    def _highlight_json(self, text):
        self._apply(text, r'\b\d+(?:\.\d+)?\b', 'number')
        self._apply(text, r'\b(?:' + '|'.join(self._JSON_CONSTANTS) + r')\b', 'constant')
        # String keys (before generic strings so keys win).
        self._apply(text, r'"[^"\n]*"(?=\s*:)', 'key')
        self._apply(text, r'"(?:[^"\\]|\\.)*"', 'string')

    # ---------------------------------------------------------------- JavaScript
    def _highlight_js(self, text):
        # Secondary tokens first; string/comment regions override them below.
        self._apply(text, r'\b0[xX][0-9a-fA-F]+\b|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b', 'number')
        self._apply_group(text, r'\b(?:function|class)\s+([A-Za-z_$]\w*)', 'function', 1)
        self._apply(text, r'\b[A-Za-z_$]\w*(?=\s*\()', 'function')
        self._apply(text, r'\b(?:' + '|'.join(self._JS_BUILTINS) + r')\b', 'builtin')
        self._apply(text, r'\b(?:' + '|'.join(self._JS_CONSTANTS) + r')\b', 'constant')
        self._apply(text, r'\b(?:' + '|'.join(self._JS_KEYWORDS) + r')\b', 'keyword')
        self._apply_group(text, r'\bclass\s+([A-Za-z_$]\w*)', 'class', 1)
        # Scan for strings (incl. template literals) and comments, which must
        # win over everything inside them.
        self._scan_c_style_strings_and_comments(text)

    def _scan_c_style_strings_and_comments(self, text, line_comments=True, templates=True):
        """Paint strings and comments of one C-style block (JS / CSS).

        Uses the highlighter block state (1 = inside a /* */ comment, 2 =
        inside a template literal) so both keep their color across lines.
        ``line_comments`` enables //, ``templates`` the backtick literals.
        """
        string_fmt = self._fmt('string')
        comment_fmt = self._fmt('comment')
        state = self.previousBlockState()
        n = len(text)
        i = 0

        if state == 1:
            close = text.find('*/')
            if close == -1:
                self.setFormat(0, n, comment_fmt)
                self.setCurrentBlockState(1)
                return
            self.setFormat(0, close + 2, comment_fmt)
            i = close + 2
        elif state == 2:
            close = self._template_end(text, 0)
            if close == -1:
                self.setFormat(0, n, string_fmt)
                self.setCurrentBlockState(2)
                return
            self.setFormat(0, close, string_fmt)
            i = close

        while i < n:
            ch = text[i]
            if line_comments and text[i:i + 2] == '//':
                self.setFormat(i, n - i, comment_fmt)
                break
            if text[i:i + 2] == '/*':
                close = text.find('*/', i + 2)
                if close == -1:
                    self.setFormat(i, n - i, comment_fmt)
                    self.setCurrentBlockState(1)
                    return
                self.setFormat(i, close + 2 - i, comment_fmt)
                i = close + 2
                continue
            if templates and ch == '`':
                close = self._template_end(text, i + 1)
                if close == -1:
                    self.setFormat(i, n - i, string_fmt)
                    self.setCurrentBlockState(2)
                    return
                self.setFormat(i, close - i, string_fmt)
                i = close
                continue
            if ch in ('"', "'"):
                # Single-line string (handles backslash escapes).
                j = i + 1
                while j < n:
                    if text[j] == '\\':
                        j += 2
                        continue
                    if text[j] == ch:
                        j += 1
                        break
                    j += 1
                self.setFormat(i, min(j, n) - i, string_fmt)
                i = min(j, n)
                continue
            i += 1

        self.setCurrentBlockState(0)

    @staticmethod
    def _template_end(text, start):
        """Index just past a template literal's closing backtick, or -1."""
        j = start
        while j < len(text):
            if text[j] == '\\':
                j += 2
                continue
            if text[j] == '`':
                return j + 1
            j += 1
        return -1

    # ---------------------------------------------------------------- HTML
    def _highlight_html(self, text):
        # Secondary tokens first; comments override them below.
        self._apply(text, r'<!DOCTYPE\s+[\w:-]+', 'keyword')
        self._apply(text, r'</?[A-Za-z][\w:-]*', 'keyword')
        self._apply(text, r'\b[\w:-]+(?=\s*=)', 'key')
        self._apply_group(text, r'=\s*("[^"]*"|\'[^\']*\')', 'string', 1)
        self._apply(text, r'&[A-Za-z]+;|&#\d+;', 'constant')
        self._scan_html_comment(text)

    def _scan_html_comment(self, text):
        """Paint <!-- --> comments (block state 1 keeps them across lines)."""
        fmt = self._fmt('comment')
        n = len(text)
        i = 0
        if self.previousBlockState() == 1:
            close = text.find('-->')
            if close == -1:
                self.setFormat(0, n, fmt)
                self.setCurrentBlockState(1)
                return
            self.setFormat(0, close + 3, fmt)
            i = close + 3
        while True:
            open_ = text.find('<!--', i)
            if open_ == -1:
                break
            close = text.find('-->', open_ + 4)
            if close == -1:
                self.setFormat(open_, n - open_, fmt)
                self.setCurrentBlockState(1)
                return
            self.setFormat(open_, close + 3 - open_, fmt)
            i = close + 3
        self.setCurrentBlockState(0)

    # ---------------------------------------------------------------- CSS
    def _highlight_css(self, text):
        # Secondary tokens first; strings/comments override them below.
        self._apply(text, r'@[\w-]+', 'decorator')
        self._apply(text, r'!important\b', 'keyword')
        self._apply(text, r'#[0-9a-fA-F]{3,8}\b', 'number')
        self._apply(text, r'\b\d+(?:\.\d+)?(?:px|em|rem|vh|vw|vmin|vmax|deg|ms|s|fr|pt|%)?(?![\w%])', 'number')
        self._apply(text, r'\b[A-Za-z-]+(?=\s*:)', 'key')
        # Selector in front of { (skipping at-rules like @media, which keep
        # their decorator color).
        self._apply_group(text, r'^[ \t]*(?!@)([^{}\n]+?)(?=\s*\{)', 'class', 1)
        self._scan_c_style_strings_and_comments(text, line_comments=False, templates=False)

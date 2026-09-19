"""Runtime tools: run / stop the game, read the editor console."""

from pygamestudio.mcp.bridge import bridge
from pygamestudio.mcp.registry import ToolError, register_resource, tool
from pygamestudio.mcp.tools.context import manager

#: Console log levels (see pygamestudio.gui.console.type).
_LEVEL_NAMES = {'INFO': 'info', 'ERROR': 'error', 'WARNING': 'warning'}


@tool(
    'run_project',
    'Run the game (same as the editor Run button): the current scene is saved '
    'and main.py is started in its own process. The game output appears in the '
    'editor console - read it with get_console_logs.',
    {
        'type': 'object',
        'properties': {
            'clear_console': {'type': 'boolean', 'default': True,
                              'description': 'Clear the console before starting (easier to read the new output).'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Run the game'},
)
def run_project(args):
    manager_ = manager()
    if args.get('clear_console', True):
        browser = _console_browser(required=False)
        if browser is not None:
            browser.clear_log()
    manager_.run_project()
    return {
        'started': True,
        'project': manager_.get_project_path(),
        'note': 'Use get_console_logs to read the game output, stop_project to stop it.',
    }


@tool(
    'stop_project',
    'Stop every running game process started from the editor.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'title': 'Stop the game', 'destructiveHint': True},
)
def stop_project(args):
    stopped = manager().stop_project()
    return {'stopped_processes': stopped}


@tool(
    'get_runtime_status',
    'Whether a game process is running right now, with its pid(s), plus how '
    'many console lines were logged so far.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Runtime status'},
)
def get_runtime_status(args):
    manager_ = manager()
    processes = manager_.get_running_processes()
    logs = _logs(required=False) or []
    return {
        'running': bool(processes),
        'processes': processes,
        'console_lines': len(logs),
        'last_log': logs[-1] if logs else None,
    }


@tool(
    'get_console_logs',
    'Read the editor console (game stdout/stderr, editor messages, build '
    'output). Use it after run_project to see errors, then read_file the '
    'script and fix it.',
    {
        'type': 'object',
        'properties': {
            'level': {'type': 'string', 'enum': ['all', 'info', 'warning', 'error'],
                      'default': 'all'},
            'contains': {'type': 'string', 'default': '',
                         'description': 'Only lines containing this text (case-insensitive).'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 500, 'default': 100,
                      'description': 'How many of the newest matching lines to return.'},
        },
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Read the console'},
)
def get_console_logs(args):
    logs = _logs()
    level = args.get('level', 'all')
    needle = (args.get('contains') or '').lower()
    entries = []
    for time_text, message, log_level in logs:
        name = _LEVEL_NAMES.get(log_level, str(log_level))
        if level != 'all' and name != level:
            continue
        if needle and needle not in str(message).lower():
            continue
        entries.append({'time': str(time_text), 'level': name, 'message': str(message)})
    entries = entries[-args['limit']:]
    return {'count': len(entries), 'total_lines': len(logs), 'entries': entries}


@tool(
    'clear_console_logs',
    'Clear the editor console.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'title': 'Clear the console'},
)
def clear_console_logs(args):
    _console_browser().clear_log()
    return 'console cleared'


def _console_browser(required=True):
    body = bridge.editor_body_or_none()
    browser = getattr(getattr(body, '_console_window', None), '_console_log_browser', None)
    if browser is None and required:
        raise ToolError('The editor console is not available.')
    return browser


def _logs(required=True):
    browser = _console_browser(required=required)
    if browser is None:
        return None
    return list(getattr(browser, '_logs', []) or [])


@register_resource(
    'pygs://editor/logs',
    'Editor console',
    'The newest lines of the editor console (game output included).',
    'text/plain')
def _logs_resource():
    logs = _logs() or []
    lines = []
    for time_text, message, log_level in logs[-250:]:
        lines.append('{} [{}] {}'.format(time_text, _LEVEL_NAMES.get(log_level, log_level), message))
    return '\n'.join(lines) if lines else '(the console is empty)'

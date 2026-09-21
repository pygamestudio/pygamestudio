"""The AI agent session: a chat loop that drives the editor through MCP tools.

The session lives on the Qt main thread, so **tool calls are plain Python calls**
into ``pygamestudio.mcp`` (no HTTP, no port, no token needed - the HTTP server
only exists for *external* clients). Only the request to the language model runs
in a short-lived worker thread, so the editor stays responsive and every tool
call / undo step happens on the thread that owns the scene.

Supported backends (both chat-completions style with tool calling):

* ``openai`` - any OpenAI compatible endpoint (OpenAI, DeepSeek, Qwen, ...),
* ``ollama``  - a local Ollama server (offline models).

The loop: send the conversation + tool schemas -> the model answers with text
and/or tool calls -> each tool call is executed (optionally after the user
confirms it) -> the results go back as tool messages -> repeat until the model
stops asking for tools or the step limit is reached.
"""

import html
import json
import threading
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, Signal

from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.config import get_editor_config, update_editor_config
from pygamestudio.gui.console.logger import Logger

PROVIDER_OPENAI = 'openai'
PROVIDER_OLLAMA = 'ollama'

#: Where the local models are served from (Ollama's default address).
OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
#: Local model the settings dialog suggests (any pulled Ollama model works).
OLLAMA_DEFAULT_MODEL = 'qwen2.5:7b'

#: Online models offered in the settings dialog: name -> (service, provider, endpoint).
#: Picking the model name is enough - the request URL comes from this table.
ONLINE_MODELS = {
    'deepseek-flash': ('DeepSeek', PROVIDER_OPENAI, 'https://api.deepseek.com/v1'),
    'deepseek-v4-pro': ('DeepSeek', PROVIDER_OPENAI, 'https://api.deepseek.com/v1'),
    'gpt-4o-mini': ('OpenAI', PROVIDER_OPENAI, 'https://api.openai.com/v1'),
}

#: Defaults of the panel settings (stored under 'agent' in the editor config).
DEFAULT_SETTINGS = {
    'provider': PROVIDER_OPENAI,
    'base_url': 'https://api.deepseek.com/v1',
    'model': 'deepseek-flash',
    'api_key': '',
    'confirm': True,
}

#: Safety stop for one turn: a model that keeps calling tools without ever
#: answering is cut off after this many steps (ask again to continue).
STEP_LIMIT = 24

#: How much of one tool result is fed back to the model.
MAX_RESULT_CHARS = 8000
#: Seconds to wait for the model before giving up on a request.
REQUEST_TIMEOUT = 180.0

#: Tools that only read - they may run without asking the user.
READ_ONLY_TOOLS = {
    'editor_status', 'get_scene_tree', 'get_object', 'find_objects', 'object_types',
    'get_current_scene', 'list_scenes', 'list_files', 'read_file', 'get_project_info',
    'get_project_config', 'get_editor_settings', 'get_build_settings', 'get_console_logs',
    'get_runtime_status', 'list_editor_panels', 'capture_scene_view', 'undo', 'redo',
    'open_panel', 'block_editor_list_types', 'block_editor_get_blocks',
    'image_editor_state', 'image_editor_capture', 'tile_map_editor_state',
    'audio_player_state',
}


class LlmError(Exception):
    """A request to the model failed (network, HTTP status, bad payload)."""


# --------------------------------------------------------------------- settings
def load_settings() -> dict:
    """The agent settings from the editor config, completed with defaults.

    Keys that are no longer part of the panel (the old ``max_steps`` for
    example) are dropped, and the cleaned settings are written back so the
    configuration file does not keep dead values around.
    """
    stored = get_editor_config().get('agent') or {}
    settings = dict(DEFAULT_SETTINGS)
    if isinstance(stored, dict):
        settings.update({key: value for key, value in stored.items()
                         if key in DEFAULT_SETTINGS and value is not None})
        if settings != stored:
            update_editor_config('agent', settings)
    return settings


def save_settings(settings: dict):
    merged = dict(DEFAULT_SETTINGS)
    merged.update({key: value for key, value in (settings or {}).items()
                   if key in DEFAULT_SETTINGS})
    update_editor_config('agent', merged)


# ----------------------------------------------------------------------- schema
def tool_schemas():
    """MCP tools in the OpenAI/Ollama ``tools`` format."""
    from pygamestudio.mcp.registry import list_tools
    return [{
        'type': 'function',
        'function': {
            'name': tool['name'],
            'description': tool['description'],
            'parameters': tool['inputSchema'],
        },
    } for tool in list_tools()]


def render_tool_result(result: dict) -> str:
    """Flatten an MCP tool result into the text the model gets back."""
    if not isinstance(result, dict):
        return str(result)
    parts = []
    for block in result.get('content', []) or []:
        if block.get('type') == 'text':
            parts.append(block.get('text', ''))
        elif block.get('type') == 'image':
            parts.append('[image: {} bytes {} - the user can see it in the editor]'.format(
                len(block.get('data', '')) * 3 // 4, block.get('mimeType', 'image/png')))
    text = '\n'.join(part for part in parts if part)
    if result.get('isError'):
        text = 'ERROR: ' + text
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + '\n... [truncated]'
    return text or '(no output)'


def system_prompt() -> str:
    """The instructions the agent starts every conversation with."""
    from pygamestudio.mcp.registry import INSTRUCTIONS
    from pygamestudio.mcp.bridge import bridge

    context = []
    manager = bridge.game_manager_or_none()
    if manager is not None and manager.get_project_path():
        context.append('Open project: {}'.format(manager.get_project_path()))
        if manager.current_scene_file_path:
            context.append('Open scene: {}'.format(manager.current_scene_file_path))
        selection = manager.get_selected_objects()
        if selection:
            context.append('Selected object: {} ({})'.format(selection[0].name, selection[0].type))
        else:
            context.append('Nothing is selected in the editor.')
    else:
        context.append('No project is open in the editor right now.')

    return (
        'You are the built-in assistant of the Pygame Studio editor, talking to the user '
        'inside the editor. Use the provided tools to inspect and change the open project.\n'
        'Rules:\n'
        '- Prefer doing over explaining: call tools to make the change, then summarise briefly.\n'
        '- Every change is undoable by the user (Ctrl+Z), so one tool call may change the scene - '
        'but never delete or overwrite things the user did not ask about.\n'
        '- Read before you write: get_scene_tree / get_object / object_types tell you the exact '
        'names and properties; read_file before editing a script.\n'
        '- After writing a script, run_project and then get_console_logs to check it works.\n'
        '- capture_scene_view shows you the scene; do not guess what it looks like.\n'
        '- Answer in the language the user writes in, and keep answers short.\n'
        '\nTool reference:\n' + INSTRUCTIONS + '\n\nEditor state:\n' + '\n'.join(context)
    )


# ---------------------------------------------------------------------- network
def _post_json(url, payload, headers, timeout):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(url, data=body, method='POST',
                                     headers={'Content-Type': 'application/json',
                                              'User-Agent': 'pygamestudio-agent',
                                              **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='replace')[:400]
        raise LlmError('HTTP {} from {}: {}'.format(e.code, url, detail))
    except urllib.error.URLError as e:
        raise LlmError('Cannot reach {}: {}'.format(url, e))
    except ValueError as e:
        raise LlmError('The model answered with invalid JSON: {}'.format(e))


def _normalize_tool_calls(raw_calls):
    """Tool calls from either provider -> [{'id', 'name', 'arguments'(dict)}]."""
    calls = []
    for index, call in enumerate(raw_calls or [], start=1):
        function = call.get('function') or {}
        name = function.get('name') or ''
        arguments = function.get('arguments')
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except ValueError:
                arguments = {'_raw': arguments}
        elif not isinstance(arguments, dict):
            arguments = {}
        calls.append({
            'id': call.get('id') or 'call_{}'.format(index),
            'name': name,
            'arguments': arguments,
        })
    return calls


def _ollama_messages(messages):
    """Messages in the shape Ollama expects (dict arguments, no tool_call_id)."""
    converted = []
    for message in messages:
        role = message.get('role')
        if role == 'assistant' and message.get('tool_calls'):
            converted.append({
                'role': 'assistant',
                'content': message.get('content') or '',
                'tool_calls': [{'function': {'name': call.get('name') or (call.get('function') or {}).get('name'),
                                             'arguments': call.get('arguments') or {}}}
                               for call in message['tool_calls']],
            })
        elif role == 'tool':
            converted.append({'role': 'tool', 'content': message.get('content', '')})
        else:
            converted.append({'role': role, 'content': message.get('content', '')})
    return converted


def chat_completion(settings, messages, tools):
    """One blocking request to the model. Returns {'content', 'tool_calls'}."""
    provider = (settings.get('provider') or PROVIDER_OPENAI).lower()
    base_url = (settings.get('base_url') or '').rstrip('/')
    model = (settings.get('model') or '').strip()
    if not base_url:
        raise LlmError('No endpoint configured: set the base URL in the agent settings.')
    if not model:
        raise LlmError('No model configured: set the model name in the agent settings.')

    if provider == PROVIDER_OLLAMA:
        payload = {'model': model, 'messages': _ollama_messages(messages), 'stream': False}
        if tools:
            payload['tools'] = tools
        data = _post_json(base_url + '/api/chat', payload, {}, REQUEST_TIMEOUT)
        message = data.get('message') or {}
        return {'content': message.get('content') or '',
                'tool_calls': _normalize_tool_calls(message.get('tool_calls'))}

    api_key = (settings.get('api_key') or '').strip()
    if not api_key:
        raise LlmError('No API key configured: add one in the agent settings.')
    payload = {'model': model, 'messages': messages}
    if tools:
        payload['tools'] = tools
        payload['tool_choice'] = 'auto'
    data = _post_json(base_url + '/chat/completions', payload,
                      {'Authorization': 'Bearer ' + api_key}, REQUEST_TIMEOUT)
    choices = data.get('choices') or []
    if not choices:
        raise LlmError('The model returned no choices: {}'.format(str(data)[:200]))
    message = choices[0].get('message') or {}
    return {'content': message.get('content') or '',
            'tool_calls': _normalize_tool_calls(message.get('tool_calls'))}


# ----------------------------------------------------------------------- session
class AgentSession(QObject):
    """The chat loop of one agent panel.

    Signals (all delivered on the main thread):

    ``message_added``      (role, text)          - user / assistant / note text
    ``tool_started``       (name, arguments)     - a tool is about to run
    ``tool_finished``      (name, ok, summary)   - a tool finished
    ``status_changed``     (text, busy)          - status line + busy flag
    ``confirmation_needed``(name, arguments)     - wait for approve()/deny()
    ``continue_needed``    (steps)               - the turn hit the step limit
    ``finished``           (error_text)          - the turn ended ('' = ok)
    """

    message_added = Signal(str, str)
    tool_started = Signal(str, dict)
    tool_finished = Signal(str, bool, str)
    status_changed = Signal(str, bool)
    confirmation_needed = Signal(str, dict)
    continue_needed = Signal(int)
    finished = Signal(str)

    # Internal bridge from the request thread (queued delivery keeps every
    # handler on the main thread).
    _on_model_answer = Signal(dict)
    _on_model_error = Signal(str)

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self._settings = dict(settings or load_settings())
        self._messages = []
        self._busy = False
        self._cancel = False
        self._step = 0
        self._pending_calls = []
        self._pending_index = 0
        self._awaiting_confirmation = None
        self._awaiting_continue = False
        self._request_thread = None
        # The worker thread hands its result over through queued signals, so no
        # Qt object is ever touched from another thread.
        self._on_model_answer.connect(self._on_answer)
        self._on_model_error.connect(self._on_error)

    # ------------------------------------------------------------ interface
    def is_busy(self) -> bool:
        """True while a turn is running (the panel shows Stop instead of Send)."""
        return self._busy

    def is_awaiting_continue(self) -> bool:
        """True while the turn is paused at the step limit (Continue button)."""
        return self._awaiting_continue

    def settings(self) -> dict:
        return dict(self._settings)

    def set_settings(self, settings):
        self._settings = dict(DEFAULT_SETTINGS)
        self._settings.update(settings or {})
        save_settings(self._settings)

    def reset(self):
        """Forget the conversation (a fresh chat)."""
        self.cancel()
        self._messages = []
        self._step = 0
        self._awaiting_continue = False

    def send(self, text):
        """Start a turn with a new user message."""
        text = (text or '').strip()
        if not text:
            return
        if self._busy:
            self.status_changed.emit(T.tr('agent.busy', 'Still working - press Stop first.'), True)
            return
        # A new prompt replaces a turn that is waiting at the step limit.
        self._awaiting_continue = False
        if not self._messages:
            self._messages.append({'role': 'system', 'content': system_prompt()})
        self._messages.append({'role': 'user', 'content': text})
        self.message_added.emit('user', text)
        self._begin()

    def continue_run(self):
        """Resume a turn that was stopped at the step limit (Continue button).

        Nothing is added to the conversation: the model simply keeps working
        from the last tool result, with a fresh step budget.
        """
        if self._busy or not self._awaiting_continue:
            return
        self._awaiting_continue = False
        self._begin()

    def dismiss_continue(self):
        """Drop a turn that is paused at the step limit (Cancel button).

        The conversation is kept - only the pending resumption is given up,
        so the user can carry on with a message of their own.
        """
        self._awaiting_continue = False

    def stop(self):
        """Ask the running turn to stop after the current step."""
        self.cancel()

    def cancel(self):
        self._cancel = True
        self._awaiting_confirmation = None
        self._awaiting_continue = False
        if self._busy:
            self._finish(T.tr('agent.stopped', 'Stopped.'))

    def approve(self, allowed: bool):
        """Answer a ``confirmation_needed`` request (Allow / Deny).

        Never blocks: the session asked for the decision and simply returned,
        so the UI stayed responsive and can call this at any time.
        """
        call = self._awaiting_confirmation
        if call is None:
            return
        self._awaiting_confirmation = None
        if self._cancel:
            return self._finish('')
        self._pending_index += 1
        if allowed:
            self._start_call(call)
        else:
            self.message_added.emit('note', T.tr(
                'agent.denied', 'Skipped {} (declined).').format(call['name']))
            self._append_tool_result(
                call, 'The user declined this change. Do not retry it; ask what to do instead.')
            self._run_next_call()

    # ---------------------------------------------------------------- loop
    def _begin(self):
        self._busy = True
        self._cancel = False
        self._step = 0
        self._request_next()

    def _request_next(self):
        if self._cancel:
            return self._finish('')
        if self._step >= STEP_LIMIT:
            return self._pause_for_continue()
        self._step += 1
        self.status_changed.emit(T.tr('agent.thinking', 'Thinking... step {}').format(self._step), True)
        self._start_request()

    def _pause_for_continue(self):
        """Stop at the step limit and let the user decide whether to go on.

        Not an error: the turn keeps its place, the panel shows a Continue
        button and locks the input, so nobody has to guess what to type.
        """
        self._busy = False
        self._awaiting_confirmation = None
        self._awaiting_continue = True
        self._step = 0
        self.status_changed.emit('', False)
        self.continue_needed.emit(STEP_LIMIT)
        self.finished.emit('')

    def _start_request(self):
        """Run the model request in a worker thread (the loop stays on the main thread)."""
        messages = json.loads(json.dumps(self._messages, ensure_ascii=False))
        tools = tool_schemas()
        settings = dict(self._settings)

        def worker():
            try:
                answer = chat_completion(settings, messages, tools)
                if not self._cancel:
                    self._on_model_answer.emit(answer)
            except LlmError as e:
                self._on_model_error.emit(str(e))
            except Exception as e:  # noqa: BLE001 - never kill the editor
                self._on_model_error.emit('{}: {}'.format(type(e).__name__, e))

        self._request_thread = threading.Thread(target=worker, name='agent-request', daemon=True)
        self._request_thread.start()

    def _on_answer(self, answer):
        if self._cancel:
            return self._finish('')
        text = (answer.get('content') or '').strip()
        calls = answer.get('tool_calls') or []
        if text:
            self.message_added.emit('assistant', text)
        # The assistant message has to be echoed back verbatim (with its tool
        # calls) so the model keeps a consistent view of the conversation.
        assistant_message = {'role': 'assistant', 'content': answer.get('content') or ''}
        if calls:
            assistant_message['tool_calls'] = [{
                'id': call['id'], 'type': 'function',
                'function': {'name': call['name'],
                             'arguments': json.dumps(call['arguments'], ensure_ascii=False)},
            } for call in calls]
        self._messages.append(assistant_message)

        if not calls:
            return self._finish('')
        self._pending_calls = calls
        self._pending_index = 0
        self._run_next_call()

    def _on_error(self, message):
        if self._cancel:
            return self._finish('')
        Logger.error('Agent request failed: {}'.format(message))
        self._finish(message)

    def _run_next_call(self):
        if self._cancel:
            return self._finish('')
        if self._pending_index >= len(self._pending_calls):
            return self._request_next()

        call = self._pending_calls[self._pending_index]
        name = call['name']

        needs_confirm = (bool(self._settings.get('confirm'))
                         and name not in READ_ONLY_TOOLS)
        if needs_confirm:
            # Ask the panel and *return*: the answer arrives through approve(),
            # which resumes the loop. Blocking here would freeze the editor.
            self._awaiting_confirmation = call
            self.status_changed.emit(T.tr('agent.waiting_confirm', 'Waiting for your confirmation...'), True)
            self.confirmation_needed.emit(name, call['arguments'])
            return

        self._pending_index += 1
        self._start_call(call)

    def _start_call(self, call):
        self.status_changed.emit(T.tr('agent.calling', 'Calling {}...').format(call['name']), True)
        self.tool_started.emit(call['name'], call['arguments'])
        self._execute(call)

    def _execute(self, call):
        from pygamestudio.mcp.registry import call_tool

        try:
            result = call_tool(call['name'], call['arguments'])
        except Exception as e:  # noqa: BLE001 - report as a tool failure
            result = {'content': [{'type': 'text', 'text': '{}: {}'.format(type(e).__name__, e)}],
                      'isError': True}

        text = render_tool_result(result)
        ok = not result.get('isError')
        self.tool_finished.emit(call['name'], ok, text)
        self._append_tool_result(call, text)
        self._run_next_call()

    def _append_tool_result(self, call, text):
        self._messages.append({
            'role': 'tool',
            'tool_call_id': call['id'],
            'content': text,
        })

    def _finish(self, error_text):
        was_busy = self._busy
        self._busy = False
        self._awaiting_confirmation = None
        self.status_changed.emit('', False)
        if was_busy or error_text:
            self.finished.emit(error_text or '')

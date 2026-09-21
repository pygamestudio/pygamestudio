"""Tool / resource registry for the hand-written MCP server.

A *tool* is a plain Python function with a name, a description and a JSON
schema. Tools are registered with the :func:`tool` decorator while the
``pygamestudio.mcp.tools`` package is imported; the server then only has to
forward ``tools/list`` and ``tools/call``.

Two rules every handler can rely on:

* it runs on the editor's **main thread** (see :mod:`pygamestudio.mcp.bridge`),
  so touching the scene, the undo stack or the widgets is safe;
* its arguments have already been validated and normalised against the schema
  (defaults applied, obvious type coercions done), so the body can be simple.
"""

from pygamestudio.mcp.bridge import EditorNotAttached, bridge
from pygamestudio.mcp.protocol import INVALID_PARAMS, JsonRpcError, to_json_text


class ToolError(Exception):
    """A tool failure that is reported to the client as a normal tool error."""


class Tool:
    """One registered tool."""

    def __init__(self, name, description, input_schema, handler, annotations=None):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler
        self.annotations = dict(annotations or {})

    def to_mcp_dict(self):
        data = {
            'name': self.name,
            'description': self.description,
            'inputSchema': self.input_schema,
        }
        if self.annotations:
            data['annotations'] = self.annotations
        return data


class Resource:
    """One registered resource (a small, read-only document)."""

    def __init__(self, uri, name, description, mime_type, handler):
        self.uri = uri
        self.name = name
        self.description = description
        self.mime_type = mime_type
        self.handler = handler

    def to_mcp_dict(self):
        return {
            'uri': self.uri,
            'name': self.name,
            'description': self.description,
            'mimeType': self.mime_type,
        }


_TOOLS = {}
_RESOURCES = {}

#: Shown to the client in the ``initialize`` result (agents read this first).
INSTRUCTIONS = (
    'Pygame Studio is a visual editor for 2D Python/pygame games. This server '
    'drives the editor that is running on the same machine: it can read and '
    'edit the scene (objects, their properties, hierarchy), read and write the '
    'project files (scripts, scenes, assets), run and stop the game, read the '
    'editor console and take a screenshot of the scene view. It can also '
    'package the project: `start_build` makes a standalone desktop app '
    '(PyInstaller) and `start_web_build` a browser bundle (index.html + '
    'game.zip, played through Pyodide/pygame-ce) - both protected like the '
    'editor\'s Build window; `get_build_settings`, `stop_build` and '
    '`open_output_dir` (target "desktop" or "web") manage them.\n'
    'Recommended workflow: call `editor_status` first to see whether a project '
    'is open, `get_scene_tree`/`object_types` before editing, then make changes '
    'with `create_object`, `update_object`, `apply_scene_patch` or '
    '`write_file`. Every change goes through the editor undo stack, so the user '
    'can undo it with Ctrl+Z. Prefer several small calls; check the result of '
    'each one. Use `run_project` + `get_console_logs` to verify a script, and '
    '`capture_scene_view` to check how the scene looks.\n'
    'Games are plain Python: the editor only stores the scene (.scene JSON) and '
    'attaches scripts from the project folder to objects.'
)


# --------------------------------------------------------------------- tools
def tool(name, description, input_schema, annotations=None):
    """Decorator that registers a tool handler."""
    def decorator(func):
        if name in _TOOLS:
            raise RuntimeError(f'Tool {name} is already registered')
        _TOOLS[name] = Tool(name, description, input_schema, func, annotations)
        return func
    return decorator


def register_resource(uri, name, description, mime_type='text/plain'):
    """Decorator that registers a resource reader."""
    def decorator(func):
        _RESOURCES[uri] = Resource(uri, name, description, mime_type, func)
        return func
    return decorator


def list_tools():
    return [t.to_mcp_dict() for t in sorted(_TOOLS.values(), key=lambda t: t.name)]


def list_resources():
    return [r.to_mcp_dict() for r in sorted(_RESOURCES.values(), key=lambda r: r.uri)]


def get_tool_names():
    return sorted(_TOOLS)


def clear_registry():
    """Testing helper: forget every tool/resource."""
    _TOOLS.clear()
    _RESOURCES.clear()


# ------------------------------------------------------------------ calling
def call_tool(name, arguments):
    """Run a tool and return its MCP result dict."""
    registered = _TOOLS.get(name)
    if registered is None:
        # The spec wants an error response (not a tool result) for a tool that
        # does not exist; name it clearly so the client can fix itself.
        raise JsonRpcError(INVALID_PARAMS,
                           'Unknown tool: {} (see tools/list)'.format(name))

    try:
        args = validate_arguments(registered.input_schema, arguments or {})
    except ToolError as e:
        return error_result(f'Invalid arguments for {name}: {e}')

    def _run():
        return normalize_result(registered.handler(args))

    try:
        return bridge.call_in_main_thread(_run)
    except EditorNotAttached as e:
        return error_result(str(e))
    except ToolError as e:
        return error_result(str(e))
    except TimeoutError as e:
        return error_result(str(e))
    except Exception as e:  # noqa: BLE001 - never leak a traceback to the client
        return error_result(f'{type(e).__name__}: {e}')


def read_resource(uri):
    """Read one resource and return the MCP ``resources/read`` result."""
    registered = _RESOURCES.get(uri)
    if registered is None:
        raise ToolError(f'Unknown resource: {uri}')
    value = bridge.call_in_main_thread(registered.handler)
    if isinstance(value, bytes):
        import base64
        return {'contents': [{'uri': uri, 'mimeType': registered.mime_type,
                              'blob': base64.b64encode(value).decode('ascii')}]}
    if isinstance(value, (dict, list)):
        import json
        text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    else:
        text = str(value)
    return {'contents': [{'uri': uri, 'mimeType': registered.mime_type, 'text': text}]}


def text_result(text):
    """A successful text result."""
    return {'content': [{'type': 'text', 'text': str(text)}], 'isError': False}


def error_result(message):
    """A failed result; models can read it and retry with better arguments."""
    return {'content': [{'type': 'text', 'text': str(message)}], 'isError': True}


def normalize_result(value):
    """Turn a handler's return value into an MCP tool result."""
    if isinstance(value, dict) and 'content' in value and isinstance(value['content'], list):
        value.setdefault('isError', False)
        return value
    if isinstance(value, str):
        return text_result(value)
    if value is None:
        return text_result('ok')
    return text_result(to_json_text(value))


# --------------------------------------------------------------- validation
_TYPE_CHECKS = {
    'object': lambda v: isinstance(v, dict),
    'array': lambda v: isinstance(v, list),
    'string': lambda v: isinstance(v, str),
    'boolean': lambda v: isinstance(v, bool),
    'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
    'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    'null': lambda v: v is None,
}


def validate_arguments(schema, arguments):
    """Validate/normalise arguments against a (small) JSON schema.

    Supports type, properties, required, additionalProperties, items, enum,
    default, minimum, maximum, minLength and the obvious coercions ('3' -> 3,
    'true' -> True, single value -> one-item array).
    """
    if not isinstance(schema, dict) or schema.get('type') != 'object':
        return dict(arguments or {}) if isinstance(arguments, dict) else {}

    if not isinstance(arguments, dict):
        raise ToolError('The arguments must be a JSON object')

    properties = schema.get('properties', {})
    allow_extra = schema.get('additionalProperties', False)
    cleaned = {}

    unknown = [key for key in arguments if key not in properties]
    if unknown and not allow_extra:
        raise ToolError(
            'Unknown argument(s): {}. Allowed: {}'.format(
                ', '.join(sorted(unknown)), ', '.join(sorted(properties)) or '(none)'))

    for key, value in arguments.items():
        if key in properties:
            cleaned[key] = _validate_value(key, properties[key], value)
        else:
            cleaned[key] = value

    for key, prop in properties.items():
        if key not in cleaned and 'default' in prop:
            cleaned[key] = prop['default']

    missing = [key for key in schema.get('required', []) if cleaned.get(key) is None]
    if missing:
        raise ToolError('Missing required argument(s): ' + ', '.join(missing))
    return cleaned


def _validate_value(name, prop, value):
    expected = prop.get('type')
    if value is None:
        return None

    if expected == 'integer' or expected == 'number':
        value = _coerce_number(name, value, expected == 'integer')
    elif expected == 'boolean':
        value = _coerce_bool(name, value)
    elif expected == 'string':
        if not isinstance(value, str):
            raise ToolError(f'"{name}" must be a string')
    elif expected == 'array':
        if not isinstance(value, list):
            value = [value]
        items = prop.get('items')
        if isinstance(items, dict):
            value = [_validate_value(name, items, item) for item in value]
    elif expected == 'object':
        if not isinstance(value, dict):
            raise ToolError(f'"{name}" must be an object')

    if expected and expected not in _TYPE_CHECKS:
        return value
    if expected and not _TYPE_CHECKS[expected](value):
        raise ToolError(f'"{name}" must be a {expected}')

    if 'enum' in prop and value not in prop['enum']:
        raise ToolError('"{}" must be one of: {}'.format(name, ', '.join(map(str, prop['enum']))))
    if 'minimum' in prop and isinstance(value, (int, float)) and value < prop['minimum']:
        raise ToolError(f'"{name}" must be >= {prop["minimum"]}')
    if 'maximum' in prop and isinstance(value, (int, float)) and value > prop['maximum']:
        raise ToolError(f'"{name}" must be <= {prop["maximum"]}')
    if 'minLength' in prop and isinstance(value, str) and len(value) < prop['minLength']:
        raise ToolError(f'"{name}" must have at least {prop["minLength"]} characters')
    return value


def _coerce_number(name, value, integer):
    if isinstance(value, bool):
        raise ToolError(f'"{name}" must be a number')
    if isinstance(value, str):
        try:
            value = float(value) if not integer else int(float(value))
        except ValueError:
            raise ToolError(f'"{name}" must be a number')
    if integer:
        if isinstance(value, float):
            if not float(value).is_integer():
                raise ToolError(f'"{name}" must be an integer')
            value = int(value)
        elif not isinstance(value, int):
            raise ToolError(f'"{name}" must be an integer')
    elif not isinstance(value, (int, float)):
        raise ToolError(f'"{name}" must be a number')
    return value


def _coerce_bool(name, value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ('true', '1', 'yes', 'on'):
            return True
        if lowered in ('false', '0', 'no', 'off'):
            return False
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise ToolError(f'"{name}" must be a boolean')


def tool_doc(name):
    """Debug helper: the schema of one tool."""
    registered = _TOOLS.get(name)
    return registered.input_schema if registered else None

"""Hand-written Model Context Protocol (JSON-RPC 2.0) core.

This module implements just enough of the MCP specification to be a *server*:
``initialize``, ``tools/list``, ``tools/call``, ``resources/list``,
``resources/read`` and ``ping``. It has no third-party dependency (the official
MCP SDK requires Python 3.10+, Pygame Studio still ships 3.9), so the protocol
is spelled out here instead of being imported.

References: MCP 2025-06-18 (tools/resources/lifecycle) over JSON-RPC 2.0.
"""

import json

#: Protocol revision this server implements (see MCP changelog).
PROTOCOL_VERSION = '2025-06-18'

#: Revisions the server accepts from a client (newest first).
SUPPORTED_PROTOCOL_VERSIONS = ('2025-06-18', '2025-03-26', '2024-11-05')

SERVER_NAME = 'pygamestudio'
SERVER_VERSION = '1.0.0'

# JSON-RPC 2.0 error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class JsonRpcError(Exception):
    """An error that is reported back to the client as a JSON-RPC error."""

    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_dict(self, request_id=None):
        error = {'code': self.code, 'message': self.message}
        if self.data is not None:
            error['data'] = self.data
        return {'jsonrpc': '2.0', 'id': request_id, 'error': error}


def parse_message(raw):
    """Parse one JSON-RPC message.

    Returns the decoded dict; raises :class:`JsonRpcError` when the payload is
    not valid JSON or not a well-formed JSON-RPC request/notification. Batch
    requests (arrays) are rejected on purpose: the MCP spec removed them.
    """
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode('utf-8')
        except UnicodeDecodeError as e:
            raise JsonRpcError(PARSE_ERROR, 'Invalid UTF-8 payload', str(e))

    try:
        message = json.loads(raw)
    except (TypeError, ValueError) as e:
        raise JsonRpcError(PARSE_ERROR, 'Parse error', str(e))

    if isinstance(message, list):
        raise JsonRpcError(INVALID_REQUEST, 'Batch requests are not supported')
    if not isinstance(message, dict):
        raise JsonRpcError(INVALID_REQUEST, 'The message must be a JSON object')
    if message.get('jsonrpc') != '2.0':
        raise JsonRpcError(INVALID_REQUEST, "The 'jsonrpc' member must be '2.0'")
    if 'method' not in message or not isinstance(message['method'], str):
        raise JsonRpcError(INVALID_REQUEST, "The 'method' member must be a string")

    params = message.get('params')
    if params is not None and not isinstance(params, (dict, list)):
        raise JsonRpcError(INVALID_PARAMS, "The 'params' member must be an object or an array")
    return message


def is_notification(message) -> bool:
    """True for a JSON-RPC notification (no id, so no response is expected)."""
    return 'id' not in message or message['id'] is None


def make_result(request_id, result):
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def make_error(request_id, code, message, data=None):
    return JsonRpcError(code, message, data).to_dict(request_id)


def text_content(text):
    """One MCP text content block."""
    return {'type': 'text', 'text': text}


def image_content(png_bytes, mime_type='image/png'):
    """One MCP image content block (base64, as the spec requires)."""
    import base64
    return {'type': 'image', 'data': base64.b64encode(png_bytes).decode('ascii'),
            'mimeType': mime_type}


def to_json_text(value, indent=2):
    """Render any JSON-serialisable value as the text of a tool result."""
    try:
        return json.dumps(value, indent=indent, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)

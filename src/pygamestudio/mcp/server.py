"""HTTP transport of the MCP server (standard library only).

A ``ThreadingHTTPServer`` bound to ``127.0.0.1`` serves one JSON-RPC endpoint:

* ``POST /mcp`` - one JSON-RPC request or notification per call, answered with
  ``application/json`` (allowed by the Streamable HTTP transport: a server MAY
  answer a single request with a JSON body instead of an SSE stream).
* ``GET /mcp`` - a small JSON status document (handy to check the server from a
  browser or a script; MCP clients use POST).
* ``GET /healthz`` - plain 'ok'.

Access control: the socket only listens on the loopback interface, and every
request has to carry the token when one is configured
(``Authorization: Bearer <token>`` or ``?token=<token>``).
"""

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pygamestudio.mcp import protocol
from pygamestudio.mcp.bridge import bridge
from pygamestudio.mcp.protocol import (
    INVALID_REQUEST, METHOD_NOT_FOUND, JsonRpcError, make_error, make_result,
)
from pygamestudio.mcp.registry import (
    INSTRUCTIONS, call_tool, list_resources, list_tools, read_resource,
)

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8765

#: Requests bigger than this are refused (a scene patch stays far below).
MAX_BODY_BYTES = 4 * 1024 * 1024


class _Handler(BaseHTTPRequestHandler):
    server_version = 'PygameStudioMCP/{}'.format(protocol.SERVER_VERSION)
    protocol_version = 'HTTP/1.1'

    # ------------------------------------------------------------- plumbing
    def log_message(self, format, *args):  # noqa: A002 - BaseHTTPRequestHandler API
        """Keep the console clean: only report problems."""
        if args and str(args[1]).startswith(('4', '5')):
            self.server.log('{} {}'.format(self.address_string(), format % args))

    def _send_json(self, payload, status=200, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200, content_type='text/plain; charset=utf-8'):
        body = text.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        token = getattr(self.server, 'token', '')
        if not token:
            return True
        header = self.headers.get('Authorization', '')
        if header.startswith('Bearer ') and secrets.compare_digest(header[7:].strip(), token):
            return True
        query = self.path.split('?', 1)[1] if '?' in self.path else ''
        for part in query.split('&'):
            if part.startswith('token='):
                if secrets.compare_digest(part[6:], token):
                    return True
        return False

    def _body_length(self) -> int:
        try:
            return int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return 0

    def _drain_body(self):
        """Read the request body that is about to be answered with an error.

        Answering without reading the body leaves unread bytes in the socket;
        closing it then makes the client see a reset connection (Windows turns
        that into "connection aborted") instead of the error we just sent.
        """
        length = self._body_length()
        if 0 < length <= MAX_BODY_BYTES:
            try:
                self.rfile.read(length)
            except OSError:
                pass

    # -------------------------------------------------------------- methods
    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split('?', 1)[0].rstrip('/') or '/'
        if path == '/healthz':
            return self._send_text('ok')
        if path in ('/mcp', '/'):
            if not self._authorized():
                return self._send_json({'error': 'unauthorized'}, status=401)
            return self._send_json({
                'name': protocol.SERVER_NAME,
                'version': protocol.SERVER_VERSION,
                'protocolVersion': protocol.PROTOCOL_VERSION,
                'endpoint': 'POST /mcp (JSON-RPC 2.0)',
                'editorAttached': bridge.is_attached,
                'projectReady': bridge.is_project_ready,
                'tools': len(list_tools()),
                'resources': len(list_resources()),
            })
        return self._send_json({'error': 'not found'}, status=404)

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split('?', 1)[0].rstrip('/') or '/'
        if path not in ('/mcp', '/'):
            self._drain_body()
            return self._send_json({'error': 'not found'}, status=404)
        if not self._authorized():
            self._drain_body()
            return self._send_json({'error': 'unauthorized'}, status=401)

        length = self._body_length()
        if length <= 0:
            return self._send_json(
                make_error(None, INVALID_REQUEST, 'Empty request body'), status=400)
        if length > MAX_BODY_BYTES:
            self.close_connection = True
            return self._send_json(
                make_error(None, INVALID_REQUEST, 'Request body too large'), status=413)

        raw = self.rfile.read(length)
        response = self._handle_message(raw)

        if response is None:
            # A notification: the spec asks for 202 with no content.
            self.send_response(202)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self._send_json(response)

    # ------------------------------------------------------------- protocol
    def _handle_message(self, raw):
        """Turn one raw JSON-RPC message into the response dict (or None)."""
        try:
            message = protocol.parse_message(raw)
        except JsonRpcError as e:
            return e.to_dict(None)

        request_id = message.get('id')
        is_notification = protocol.is_notification(message)
        method = message['method']
        params = message.get('params') or {}
        if isinstance(params, list):  # positional params are not used by MCP
            params = {}

        try:
            result = self._dispatch(method, params)
        except JsonRpcError as e:
            if is_notification:
                return None
            return e.to_dict(request_id)
        except Exception as e:  # noqa: BLE001 - a bug in a tool must not kill the server
            self.server.log('internal error in {}: {}'.format(method, e))
            if is_notification:
                return None
            return make_error(request_id, protocol.INTERNAL_ERROR, str(e))

        if is_notification:
            return None
        return make_result(request_id, result)

    def _dispatch(self, method, params):
        if method == 'initialize':
            client_version = params.get('protocolVersion')
            version = (client_version if client_version in protocol.SUPPORTED_PROTOCOL_VERSIONS
                       else protocol.PROTOCOL_VERSION)
            return {
                'protocolVersion': version,
                'capabilities': {
                    'tools': {'listChanged': False},
                    'resources': {'subscribe': False, 'listChanged': False},
                    'logging': {},
                },
                'serverInfo': {
                    'name': protocol.SERVER_NAME,
                    'version': protocol.SERVER_VERSION,
                    'title': 'Pygame Studio editor',
                },
                'instructions': INSTRUCTIONS,
            }
        if method in ('notifications/initialized', 'initialized', 'notifications/cancelled',
                      'notifications/roots/list_changed'):
            return {}
        if method == 'ping':
            return {}
        if method == 'tools/list':
            return {'tools': list_tools()}
        if method == 'tools/call':
            name = params.get('name')
            if not name:
                raise JsonRpcError(protocol.INVALID_PARAMS, "tools/call needs a 'name'")
            return call_tool(name, params.get('arguments') or {})
        if method == 'resources/list':
            return {'resources': list_resources()}
        if method == 'resources/read':
            uri = params.get('uri')
            if not uri:
                raise JsonRpcError(protocol.INVALID_PARAMS, "resources/read needs a 'uri'")
            try:
                return read_resource(uri)
            except Exception as e:  # noqa: BLE001 - report as a JSON-RPC error
                raise JsonRpcError(protocol.INVALID_PARAMS, str(e))
        if method == 'prompts/list':
            return {'prompts': []}
        if method == 'logging/setLevel':
            return {}
        raise JsonRpcError(METHOD_NOT_FOUND, 'Method not found: {}'.format(method))


class MCPServerThread(threading.Thread):
    """The HTTP server running in a background thread."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, token=''):
        super().__init__(name='pygamestudio-mcp', daemon=True)
        self._httpd = None
        self._host = host
        self._port = port
        self._token = token

    def start(self):  # noqa: D102 - threading.Thread API
        self._httpd = ThreadingHTTPServer((self._host, self._port), _Handler)
        self._httpd.token = self._token
        self._httpd.log = lambda message: _log(message)
        self._httpd.daemon_threads = True
        super().start()

    def run(self):  # noqa: D102 - threading.Thread API
        _log('MCP server listening on http://{}:{}/mcp'.format(self._host, self.port))
        self._httpd.serve_forever(poll_interval=0.2)

    @property
    def port(self) -> int:
        """The bound port (useful when port 0 was requested for a free port)."""
        return self._httpd.server_address[1] if self._httpd is not None else self._port

    @property
    def url(self) -> str:
        return 'http://{}:{}/mcp'.format(self._host, self.port)

    def stop(self):
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        _log('MCP server stopped')


# ------------------------------------------------------------------ module API
_server = None
_lock = threading.RLock()


def _log(message):
    """Log through the editor console when it is available, else stderr."""
    try:
        from pygamestudio.gui.console.logger import Logger
        Logger.info(message)
    except Exception:  # pragma: no cover - headless mode
        import sys
        print('[mcp] {}'.format(message), file=sys.stderr)


def start_server(host=DEFAULT_HOST, port=DEFAULT_PORT, token='', force=False) -> dict:
    """Start the MCP HTTP server (idempotent unless ``force``).

    Returns a dict with the endpoint URL, the token and the tool count.
    """
    global _server
    with _lock:
        if _server is not None:
            if not force:
                return server_info()
            stop_server()
        if token is None:
            token = ''
        server = MCPServerThread(host=host, port=int(port or 0), token=token)
        server.start()
        _server = server
        return server_info()


def stop_server():
    global _server
    with _lock:
        if _server is None:
            return False
        _server.stop()
        _server = None
        return True


def is_running() -> bool:
    with _lock:
        return _server is not None and _server.is_alive()


def server_info() -> dict:
    """Current state of the server (safe to call at any time)."""
    with _lock:
        running = _server is not None and _server.is_alive()
        return {
            'running': running,
            'url': _server.url if running else None,
            'host': _server._host if _server is not None else DEFAULT_HOST,  # noqa: SLF001
            'port': _server.port if _server is not None else DEFAULT_PORT,
            'token': _server._token if _server is not None else '',  # noqa: SLF001
            'editor_attached': bridge.is_attached,
            'project_ready': bridge.is_project_ready,
            'tools': len(list_tools()),
            'resources': len(list_resources()),
            'protocol_version': protocol.PROTOCOL_VERSION,
        }

"""stdio bridge: lets clients that spawn a process talk to the running editor.

MCP over stdio is one JSON-RPC message per line on stdin/stdout. The actual
editor lives in another process, so this bridge simply forwards each message to
the editor's local HTTP endpoint and writes the answer back:

    pygs mcp                 # uses the port/token from the editor settings
    pygs mcp --url http://127.0.0.1:8765/mcp --token ABC

Nothing else may be written to stdout (that would corrupt the protocol), so all
messages of this module go to stderr.
"""

import json
import sys
import urllib.error
import urllib.request

from pygamestudio.mcp.server import DEFAULT_HOST, DEFAULT_PORT

_TIMEOUT = 120.0


def _stderr(message):
    print('[pygs-mcp] {}'.format(message), file=sys.stderr, flush=True)


def editor_endpoint(url='', token=''):
    """Find the running editor's MCP endpoint (explicit values win)."""
    port, stored_token = DEFAULT_PORT, ''
    try:
        from pygamestudio.common.utils.config import get_editor_config
        config = get_editor_config()
        port = int(config.get('mcp_port') or DEFAULT_PORT)
        stored_token = str(config.get('mcp_token') or '')
    except Exception as e:  # noqa: BLE001 - the editor config may not exist at all
        _stderr('could not read the editor settings ({}); using the default port'.format(e))

    if not url:
        url = 'http://{}:{}/mcp'.format(DEFAULT_HOST, port)
    return url, (token or stored_token)


def _post(url, token, payload, timeout=_TIMEOUT):
    request = urllib.request.Request(
        url, data=payload.encode('utf-8'), method='POST',
        headers={'Content-Type': 'application/json',
                 'Accept': 'application/json, text/event-stream',
                 'User-Agent': 'pygamestudio-mcp-bridge'})
    if token:
        request.add_header('Authorization', 'Bearer {}'.format(token))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        if not body:
            return None
        return json.loads(body.decode('utf-8'))


def run_stdio(url='', token='', timeout=_TIMEOUT):
    """Forward stdin -> editor HTTP -> stdout until stdin is closed."""
    endpoint, token = editor_endpoint(url, token)
    _stderr('Proxying MCP to {}'.format(endpoint))

    for line in sys.stdin:
        message = line.strip()
        if not message:
            continue
        try:
            payload = json.loads(message)
        except ValueError as e:
            _stderr('ignoring a line that is not JSON: {}'.format(e))
            continue

        try:
            answer = _post(endpoint, token, message, timeout=timeout)
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', errors='replace')
            _stderr('HTTP {} from the editor: {}'.format(e.code, detail))
            answer = _error_for(payload, 'The editor answered HTTP {}: {}'.format(e.code, detail))
        except urllib.error.URLError as e:
            _stderr('the editor is not reachable: {}'.format(e))
            answer = _error_for(
                payload,
                'Pygame Studio is not running (or its MCP server is off): {}. '
                'Start the editor and enable the MCP server in the editor settings.'.format(e))
        except Exception as e:  # noqa: BLE001 - never crash the bridge
            _stderr('request failed: {}'.format(e))
            answer = _error_for(payload, str(e))

        if answer is not None:
            sys.stdout.write(json.dumps(answer, ensure_ascii=False) + '\n')
            sys.stdout.flush()


def _error_for(payload, message):
    """An MCP error answer for a request (notifications get no answer)."""
    if not isinstance(payload, dict) or 'id' not in payload or payload.get('id') is None:
        return None
    return {'jsonrpc': '2.0', 'id': payload['id'],
            'error': {'code': -32000, 'message': message}}

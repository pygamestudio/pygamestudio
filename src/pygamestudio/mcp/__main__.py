"""Command line entry point for the MCP server.

    pygs mcp                      # stdio bridge to the running editor (default)
    pygs mcp --serve              # run the HTTP server in this process
    pygs mcp --serve --port 0     # ... on a free port, printed to stdout
    pygs mcp --url http://... --token ...   # bridge to an explicit endpoint

Only ``--serve`` needs no editor: it is meant for tests and for hosting the
tools of a *headless* session (most tools then report that no project is open).
"""

import argparse
import json
import sys


def build_parser():
    parser = argparse.ArgumentParser(
        prog='pygs mcp',
        description='Pygame Studio MCP server / stdio bridge')
    parser.add_argument('--serve', action='store_true',
                        help='run the HTTP MCP server in this process instead of bridging')
    parser.add_argument('--host', default='127.0.0.1', help='host to bind (default 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8765,
                        help='port to bind; 0 picks a free one (default 8765)')
    parser.add_argument('--token', default='', help='require this bearer token')
    parser.add_argument('--url', default='', help='bridge: editor MCP url (default: from settings)')
    parser.add_argument('--timeout', type=float, default=120.0,
                        help='bridge: seconds to wait for the editor (default 120)')
    parser.add_argument('--open', action='store_true',
                        help='serve: launch the editor as well (not implemented yet)')
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.serve:
        from pygamestudio.mcp.server import start_server
        info = start_server(host=args.host, port=args.port, token=args.token, force=True)
        print(json.dumps(info, ensure_ascii=False))
        try:
            import time
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            from pygamestudio.mcp.server import stop_server
            stop_server()
        return 0

    from pygamestudio.mcp.stdio import run_stdio
    run_stdio(url=args.url, token=args.token, timeout=args.timeout)
    return 0


if __name__ == '__main__':
    sys.exit(main())

"""Engram CLI entry point. Run with: python -m engram serve"""

import argparse
import sys
from engram.config import EngramConfig


def main():
    parser = argparse.ArgumentParser(prog="engram", description="Engram Memory Engine")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    serve_parser = subparsers.add_parser("serve", help="Start the Engram server")
    serve_parser.add_argument("--host", default=None, help="Bind host")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port")
    serve_parser.add_argument("--config", default=None, help="Path to TOML config file")

    args = parser.parse_args()

    if args.command == "serve":
        if args.config:
            config = EngramConfig.from_toml(args.config)
        else:
            config = EngramConfig()

        host = args.host or config.server_host
        port = args.port or config.server_port

        from engram.server.app import create_app
        import uvicorn

        app = create_app(config)
        print(f"Engram v0.1.0")
        print(f"Starting server at http://{host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

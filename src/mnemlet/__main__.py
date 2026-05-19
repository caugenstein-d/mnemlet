"""Mnemlet CLI entry point. Run with: python -m mnemlet serve"""

import argparse
import sys
from mnemlet.config import MnemletConfig


def main():
    parser = argparse.ArgumentParser(prog="mnemlet", description="Mnemlet Memory Engine")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    serve_parser = subparsers.add_parser("serve", help="Start the Mnemlet server")
    serve_parser.add_argument("--host", default=None, help="Bind host")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port")
    serve_parser.add_argument("--config", default=None, help="Path to TOML config file")

    args = parser.parse_args()

    if args.command == "serve":
        if args.config:
            config = MnemletConfig.from_toml(args.config)
        else:
            config = MnemletConfig()

        host = args.host or config.server_host
        port = args.port or config.server_port

        from mnemlet.server.app import create_app
        import uvicorn

        app = create_app(config)
        print(f"Mnemlet v0.1.0")
        print(f"Starting server at http://{host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

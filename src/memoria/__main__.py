"""Memoria CLI entry point. Run with: python -m memoria serve"""

import argparse
import sys
from memoria.config import MemoriaConfig


def main():
    parser = argparse.ArgumentParser(prog="memoria", description="Memoria Memory Engine")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    serve_parser = subparsers.add_parser("serve", help="Start the Memoria server")
    serve_parser.add_argument("--host", default=None, help="Bind host")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port")
    serve_parser.add_argument("--config", default=None, help="Path to TOML config file")

    args = parser.parse_args()

    if args.command == "serve":
        if args.config:
            config = MemoriaConfig.from_toml(args.config)
        else:
            config = MemoriaConfig()

        host = args.host or config.server_host
        port = args.port or config.server_port

        from memoria.server.app import create_app
        import uvicorn

        app = create_app(config)
        print(f"Memoria v0.1.0")
        print(f"Starting server at http://{host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

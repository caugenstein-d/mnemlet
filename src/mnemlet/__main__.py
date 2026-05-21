"""Mnemlet CLI entry point. Run with: python -m mnemlet serve"""

import argparse
import sys
from pathlib import Path

from mnemlet.config import MnemletConfig


def main():
    parser = argparse.ArgumentParser(prog="mnemlet", description="Mnemlet Memory Engine")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    serve_parser = subparsers.add_parser("serve", help="Start the Mnemlet server")
    serve_parser.add_argument("--host", default=None, help="Bind host")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port")
    serve_parser.add_argument("--config", default=None, help="Path to TOML config file")

    benchmark_parser = subparsers.add_parser("benchmark", help="Run Mnemlet benchmarks")
    benchmark_subparsers = benchmark_parser.add_subparsers(dest="benchmark_mode", help="Benchmark modes")
    benchmark_mode_parsers = {}
    for mode in ("quick", "full"):
        mode_parser = benchmark_subparsers.add_parser(mode, help=f"Run {mode} benchmark")
        benchmark_mode_parsers[mode] = mode_parser
        mode_parser.add_argument("--dataset", default="public", help="Benchmark dataset")
        mode_parser.add_argument("--output", default="benchmark-results/latest", help="Output directory")
        mode_parser.add_argument("--format", default="json,md,csv", help="Comma-separated report formats")
        mode_parser.add_argument("--min-score", type=float, default=0.1, help="Minimum recall score")
        mode_parser.add_argument("--limit", type=int, default=5, help="Recall result limit")
        mode_parser.add_argument("--include-adapters", action="store_true", help="Run safe adapter-level checks")
        mode_parser.add_argument("--include-live-opencode", action="store_true", help="Reserved for live OpenCode checks")
        mode_parser.add_argument("--include-live-openwebui", action="store_true", help="Reserved for live OpenWebUI checks")
        mode_parser.add_argument("--retrieval-only", action="store_true", help="Run only retrieval checks")

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
    elif args.command == "benchmark":
        if args.benchmark_mode is None:
            benchmark_parser.print_help()
            sys.exit(1)

        from mnemlet.benchmark.datasets import load_dataset
        from mnemlet.benchmark.reports import environment_info, new_run_id, write_reports
        from mnemlet.benchmark.runner import run_retrieval_benchmark

        formats = _parse_benchmark_formats(args.format, benchmark_mode_parsers[args.benchmark_mode])
        output_dir = Path(args.output)
        dataset = load_dataset(args.dataset, root=Path.cwd())
        result = run_retrieval_benchmark(
            dataset,
            output_dir=output_dir,
            limit=args.limit,
            min_score=args.min_score,
        )
        result["run_id"] = new_run_id()
        result["mode"] = args.benchmark_mode
        result["command"] = " ".join(["mnemlet", *sys.argv[1:]])
        result["environment"] = environment_info()

        if args.include_adapters and not args.retrieval_only:
            from mnemlet.benchmark.adapters import run_adapter_checks, summarize_adapter_results

            adapter_results = run_adapter_checks()
            result["adapter_results"] = adapter_results
            result["summary"].update(summarize_adapter_results(adapter_results))

        paths = write_reports(result, output_dir, formats=formats)

        print(f"Benchmark complete: {result['query_count']} queries")
        for report_format, path in paths.items():
            print(f"{report_format}: {path}")
    else:
        parser.print_help()
        sys.exit(1)


def _parse_benchmark_formats(value: str, parser: argparse.ArgumentParser) -> tuple[str, ...]:
    formats = tuple(item.strip() for item in value.split(",") if item.strip())
    supported_formats = {"json", "md", "csv"}
    unsupported_formats = sorted(set(formats) - supported_formats)
    if not formats:
        parser.error("invalid --format: at least one format is required")
    if unsupported_formats:
        parser.error(
            "unsupported --format value(s): "
            + ", ".join(unsupported_formats)
            + "; supported formats are json, md, csv"
        )
    return formats


if __name__ == "__main__":
    main()

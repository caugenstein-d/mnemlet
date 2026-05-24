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
    for mode in ("quick", "full", "quality"):
        mode_parser = benchmark_subparsers.add_parser(mode, help=f"Run {mode} benchmark")
        benchmark_mode_parsers[mode] = mode_parser
        _add_benchmark_common_args(mode_parser)
        if mode in {"quick", "full"}:
            _add_retrieval_benchmark_args(mode_parser)
        if mode == "full":
            _add_live_benchmark_args(mode_parser)

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

        from mnemlet.benchmark.reports import environment_info, new_run_id, write_reports

        formats = _parse_benchmark_formats(args.format, benchmark_mode_parsers[args.benchmark_mode])
        output_dir = Path(args.output)

        if args.benchmark_mode == "quality":
            from mnemlet.benchmark.datasets import load_quality_dataset
            from mnemlet.benchmark.quality import run_quality_benchmark

            dataset = load_quality_dataset(args.dataset, root=Path.cwd())
            result = run_quality_benchmark(dataset, output_dir=output_dir)
        else:
            from mnemlet.benchmark.datasets import load_dataset
            from mnemlet.benchmark.runner import run_retrieval_benchmark

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

        if args.benchmark_mode != "quality" and args.include_adapters and not args.retrieval_only:
            from mnemlet.benchmark.adapters import run_adapter_checks, summarize_adapter_results

            adapter_results = run_adapter_checks()
            result["adapter_results"] = adapter_results
            result["summary"].update(summarize_adapter_results(adapter_results))

        if args.benchmark_mode == "full":
            from mnemlet.benchmark.live import run_live_checks

            if args.retrieval_only:
                result["live_results"] = []
            else:
                result["live_results"] = run_live_checks(
                    include_opencode=args.include_live_opencode,
                    include_openwebui=args.include_live_openwebui,
                )

        paths = write_reports(result, output_dir, formats=formats)

        if args.benchmark_mode == "quality":
            print(f"Benchmark complete: {result['scenario_count']} scenarios")
        else:
            print(f"Benchmark complete: {result['query_count']} queries")
        for report_format, path in paths.items():
            print(f"{report_format}: {path}")
    else:
        parser.print_help()
        sys.exit(1)


def _add_benchmark_common_args(mode_parser: argparse.ArgumentParser) -> None:
    mode_parser.add_argument("--dataset", default="public", help="Benchmark dataset")
    mode_parser.add_argument("--output", default="benchmark-results/latest", help="Output directory")
    mode_parser.add_argument("--format", default="json,md,csv", help="Comma-separated report formats")


def _add_retrieval_benchmark_args(mode_parser: argparse.ArgumentParser) -> None:
    mode_parser.add_argument("--min-score", type=float, default=0.1, help="Minimum recall score")
    mode_parser.add_argument("--limit", type=int, default=5, help="Recall result limit")
    mode_parser.add_argument("--include-adapters", action="store_true", help="Run safe adapter-level checks")
    mode_parser.add_argument("--retrieval-only", action="store_true", help="Run only retrieval checks")


def _add_live_benchmark_args(mode_parser: argparse.ArgumentParser) -> None:
    mode_parser.add_argument("--include-live-opencode", action="store_true", help="Run opt-in live OpenCode checks in full mode")
    mode_parser.add_argument("--include-live-openwebui", action="store_true", help="Run opt-in live OpenWebUI checks in full mode")


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

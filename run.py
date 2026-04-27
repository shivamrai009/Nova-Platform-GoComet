from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_command(command: list[str], *, extra_env: dict[str, str] | None = None) -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    if extra_env:
        env.update(extra_env)

    process = subprocess.run(command, cwd=ROOT, env=env)
    return process.returncode


def command_serve(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        cmd.append("--reload")
    return run_command(cmd)


def command_demo(_: argparse.Namespace) -> int:
    cmd = [sys.executable, "scripts/run_demo.py"]
    return run_command(cmd)


def command_test(_: argparse.Namespace) -> int:
    cmd = [sys.executable, "-m", "pytest", "-q"]
    try:
        return run_command(cmd)
    except Exception as error:
        print(f"Unable to run tests: {error}")
        print("Install pytest in your environment first, then rerun: pip install pytest")
        return 1


def command_check(_: argparse.Namespace) -> int:
    checks: list[tuple[str, list[str]]] = [
        ("health endpoint", [sys.executable, "-c", "from app.main import app; print('ok' if app else 'fail')"]),
        ("demo import", [sys.executable, "-c", "from scripts.run_demo import main; print('ok')"]),
    ]

    for label, cmd in checks:
        code = run_command(cmd)
        if code != 0:
            print(f"Check failed: {label}")
            return code
        print(f"Check passed: {label}")

    print("All quick checks passed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Nova Platform runner for serve/demo/test/check tasks.",
    )
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="Run FastAPI app with uvicorn.")
    serve.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    serve.add_argument("--port", default=8000, type=int, help="Port to bind.")
    serve.add_argument("--reload", action="store_true", help="Enable auto-reload for development.")
    serve.set_defaults(handler=command_serve)

    demo = subparsers.add_parser("demo", help="Run CLI demo over sample docs.")
    demo.set_defaults(handler=command_demo)

    test = subparsers.add_parser("test", help="Run test suite (pytest).")
    test.set_defaults(handler=command_test)

    check = subparsers.add_parser("check", help="Run quick import/health checks.")
    check.set_defaults(handler=command_check)

    return parser


def main() -> int:
    if len(sys.argv) == 1:
        sys.argv.append("serve")
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "handler"):
        parser.print_help()
        return 1
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

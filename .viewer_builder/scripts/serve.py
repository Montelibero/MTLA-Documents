#!/usr/bin/env python3

from __future__ import annotations

import argparse
import http.server
import socketserver
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / ".viewer_builder" / "config.yml"


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class PrefixAwareHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, base_path: str, **kwargs):
        self._base_path = base_path.rstrip("/")
        super().__init__(*args, directory=directory, **kwargs)

    def guess_type(self, path: str) -> str:
        content_type = super().guess_type(path)
        if content_type.startswith("text/") and "charset=" not in content_type:
            return f"{content_type}; charset=utf-8"
        if content_type in {"application/json", "application/javascript"}:
            return f"{content_type}; charset=utf-8"
        return content_type

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        if self._base_path and self.path.startswith(self._base_path + "/"):
            self.path = self.path[len(self._base_path):]
        elif self._base_path and self.path == self._base_path:
            self.path = "/"
        super().do_GET()

    def do_HEAD(self):
        if self._base_path and self.path.startswith(self._base_path + "/"):
            self.path = self.path[len(self._base_path):]
        elif self._base_path and self.path == self._base_path:
            self.path = "/"
        super().do_HEAD()


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the generated viewer locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    config = load_config()
    output_dir = ROOT / config.get("output_dir", ".viewer_builder/.output/site")
    base_path = str(config.get("site_base_path", "") or "")

    if not output_dir.exists():
        print(f"Build output not found: {output_dir}", file=sys.stderr)
        print("Run `python3 .viewer_builder/scripts/build.py` first.", file=sys.stderr)
        return 1

    handler = lambda *handler_args, **handler_kwargs: PrefixAwareHandler(  # noqa: E731
        *handler_args,
        directory=str(output_dir),
        base_path=base_path,
        **handler_kwargs,
    )

    with ReusableTCPServer((args.host, args.port), handler) as httpd:
        prefix = f"{base_path.rstrip('/')}/" if base_path else "/"
        print(f"Serving {output_dir}")
        print(f"Open http://{args.host}:{args.port}{prefix}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

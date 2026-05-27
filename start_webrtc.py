#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start mediamtx + RTSP publisher (WebRTC viewer).")
    parser.add_argument("--config", default="config.json", help="Path to streamer config")
    parser.add_argument(
        "--mediamtx-bin",
        default="bin/mediamtx",
        help="Path to mediamtx binary (default: bin/mediamtx)",
    )
    parser.add_argument(
        "--mediamtx-config",
        default="mediamtx.yml",
        help="Path to mediamtx config (default: mediamtx.yml)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parent

    config_path = (root / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    if not config_path.exists():
        print(f"[supervisor] config not found: {config_path}", file=sys.stderr)
        return 1

    mediamtx_path = (root / args.mediamtx_bin).resolve()
    if not mediamtx_path.exists():
        print(
            f"[supervisor] mediamtx binary not found at {mediamtx_path}\n"
            "Download mediamtx for your Pi and place it at bin/mediamtx (chmod +x).",
            file=sys.stderr,
        )
        return 1

    if shutil.which("ffmpeg") is None:
        print("[supervisor] ffmpeg not found. Install ffmpeg first.", file=sys.stderr)
        return 1

    stopping = False

    def handle_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    mediamtx_cmd = [
        str(mediamtx_path),
        str((root / args.mediamtx_config).resolve()),
    ]
    publisher_cmd = [
        sys.executable,
        str(root / "streamer_webrtc.py"),
        "--config",
        str(config_path),
    ]

    mediamtx_proc = subprocess.Popen(mediamtx_cmd, env=os.environ.copy())
    print(f"[supervisor] started mediamtx pid={mediamtx_proc.pid}")
    time.sleep(0.5)

    publisher_proc = subprocess.Popen(publisher_cmd, env=os.environ.copy())
    print(f"[supervisor] started publisher pid={publisher_proc.pid}")

    print("[supervisor] Open the mediamtx WebRTC page at:")
    print("[supervisor]   http://<pi-ip>:8889")
    print("[supervisor] Then select/play the 'basicstream' path.")

    try:
        while not stopping:
            if mediamtx_proc.poll() is not None:
                print(f"[supervisor] mediamtx exited code={mediamtx_proc.returncode}")
                return mediamtx_proc.returncode or 1
            if publisher_proc.poll() is not None:
                print(f"[supervisor] publisher exited code={publisher_proc.returncode}")
                return publisher_proc.returncode or 1
            time.sleep(0.1)
    finally:
        for name, proc in [("publisher", publisher_proc), ("mediamtx", mediamtx_proc)]:
            if proc.poll() is None:
                print(f"[supervisor] stopping {name} pid={proc.pid}")
                proc.terminate()
        time.sleep(0.5)
        for name, proc in [("publisher", publisher_proc), ("mediamtx", mediamtx_proc)]:
            if proc.poll() is None:
                print(f"[supervisor] killing {name} pid={proc.pid}")
                proc.kill()
        print("[supervisor] stopped")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


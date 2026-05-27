#!/usr/bin/env python3
"""
Publish Pi Camera H.264 to RTSP (mediamtx -> WebRTC).

Power/CPU goal: no re-encode.
- picamera2 encodes H.264 in hardware
- ffmpeg remuxes (copy) into RTSP over TCP
"""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

PROFILE_DEFAULTS: dict[str, dict[str, int]] = {
    "low_power": {"fps": 10, "bitrate": 800_000, "intra_period": 20},
    "balanced": {"fps": 12, "bitrate": 1_000_000, "intra_period": 24},
    "high_quality": {"fps": 15, "bitrate": 1_500_000, "intra_period": 30},
}


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. Copy config.example.json to config.json first."
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def merged_settings(config: dict[str, Any]) -> dict[str, Any]:
    profile_name = config.get("profile", "low_power")
    if profile_name not in PROFILE_DEFAULTS:
        raise ValueError(
            f"Unknown profile '{profile_name}'. Expected one of: {', '.join(PROFILE_DEFAULTS)}"
        )

    defaults = PROFILE_DEFAULTS[profile_name]
    camera_cfg = config.get("camera", {})
    encoder_cfg = config.get("encoder", {})
    rtsp_cfg = config.get("rtsp", {})

    return {
        "profile": profile_name,
        "width": int(camera_cfg.get("width", 1280)),
        "height": int(camera_cfg.get("height", 720)),
        "fps": int(camera_cfg.get("fps", defaults["fps"])),
        "bitrate": int(encoder_cfg.get("bitrate", defaults["bitrate"])),
        "intra_period": int(encoder_cfg.get("intra_period", defaults["intra_period"])),
        "rtsp_url": str(rtsp_cfg.get("url", "rtsp://127.0.0.1:8554/basicstream")),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish H.264 to RTSP for WebRTC viewing.")
    parser.add_argument("--config", default="config.json", help="Path to JSON config file")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    s = merged_settings(load_config(Path(args.config)))

    print(
        "Starting RTSP publisher profile={profile} size={width}x{height} fps={fps} "
        "bitrate={bitrate} rtsp={rtsp_url}".format(**s)
    )

    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-f",
        "h264",
        "-i",
        "-",
        "-c:v",
        "copy",
        "-an",
        "-f",
        "rtsp",
        "-rtsp_transport",
        "tcp",
        s["rtsp_url"],
    ]

    ffmpeg_proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    if ffmpeg_proc.stdin is None:
        raise RuntimeError("Failed to open ffmpeg stdin for RTSP output")

    picam2 = Picamera2()
    video_config = picam2.create_video_configuration(
        main={"size": (s["width"], s["height"]), "format": "YUV420"},
        controls={"FrameRate": float(s["fps"])},
    )
    picam2.configure(video_config)

    encoder = H264Encoder(bitrate=s["bitrate"], iperiod=s["intra_period"])
    output = FileOutput(ffmpeg_proc.stdin)

    stop_requested = False

    def _signal_handler(_signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    picam2.start()
    picam2.start_recording(encoder, output)

    try:
        while not stop_requested:
            time.sleep(0.5)
    finally:
        picam2.stop_recording()
        picam2.stop()
        ffmpeg_proc.stdin.close()
        ffmpeg_proc.terminate()
        try:
            ffmpeg_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ffmpeg_proc.kill()
        print("Publisher stopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())


#!/usr/bin/env python3
"""
Voxl Game Testing & Streaming Client
Provides an agent-friendly Python interface to Voxl's low-latency streaming
and automated testing endpoints (/screenshot, /record, /wait).
"""

import os
import sys
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

DEFAULT_PORT = 6901
DEFAULT_HOST = "127.0.0.1"

def get_base_url(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    return f"http://{host}:{port}"

def get_headers(password: str = None) -> dict:
    pwd = password or os.environ.get("VOXL_PASSWORD", "")
    headers = {"User-Agent": "GameMaker-Agent/1.0"}
    if pwd:
        import base64
        b64 = base64.b64encode(f":{pwd}".encode()).decode()
        headers["Authorization"] = f"Basic {b64}"
    return headers

def check_status(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    url = f"{get_base_url(host, port)}/healthz"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VoxlClient"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False

def take_screenshot(output_path: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, password: str = None) -> bool:
    url = f"{get_base_url(host, port)}/screenshot"
    headers = get_headers(password)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp, open(output_path, "wb") as f:
            f.write(resp.read())
        print(f"Screenshot captured: {output_path} ({round(output_path.stat().st_size / 1024, 1)} KB)")
        return True
    except Exception as e:
        print(f"Failed to capture screenshot: {e}")
        return False

def record_clip(output_path: Path, seconds: int = 5, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, password: str = None) -> bool:
    url = f"{get_base_url(host, port)}/record?seconds={seconds}"
    headers = get_headers(password)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Recording {seconds} seconds of gameplay stream...", flush=True)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=seconds + 10) as resp, open(output_path, "wb") as f:
            f.write(resp.read())
        print(f"Recording saved: {output_path} ({round(output_path.stat().st_size / 1024, 1)} KB)")
        return True
    except Exception as e:
        print(f"Failed to record clip: {e}")
        return False

def wait_for_screen(idle_ms: int = 300, change: bool = False, timeout_ms: int = 10000,
                    region: str = None, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, password: str = None) -> dict:
    params = []
    if change:
        params.append("change")
    else:
        params.append(f"idle={idle_ms}")
    if timeout_ms:
        params.append(f"timeout={timeout_ms}")
    if region:
        params.append(f"region={region}")

    query = "&".join(params)
    url = f"{get_base_url(host, port)}/wait?{query}"
    headers = get_headers(password)

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout_ms / 1000.0 + 5) as resp:
            import json
            data = json.loads(resp.read().decode())
            print(f"Wait result: {data}")
            return data
    except Exception as e:
        print(f"Wait call failed: {e}")
        return {"error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Voxl Streaming & Game Testing CLI")
    subparsers = parser.add_subparsers(dest="command")

    # status
    subparsers.add_parser("status", help="Check if Voxl server is running")

    # screenshot
    s_p = subparsers.add_parser("screenshot", help="Capture desktop / game window screenshot")
    s_p.add_argument("-o", "--output", default="screenshot.png", help="Output PNG path")
    s_p.add_argument("--port", type=int, default=DEFAULT_PORT)

    # record
    r_p = subparsers.add_parser("record", help="Record an MP4 video clip")
    r_p.add_argument("-s", "--seconds", type=int, default=5, help="Duration in seconds")
    r_p.add_argument("-o", "--output", default="clip.mp4", help="Output MP4 path")
    r_p.add_argument("--port", type=int, default=DEFAULT_PORT)

    # wait
    w_p = subparsers.add_parser("wait", help="Wait for screen to settle or change")
    w_p.add_argument("--change", action="store_true", help="Return on first screen change")
    w_p.add_argument("--idle", type=int, default=300, help="Milliseconds screen must stay still")
    w_p.add_argument("--timeout", type=int, default=10000, help="Timeout in ms")
    w_p.add_argument("--region", default=None, help="Bounding box x,y,w,h to monitor")
    w_p.add_argument("--port", type=int, default=DEFAULT_PORT)

    args = parser.parse_args()

    if args.command == "status":
        running = check_status(port=DEFAULT_PORT)
        if running:
            print(f"Voxl is active and streaming on http://{DEFAULT_HOST}:{DEFAULT_PORT}")
        else:
            print(f"Voxl is NOT currently running on port {DEFAULT_PORT}.")
    elif args.command == "screenshot":
        take_screenshot(Path(args.output), port=args.port)
    elif args.command == "record":
        record_clip(Path(args.output), seconds=args.seconds, port=args.port)
    elif args.command == "wait":
        wait_for_screen(idle_ms=args.idle, change=args.change, timeout_ms=args.timeout, region=args.region, port=args.port)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

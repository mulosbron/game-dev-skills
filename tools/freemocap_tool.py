#!/usr/bin/env python3
"""
FreeMoCap Pipeline Helper CLI (freemocap_tool.py)
Lightweight companion tool for FreeMoCap v2.0+ (FastAPI backend on http://localhost:8005):
  - health:            Check if the local FreeMoCap server is running.
  - detect-blender:    Detect Blender executable via server /blender/detect or local PATH.
  - inspect-recording: Inspect a FreeMoCap recording directory for videos, 3D data, .blend, FBX/BVH.
  - export-blender:    Trigger /blender/export with BlenderExportConfig (fbx/bvh, tpose/apose, foot locking).
  - verify:            Run offline self-tests for export payload schema and recording inspection.

Zero third-party dependencies (Python 3.10+ stdlib only).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_URL = "http://localhost:8005"
VALID_FORMATS = ("fbx", "bvh")
VALID_REST_POSES = ("tpose", "apose")


def build_blender_export_payload(
    recording_folder: str,
    formats: Optional[List[str]] = None,
    rest_pose: str = "tpose",
    apply_foot_locking: bool = False,
    limit_hand_rom: bool = False,
    blender_exe_path: Optional[str] = None,
    auto_open: bool = False,
) -> Dict[str, Any]:
    """Build a validated ExportToBlenderRequest payload matching FreeMoCap v2.0 schema."""
    fmts = list(formats) if formats is not None else ["fbx", "bvh"]
    invalid_f = [f for f in fmts if f not in VALID_FORMATS]
    if invalid_f:
        raise ValueError(f"Unsupported Blender export format(s): {invalid_f}. Valid: {VALID_FORMATS}")
    if rest_pose not in VALID_REST_POSES:
        raise ValueError(f"Unsupported restPose: {rest_pose!r}. Valid: {VALID_REST_POSES}")
    return {
        "recordingFolderPath": str(recording_folder),
        "blenderExePath": blender_exe_path,
        "autoOpenBlendFile": bool(auto_open),
        "blenderExportConfig": {
            "formats": fmts,
            "restPose": rest_pose,
            "applyFootLocking": bool(apply_foot_locking),
            "limitHandMarkersRangeOfMotion": bool(limit_hand_rom),
        },
    }


def _http_json(url: str, method: str = "GET", payload: Optional[dict] = None, timeout: float = 5.0) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {"status": resp.status}


def find_local_blender() -> Optional[str]:
    found = shutil.which("blender")
    if found:
        return found
    candidates = [
        Path(r"C:\Program Files\Blender Foundation"),
        Path("/Applications/Blender.app/Contents/MacOS/Blender"),
    ]
    for base in candidates:
        if base.is_file():
            return str(base)
        if base.is_dir():
            exes = sorted(base.glob("Blender*/blender.exe"), reverse=True)
            if exes:
                return str(exes[0])
    return None


def inspect_recording_dir(folder: Path) -> Dict[str, Any]:
    """Inspect a FreeMoCap recording directory offline."""
    if not folder.exists() or not folder.is_dir():
        return {"ok": False, "error": f"Recording directory not found: {folder}"}

    videos = sorted(str(p.relative_to(folder)) for p in folder.rglob("*.mp4"))
    npy_files = sorted(str(p.relative_to(folder)) for p in folder.rglob("*.npy"))
    csv_files = sorted(str(p.relative_to(folder)) for p in folder.rglob("*.csv"))
    blend_files = sorted(str(p.relative_to(folder)) for p in folder.rglob("*.blend"))
    fbx_files = sorted(str(p.relative_to(folder)) for p in folder.rglob("*.fbx"))
    bvh_files = sorted(str(p.relative_to(folder)) for p in folder.rglob("*.bvh"))

    return {
        "ok": True,
        "recording_folder": str(folder),
        "counts": {
            "videos_mp4": len(videos),
            "data_npy": len(npy_files),
            "data_csv": len(csv_files),
            "blend": len(blend_files),
            "fbx": len(fbx_files),
            "bvh": len(bvh_files),
        },
        "ready_for_blender_export": len(npy_files) > 0 or len(csv_files) > 0,
        "has_engine_exports": len(fbx_files) > 0 or len(bvh_files) > 0,
        "exports": {"blend": blend_files, "fbx": fbx_files, "bvh": bvh_files},
    }


def run_verify() -> Dict[str, Any]:
    checks: Dict[str, Any] = {}

    # 1. Valid payload schema check
    p = build_blender_export_payload("demo_session", formats=["fbx", "bvh"], rest_pose="apose", apply_foot_locking=True)
    cfg = p["blenderExportConfig"]
    checks["export_payload_schema"] = {
        "ok": cfg["formats"] == ["fbx", "bvh"] and cfg["restPose"] == "apose" and cfg["applyFootLocking"] is True,
    }

    # 2. Invalid format (e.g. broken gltf) rejected cleanly
    rejected_gltf = False
    try:
        build_blender_export_payload("demo_session", formats=["gltf"])
    except ValueError:
        rejected_gltf = True
    checks["rejects_unsupported_gltf_format"] = {"ok": rejected_gltf}

    # 3. Offline recording directory inspector
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "output_data").mkdir()
        (root / "3d_models").mkdir()
        (root / "output_data" / "mediaPipeSkel_3d.npy").write_bytes(b"")
        (root / "3d_models" / "session.fbx").write_bytes(b"")
        info = inspect_recording_dir(root)
        checks["inspect_recording_offline"] = {
            "ok": info["ok"] and info["ready_for_blender_export"] and info["has_engine_exports"],
            "counts": info["counts"],
        }

    all_ok = all(bool(v["ok"]) for v in checks.values())
    return {
        "ok": all_ok,
        "passed": sum(1 for v in checks.values() if v["ok"]),
        "total": len(checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="FreeMoCap v2.0+ Pipeline Helper CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ver = sub.add_parser("verify", help="Run offline self-tests for FreeMoCap config schema and recording inspector")
    p_ver.add_argument("--json", action="store_true")

    p_hlth = sub.add_parser("health", help="Check if local FreeMoCap FastAPI server is reachable")
    p_hlth.add_argument("--url", default=DEFAULT_URL)
    p_hlth.add_argument("--json", action="store_true")

    p_det = sub.add_parser("detect-blender", help="Detect Blender executable (via server or local fallback)")
    p_det.add_argument("--url", default=DEFAULT_URL)
    p_det.add_argument("--json", action="store_true")

    p_insp = sub.add_parser("inspect-recording", help="Inspect a FreeMoCap recording directory offline")
    p_insp.add_argument("folder", type=Path)
    p_insp.add_argument("--json", action="store_true")

    p_exp = sub.add_parser("export-blender", help="Trigger headless Blender + FBX/BVH export via FreeMoCap server")
    p_exp.add_argument("--recording", required=True, help="Path to processed FreeMoCap recording folder")
    p_exp.add_argument("--formats", default="fbx,bvh", help="Comma-separated formats: fbx,bvh (or empty)")
    p_exp.add_argument("--rest-pose", choices=list(VALID_REST_POSES), default="tpose")
    p_exp.add_argument("--foot-locking", action="store_true")
    p_exp.add_argument("--limit-hands", action="store_true")
    p_exp.add_argument("--blender-exe", default=None)
    p_exp.add_argument("--no-open", action="store_true", help="Do not auto-open the resulting .blend file")
    p_exp.add_argument("--url", default=DEFAULT_URL)
    p_exp.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.cmd == "verify":
        res = run_verify()
        print(json.dumps(res, indent=2) if args.json else f"FreeMoCap verify: {res['passed']}/{res['total']} passed")
        return 0 if res["ok"] else 1

    if args.cmd == "inspect-recording":
        res = inspect_recording_dir(args.folder)
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1

    if args.cmd == "health":
        try:
            data = _http_json(f"{args.url.rstrip('/')}/health", timeout=3.0)
            out = {"ok": True, "url": args.url, "server": data}
        except Exception as exc:
            out = {"ok": False, "url": args.url, "error": str(exc)}
        print(json.dumps(out, indent=2))
        return 0 if out["ok"] else 1

    if args.cmd == "detect-blender":
        try:
            data = _http_json(f"{args.url.rstrip('/')}/blender/detect", timeout=3.0)
            out = {"ok": bool(data.get("found")), "source": "server", **data}
        except Exception:
            local = find_local_blender()
            out = {"ok": local is not None, "source": "local", "found": local is not None, "blender_exe_path": local}
        print(json.dumps(out, indent=2))
        return 0 if out["ok"] else 1

    if args.cmd == "export-blender":
        fmts = [f.strip().lower() for f in args.formats.split(",") if f.strip()]
        payload = build_blender_export_payload(
            recording_folder=args.recording,
            formats=fmts,
            rest_pose=args.rest_pose,
            apply_foot_locking=args.foot_locking,
            limit_hand_rom=args.limit_hands,
            blender_exe_path=args.blender_exe,
            auto_open=not args.no_open,
        )
        try:
            resp = _http_json(f"{args.url.rstrip('/')}/blender/export", method="POST", payload=payload, timeout=180.0)
            out = {"ok": bool(resp.get("success", True)), "response": resp}
        except Exception as exc:
            out = {"ok": False, "error": str(exc), "payload": payload}
        print(json.dumps(out, indent=2))
        return 0 if out["ok"] else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

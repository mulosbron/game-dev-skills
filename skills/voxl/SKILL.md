---
name: voxl
description: >-
  Ultra-fast 60 FPS remote desktop streaming and automated game testing for AI agents written in Rust.
  Provides zero-cost /screenshot, /record (MP4 clip), and /wait (event-driven dirty-rect change detection)
  APIs to visually inspect and test running GameMaker, Godot, and web games in real-time.
---

# Voxl - Low-Latency Streaming & Automated Game Testing Skill

Voxl is an ultra-fast desktop streaming server written in Rust (`tembo/voxl`) that streams a Windows desktop, macOS screen, or Linux X11 display as H.264 over a single WebSocket to any browser at 60 FPS with 12–99 ms latency.

For AI agents and game developers, Voxl solves the core problem of **visual feedback and game testing** by exposing dedicated agent APIs:
- `/screenshot`: Captures the game screen as PNG without interrupting execution.
- `/record`: Exports raw streaming H.264 as an MP4 clip with zero CPU re-encoding overhead.
- `/wait`: Event-driven screen change detector using OS dirty-rect events (DXGI / ScreenCaptureKit / XDamage) so agents never have to guess `time.sleep()`.

---

## ⚡ Agent CLI Tooling (`tools/voxl_client.py`)

A helper client is bundled in `tools\voxl_client.py`:

### 1. Check Server Status
```powershell
python tools/voxl_client.py status
```

### 2. Capture Visual Game State (`screenshot`)
Take an instant screenshot of the running game window or room:
```powershell
python tools/voxl_client.py screenshot -o "exports/tests/game_title_screen.png"
```

### 3. Record Gameplay Video Clip (`record`)
Record gameplay action (e.g., verifying a jump animation, combat combo, or projectile trail):
```powershell
# Records 5 seconds of gameplay directly to an MP4 video:
python tools/voxl_client.py record -s 5 -o "exports/tests/combat_test.mp4"
```

### 4. Event-Driven Game Wait (`wait`)
Wait for the game window to load or render a visual change without polling loops:
```powershell
# Wait until the screen changes (returns the exact millisecond a frame draws):
python tools/voxl_client.py wait --change

# Wait until motion settles for 500 ms (e.g. after a room transition):
python tools/voxl_client.py wait --idle 500 --timeout 5000

# Monitor a specific region (x, y, w, h):
python tools/voxl_client.py wait --change --region "100,100,640,480"
```

---

## 🌐 Remote Browser Playtesting

While testing a game or running a build:
1. Connect via any modern web browser (Chrome, Edge, Safari, Firefox) at:
   `http://localhost:6901/?token=<password>`
2. Stream games at smooth 60 FPS with audio, gamepad, touch controls, and keyboard inputs over a single WebSocket through proxies, tunnels, or LAN.

---

## 🛠️ Building / Running Voxl Server

The source code is stored in `libraries\com.github.tembo.voxl` (MIT License):
- **Windows Build:** Requires Rust, LLVM, and vcpkg (`x264`, `libyuv`, `opus`).
- **Binary invocation:**
  ```powershell
  voxl.exe --port=6901
  ```

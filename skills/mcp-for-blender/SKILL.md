---
name: mcp-for-blender
description: "Connect AI agents to a live Blender 3.0+ session via MCP (`mcp-for-blender` / `blender_mcp`). Covers socket addon setup, viewport/multi-angle/animation-strip capture (`look`), scene inspection, safe mode & telemetry consent, asset integrations (Poly Haven, Sketchfab, Poly Pizza), AI 3D generation (Hunyuan3D, Meshy, Tripo, Hyper3D Rodin, World Labs), and bundled production guides."
license: MIT
metadata:
  homepage: "https://mcp-for-blender.com/"
  repository: "https://github.com/ahujasid/mcp-for-blender"
---

# MCP for Blender (`mcp-for-blender`)

Two-way bridge connecting MCP clients to a live **Blender 3.0+** instance (`MIT`, PyPI `mcp-for-blender` v2.2.9, legacy alias `blender-mcp`, requires Python `>= 3.10` and `uv`).

Located in `libraries\com.github.3d-gen-ai.mcp-for-blender`, with bundled Blender production guides copied into `references\`.

---

## Components & Setup

1. **Blender Addon** (`addon.py` / `src/blender_mcp/bundled/addon.py`): Runs a local JSON-over-TCP socket server inside Blender (default `localhost:9876`).
2. **MCP Server** (`src/blender_mcp/server.py`, entrypoint `mcp-for-blender`): Translates MCP tool calls into socket commands and returns structured summaries and images.

### Install & Register

```powershell
# Recommended one-step setup (configures detected MCP clients + installs/enables Blender addon)
uvx mcp-for-blender setup

# Or install only the Blender addon and inspect detected Blender paths
uvx mcp-for-blender install-addon
uvx mcp-for-blender addon-paths

# Upgrade both server and addon safely (creates .bak backups)
uvx mcp-for-blender@latest update
```

Manual MCP client config (STDIO):
```json
{
  "mcpServers": {
    "blender": {
      "command": "uvx",
      "args": ["mcp-for-blender"],
      "env": {
        "BLENDER_HOST": "localhost",
        "BLENDER_PORT": "9876"
      }
    }
  }
}
```
Run multiple Blender instances side-by-side by passing `--port <PORT>` to `mcp-for-blender` and matching the port in Blender's `N` sidebar → **MCP for Blender** tab. Run only one MCP server instance per active Blender listener.

---

## MCP Tool Surface (`src/blender_mcp/server.py`)

| Tool | Purpose |
|---|---|
| `get_addon_status` | Returns `blender_version`, addon version, enabled asset libraries, and active 3D generators. Always check version first before version-sensitive `bpy` code. |
| `get_scene_info` | Compact per-object summary with selectable `fields` (placement, `materials`, `topology`, `weights`, etc.) and `root` / `query` filters. |
| `execute_blender_code` | Executes Blender Python (`bpy`, `bmesh`, `mathutils`) inside the live scene. |
| `look` | Visual verification from `viewport`, `camera`, `angles` (auto-framed multi-view sheet), or `frames` (animation frame strip), in `solid`, `material`, `rendered`, `wireframe`, or `xray` shading; or inspect an existing image/render. |
| `search_assets` / `import_asset` | Search with optional thumbnail `previews` and import into the scene from **Poly Haven**, **Sketchfab**, or **Poly Pizza** (with optional `target_size`, `apply_to` material assignment, `resolution`, `file_format`). |
| `generate_3d` | One-call text/image-to-3D generation and scene import via **Tripo**, **Hunyuan3D**, **Hyper3D Rodin**, or **Meshy** (prefers Premium automatically if active, otherwise uses configured API keys). |
| `generate_gaussian_world` | Generates an explorable **World Labs** Marble 1.1 / 1.1 Plus environment as Gaussian splats + collision mesh + world panorama (**Blender 5.3+** required). |
| `search_mentions` | Autocomplete `@`-mentions for objects, materials, and collections (`blender://...` resources). |
| `open_viewport` / `viewport_*` | Inline interactive viewport app (`viewport_latest`, `viewport_capture`, `viewport_pick`) for supporting clients (e.g., Codex plugin with `BLENDER_MCP_APPS=1`). |
| `disable_telemetry` / `record_trajectory_feedback` | Opt-out / feedback controls for telemetry. |

---

## Asset Libraries & AI 3D Integrations

| Integration | Scope & Key Notes | Config / Auth |
|---|---|---|
| **Poly Haven** | ~2,400 CC0 HDRIs, PBR textures, and `.blend` models (textures build full Principled BSDF setups; HDRIs pack cleanly into a new world). Prefer 1k/2k unless hero close-up. | No API key; toggle **Poly Haven** in sidebar. |
| **Sketchfab** | Real-world / named 3D models. Check licence and polygon count before importing. | Addon prefs or `BLENDERMCP_SKETCHFAB_API_KEY`. |
| **Poly Pizza** | ~10,600 stylized low-poly `.glb` models. Writes `polypizza_attribution` custom property for CC-BY credit (or filter `licence="CC0"`). | Free API key (`BLENDERMCP_POLYPIZZA_API_KEY`). |
| **Tripo** | Textured 3D models from text or reference image (`tripo3d.ai` global or `.com` China domain setting). | Premium or `BLENDERMCP_TRIPO_API_KEY`. |
| **Meshy** | Text/image-to-3D sized in real-world meters at origin (`z=0`); supports A-pose / T-pose character prompts on own key. | Premium or `BLENDERMCP_MESHY_API_KEY`. |
| **Hunyuan3D** | Official Tencent Cloud API: Mainland `cloud.tencent.com` uses `ai3d` (`ap-guangzhou`, toggle off); International `tencentcloud.com` Pro uses `hunyuan` (`ap-singapore`, tick **International (Pro) account**). | Premium or `BLENDERMCP_HUNYUAN3D_SECRET_ID` + `_SECRET_KEY` (+ `_API_URL`). |
| **Hyper3D Rodin** | Text/image-to-3D (`Gen-2.5-Medium` on main site or fal.ai). | Premium or `BLENDERMCP_HYPER3D_API_KEY`. |
| **World Labs** | Marble 1.1 / 1.1 Plus Gaussian-splat worlds (text, image, 360° panorama, or up to 4 ordered photos). Requires Blender 5.3+. | Premium or `BLENDERMCP_WORLDLABS_API_KEY`. |

---

## Safe Mode, Networking & Telemetry Consent

- **Safe Mode (`BLENDER_MCP_SAFE_MODE=1`)**: Enables an AST allowlist (`src/blender_mcp/safe_mode.py`) on `execute_blender_code` to mitigate prompt injection from third-party asset metadata:
  - **Allowed**: `bpy`, `bmesh`, `mathutils`, pure-Python stdlib (`math`, `json`, `re`, `collections`, etc.), rendering, saving/opening `.blend` files, and `bpy` import/export operators.
  - **Blocked**: `eval`/`exec`/`compile`/`open`/`__import__`, dunder reflection escapes, `os`/`sys`/`subprocess`/`socket`, persistent `bpy.app.handlers`/`timers`/drivers/`register_class`, `bpy.ops.script`/`preferences`/`extensions`, and external `.blend` `wm.append`/`wm.link`.
- **Network Safety**: The addon socket has no authentication or encryption. Keep `BLENDER_HOST=localhost` unless tunneling via SSH on a trusted LAN.
- **Telemetry & Consent (`consent_prompt.py`)**:
  - Recording prompts, generated code, viewport screenshots, and trajectory steps is **strictly opt-in** (off by default via addon preferences `telemetry_consent` or one-time client elicitation dialog).
  - Minimal anonymous usage metrics (random install ID, session ID, tool name, success/timing, versions, OS) can be turned off completely with `DISABLE_TELEMETRY=true`.

---

## Bundled Blender Production Guides (`references/`)

Read the matching guide in `references\` before authoring complex Blender Python:

- [`references/bpy.md`](references/bpy.md) — Version-proof `bpy` scripting (RNA introspection, Blender 4.0 Principled BSDF socket renames, EEVEE engine identifier differences, Blender 4.4+/5.0 slotted actions/fcurves, `temp_override` context for operators).
- [`references/scene.md`](references/scene.md) — Scene blockout, real-world scale (`1 unit = 1m`), bounding-box grounding (`z -= min_z`), lighting, HDRIs, camera focal lengths, and `look()` verification.
- [`references/materials.md`](references/materials.md) — Defensive Principled BSDF node wiring, physically plausible PBR albedo/metallic/roughness ranges, box/Smart UV projection, `Non-Color` maps, and procedural variation.
- [`references/retopology.md`](references/retopology.md) — Mesh cleanup (`bmesh` `remove_doubles` / `dissolve_degenerate` / `recalc_face_normals`), Decimate vs. Voxel Remesh vs. QuadriFlow + Shrinkwrap, engine triangle budgets, Smart UV / seam unwrapping, and Cycles high-to-low normal/diffuse baking.
- [`references/rigging.md`](references/rigging.md) — Pre-rigging scale/orientation (`-Y` front, grounded at origin), Rigify humanoid metarig fitting and generation, custom armatures, rigid mechanical bone parenting, `ARMATURE_AUTO` heat-weighting troubleshooting, and `get_scene_info(fields=["weights"])` verification.
- [`references/animation.md`](references/animation.md) — Cross-version keyframing (`keyframe_insert`, slotted fcurve lookup), easing/Cycles loops, anticipation/follow-through/arcs, NLA strips, and checking motion with `look(mode="frames")`.
- [`references/level-design.md`](references/level-design.md) — Humanoid player metrics (`1.8m × 0.6m` capsule, `2m`/`4m` modular grid), grey-box collection layout, linked duplicates/collection instances, engine collision naming (`SM_`/`UCX_` Unreal, `-col`/`-colonly` Godot), lightmap UVs, and glTF/FBX export.

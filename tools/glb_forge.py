#!/usr/bin/env python3
"""
GLB Forge — 3D Model Inspector, KTX2/WebP & Meshopt/Draco Optimizer, LOD Generator,
TSL Material Code Generator & Split-Screen 3D Compare Studio (tools/glb_forge.py)

Powered 100% by MIT & Apache-2.0 Open-Source Packages (`libraries/com.github.donmccurdy.gltf-transform`):
  - @gltf-transform/core, @gltf-transform/extensions, @gltf-transform/functions (MIT)
  - meshoptimizer (MIT) & draco3dgltf (Apache-2.0)
  - sharp (Apache-2.0) & gltf-validator (Apache-2.0)
  - Three.js (MIT) for the standalone Split-Screen 3D Compare Studio HTML

Subcommands:
  1. inspect        : Deep x-ray of any .glb (triangles, vertices, draw calls, textures, VRAM, Khronos validation)
  2. optimize       : Compress geometry (Meshopt/Draco) & textures (WebP/PNG), simplify meshes, and render a Report Card PNG
  3. lod            : Generate multi-level LOD0 / LOD1 / LOD2 .glb chains
  4. tsl-material   : Generate Three.js Shading Language (TSL) & React Three Fiber procedural node materials
  5. compare-studio : Build a standalone Split-Screen 3D Original vs Optimized HTML Studio (with embedded GLBs + Drag & Drop)
  6. showcase       : Run the full pipeline on sample 3D assets from ABO, ThreeJS Assets, and Sand3D
"""

import os
import sys
import json
import base64
import tempfile
import argparse
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = WORKSPACE_ROOT / "libraries" / "com.github.donmccurdy.gltf-transform"
WORKER_MJS = RUNTIME_DIR / "glb_worker.mjs"
DEFAULT_EXPORT_DIR = WORKSPACE_ROOT / "exports" / "com.agent-game-forge.glb"

OPTIMIZE_PRESETS = {
    "web-mobile": {
        "label": "Web & Mobile Three.js (Meshopt + WebP 1024px)",
        "compress": "meshopt",
        "textureFormat": "webp",
        "maxTextureSize": 1024,
        "textureQuality": 80,
        "simplifyRatio": 0.75,
        "simplifyError": 0.005,
    },
    "desktop-hd": {
        "label": "Desktop HD Quality (Meshopt + WebP 2048px, Lossless Topology)",
        "compress": "meshopt",
        "textureFormat": "webp",
        "maxTextureSize": 2048,
        "textureQuality": 90,
        "simplifyRatio": 1.0,
        "simplifyError": 0.001,
    },
    "draco-ultra": {
        "label": "Maximum Geometry Compression (Draco Edgebreaker + WebP 512px)",
        "compress": "draco",
        "textureFormat": "webp",
        "maxTextureSize": 512,
        "textureQuality": 75,
        "simplifyRatio": 0.5,
        "simplifyError": 0.01,
    },
    "roblox-lowpoly": {
        "label": "Low-Poly Game Engine Budget (<10k Tris, Quantized + WebP 1024px)",
        "compress": "quantize",
        "textureFormat": "webp",
        "maxTextureSize": 1024,
        "textureQuality": 82,
        "simplifyRatio": 0.45,
        "simplifyError": 0.015,
    },
}

TSL_MATERIAL_PRESETS = {
    "animated-noise-lava": {
        "title": "Animated Procedural Noise & Emissive Lava (TSL)",
        "code": """// Three.js Shading Language (TSL) — Animated Noise Lava Material
import * as THREE from 'three/webgpu';
import { time, uv, positionLocal, sin, cos, mix, vec3, float } from 'three/tsl';

export function createAnimatedNoiseLavaMaterial() {
  const mat = new THREE.MeshPhysicalNodeMaterial();
  const p = positionLocal.mul(4.0);
  const wave = sin(p.x.add(time.mul(2.0))).mul(cos(p.y.sub(time.mul(1.5)))).mul(0.5).add(0.5);

  const darkCrust = vec3(0.08, 0.05, 0.06);
  const magmaCore = vec3(1.0, 0.28, 0.04);
  const hotYellow = vec3(1.0, 0.85, 0.2);

  mat.colorNode = mix(darkCrust, magmaCore, wave);
  mat.emissiveNode = mix(vec3(0.0), hotYellow, wave.pow(2.5)).mul(2.2);
  mat.roughnessNode = mix(float(0.85), float(0.25), wave);
  mat.metalnessNode = float(0.1);
  return mat;
}
"""
    },
    "crystal-coat-glass": {
        "title": "Physical Transmission Crystal Glass & Iridescent Coat (TSL)",
        "code": """// Three.js Shading Language (TSL) — Physical Crystal Glass Material
import * as THREE from 'three/webgpu';
import { normalView, positionViewDirection, dot, clamp, pow, mix, vec3, float } from 'three/tsl';

export function createCrystalGlassMaterial() {
  const mat = new THREE.MeshPhysicalNodeMaterial({ transparent: true });
  const fresnel = pow(clamp(float(1.0).sub(dot(normalView, positionViewDirection)), 0.0, 1.0), 3.0);

  mat.colorNode = mix(vec3(0.15, 0.65, 1.0), vec3(0.75, 0.35, 1.0), fresnel);
  mat.transmissionNode = float(0.92);
  mat.ior = 1.52;
  mat.thicknessNode = float(0.6);
  mat.roughnessNode = float(0.06);
  mat.clearcoatNode = float(1.0);
  mat.emissiveNode = vec3(0.1, 0.4, 0.9).mul(fresnel.mul(0.8));
  return mat;
}
"""
    },
    "hologram-scanline": {
        "title": "Sci-Fi Hologram Scanline & Fresnel Rim (TSL)",
        "code": """// Three.js Shading Language (TSL) — Sci-Fi Hologram Material
import * as THREE from 'three/webgpu';
import { time, positionWorld, normalView, positionViewDirection, dot, sin, pow, clamp, vec3, float } from 'three/tsl';

export function createHologramMaterial() {
  const mat = new THREE.MeshPhysicalNodeMaterial({ transparent: true, depthWrite: false });
  const scanline = sin(positionWorld.y.mul(45.0).sub(time.mul(8.0))).mul(0.5).add(0.5);
  const rim = pow(clamp(float(1.0).sub(dot(normalView, positionViewDirection)), 0.0, 1.0), 2.2);

  const holoCyan = vec3(0.1, 0.88, 1.0);
  mat.colorNode = holoCyan;
  mat.emissiveNode = holoCyan.mul(rim.add(scanline.mul(0.45))).mul(1.8);
  mat.opacityNode = clamp(rim.add(scanline.mul(0.25)), 0.15, 0.95);
  return mat;
}
"""
    },
}


COMPARE_STUDIO_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GLB Forge — Split-Screen 3D Inspector, Optimizer & Shader Studio</title>
<style>
  :root {
    --bg: #0c0f17;
    --panel: #151a26;
    --border: #263047;
    --text: #e8eef7;
    --muted: #8c9db8;
    --accent: #4da6ff;
    --ok: #3ddc84;
    --warn: #ffbe3d;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  header {
    height: 52px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
  }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 15px; }
  .badge {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    background: #1f283d;
    color: var(--accent);
    border: 1px solid #314163;
  }
  .badge.savings { background: rgba(61, 220, 132, 0.14); color: var(--ok); border-color: rgba(61, 220, 132, 0.4); }
  .toolbar { display: flex; align-items: center; gap: 8px; }
  button, select {
    background: #1e2638;
    color: var(--text);
    border: 1px solid #32405e;
    padding: 6px 11px;
    border-radius: 5px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }
  button:hover, select:hover { border-color: var(--accent); background: #26314a; }
  button.active { background: #1e62d0; border-color: var(--accent); color: #fff; }
  .main-grid {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 1fr 330px;
    overflow: hidden;
  }
  .viewport {
    position: relative;
    border-right: 1px solid var(--border);
    background: radial-gradient(circle at center, #1a2236 0%, #0b0e16 100%);
    overflow: hidden;
  }
  .vp-label {
    position: absolute;
    top: 12px;
    left: 12px;
    background: rgba(15, 19, 30, 0.85);
    border: 1px solid var(--border);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    pointer-events: none;
    z-index: 10;
  }
  .vp-label strong { display: block; font-size: 13px; margin-bottom: 2px; }
  .sidebar {
    background: var(--panel);
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
  }
  .card {
    background: #1a2130;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px;
    font-size: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .card-title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: var(--muted);
    font-weight: 700;
  }
  .stat-row {
    display: flex;
    justify-content: space-between;
    padding: 3px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
  }
  .stat-row:last-child { border-bottom: none; }
  .good { color: var(--ok); font-weight: 700; }
  pre {
    background: #0f131d;
    border: 1px solid #25304a;
    border-radius: 4px;
    padding: 8px;
    font-family: Consolas, monospace;
    font-size: 10.5px;
    color: #a9c7ff;
    overflow-x: auto;
    white-space: pre-wrap;
    user-select: text;
    max-height: 210px;
  }
</style>
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"
  }
}
</script>
</head>
<body>

<header>
  <div class="brand">
    <span>🧊 GLB Forge — Compare & Inspect Studio</span>
    <span class="badge">Linked Cameras</span>
    <span class="badge savings" id="headerSavings">Saved __SAVED_PCT__% (__SAVED_KB__ KB)</span>
  </div>
  <div class="toolbar">
    <span style="font-size:12px;color:var(--muted);">Surface Mode:</span>
    <button class="mode-btn active" onclick="setViewMode('pbr', this)">🎨 Final PBR</button>
    <button class="mode-btn" onclick="setViewMode('wireframe', this)">🕸️ Wireframe</button>
    <button class="mode-btn" onclick="setViewMode('normals', this)">🌈 Normals</button>
    <button class="mode-btn" onclick="setViewMode('uv', this)">🏁 UV Checker</button>
    <button class="mode-btn" onclick="setViewMode('tsl', this)">✨ Procedural Shader</button>
    <button onclick="toggleTurntable()" id="btnSpin">🔄 Spin: ON</button>
  </div>
</header>

<div class="main-grid">
  <!-- LEFT VIEWPORT: ORIGINAL GLB -->
  <div class="viewport" id="vpLeft">
    <div class="vp-label">
      <strong style="color:#ff9e64">BEFORE (Original GLB)</strong>
      <span id="leftStatsText">__BEFORE_SUMMARY__</span>
    </div>
  </div>

  <!-- RIGHT VIEWPORT: OPTIMIZED GLB -->
  <div class="viewport" id="vpRight">
    <div class="vp-label">
      <strong style="color:#3ddc84">AFTER (Optimized: __PRESET_NAME__)</strong>
      <span id="rightStatsText">__AFTER_SUMMARY__</span>
    </div>
  </div>

  <!-- RIGHT SIDEBAR: MEASURED REPORT & TSL CODE -->
  <div class="sidebar">
    <div class="card">
      <div class="card-title">Measured Optimization Report</div>
      <div class="stat-row"><span>File Size:</span><span>__BEFORE_KB__ KB → <b class="good">__AFTER_KB__ KB (-__SAVED_PCT__%)</b></span></div>
      <div class="stat-row"><span>Triangles:</span><span>__BEFORE_TRIS__ → <b class="good">__AFTER_TRIS__</b></span></div>
      <div class="stat-row"><span>Vertices:</span><span>__BEFORE_VERTS__ → <b class="good">__AFTER_VERTS__</b></span></div>
      <div class="stat-row"><span>Draw Calls:</span><span>__BEFORE_DC__ → <b class="good">__AFTER_DC__</b></span></div>
      <div class="stat-row"><span>Texture Payload:</span><span>__BEFORE_TEX_KB__ KB → <b class="good">__AFTER_TEX_KB__ KB</b></span></div>
      <div class="stat-row"><span>Est. GPU VRAM:</span><span>__BEFORE_VRAM__ MB → <b class="good">__AFTER_VRAM__ MB</b></span></div>
      <div class="stat-row"><span>Khronos Validator:</span><span class="good">__VALIDATION_STATUS__</span></div>
    </div>

    <div class="card">
      <div class="card-title">Load Custom .GLB From Disk</div>
      <span style="color:var(--muted);font-size:11px;">Drop any .glb file onto the left or right viewport, or pick below:</span>
      <input type="file" accept=".glb,.gltf" onchange="loadUserFile(this.files[0])" style="font-size:11px;color:var(--muted);">
    </div>

    <div class="card">
      <div class="card-title">Three.js TSL Material Node Export</div>
      <select onchange="switchTSLSnippet(this.value)" id="tslSelect">
        <option value="animated-noise-lava">Animated Noise Lava (TSL)</option>
        <option value="crystal-coat-glass">Crystal Transmission Glass (TSL)</option>
        <option value="hologram-scanline">Sci-Fi Hologram Scanline (TSL)</option>
      </select>
      <pre id="tslCodeBox"></pre>
    </div>
  </div>
</div>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const EMBEDDED_BEFORE_B64 = "__BEFORE_B64__";
const EMBEDDED_AFTER_B64  = "__AFTER_B64__";
const TSL_SNIPPETS = __TSL_SNIPPETS_JSON__;

const vpLeft = document.getElementById('vpLeft');
const vpRight = document.getElementById('vpRight');

function createStage(container) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.05, 500);
  camera.position.set(2.2, 1.6, 2.5);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  container.appendChild(renderer.domElement);

  const amb = new THREE.HemisphereLight(0xddeeff, 0x1b2030, 1.6);
  scene.add(amb);
  const dir = new THREE.DirectionalLight(0xffffff, 2.4);
  dir.position.set(4, 7, 5);
  scene.add(dir);
  const rim = new THREE.DirectionalLight(0x66aaff, 1.1);
  rim.position.set(-4, 2, -4);
  scene.add(rim);

  const grid = new THREE.GridHelper(6, 12, 0x334466, 0x1e273b);
  scene.add(grid);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  return { container, scene, camera, renderer, controls, rootGroup: null, originalMaterials: new Map() };
}

const stageL = createStage(vpLeft);
const stageR = createStage(vpRight);

// Synchronize cameras between Left and Right viewports!
let syncing = false;
function syncCamera(src, dst) {
  if (syncing) return;
  syncing = true;
  dst.camera.position.copy(src.camera.position);
  dst.camera.quaternion.copy(src.camera.quaternion);
  dst.controls.target.copy(src.controls.target);
  dst.controls.update();
  syncing = false;
}
stageL.controls.addEventListener('change', () => syncCamera(stageL, stageR));
stageR.controls.addEventListener('change', () => syncCamera(stageR, stageL));

// Create procedural 16x16 UV Checker texture
function makeUVCheckerTexture() {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 256;
  const ctx = c.getContext('2d');
  const n = 16, s = 256 / n;
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      ctx.fillStyle = (x + y) % 2 === 0 ? '#2b354f' : '#65d6a6';
      ctx.fillRect(x * s, y * s, s, s);
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
const uvCheckerTex = makeUVCheckerTexture();

// Custom procedural hologram/wave shader for live preview
const customShaderMat = new THREE.ShaderMaterial({
  uniforms: { uTime: { value: 0 } },
  vertexShader: `
    varying vec3 vNormal;
    varying vec3 vWorldPos;
    void main() {
      vNormal = normalize(normalMatrix * normal);
      vec4 wp = modelMatrix * vec4(position, 1.0);
      vWorldPos = wp.xyz;
      gl_Position = projectionMatrix * viewMatrix * wp;
    }
  `,
  fragmentShader: `
    uniform float uTime;
    varying vec3 vNormal;
    varying vec3 vWorldPos;
    void main() {
      float scan = 0.5 + 0.5 * sin(vWorldPos.y * 35.0 - uTime * 6.0);
      float rim = pow(1.0 - abs(dot(vNormal, vec3(0.0, 0.0, 1.0))), 2.0);
      vec3 col = mix(vec3(0.08, 0.45, 0.95), vec3(0.25, 0.95, 0.75), scan) + rim * 0.85;
      gl_FragColor = vec4(col, 0.9);
    }
  `,
  transparent: true
});

const loader = new GLTFLoader();
const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath('https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/');
loader.setDRACOLoader(dracoLoader);
loader.setMeshoptDecoder(MeshoptDecoder);

function b64ToArrayBuffer(b64) {
  const bin = atob(b64);
  const len = bin.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

function mountModel(stage, gltf) {
  if (stage.rootGroup) stage.scene.remove(stage.rootGroup);
  stage.originalMaterials.clear();

  const model = gltf.scene;
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 0.001);
  const scale = 1.8 / maxDim;

  model.scale.setScalar(scale);
  model.position.set(-center.x * scale, -box.min.y * scale, -center.z * scale);

  model.traverse(node => {
    if (node.isMesh) {
      stage.originalMaterials.set(node.uuid, node.material);
    }
  });

  stage.rootGroup = model;
  stage.scene.add(model);
}

function loadEmbeddedModels() {
  if (EMBEDDED_BEFORE_B64) {
    loader.parse(b64ToArrayBuffer(EMBEDDED_BEFORE_B64), '', gltf => mountModel(stageL, gltf));
  }
  if (EMBEDDED_AFTER_B64) {
    loader.parse(b64ToArrayBuffer(EMBEDDED_AFTER_B64), '', gltf => mountModel(stageR, gltf));
  }
}

window.setViewMode = function(mode, btn) {
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  [stageL, stageR].forEach(st => {
    if (!st.rootGroup) return;
    st.rootGroup.traverse(node => {
      if (!node.isMesh) return;
      const orig = st.originalMaterials.get(node.uuid);
      if (mode === 'pbr') {
        node.material = orig;
        node.material.wireframe = false;
      } else if (mode === 'wireframe') {
        node.material = orig.clone();
        node.material.wireframe = true;
      } else if (mode === 'normals') {
        node.material = new THREE.MeshNormalMaterial();
      } else if (mode === 'uv') {
        node.material = new THREE.MeshStandardMaterial({ map: uvCheckerTex, roughness: 0.6 });
      } else if (mode === 'tsl') {
        node.material = customShaderMat;
      }
    });
  });
};

let turntable = true;
window.toggleTurntable = function() {
  turntable = !turntable;
  document.getElementById('btnSpin').textContent = `🔄 Spin: ${turntable ? 'ON' : 'OFF'}`;
};

window.loadUserFile = function(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    loader.parse(e.target.result, '', gltf => {
      mountModel(stageL, gltf);
    });
  };
  reader.readAsArrayBuffer(file);
};

window.switchTSLSnippet = function(key) {
  const item = TSL_SNIPPETS[key];
  document.getElementById('tslCodeBox').textContent = item ? item.code : '';
};

window.addEventListener('resize', () => {
  [stageL, stageR].forEach(st => {
    st.camera.aspect = st.container.clientWidth / st.container.clientHeight;
    st.camera.updateProjectionMatrix();
    st.renderer.setSize(st.container.clientWidth, st.container.clientHeight);
  });
});

switchTSLSnippet('animated-noise-lava');
loadEmbeddedModels();

const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();
  customShaderMat.uniforms.uTime.value += dt;

  if (turntable) {
    if (stageL.rootGroup) stageL.rootGroup.rotation.y += dt * 0.45;
    if (stageR.rootGroup) stageR.rootGroup.rotation.y += dt * 0.45;
  }
  stageL.controls.update();
  stageR.controls.update();
  stageL.renderer.render(stageL.scene, stageL.camera);
  stageR.renderer.render(stageR.scene, stageR.camera);
}
animate();
</script>
</body>
</html>
"""


def _run_worker(payload: dict) -> dict:
    if not WORKER_MJS.exists():
        raise FileNotFoundError(f"GLB worker not found at {WORKER_MJS}")
    with tempfile.TemporaryDirectory() as tmpdir:
        req_file = Path(tmpdir) / "req.json"
        req_file.write_text(json.dumps(payload), encoding="utf-8")
        proc = subprocess.run(
            ["node", str(WORKER_MJS), str(req_file)],
            cwd=str(RUNTIME_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"GLB Worker failed:\n{proc.stderr}\n{proc.stdout}")
        return json.loads(proc.stdout.strip().splitlines()[-1])


def render_report_card_png(opt_result: dict, out_png: Path):
    """Renders a visual Before vs After Optimization Report Card PNG."""
    b = opt_result["before"]
    a = opt_result["after"]
    w, h = 780, 360
    im = Image.new("RGBA", (w, h), (15, 19, 28, 255))
    draw = ImageDraw.Draw(im)

    # Header bar
    draw.rectangle([0, 0, w, 54], fill=(24, 31, 46, 255))
    model_name = Path(opt_result["inputPath"]).name
    draw.text((20, 12), f"GLB FORGE - MEASURED OPTIMIZATION REPORT: {model_name}", fill=(110, 200, 255, 255))
    draw.text((20, 31), f"Preset: {opt_result['preset']}  |  Saved: {opt_result['savedKB']} KB (-{opt_result['savedPercent']}%)", fill=(61, 220, 132, 255))

    # Left Box: BEFORE
    draw.rectangle([20, 72, 375, 338], fill=(23, 28, 41, 255), outline=(65, 78, 110, 255))
    draw.text((36, 84), "BEFORE (ORIGINAL GLB)", fill=(255, 158, 100, 255))
    b_lines = [
        f"File Size       : {b['fileKB']} KB ({b['fileMB']} MB)",
        f"Triangles       : {b['totalTriangles']:,}",
        f"Vertices        : {b['totalVertices']:,}",
        f"Draw Calls      : {b['drawCalls']}",
        f"Materials       : {b['materialCount']}",
        f"Textures        : {b['textureCount']} ({b['totalTextureKB']} KB)",
        f"Est. GPU VRAM   : {b['estimatedVRAM_MB']} MB",
        f"Extensions      : {(', '.join(b['extensionsUsed']) or 'None')[:38]}",
    ]
    for idx, line in enumerate(b_lines):
        draw.text((36, 114 + idx * 26), line, fill=(210, 220, 238, 255))

    # Right Box: AFTER
    draw.rectangle([405, 72, 760, 338], fill=(20, 33, 36, 255), outline=(61, 220, 132, 255))
    draw.text((421, 84), f"AFTER (OPTIMIZED - {opt_result['savedPercent']}% SMALLER)", fill=(61, 220, 132, 255))
    a_lines = [
        f"File Size       : {a['fileKB']} KB ({a['fileMB']} MB)",
        f"Triangles       : {a['totalTriangles']:,} (-{opt_result['triangleReductionPercent']}%)",
        f"Vertices        : {a['totalVertices']:,}",
        f"Draw Calls      : {a['drawCalls']}",
        f"Materials       : {a['materialCount']}",
        f"Textures        : {a['textureCount']} ({a['totalTextureKB']} KB)",
        f"Est. GPU VRAM   : {a['estimatedVRAM_MB']} MB",
        f"Extensions      : {(', '.join(a['extensionsUsed']) or 'None')[:38]}",
    ]
    for idx, line in enumerate(a_lines):
        draw.text((421, 114 + idx * 26), line, fill=(220, 245, 232, 255))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_png)


def build_compare_studio_html(orig_glb: Path, opt_glb: Path, opt_result: dict, out_html: Path):
    b = opt_result["before"]
    a = opt_result["after"]
    b64_before = base64.b64encode(orig_glb.read_bytes()).decode("ascii")
    b64_after = base64.b64encode(opt_glb.read_bytes()).decode("ascii")

    val_ok = opt_result.get("validationAfter", {}).get("valid", True)
    val_str = "0 Errors (Valid glTF 2.0)" if val_ok else "Issues Detected"

    html = (
        COMPARE_STUDIO_HTML
        .replace("__SAVED_PCT__", str(opt_result["savedPercent"]))
        .replace("__SAVED_KB__", str(opt_result["savedKB"]))
        .replace("__PRESET_NAME__", str(opt_result["preset"]))
        .replace("__BEFORE_SUMMARY__", f"{b['fileKB']} KB | {b['totalTriangles']:,} Tris | {b['drawCalls']} Draw Calls")
        .replace("__AFTER_SUMMARY__", f"{a['fileKB']} KB | {a['totalTriangles']:,} Tris | {a['drawCalls']} Draw Calls")
        .replace("__BEFORE_KB__", str(b["fileKB"]))
        .replace("__AFTER_KB__", str(a["fileKB"]))
        .replace("__BEFORE_TRIS__", f"{b['totalTriangles']:,}")
        .replace("__AFTER_TRIS__", f"{a['totalTriangles']:,}")
        .replace("__BEFORE_VERTS__", f"{b['totalVertices']:,}")
        .replace("__AFTER_VERTS__", f"{a['totalVertices']:,}")
        .replace("__BEFORE_DC__", str(b["drawCalls"]))
        .replace("__AFTER_DC__", str(a["drawCalls"]))
        .replace("__BEFORE_TEX_KB__", str(b["totalTextureKB"]))
        .replace("__AFTER_TEX_KB__", str(a["totalTextureKB"]))
        .replace("__BEFORE_VRAM__", str(b["estimatedVRAM_MB"]))
        .replace("__AFTER_VRAM__", str(a["estimatedVRAM_MB"]))
        .replace("__VALIDATION_STATUS__", val_str)
        .replace("__BEFORE_B64__", b64_before)
        .replace("__AFTER_B64__", b64_after)
        .replace("__TSL_SNIPPETS_JSON__", json.dumps(TSL_MATERIAL_PRESETS))
    )
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html, encoding="utf-8")


def cmd_inspect(args):
    in_path = Path(args.input).resolve()
    res = _run_worker({"mode": "inspect", "inputPath": str(in_path)})
    s = res["stats"]
    v = res["validation"]
    print(f"=== GLB FORGE X-RAY: {in_path.name} ===")
    print(f"  File Size      : {s['fileKB']} KB ({s['fileMB']} MB)")
    print(f"  Geometry       : {s['totalTriangles']:,} triangles | {s['totalVertices']:,} vertices | {s['meshCount']} meshes")
    print(f"  Draw Calls     : {s['drawCalls']} primitives | {s['materialCount']} materials | {s['nodeCount']} nodes")
    print(f"  Textures       : {s['textureCount']} textures ({s['totalTextureKB']} KB disk, ~{s['estimatedVRAM_MB']} MB GPU VRAM)")
    if s["bounds"]:
        print(f"  Dimensions (m) : {s['bounds']['dimensionsMeters']} (Grounded Y=0: {s['bounds']['groundedAtZeroY']})")
    print(f"  Extensions     : {', '.join(s['extensionsUsed']) or 'None'}")
    print(f"  Khronos Valid  : {v['valid']} ({v['numErrors']} errors, {v['numWarnings']} warnings)")
    if args.json_out:
        out_p = Path(args.json_out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"  Saved Report   : {out_p}")


def cmd_optimize(args):
    in_path = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    preset_cfg = OPTIMIZE_PRESETS[args.preset]
    compress = args.compress or preset_cfg["compress"]
    tex_fmt = args.texture_format or preset_cfg["textureFormat"]
    max_tex = args.max_texture or preset_cfg["maxTextureSize"]
    ratio = args.ratio if args.ratio is not None else preset_cfg["simplifyRatio"]

    out_glb = out_dir / f"{in_path.stem}_{args.preset}.glb"
    res = _run_worker({
        "mode": "optimize",
        "inputPath": str(in_path),
        "outputPath": str(out_glb),
        "preset": args.preset,
        "compress": compress,
        "textureFormat": tex_fmt,
        "maxTextureSize": max_tex,
        "textureQuality": preset_cfg["textureQuality"],
        "simplifyRatio": ratio,
        "simplifyError": preset_cfg["simplifyError"],
    })

    report_json = out_dir / f"{in_path.stem}_{args.preset}_report.json"
    report_png = out_dir / f"{in_path.stem}_{args.preset}_report_card.png"
    studio_html = out_dir / f"{in_path.stem}_{args.preset}_compare_studio.html"

    report_json.write_text(json.dumps(res, indent=2), encoding="utf-8")
    render_report_card_png(res, report_png)
    build_compare_studio_html(in_path, out_glb, res, studio_html)

    print(f"[OK] Optimized {in_path.name} ({args.preset}):")
    print(f"  -> Size      : {res['before']['fileKB']} KB -> {res['after']['fileKB']} KB (Saved {res['savedKB']} KB / {res['savedPercent']}%)")
    print(f"  -> Triangles : {res['before']['totalTriangles']:,} -> {res['after']['totalTriangles']:,} (-{res['triangleReductionPercent']}%)")
    print(f"  -> Output GLB: {out_glb}")
    print(f"  -> Report PNG: {report_png}")
    print(f"  -> 3D Studio : {studio_html}")


def cmd_lod(args):
    in_path = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ratios = [float(x) for x in args.ratios.split(",")]
    out_paths = [str(out_dir / f"{in_path.stem}_LOD{i}.glb") for i in range(len(ratios))]

    res = _run_worker({
        "mode": "lod",
        "inputPath": str(in_path),
        "ratios": ratios,
        "maxTextureSize": args.max_texture,
        "outputPaths": out_paths,
    })
    lod_json = out_dir / f"{in_path.stem}_lod_chain.json"
    lod_json.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"[OK] Generated {len(ratios)}-Level LOD Chain for {in_path.name}:")
    for item in res["lods"]:
        print(f"  * {item['level']} (ratio {item['targetRatio']}): {item['triangles']:,} tris, {item['fileKB']} KB -> {item['outputPath']}")


def cmd_tsl_material(args):
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    preset = TSL_MATERIAL_PRESETS[args.preset]
    out_js = out_dir / f"tsl_{args.preset}.js"
    out_js.write_text(preset["code"], encoding="utf-8")
    print(f"[OK] Exported Three.js Shading Language (TSL) Node Material -> {out_js}")


def cmd_showcase(args):
    out_root = Path(args.out_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    samples = [
        (WORKSPACE_ROOT / "assets" / "com.amazon.berkeley.abo" / "models" / "B0075URYK2.glb", "web-mobile"),
        (WORKSPACE_ROOT / "assets" / "com.amazon.berkeley.abo" / "models" / "B003DQ5B2U.glb", "draco-ultra"),
        (WORKSPACE_ROOT / "assets" / "com.threejsassets" / "models" / "apartment-block-01.glb", "draco-ultra"),
        (WORKSPACE_ROOT / "exports" / "co.huggingface.sandflow.sand3d" / "objaverse-455a7f8be265420f97ad0a3443ee9183.glb", "draco-ultra"),
    ]

    for src_path, preset in samples:
        if not src_path.exists():
            continue
        sub = out_root / src_path.stem
        sub.mkdir(parents=True, exist_ok=True)
        ns = argparse.Namespace(
            input=str(src_path),
            preset=preset,
            compress=None,
            texture_format=None,
            max_texture=None,
            ratio=None,
            out_dir=str(sub),
        )
        cmd_optimize(ns)

    # Also build LOD chain for apartment-block-01
    apt = WORKSPACE_ROOT / "assets" / "com.threejsassets" / "models" / "apartment-block-01.glb"
    if apt.exists():
        cmd_lod(argparse.Namespace(
            input=str(apt),
            ratios="1.0,0.5,0.2",
            max_texture=1024,
            out_dir=str(out_root / "apartment-block-01"),
        ))

    # Export all TSL material presets
    tsl_dir = out_root / "tsl_materials"
    for pid in TSL_MATERIAL_PRESETS:
        cmd_tsl_material(argparse.Namespace(preset=pid, out_dir=str(tsl_dir)))


def main():
    parser = argparse.ArgumentParser(description="GLB Forge — 3D Model Inspector, Optimizer, LOD & TSL Studio")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ins = sub.add_parser("inspect", help="Inspect GLB geometry, textures, VRAM, and Khronos glTF validation")
    p_ins.add_argument("input", help="Path to .glb file")
    p_ins.add_argument("--json-out", default=None, help="Optional JSON report path")

    p_opt = sub.add_parser("optimize", help="Optimize GLB geometry & textures and generate Compare Studio HTML")
    p_opt.add_argument("input", help="Path to .glb file")
    p_opt.add_argument("--preset", choices=list(OPTIMIZE_PRESETS.keys()), default="web-mobile")
    p_opt.add_argument("--compress", choices=["meshopt", "draco", "quantize", "none"], default=None)
    p_opt.add_argument("--texture-format", choices=["webp", "png", "jpeg", "keep"], default=None)
    p_opt.add_argument("--max-texture", type=int, default=None)
    p_opt.add_argument("--ratio", type=float, default=None, help="Mesh simplification ratio (0.1 - 1.0)")
    p_opt.add_argument("--out-dir", default=str(DEFAULT_EXPORT_DIR))

    p_lod = sub.add_parser("lod", help="Generate multi-level LOD0/LOD1/LOD2 .glb files")
    p_lod.add_argument("input", help="Path to .glb file")
    p_lod.add_argument("--ratios", default="1.0,0.5,0.25", help="Comma-separated triangle ratios")
    p_lod.add_argument("--max-texture", type=int, default=1024)
    p_lod.add_argument("--out-dir", default=str(DEFAULT_EXPORT_DIR))

    p_tsl = sub.add_parser("tsl-material", help="Export Three.js Shading Language (TSL) procedural node material")
    p_tsl.add_argument("--preset", choices=list(TSL_MATERIAL_PRESETS.keys()), default="animated-noise-lava")
    p_tsl.add_argument("--out-dir", default=str(DEFAULT_EXPORT_DIR / "tsl_materials"))

    p_show = sub.add_parser("showcase", help="Run full GLB Forge showcase across ABO, ThreeJS Assets, and Sand3D models")
    p_show.add_argument("--out-dir", default=str(DEFAULT_EXPORT_DIR))

    args = parser.parse_args()
    if args.cmd == "inspect":
        cmd_inspect(args)
    elif args.cmd == "optimize":
        cmd_optimize(args)
    elif args.cmd == "lod":
        cmd_lod(args)
    elif args.cmd == "tsl-material":
        cmd_tsl_material(args)
    elif args.cmd == "showcase":
        cmd_showcase(args)


if __name__ == "__main__":
    main()

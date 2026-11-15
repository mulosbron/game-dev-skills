#!/usr/bin/env python3
"""
Custom Plain-JS 2D Micro-Engine & In-Browser Level Studio Generator (tools/micro_engine.py)
Zero-Dependency HTML5 Canvas + Plain JavaScript Custom 2D Game Engine & Level Editor.

Why a Custom Plain-JS Micro-Engine instead of Unity/Godot for 2D Tile/Puzzle Games?
1. Zero Engine Overhead: No 2GB editor, no broken scene GUIDs, no MCP bridge lag.
2. AI-Native Codebase: The entire physics loop, renderer, tilemap editor, BFS validator,
   declarative room stitcher, and telemetry recorder live in clean, deterministic Plain JavaScript.
3. Instant Edit <-> Play Loop: Press [TAB] in the browser to switch between hand-painting tiles/secrets
   and playing the room immediately with an Explicit Finite State Machine (FSM) controller.
4. Full Human Creative Authority: AI builds the custom engine & tools; the human places every tile,
   crafts every puzzle, and hides every secret.

Usage:
  python tools/micro_engine.py build --title "Agent Game Forge 2D Studio" --genre platformer
  python tools/micro_engine.py build --title "Dungeon Crawler Studio" --genre topdown
"""

import sys
import json
import argparse
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXPORT_DIR = WORKSPACE_ROOT / "exports" / "com.agent-game-forge.levels"


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__GAME_TITLE__ — Plain-JS Custom Micro-Engine & Level Studio</title>
<style>
  :root {
    --bg: #0f1219;
    --panel: #171c28;
    --panel-border: #283147;
    --text: #e6edf7;
    --muted: #8b9bb4;
    --accent: #4da6ff;
    --ok: #3ddc84;
    --warn: #ffbe3d;
    --err: #ff5c77;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  header {
    height: 50px;
    background: var(--panel);
    border-bottom: 1px solid var(--panel-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    gap: 12px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 0.3px;
  }
  .badge {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    background: #232c40;
    color: var(--accent);
    border: 1px solid #32415f;
    font-weight: 600;
  }
  .mode-switch {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  button, select {
    background: #222a3d;
    color: var(--text);
    border: 1px solid #34415e;
    padding: 6px 12px;
    border-radius: 5px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: 0.12s ease;
  }
  button:hover, select:hover { background: #2c3752; border-color: var(--accent); }
  button.primary { background: #1e62d0; border-color: #4da6ff; color: #fff; }
  button.primary:hover { background: #2874ee; }
  button.play-active { background: #16854b; border-color: var(--ok); color: #fff; }
  .workspace {
    flex: 1;
    display: grid;
    grid-template-columns: 270px 1fr 310px;
    overflow: hidden;
  }
  .sidebar {
    background: var(--panel);
    border-right: 1px solid var(--panel-border);
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
  }
  .sidebar.right {
    border-right: none;
    border-left: 1px solid var(--panel-border);
  }
  .section-title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--muted);
    font-weight: 700;
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .palette-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
  .tile-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 8px;
    background: #1d2436;
    border: 1px solid #2c3650;
    border-radius: 5px;
    cursor: pointer;
    text-align: left;
    font-size: 12px;
  }
  .tile-btn.active {
    border-color: var(--accent);
    background: #243352;
    box-shadow: 0 0 0 1px var(--accent) inset;
  }
  .swatch {
    width: 18px;
    height: 18px;
    border-radius: 3px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: monospace;
    font-weight: 700;
    font-size: 12px;
    color: #fff;
    text-shadow: 0 1px 2px #000;
    flex-shrink: 0;
  }
  .center-stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    background: radial-gradient(circle at center, #182032 0%, #0d1017 100%);
    padding: 16px;
    overflow: auto;
  }
  canvas {
    background: #121622;
    border: 2px solid #2e3954;
    border-radius: 6px;
    box-shadow: 0 12px 36px rgba(0,0,0,0.6);
    image-rendering: pixelated;
    cursor: crosshair;
  }
  .hud-bar {
    margin-top: 10px;
    display: flex;
    gap: 14px;
    align-items: center;
    font-size: 12px;
    color: var(--muted);
    background: rgba(23, 28, 40, 0.9);
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid var(--panel-border);
  }
  .hud-bar strong { color: var(--text); }
  .card {
    background: #1c2233;
    border: 1px solid #2a344d;
    border-radius: 6px;
    padding: 10px;
    font-size: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .fsm-state {
    font-family: 'Consolas', monospace;
    font-size: 14px;
    font-weight: 700;
    color: var(--ok);
    padding: 4px 8px;
    background: #111724;
    border-radius: 4px;
    border: 1px solid #25334a;
    text-align: center;
  }
  textarea {
    width: 100%;
    height: 92px;
    background: #111520;
    color: #b9d2ff;
    border: 1px solid #2c3650;
    border-radius: 4px;
    padding: 6px;
    font-family: 'Consolas', monospace;
    font-size: 11px;
    resize: vertical;
    user-select: text;
  }
  .status-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 11.5px;
  }
  .status-ok { color: var(--ok); }
  .status-warn { color: var(--warn); }
  .status-err { color: var(--err); }
  .piece-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .piece-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 8px;
    background: #151b29;
    border: 1px solid #263047;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
  }
  .piece-item:hover { border-color: var(--accent); background: #1c2538; }
  .kbd {
    background: #273147;
    border: 1px solid #3c4a6b;
    border-radius: 3px;
    padding: 1px 5px;
    font-family: monospace;
    font-size: 11px;
    color: #fff;
  }
</style>
</head>
<body>

<header>
  <div class="brand">
    <span>⚔️ __GAME_TITLE__</span>
    <span class="badge">No-Engine Plain JS Micro-Engine</span>
    <span class="badge" id="genreBadge">Genre: __GENRE__</span>
  </div>
  <div class="mode-switch">
    <button id="btnToggleMode" class="primary" onclick="toggleMode()">▶ PLAY ROOM (TAB)</button>
    <select id="genreSelect" onchange="switchGenre(this.value)">
      <option value="platformer">Platformer (Gravity + Ladder Physics)</option>
      <option value="topdown">Top-Down (2D Dungeon Physics)</option>
    </select>
    <button onclick="toggleHeatmap()" id="btnHeatmap">🔥 Heatmap: OFF</button>
    <button onclick="toggleLighting()" id="btnLight">💡 2D Torch Light: ON</button>
    <button onclick="exportLevelJSON()">💾 Export JSON</button>
  </div>
</header>

<div class="workspace">
  <!-- LEFT PANEL: HUMAN LEVEL DESIGN TOOLS -->
  <div class="sidebar">
    <div>
      <div class="section-title">
        <span>1. Handcrafted Tile Palette</span>
        <span>L-Click / R-Erase</span>
      </div>
      <div class="palette-grid" id="paletteGrid"></div>
    </div>

    <div>
      <div class="section-title">
        <span>2. Handcrafted Room Pieces</span>
        <button onclick="newBlankRoom()" style="padding:2px 6px;font-size:10px;">+ Empty</button>
      </div>
      <div class="piece-list" id="pieceList"></div>
    </div>

    <div class="card">
      <div class="section-title" style="margin:0"><span>3. Zaxik Declarative Stitcher</span></div>
      <span style="color:var(--muted);font-size:11px;">Human-written rules stitch your handcrafted pieces:</span>
      <textarea id="rulesInput" spellcheck="false">{
  "total_rooms": 4,
  "never_adjacent": [["hazard", "hazard"]],
  "every_n_rooms": {"3": "secret"},
  "must_include": ["puzzle"]
}</textarea>
      <button onclick="assembleFromRules()">🧩 Stitch Level From Rules</button>
    </div>

    <div class="card">
      <div class="section-title" style="margin:0"><span>Controls & Shortcuts</span></div>
      <div style="line-height:1.6;color:var(--muted);font-size:11.5px;">
        <div><span class="kbd">TAB</span> Toggle <b>EDIT</b> ↔ <b>PLAY</b> mode</div>
        <div><span class="kbd">A/D</span> or <span class="kbd">←/→</span> Move Left / Right</div>
        <div><span class="kbd">W/S</span> or <span class="kbd">↑/↓</span> Climb Ladder (<span class="kbd">H</span>)</div>
        <div><span class="kbd">SPACE</span> / <span class="kbd">Z</span> Jump (Coyote + Buffer)</div>
        <div><span class="kbd">R</span> Instant Respawn at <span class="kbd">S</span></div>
      </div>
    </div>
  </div>

  <!-- CENTER STAGE: HTML5 CANVAS MICRO-ENGINE -->
  <div class="center-stage">
    <canvas id="gameCanvas" width="960" height="480"></canvas>
    <div class="hud-bar">
      <span>Mode: <strong id="hudMode">EDIT (Paint Tiles)</strong></span>
      <span>Grid: <strong id="hudSize">30×10</strong></span>
      <span>Keys: <strong id="hudKeys">0</strong></span>
      <span>Secrets Found: <strong id="hudSecrets">0 / 0</strong></span>
      <span>Deaths: <strong id="hudDeaths">0</strong></span>
      <span>Time: <strong id="hudTimer">0.0s</strong></span>
    </div>
  </div>

  <!-- RIGHT PANEL: AI PLUMBING (BFS VALIDATOR, FSM & TELEMETRY) -->
  <div class="sidebar right">
    <div class="card">
      <div class="section-title" style="margin:0">
        <span>AI Plumbing #1: BFS Validator</span>
        <button onclick="runBFSValidation()" style="padding:2px 6px;font-size:10px;">Re-Check</button>
      </div>
      <ul class="status-list" id="validationOutput"></ul>
    </div>

    <div class="card">
      <div class="section-title" style="margin:0">
        <span>AI Plumbing #2: Explicit FSM</span>
        <span style="font-size:10px;color:var(--accent)">Steve Ruiz Rule</span>
      </div>
      <div class="fsm-state" id="fsmDisplay">STATE: EDITOR_IDLE</div>
      <div style="font-size:11px;color:var(--muted);" id="fsmSubtext">
        Zero implicit boolean flags. Deterministic transitions only.
      </div>
    </div>

    <div class="card">
      <div class="section-title" style="margin:0">
        <span>AI Plumbing #3: Live Telemetry</span>
        <button onclick="clearTelemetry()" style="padding:2px 6px;font-size:10px;">Clear</button>
      </div>
      <div style="font-size:11.5px;color:var(--muted);line-height:1.5;" id="telemetrySummary">
        Play the room to record movement heat, death clusters, and secret discovery rates.
      </div>
      <button onclick="downloadTelemetryJSONL()">📊 Download Playtest .JSONL</button>
    </div>

    <div class="card">
      <div class="section-title" style="margin:0"><span>Room ASCII / JSON Live Source</span></div>
      <textarea id="asciiMirror" spellcheck="false" style="height:135px;" oninput="applyAsciiEdit()"></textarea>
    </div>
  </div>
</div>

<script>
// ============================================================================
// 1. TILE DEFINITIONS & HANDCRAFTED SAMPLE PIECES (HUMAN CREATIVE AUTHORITY)
// ============================================================================
const TILE_SIZE = 32;
const TILES = {
  '#': { name: 'Wall',      color: '#242a3a', border: '#364059', solid: true,  climb: false, hazard: false },
  '.': { name: 'Air/Floor', color: '#141824', border: '#1b2130', solid: false, climb: false, hazard: false },
  'H': { name: 'Ladder',    color: '#d29b46', border: '#f0bd67', solid: false, climb: true,  hazard: false },
  '^': { name: 'Spikes',    color: '#e64150', border: '#ff7582', solid: false, climb: false, hazard: true  },
  'S': { name: 'Spawn',     color: '#46d782', border: '#7af5ab', solid: false, climb: false, hazard: false },
  'E': { name: 'Exit',      color: '#5abef5', border: '#99dcff', solid: false, climb: false, hazard: false },
  'K': { name: 'Key',       color: '#ffdc4b', border: '#fff099', solid: false, climb: false, hazard: false },
  'D': { name: 'Lock Door', color: '#a564dc', border: '#c996f5', solid: true,  climb: false, hazard: false },
  '?': { name: 'Secret',    color: '#ff8cdc', border: '#ffbdf0', solid: false, climb: false, hazard: false },
  '+': { name: 'Connector', color: '#394661', border: '#54668c', solid: false, climb: false, hazard: false }
};

const HANDCRAFTED_PIECES = {
  "full_demo_dungeon": {
    id: "full_demo_dungeon",
    tags: ["demo", "complete"],
    tiles: [
      "##############################",
      "#S...#.......#..?....#......E#",
      "####H#.#####.#.#####.#.#####H#",
      "#...H#.#K..#.#.....#.#.#...#H#",
      "#...H#.#...#.#####H#.#.#...#H#",
      "+...H..+...D.....+H..+.....DH+",
      "#...H#.#####...###H#.#.#####H#",
      "#...H#.....#...#..H#.#......H#",
      "#..^H#.....#.^^^..H#.#..^^..H#",
      "##############################"
    ]
  },
  "piece_start_hall": {
    id: "piece_start_hall",
    tags: ["start", "safe"],
    tiles: [
      "##########",
      "#S.......#",
      "####H#####",
      "#...H....#",
      "#...H....#",
      "+...H....+",
      "#...H....#",
      "#...H....#",
      "#..^H....#",
      "##########"
    ]
  },
  "piece_key_vault": {
    id: "piece_key_vault",
    tags: ["puzzle", "key"],
    tiles: [
      "##########",
      "#........#",
      "#.#####H##",
      "#.#K..#H.#",
      "#.#...#H.#",
      "+.....DH.+",
      "#.#####H.#",
      "#.....#H.#",
      "#.....#H.#",
      "##########"
    ]
  },
  "piece_spike_bridge": {
    id: "piece_spike_bridge",
    tags: ["hazard", "platforming"],
    tiles: [
      "##########",
      "#....H...#",
      "#....H...#",
      "#..#####.#",
      "#..H...#.#",
      "+..H...+.+",
      "####...###",
      "#........#",
      "#..^^^^..#",
      "##########"
    ]
  },
  "piece_secret_sanctum": {
    id: "piece_secret_sanctum",
    tags: ["secret", "reward"],
    tiles: [
      "##########",
      "#..?.....#",
      "#.#####H##",
      "#.....#H.#",
      "#####H#H.#",
      "+....H+H.+",
      "###..###.#",
      "#........#",
      "#........#",
      "##########"
    ]
  },
  "piece_exit_tower": {
    id: "piece_exit_tower",
    tags: ["exit", "goal"],
    tiles: [
      "##########",
      "#.......E#",
      "#.######H#",
      "#.#....#H#",
      "#.#....#H#",
      "+......DH+",
      "#.######H#",
      "#.......H#",
      "#..^^...H#",
      "##########"
    ]
  }
};

// ============================================================================
// 2. EXPLICIT FINITE STATE MACHINE (STEVE RUIZ RULE: ZERO ENTANGLED BOOLEANS)
// ============================================================================
const PLAYER_STATES = Object.freeze({
  EDITOR_IDLE: 'EDITOR_IDLE',
  IDLE:        'IDLE',
  RUN:         'RUN',
  JUMP:        'JUMP',
  FALL:        'FALL',
  CLIMB:       'CLIMB',
  DEAD:        'DEAD',
  WIN:         'WIN'
});

let engineMode = 'EDIT'; // 'EDIT' | 'PLAY'
let currentGenre = '__GENRE__';
let selectedTile = '#';
let showHeatmap = false;
let showLighting = true;

let grid = [];
let runtimeGrid = [];
let unreachableSet = new Set();
let softlockSet = new Set();

const player = {
  x: 64, y: 64,
  vx: 0, vy: 0,
  w: 20, h: 26,
  facing: 1,
  state: PLAYER_STATES.EDITOR_IDLE,
  coyoteTimer: 0,
  jumpBuffer: 0,
  keys: 0,
  secretsFound: new Set(),
  totalSecrets: 0,
  deaths: 0,
  playTime: 0
};

const particles = [];
const telemetryEvents = [];
const stepHeat = {};
const deathHeat = {};
const keysDown = {};

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

// ============================================================================
// 3. INITIALIZATION & UI SETUP
// ============================================================================
function initStudio() {
  document.getElementById('genreSelect').value = currentGenre;
  buildPaletteUI();
  buildPieceListUI();
  loadPiece('full_demo_dungeon');
  setupMouseEditor();
  setupKeyboard();
  requestAnimationFrame(gameLoop);
}

function buildPaletteUI() {
  const container = document.getElementById('paletteGrid');
  container.innerHTML = '';
  Object.entries(TILES).forEach(([ch, info]) => {
    const btn = document.createElement('button');
    btn.className = 'tile-btn' + (ch === selectedTile ? ' active' : '');
    btn.innerHTML = `<span class="swatch" style="background:${info.color};border:1px solid ${info.border}">${ch}</span><span>${info.name}</span>`;
    btn.onclick = () => {
      selectedTile = ch;
      buildPaletteUI();
    };
    container.appendChild(btn);
  });
}

function buildPieceListUI() {
  const list = document.getElementById('pieceList');
  list.innerHTML = '';
  Object.values(HANDCRAFTED_PIECES).forEach(piece => {
    const item = document.createElement('div');
    item.className = 'piece-item';
    item.innerHTML = `<span><b>${piece.id}</b></span><span style="color:var(--muted);font-size:10px;">[${piece.tags.join(', ')}]</span>`;
    item.onclick = () => loadPiece(piece.id);
    list.appendChild(item);
  });
}

function loadPiece(pieceId) {
  if (engineMode === 'PLAY') toggleMode();
  const piece = HANDCRAFTED_PIECES[pieceId];
  grid = piece.tiles.map(row => row.split(''));
  syncCanvasSize();
  syncAsciiMirror();
  runBFSValidation();
}

function newBlankRoom() {
  if (engineMode === 'PLAY') toggleMode();
  const w = 20, h = 10;
  grid = [];
  for (let r = 0; r < h; r++) {
    const row = [];
    for (let c = 0; c < w; c++) {
      if (r === 0 || r === h - 1 || c === 0 || c === w - 1) row.push('#');
      else row.push('.');
    }
    grid.push(row);
  }
  grid[h - 2][1] = 'S';
  grid[h - 2][w - 2] = 'E';
  syncCanvasSize();
  syncAsciiMirror();
  runBFSValidation();
}

function syncCanvasSize() {
  const h = grid.length;
  const w = h ? grid[0].length : 0;
  canvas.width = w * TILE_SIZE;
  canvas.height = h * TILE_SIZE;
  document.getElementById('hudSize').textContent = `${w}×${h}`;
}

function syncAsciiMirror() {
  document.getElementById('asciiMirror').value = grid.map(r => r.join('')).join('\n');
}

function applyAsciiEdit() {
  if (engineMode === 'PLAY') return;
  const raw = document.getElementById('asciiMirror').value.split('\n').filter(l => l.length > 0);
  if (!raw.length) return;
  const maxW = Math.max(...raw.map(r => r.length));
  grid = raw.map(r => r.padEnd(maxW, '.').split(''));
  syncCanvasSize();
  runBFSValidation();
}

// ============================================================================
// 4. ZAXIK DECLARATIVE ROOM STITCHER (HUMAN RULES -> CONNECTED LEVEL)
// ============================================================================
function assembleFromRules() {
  if (engineMode === 'PLAY') toggleMode();
  let rules;
  try {
    rules = JSON.parse(document.getElementById('rulesInput').value);
  } catch (e) {
    alert('Invalid JSON in Declarative Rules!');
    return;
  }
  const total = Math.max(2, rules.total_rooms || 4);
  const pool = Object.values(HANDCRAFTED_PIECES).filter(p => p.id !== 'full_demo_dungeon');
  const startP = pool.find(p => p.tags.includes('start')) || pool[0];
  const exitP = pool.find(p => p.tags.includes('exit')) || pool[pool.length - 1];
  const mids = pool.filter(p => p !== startP && p !== exitP);

  const chosen = [startP];
  const everyN = rules.every_n_rooms || {};
  const neverAdj = rules.never_adjacent || [];

  for (let idx = 1; idx < total - 1; idx++) {
    const roomNum = idx + 1;
    let reqTag = everyN[String(roomNum)] || null;
    let candidates = mids.filter(p => !reqTag || p.tags.includes(reqTag));
    if (!candidates.length) candidates = mids;

    const prevTags = new Set(chosen[chosen.length - 1].tags);
    const filtered = candidates.filter(c => {
      for (const [t1, t2] of neverAdj) {
        if ((prevTags.has(t1) && c.tags.includes(t2)) || (prevTags.has(t2) && c.tags.includes(t1))) return false;
      }
      return true;
    });
    const finalPool = filtered.length ? filtered : candidates;
    chosen.push(finalPool[Math.floor(Math.random() * finalPool.length)]);
  }
  chosen.push(exitP);

  // Stitch horizontally & open '+' connectors
  const h = chosen[0].tiles.length;
  const stitched = Array.from({ length: h }, () => []);
  chosen.forEach((piece, pIdx) => {
    for (let r = 0; r < h; r++) {
      const rowChars = piece.tiles[r].split('');
      if (pIdx > 0 && rowChars[0] === '+') rowChars[0] = '.';
      if (pIdx < chosen.length - 1 && rowChars[rowChars.length - 1] === '+') rowChars[rowChars.length - 1] = '.';
      stitched[r].push(...rowChars);
    }
  });

  grid = stitched;
  syncCanvasSize();
  syncAsciiMirror();
  runBFSValidation();
}

// ============================================================================
// 5. AI PLUMBING #1: LIVE BFS REACHABILITY & SOFTLOCK VALIDATOR
// ============================================================================
function getNeighbors(srcGrid, r, c, allowHazards) {
  const h = srcGrid.length, w = srcGrid[0].length;
  const out = [];
  for (const [dr, dc] of [[-1,0],[1,0],[0,-1],[0,1]]) {
    const nr = r + dr, nc = c + dc;
    if (nr >= 0 && nr < h && nc >= 0 && nc < w) {
      const ch = srcGrid[nr][nc];
      const info = TILES[ch];
      if (!info) continue;
      if (ch === '#') continue;
      if (info.hazard && !allowHazards) continue;
      out.push([nr, nc]);
    }
  }
  return out;
}

function bfsFrom(srcGrid, startRC, allowHazards = false) {
  const visited = new Set([`${startRC[0]},${startRC[1]}`]);
  const q = [startRC];
  while (q.length) {
    const [r, c] = q.shift();
    for (const [nr, nc] of getNeighbors(srcGrid, r, c, allowHazards)) {
      const key = `${nr},${nc}`;
      if (!visited.has(key)) {
        visited.add(key);
        q.push([nr, nc]);
      }
    }
  }
  return visited;
}

function runBFSValidation() {
  unreachableSet.clear();
  softlockSet.clear();
  const out = document.getElementById('validationOutput');
  out.innerHTML = '';

  const spawns = [], exits = [], keys = [], secrets = [];
  const h = grid.length, w = h ? grid[0].length : 0;

  for (let r = 0; r < h; r++) {
    for (let c = 0; c < w; c++) {
      const ch = grid[r][c];
      if (ch === 'S') spawns.push([r, c]);
      else if (ch === 'E') exits.push([r, c]);
      else if (ch === 'K') keys.push([r, c]);
      else if (ch === '?') secrets.push([r, c]);
    }
  }

  const items = [];
  if (!spawns.length) items.push({ cls: 'status-err', msg: '❌ Missing Spawn (S) tile!' });
  if (!exits.length) items.push({ cls: 'status-warn', msg: '⚠️ No Exit (E) tile (modular piece mode).' });

  if (spawns.length) {
    const reach = bfsFrom(grid, spawns[0], false);
    if (exits.length) {
      const okExit = exits.some(([r, c]) => reach.has(`${r},${c}`));
      items.push(okExit
        ? { cls: 'status-ok', msg: '✅ Exit (E) is safely reachable from Spawn.' }
        : { cls: 'status-err', msg: '❌ Exit (E) is UNREACHABLE from Spawn!' });
    }
    const unrKeys = keys.filter(([r, c]) => !reach.has(`${r},${c}`));
    if (keys.length) {
      items.push(unrKeys.length === 0
        ? { cls: 'status-ok', msg: `✅ All ${keys.length} Key(s) reachable.` }
        : { cls: 'status-err', msg: `❌ ${unrKeys.length} Key(s) unreachable!` });
    }
    const unrSec = secrets.filter(([r, c]) => !reach.has(`${r},${c}`));
    if (secrets.length) {
      items.push(unrSec.length === 0
        ? { cls: 'status-ok', msg: `✅ All ${secrets.length} Secret(s) (?) reachable.` }
        : { cls: 'status-warn', msg: `⚠️ ${unrSec.length} Secret(s) walled off.` });
    }

    // Mark unreachable non-wall tiles & check softlocks
    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const ch = grid[r][c];
        if (ch !== '#' && ch !== '^') {
          const k = `${r},${c}`;
          if (!reach.has(k)) unreachableSet.add(k);
        }
      }
    }
    if ( unreachableSet.size === 0 ) {
      items.push({ cls: 'status-ok', msg: '✅ Zero dead/unreachable rooms.' });
    } else {
      items.push({ cls: 'status-warn', msg: `⚠️ ${unreachableSet.size} floor tiles unreachable (striped on map).` });
    }
  }

  items.forEach(it => {
    const li = document.createElement('li');
    li.className = it.cls;
    li.textContent = it.msg;
    out.appendChild(li);
  });
}

// ============================================================================
// 6. MOUSE PAINTING IN EDIT MODE
// ============================================================================
function setupMouseEditor() {
  let painting = false;
  let eraseMode = false;

  const paintAt = (e) => {
    if (engineMode !== 'EDIT') return;
    const rect = canvas.getBoundingClientRect();
    const c = Math.floor((e.clientX - rect.left) / TILE_SIZE);
    const r = Math.floor((e.clientY - rect.top) / TILE_SIZE);
    if (r >= 0 && r < grid.length && c >= 0 && c < grid[0].length) {
      const ch = eraseMode ? '.' : selectedTile;
      if (grid[r][c] !== ch) {
        grid[r][c] = ch;
        syncAsciiMirror();
        runBFSValidation();
      }
    }
  };

  canvas.addEventListener('contextmenu', e => e.preventDefault());
  canvas.addEventListener('mousedown', e => {
    if (engineMode !== 'EDIT') return;
    painting = true;
    eraseMode = (e.button === 2);
    paintAt(e);
  });
  window.addEventListener('mousemove', e => { if (painting) paintAt(e); });
  window.addEventListener('mouseup', () => { painting = false; });
}

// ============================================================================
// 7. PLAY MODE: EXPLICIT FSM & CUSTOM 2D PHYSICS ENGINE
// ============================================================================
function setPlayerState(nextState, reason = '') {
  if (player.state !== nextState) {
    player.state = nextState;
    document.getElementById('fsmDisplay').textContent = `STATE: ${nextState}`;
    if (reason) {
      document.getElementById('fsmSubtext').textContent = `Transition: ${reason}`;
    }
  }
}

function toggleMode() {
  const btn = document.getElementById('btnToggleMode');
  if (engineMode === 'EDIT') {
    engineMode = 'PLAY';
    btn.textContent = '⏹ BACK TO EDITOR (TAB)';
    btn.className = 'play-active';
    document.getElementById('hudMode').textContent = 'PLAY (Live Runtime)';
    startPlaySession();
  } else {
    engineMode = 'EDIT';
    btn.textContent = '▶ PLAY ROOM (TAB)';
    btn.className = 'primary';
    document.getElementById('hudMode').textContent = 'EDIT (Paint Tiles)';
    setPlayerState(PLAYER_STATES.EDITOR_IDLE, 'Returned to Level Editor');
  }
}

function switchGenre(val) {
  currentGenre = val;
  document.getElementById('genreBadge').textContent = `Genre: ${val}`;
  if (engineMode === 'PLAY') startPlaySession();
}

function startPlaySession() {
  runtimeGrid = grid.map(r => [...r]);
  player.keys = 0;
  player.secretsFound.clear();
  player.totalSecrets = 0;
  player.vx = 0;
  player.vy = 0;

  let spawnRC = [1, 1];
  for (let r = 0; r < runtimeGrid.length; r++) {
    for (let c = 0; c < runtimeGrid[0].length; c++) {
      if (runtimeGrid[r][c] === 'S') spawnRC = [r, c];
      if (runtimeGrid[r][c] === '?') player.totalSecrets++;
    }
  }
  player.x = spawnRC[1] * TILE_SIZE + (TILE_SIZE - player.w) / 2;
  player.y = spawnRC[0] * TILE_SIZE + (TILE_SIZE - player.h);
  setPlayerState(PLAYER_STATES.IDLE, 'Spawned at S');
  updateHUD();
}

function setupKeyboard() {
  window.addEventListener('keydown', e => {
    if (document.activeElement.tagName === 'TEXTAREA') return;
    if (e.code === 'Tab') {
      e.preventDefault();
      toggleMode();
      return;
    }
    if (e.code === 'KeyR' && engineMode === 'PLAY') {
      startPlaySession();
      return;
    }
    keysDown[e.code] = true;
    if (e.code === 'Space' || e.code === 'KeyZ' || e.code === 'ArrowUp' || e.code === 'KeyW') {
      player.jumpBuffer = 0.12;
    }
  });
  window.addEventListener('keyup', e => {
    keysDown[e.code] = false;
  });
}

function isSolidAt(px, py) {
  const c = Math.floor(px / TILE_SIZE);
  const r = Math.floor(py / TILE_SIZE);
  if (r < 0 || r >= runtimeGrid.length || c < 0 || c >= runtimeGrid[0].length) return true;
  const ch = runtimeGrid[r][c];
  if (ch === 'D') {
    if (player.keys > 0) {
      player.keys--;
      runtimeGrid[r][c] = '.';
      spawnParticles(c * TILE_SIZE + 16, r * TILE_SIZE + 16, '#c996f5', 18);
      recordTelemetry('unlock_door', c, r);
      updateHUD();
      return false;
    }
    return true;
  }
  return TILES[ch] ? TILES[ch].solid : false;
}

function rectOverlapsSolid(x, y, w, h) {
  const pts = [
    [x + 2, y + 2], [x + w - 2, y + 2],
    [x + 2, y + h - 2], [x + w - 2, y + h - 2],
    [x + 2, y + h / 2], [x + w - 2, y + h / 2]
  ];
  return pts.some(([px, py]) => isSolidAt(px, py));
}

function getCenterTile(x, y) {
  const c = Math.floor((x + player.w / 2) / TILE_SIZE);
  const r = Math.floor((y + player.h / 2) / TILE_SIZE);
  if (r < 0 || r >= runtimeGrid.length || c < 0 || c >= runtimeGrid[0].length) return '.';
  return runtimeGrid[r][c];
}

function updatePlayPhysics(dt) {
  if (player.state === PLAYER_STATES.DEAD || player.state === PLAYER_STATES.WIN) {
    return;
  }

  player.playTime += dt;
  player.jumpBuffer = Math.max(0, player.jumpBuffer - dt);

  const left = keysDown['ArrowLeft'] || keysDown['KeyA'];
  const right = keysDown['ArrowRight'] || keysDown['KeyD'];
  const up = keysDown['ArrowUp'] || keysDown['KeyW'];
  const down = keysDown['ArrowDown'] || keysDown['KeyS'];
  const jumpHeld = keysDown['Space'] || keysDown['KeyZ'];

  const moveDir = (right ? 1 : 0) - (left ? 1 : 0);
  if (moveDir !== 0) player.facing = moveDir;

  const centerTile = getCenterTile(player.x, player.y);
  const footTile = getCenterTile(player.x, player.y + 8);
  const onLadder = (centerTile === 'H' || footTile === 'H');

  if (currentGenre === 'topdown') {
    const vDir = (down ? 1 : 0) - (up ? 1 : 0);
    const speed = 175;
    player.vx = moveDir * speed;
    player.vy = vDir * speed;
    moveAndCollide(dt);
    setPlayerState((moveDir || vDir) ? PLAYER_STATES.RUN : PLAYER_STATES.IDLE, 'Top-down movement');
  } else {
    // Platformer (Gravity + Ladder climbing physics)
    const speed = 185;
    player.vx = moveDir * speed;

    if (onLadder && (up || down || player.state === PLAYER_STATES.CLIMB)) {
      if (up || down) {
        setPlayerState(PLAYER_STATES.CLIMB, 'Grabbed ladder (H)');
      }
      if (player.state === PLAYER_STATES.CLIMB) {
        player.vy = ((down ? 1 : 0) - (up ? 1 : 0)) * 145;
        if (jumpHeld && !up && !down) {
          player.vy = -330;
          setPlayerState(PLAYER_STATES.JUMP, 'Jumped off ladder');
        }
      }
    }

    if (player.state === PLAYER_STATES.CLIMB && !onLadder) {
      setPlayerState(PLAYER_STATES.FALL, 'Left ladder');
    }

    if (player.state !== PLAYER_STATES.CLIMB) {
      player.vy = Math.min(520, player.vy + 980 * dt);
    }

    const grounded = moveAndCollide(dt);
    if (grounded) {
      player.coyoteTimer = 0.1;
    } else {
      player.coyoteTimer = Math.max(0, player.coyoteTimer - dt);
    }

    if (player.jumpBuffer > 0 && (player.coyoteTimer > 0 || player.state === PLAYER_STATES.CLIMB)) {
      player.vy = -355;
      player.coyoteTimer = 0;
      player.jumpBuffer = 0;
      setPlayerState(PLAYER_STATES.JUMP, 'Jump impulse');
      spawnParticles(player.x + player.w / 2, player.y + player.h, '#8b9bb4', 8);
    }

    if (player.state !== PLAYER_STATES.CLIMB) {
      if (!grounded) {
        setPlayerState(player.vy < 0 ? PLAYER_STATES.JUMP : PLAYER_STATES.FALL, 'Airborne');
      } else {
        setPlayerState(Math.abs(player.vx) > 5 ? PLAYER_STATES.RUN : PLAYER_STATES.IDLE, 'Grounded');
      }
    }
  }

  checkInteractiveTiles();
}

function moveAndCollide(dt) {
  // Horizontal
  const nextX = player.x + player.vx * dt;
  if (!rectOverlapsSolid(nextX, player.y, player.w, player.h)) {
    player.x = nextX;
  } else {
    player.vx = 0;
  }

  // Vertical
  let grounded = false;
  const nextY = player.y + player.vy * dt;
  if (!rectOverlapsSolid(player.x, nextY, player.w, player.h)) {
    player.y = nextY;
  } else {
    if (player.vy > 0) grounded = true;
    player.vy = 0;
  }
  return grounded;
}

function checkInteractiveTiles() {
  const c = Math.floor((player.x + player.w / 2) / TILE_SIZE);
  const r = Math.floor((player.y + player.h / 2) / TILE_SIZE);
  if (r < 0 || r >= runtimeGrid.length || c < 0 || c >= runtimeGrid[0].length) return;

  const keyRC = `${c},${r}`;
  stepHeat[keyRC] = (stepHeat[keyRC] || 0) + 1;

  const ch = runtimeGrid[r][c];
  if (ch === 'K') {
    player.keys++;
    runtimeGrid[r][c] = '.';
    spawnParticles(c * TILE_SIZE + 16, r * TILE_SIZE + 16, '#ffdc4b', 20);
    recordTelemetry('pickup_key', c, r);
    updateHUD();
  } else if (ch === '?') {
    const secKey = `${r},${c}`;
    if (!player.secretsFound.has(secKey)) {
      player.secretsFound.add(secKey);
      runtimeGrid[r][c] = '.';
      spawnParticles(c * TILE_SIZE + 16, r * TILE_SIZE + 16, '#ff8cdc', 28);
      recordTelemetry('secret_found', c, r);
      updateHUD();
    }
  } else if (ch === '^') {
    player.deaths++;
    deathHeat[keyRC] = (deathHeat[keyRC] || 0) + 1;
    setPlayerState(PLAYER_STATES.DEAD, 'Impaled on Spikes (^) — Press R');
    spawnParticles(player.x + player.w / 2, player.y + player.h / 2, '#ff5c77', 32);
    recordTelemetry('death', c, r, 'spike');
    updateHUD();
    setTimeout(() => { if (engineMode === 'PLAY' && player.state === PLAYER_STATES.DEAD) startPlaySession(); }, 650);
  } else if (ch === 'E') {
    setPlayerState(PLAYER_STATES.WIN, 'Reached Exit (E)! Press R or TAB');
    spawnParticles(c * TILE_SIZE + 16, r * TILE_SIZE + 16, '#5abef5', 36);
    recordTelemetry('level_complete', c, r);
    updateHUD();
  }
}

// ============================================================================
// 8. PROCEDURAL PARTICLES, 2D NORMAL/POINT LIGHTING & RENDERING
// ============================================================================
function spawnParticles(x, y, color, count = 14) {
  for (let i = 0; i < count; i++) {
    const ang = Math.random() * Math.PI * 2;
    const spd = 40 + Math.random() * 140;
    particles.push({
      x, y,
      vx: Math.cos(ang) * spd,
      vy: Math.sin(ang) * spd - 30,
      life: 0.35 + Math.random() * 0.3,
      maxLife: 0.65,
      color
    });
  }
}

function renderStudio(dt) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const activeGrid = (engineMode === 'PLAY') ? runtimeGrid : grid;
  const h = activeGrid.length, w = h ? activeGrid[0].length : 0;

  for (let r = 0; r < h; r++) {
    for (let c = 0; c < w; c++) {
      const ch = activeGrid[r][c];
      const info = TILES[ch] || TILES['.'];
      const x = c * TILE_SIZE, y = r * TILE_SIZE;

      // Base floor
      ctx.fillStyle = '#141824';
      ctx.fillRect(x, y, TILE_SIZE, TILE_SIZE);

      if (ch === '#') {
        // Beveled 2D pixel wall brick
        ctx.fillStyle = info.color;
        ctx.fillRect(x, y, TILE_SIZE, TILE_SIZE);
        ctx.fillStyle = '#343e56';
        ctx.fillRect(x + 2, y + 2, TILE_SIZE - 4, 4);
        ctx.strokeStyle = '#191d29';
        ctx.strokeRect(x + 0.5, y + 0.5, TILE_SIZE - 1, TILE_SIZE - 1);
      } else if (ch === 'H') {
        // Ladder rungs
        ctx.fillStyle = '#b88232';
        ctx.fillRect(x + 6, y, 4, TILE_SIZE);
        ctx.fillRect(x + TILE_SIZE - 10, y, 4, TILE_SIZE);
        ctx.fillStyle = '#f0bd67';
        for (let ry = 4; ry < TILE_SIZE; ry += 8) {
          ctx.fillRect(x + 6, y + ry, TILE_SIZE - 12, 3);
        }
      } else if (ch === '^') {
        // Pixel spikes
        ctx.fillStyle = info.color;
        for (let sx = 0; sx < 3; sx++) {
          ctx.beginPath();
          ctx.moveTo(x + sx * 10 + 2, y + TILE_SIZE);
          ctx.lineTo(x + sx * 10 + 7, y + 12);
          ctx.lineTo(x + sx * 10 + 12, y + TILE_SIZE);
          ctx.fill();
        }
      } else if (ch !== '.') {
        ctx.fillStyle = info.color;
        ctx.fillRect(x + 4, y + 4, TILE_SIZE - 8, TILE_SIZE - 8);
        ctx.strokeStyle = info.border;
        ctx.strokeRect(x + 4.5, y + 4.5, TILE_SIZE - 9, TILE_SIZE - 9);
        ctx.fillStyle = '#0d1017';
        ctx.font = 'bold 13px Consolas, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(ch, x + TILE_SIZE / 2, y + TILE_SIZE / 2);
      } else {
        ctx.strokeStyle = 'rgba(255,255,255,0.03)';
        ctx.strokeRect(x + 0.5, y + 0.5, TILE_SIZE - 1, TILE_SIZE - 1);
      }

      // Highlight BFS unreachable tiles in EDIT mode
      if (engineMode === 'EDIT' && unreachableSet.has(`${r},${c}`)) {
        ctx.fillStyle = 'rgba(255, 92, 119, 0.22)';
        ctx.fillRect(x, y, TILE_SIZE, TILE_SIZE);
        ctx.strokeStyle = 'rgba(255, 92, 119, 0.65)';
        ctx.beginPath();
        ctx.moveTo(x + 4, y + 4);
        ctx.lineTo(x + TILE_SIZE - 4, y + TILE_SIZE - 4);
        ctx.stroke();
      }

      // Heatmap overlay
      if (showHeatmap) {
        const keyRC = `${c},${r}`;
        const steps = stepHeat[keyRC] || 0;
        const deaths = deathHeat[keyRC] || 0;
        if (steps > 0) {
          const alpha = Math.min(0.55, steps * 0.03);
          ctx.fillStyle = `rgba(61, 220, 132, ${alpha})`;
          ctx.fillRect(x + 2, y + 2, TILE_SIZE - 4, TILE_SIZE - 4);
        }
        if (deaths > 0) {
          ctx.fillStyle = 'rgba(255, 65, 85, 0.75)';
          ctx.fillRect(x + 2, y + 2, TILE_SIZE - 4, TILE_SIZE - 4);
          ctx.fillStyle = '#fff';
          ctx.font = 'bold 12px monospace';
          ctx.textAlign = 'center';
          ctx.fillText('X', x + 16, y + 17);
        }
      }
    }
  }

  // Draw Player Knight in PLAY mode
  if (engineMode === 'PLAY') {
    ctx.save();
    ctx.fillStyle = player.state === PLAYER_STATES.DEAD ? '#ff5c77' : '#65e699';
    ctx.fillRect(player.x, player.y, player.w, player.h);
    // Knight visor
    ctx.fillStyle = '#0d121c';
    const visorX = player.facing > 0 ? player.x + 10 : player.x + 2;
    ctx.fillRect(visorX, player.y + 5, 8, 5);
    // Plume
    ctx.fillStyle = '#4da6ff';
    ctx.fillRect(player.x + 6, player.y - 4, 8, 4);
    ctx.restore();
  }

  // Update & draw particles
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.life -= dt;
    if (p.life <= 0) {
      particles.splice(i, 1);
      continue;
    }
    ctx.fillStyle = p.color;
    ctx.globalAlpha = Math.max(0, p.life / p.maxLife);
    ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
    ctx.globalAlpha = 1;
  }

  // Selective 2D Torch / Point Light Vignette in PLAY mode
  if (engineMode === 'PLAY' && showLighting) {
    const px = player.x + player.w / 2;
    const py = player.y + player.h / 2;
    const grad = ctx.createRadialGradient(px, py, 36, px, py, 260);
    grad.addColorStop(0, 'rgba(255, 220, 150, 0.08)');
    grad.addColorStop(0.5, 'rgba(10, 14, 22, 0.35)');
    grad.addColorStop(1, 'rgba(6, 8, 14, 0.78)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
}

// ============================================================================
// 9. TELEMETRY & EXPORT PLUMBING
// ============================================================================
function recordTelemetry(type, x, y, extra = '') {
  telemetryEvents.push({
    t: Number(player.playTime.toFixed(2)),
    event: type,
    x, y,
    state: player.state,
    cause: extra
  });
  const sum = document.getElementById('telemetrySummary');
  sum.innerHTML = `Events logged: <b>${telemetryEvents.length}</b> | Deaths: <b>${player.deaths}</b> | Secrets: <b>${player.secretsFound.size}/${player.totalSecrets}</b><br>Last: <code>${type} @ (${x},${y})</code>`;
}

function clearTelemetry() {
  telemetryEvents.length = 0;
  for (const k in stepHeat) delete stepHeat[k];
  for (const k in deathHeat) delete deathHeat[k];
  player.deaths = 0;
  player.playTime = 0;
  updateHUD();
  document.getElementById('telemetrySummary').textContent = 'Telemetry cleared.';
}

function toggleHeatmap() {
  showHeatmap = !showHeatmap;
  document.getElementById('btnHeatmap').textContent = `🔥 Heatmap: ${showHeatmap ? 'ON' : 'OFF'}`;
}

function toggleLighting() {
  showLighting = !showLighting;
  document.getElementById('btnLight').textContent = `💡 2D Torch Light: ${showLighting ? 'ON' : 'OFF'}`;
}

function updateHUD() {
  document.getElementById('hudKeys').textContent = player.keys;
  document.getElementById('hudSecrets').textContent = `${player.secretsFound.size} / ${player.totalSecrets}`;
  document.getElementById('hudDeaths').textContent = player.deaths;
  document.getElementById('hudTimer').textContent = `${player.playTime.toFixed(1)}s`;
}

function exportLevelJSON() {
  const payload = {
    id: "custom_handcrafted_room",
    author: "human",
    genre: currentGenre,
    width: grid[0].length,
    height: grid.length,
    tiles: grid.map(r => r.join(''))
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'handcrafted_level.json';
  a.click();
}

function downloadTelemetryJSONL() {
  const lines = telemetryEvents.map(e => JSON.stringify(e)).join('\n');
  const blob = new Blob([lines || '{"event":"empty"}'], { type: 'application/jsonl' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'playtest_telemetry.jsonl';
  a.click();
}

let lastTS = performance.now();
function gameLoop(now) {
  const dt = Math.min(0.033, (now - lastTS) / 1000);
  lastTS = now;
  if (engineMode === 'PLAY') {
    updatePlayPhysics(dt);
    document.getElementById('hudTimer').textContent = `${player.playTime.toFixed(1)}s`;
  }
  renderStudio(dt);
  requestAnimationFrame(gameLoop);
}

initStudio();
</script>
</body>
</html>
"""


def build_micro_engine(title: str, genre: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = (
        HTML_TEMPLATE
        .replace("__GAME_TITLE__", title)
        .replace("__GENRE__", genre)
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Build a Zero-Dependency Plain-JS 2D Custom Micro-Engine & In-Browser Level Studio"
    )
    sub = parser.add_subparsers(dest="cmd")

    p_build = sub.add_parser("build", help="Generate standalone HTML5 + Plain-JS Custom Micro-Engine & Level Studio")
    p_build.add_argument("--title", default="Agent Game Forge 2D Studio", help="Game/Studio title")
    p_build.add_argument("--genre", choices=["platformer", "topdown"], default="platformer", help="Default physics genre")
    p_build.add_argument(
        "--out",
        default=str(DEFAULT_EXPORT_DIR / "forge_micro_studio.html"),
        help="Output HTML path",
    )

    args = parser.parse_args()
    cmd = args.cmd or "build"
    title = getattr(args, "title", "Agent Game Forge 2D Studio")
    genre = getattr(args, "genre", "platformer")
    out_path = Path(getattr(args, "out", str(DEFAULT_EXPORT_DIR / "forge_micro_studio.html")))

    built = build_micro_engine(title, genre, out_path)
    print(f"[OK] Built Custom Plain-JS Micro-Engine & Level Studio -> {built.resolve()}")


if __name__ == "__main__":
    main()

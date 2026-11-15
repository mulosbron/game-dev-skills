---
name: claude-code-game-studios
description: "Complete AI game studio architecture and production router (`Donchitos/Claude-Code-Game-Studios`). Coordinates 78 slash subskills (`subskills/`), 49 role-tiered studio & engine agents (`agents/`), 4 engine profiles (`engines/`), 69 genre chipsets & art direction (`genres/`), 14 path-scoped rules (`rules/`), 54 helper scripts (`scripts/`), and 28 director/QA/playtest gates (`docs/`)."
license: MIT
metadata:
  repository: "https://github.com/Donchitos/Claude-Code-Game-Studios"
---

# Claude Code Game Studios — Master Studio Router (`claude-code-game-studios`)

Structured full-lifecycle game production framework covering ideation, rapid playable browser prototyping, GDD/ADR authoring, multi-engine implementation (**Web**, **Godot 4**, **Unity**, **Unreal Engine 5**), automated visual run-and-observe verification, QA/playtest gates, and release shipping.

---

## Package Layout Inside This Skill

| Directory | Contents | Count |
|---|---|---|
| [`subskills/`](subskills/) | Complete slash-command subskill playbooks (75 commands + 3 legacy redirect aliases: `help` → `next-step`, `settings` → `project-settings`, `changelog` → `write-changelog`) | 78 dirs (209 files) |
| [`agents/`](agents/) | Tiered Director, Department Lead, Specialist, and Engine Specialist agent definitions | 49 `.md` files |
| [`engines/`](engines/) | Unified engine table (`engines.tsv`), schema docs (`README.md`), and Vite/TypeScript/Playwright `web/` starter scaffold | 3 items (28 files) |
| [`genres/`](genres/) | Genre design & art direction pack: `chipsets.yaml`, `art-direction.md`, `mashups.md`, `online-and-devices.md`, `sources.md`, and 69 genre sheets in `chipsets/` | 6 items (74 files) |
| [`rules/`](rules/) | Path-scoped coding, design-doc, shader, narrative, network, prototype, scene, test, and skill rules | 14 `.md` files |
| [`docs/`](docs/) | `workflow-catalog.yaml`, `director-gates.md` + 28 `director-gates/` specs, `run-and-observe.md`, `skills-reference.md`, `templates/` (62 templates), `hooks-reference/`, config/automation docs | 29 items (134 files) |
| [`scripts/`](scripts/) | Shell/AWK/JS/GDScript utilities (`artifact-check.sh`, `page-shot.sh`, `test-run.sh`, `one-shot-*.sh`, `godot-parse-check.gd`, `itch-zip.sh`, etc.) | 54 files |

---

## Core Production Workflows & Rigor Tiers

Configuration lives in `project.yaml` (overridable personally via `project.local.yaml`). The primary knob is **`modes.rigor`**:

- **`minimal`** (default, light path): `/prototype` asks genre-tuned questions, writes a one-page `design/game-brief.md`, builds a double-clickable browser prototype (`prototypes/<name>/`), runs a headless Chromium/Edge check, and hands it over. Grow it into a Vite/TypeScript web project or configure an engine (`/setup-engine`) and build feature-by-feature or story-by-story (`/create-stories` → `/dev-story` → `/story-done`).
- **`standard`**: Adds 5 required GDD sections, balanced doc depth, Logic + Integration QA evidence, and `lean` review mode (`PHASE-GATE` directors only).
- **`full`**: All 8 GDD sections, thorough docs, full test coverage + regression suites, `full` director gates on every step, and `studio` specialist depth.

### 7-Phase Production Ladder (`docs/workflow-catalog.yaml`)

1. **Concept** (`/start`, `/brainstorm`, `/art-bible`, `/map-systems`, `/setup-engine`)
2. **Systems Design** (`/design-system`, `/quick-design`, `/design-review`, `/review-all-gdds`, `/ux-design`)
3. **Technical Setup** (`/create-architecture`, `/architecture-decision`, `/architecture-review`, `/create-control-manifest`, `/test-setup`)
4. **Pre-Production** (`/prototype`, `/vertical-slice`)
5. **Production** (`/create-epics`, `/create-stories`, `/sprint-plan`, `/story-readiness`, `/dev-story`, `/story-done`, `/sprint-status`)
6. **Polish** (`/perf-profile`, `/balance-check`, `/playtest-report`, `/smoke-check`, `/soak-test`, `/regression-suite`, `/bug-triage`, `/cut`)
7. **Release** (`/release-checklist`, `/launch-checklist`, `/write-changelog`, `/patch-notes`, `/hotfix`, `/day-one-patch`)

---

## Subskill Router (`subskills/`)

| Domain | Subskills (`subskills/<name>/SKILL.md`) |
|---|---|
| **Onboarding & Navigation** | `start`, `next-step`, `project-stage-detect`, `setup-engine`, `adopt`, `project-settings` *(aliases: `help`, `settings`)* |
| **Prototyping & Finishing** | `prototype`, `vertical-slice`, `cut`, `onboard`, `localize` |
| **Game Design & Narrative** | `brainstorm`, `map-systems`, `design-system`, `quick-design`, `review-all-gdds`, `propagate-design-change`, `consistency-check` |
| **Art, Assets & UX** | `art-bible`, `asset-spec`, `asset-audit`, `ux-design`, `ux-review` |
| **Architecture** | `create-architecture`, `architecture-decision`, `architecture-review`, `create-control-manifest` |
| **Sprints & Implementation** | `create-epics`, `create-stories`, `dev-story`, `sprint-plan`, `sprint-status`, `story-readiness`, `story-done`, `estimate` |
| **Reviews & Auditing** | `design-review`, `code-review`, `balance-check`, `content-audit`, `scope-check`, `perf-profile`, `tech-debt`, `gate-check`, `security-audit` |
| **QA, Testing & Playtest** | `qa-plan`, `smoke-check`, `soak-test`, `regression-suite`, `test-setup`, `test-helpers`, `test-evidence-review`, `test-flakiness`, `bug-report`, `bug-triage`, `playtest-report`, `milestone-review`, `retrospective`, `reverse-document` |
| **Release & Live Ops** | `release-checklist`, `launch-checklist`, `write-changelog`, `patch-notes`, `hotfix`, `day-one-patch` *(alias: `changelog`)* |
| **Framework QA** | `skill-test`, `skill-improve` |
| **Team Orchestration** | `team-combat`, `team-narrative`, `team-ui`, `team-release`, `team-polish`, `team-audio`, `team-level`, `team-live-ops`, `team-qa` |

---

## Studio Agent Hierarchy (`agents/`)

- **Tier 1 — Directors** (3): `creative-director`, `technical-director`, `producer`
- **Tier 2 — Department Leads** (8): `game-designer`, `lead-programmer`, `art-director`, `audio-director`, `narrative-director`, `qa-lead`, `release-manager`, `localization-lead`
- **Tier 3 — Core Specialists** (23): `gameplay-programmer`, `engine-programmer`, `ai-programmer`, `network-programmer`, `tools-programmer`, `ui-programmer`, `systems-designer`, `level-designer`, `economy-designer`, `technical-artist`, `sound-designer`, `writer`, `world-builder`, `ux-designer`, `prototyper`, `performance-analyst`, `devops-engineer`, `analytics-engineer`, `security-engineer`, `qa-tester`, `accessibility-specialist`, `live-ops-designer`, `community-manager`
- **Engine Specialists** (15):
  - **Godot 4** (5): `godot-specialist`, `godot-gdscript-specialist`, `godot-csharp-specialist`, `godot-shader-specialist`, `godot-gdextension-specialist`
  - **Unity** (5): `unity-specialist`, `unity-dots-specialist`, `unity-shader-specialist`, `unity-addressables-specialist`, `unity-ui-specialist`
  - **Unreal Engine 5** (5): `unreal-specialist`, `ue-gas-specialist`, `ue-blueprint-specialist`, `ue-replication-specialist`, `ue-umg-specialist`

**Collaboration Protocol**: Agents default to **Question → Options → Decision → Draft → Approval** (asking before writing files or running multi-file edits), with vertical delegation, horizontal consultation, and `production/session-state/active.md` as the persistent session checkpoint.

---

## Engines, Genres & Path-Scoped Rules

- **Engine Matrix (`engines/engines.tsv`)**:
  - **Web**: `code_root=src`, `test_root=tests`, `asset_root=assets`, `npm run dev` / `build` / `test` / `smoke` (Vite + TypeScript + optional Three.js / Phaser / PixiJS scaffold in `engines/web/`).
  - **Godot**: `code_root=src`, `test_root=tests`, `asset_root=assets`, `gdUnit4` headless test command, `--quit-after 5` smoke check.
  - **Unity**: `code_root=Assets`, `test_root=Assets/Tests`, `asset_root=Assets`.
  - **Unreal**: `code_root=Source`, `test_root=Source/<Module>/Private/Tests`, `asset_root=Content`.
- **Genre & Look Playbooks (`genres/`)**: `chipsets.yaml` maps user pitches onto **69 genre sheets** (`genres/chipsets/*.md` — platformer, survivors-like, roguelike-deckbuilder, soulslike, city-builder, cozy-cleanup, etc.), paired with `art-direction.md` (silhouette/palette/mood discipline, zero unrequested emoji art), `mashups.md`, and `online-and-devices.md`.
- **Coding & Content Rules (`rules/`)**: 14 path-scoped standards covering `gameplay-code.md`, `engine-code.md`, `ai-code.md`, `network-code.md`, `ui-code.md`, `shader-code.md`, `scene-files.md`, `data-files.md`, `prototype-code.md`, `design-docs.md`, `narrative.md`, `test-standards.md`, `agent-memory.md`, and `skill-authoring.md`.

---

## QA, Visual Run-and-Observe & Director Gates

1. **Visual Run-and-Observe (`docs/run-and-observe.md`)**: Every player-visible story must be launched windowed (never `--headless` / `-batchmode` / `-nullrhi`, except Web via headless Chrome/Edge `scripts/page-shot.sh`), observed via screenshot, and retained under `production/qa/evidence/<story-slug>/` with hash stamps (`scripts/review-receipts.sh`) before closing.
2. **QA & Smoke Pipeline**:
   - `/qa-plan` classifies sprint/feature stories (`Logic`, `Integration`, `Visual`, `UI`) before implementation starts (includes mandatory `N=0` empty-scope block).
   - `/smoke-check` (`sprint` / `quick`, `--platform pc|console|mobile|all`) gates hand-off to QA — failing builds do not enter QA.
   - `/playtest-report` generates structured first-5-minutes/pain-point templates or analyzes playtest notes (`CD-PLAYTEST` review).
   - `/soak-test`, `/regression-suite`, `/test-evidence-review`, and `/test-flakiness` guard stability.
3. **Director & Phase Gates (`docs/director-gates.md` & `subskills/gate-check/SKILL.md`)**:
   - **28 gate specs** under `docs/director-gates/` (`CD-*`, `TD-*`, `PR-*`, `AD-*`, `LP-*`, `QL-*`, `ND-*`), returning `APPROVE/READY`, `CONCERNS`, `REJECT/NOT READY`, or `NOT ASSESSED` (strictest-verdict escalation; spawned agents read their own gate file directly).
   - Controlled by `modes.review_mode` (`solo` skips all gates, `lean` runs `PHASE-GATE`s only, `full` runs all gates; overridable per run via `--review [full|lean|solo]`).
   - `/gate-check` validates readiness between the 7 production phases and dual-writes `project.stage` in `project.yaml` and `production/stage.txt` upon approval.

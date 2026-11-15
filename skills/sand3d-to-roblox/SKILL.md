---
name: sand3d-to-roblox
description: >-
  Search Sand3D's 100,000+ open-source parametric 3D datasets, reconstruct models via headless
  Blender + Sand3D, optimize geometry (bottom-center grounded pivots, 10k triangle budgets),
  and import persistent 3D assets into Roblox Studio, Godot, Unreal, or GameMaker 3D from
  natural language scene prompts (e.g. 'post-apocalyptic bunker', 'cozy cafe props').
---

# Sand3D to Roblox & Game Engine 3D Pipeline

Turn natural language scene prompts (e.g., *"Make a post-apocalyptic bunker with wall weapons and dirty computers"* or *"Find five cozy props and put them in my scene"*) into actual, reconstructed 3D game assets from **Sand3D's 100,000+ open-source collection** (`Sandflow/sand3d-objaverse`, `simready`, `cad`, `articraft`, `automate`).

All Sand3D assets are code-defined (Python parametric programs), 100% cleared for commercial use (CC0, CC-BY-4.0, Apache 2.0), and compiled into clean binary `.glb` and `.blend` files via local headless Blender.

---

## ⚡ The 5-Step AI Agent Workflow

```
[1. Search 100k+ Dataset] -> [2. Headless Reconstruct] -> [3. Optimize Geometry] -> [4. Roblox / Engine Import] -> [5. Verify & Attribute]
DuckDB Remote Parquet       Blender 5.2 + Sand3D 1.6.3   10k Triangles, Grounded    Open Cloud / Lua / GLB        CC-BY Legal Ledger
```

### 1. Search & Browse (`search`)
Search remote HuggingFace datasets via DuckDB HTTP range queries without downloading gigabytes of data:
```powershell
# Search everyday props in Objaverse:
python tools/sand3d_builder.py search "computer" --wanted 6

# Search industrial CAD and mechanical tools:
python tools/sand3d_builder.py search "drill" --dataset cad

# Search NVIDIA SimReady props:
python tools/sand3d_builder.py search "crate" --dataset simready
```
Returns numbered choices with IDs, families, licenses, attributions, and interactive USDA 3D preview links. Results are cached in `catalogs/sand3d_search_cache.json`.

### 2. Reconstruct & Finish (`build`)
Reconstructs the parametric Python code in Blender 5.2 headlessly:
```powershell
# Rebuild by selection number from recent search:
python tools/sand3d_builder.py build 1

# Rebuild by asset ID directly:
python tools/sand3d_builder.py build "objaverse-455a7f8be265420f97ad0a3443ee9183" --budget 8000
```
- Re-executes the exact Sand3D procedural program.
- Automatically sets **Bottom-Center grounded pivot** $(x_{center}, y_{center}, z_{ground})$ so props place directly onto floors or terrain without sinking.
- Converts millimeter source measurements to meters.
- Applies Decimate modifier if triangle count exceeds the budget (default: 10,000 tris).
- Exports ready `.glb`, `.blend`, `metadata.json`, and appends attribution to [`assets/co.huggingface.sandflow.sand3d/LICENSES.txt`](assets/co.huggingface.sandflow.sand3d/LICENSES.txt).

### 3. Natural Language Scene Batch (`batch`)
Give a prompt, and the agent/script searches and rebuilds matching props automatically:
```powershell
python tools/sand3d_builder.py batch "post-apocalyptic bunker props" --count 5
```

---

## 🟥 Roblox Studio Deployment Pipeline

Each build automatically generates an `import_to_roblox.lua` helper inside the output directory:

### Method A: Studio Native 3D Importer (Key-Free)
1. Open your Roblox Studio Place.
2. In the top ribbon, select **Avatar** → **3D Importer**.
3. Select the generated `.glb` file in `exports/co.huggingface.sandflow.sand3d/<asset_id>/<asset_id>.glb`.
4. Check **Import as Single Model**, set Anchor to True for decorative props, and click **Import**.

### Method B: Roblox Open Cloud Asset Upload (Automated API)
If `ROBLOX_API_KEY` is configured in your environment:
- POST GLB to `https://apis.roblox.com/assets/v1/assets` multipart with `assetType: Model`.
- In Studio Command Bar, execute:
  ```lua
  local model = game:GetService("InsertService"):LoadAsset(ASSET_ID)
  model.Parent = workspace.Sand3D_Assets
  ```

### Method C: Grouping & Attribution Attributes
The generated Lua script automatically attaches legal metadata attributes to each Model in Roblox:
- `SourceId`: Original Sand3D / Objaverse ID
- `Dataset`: `Sandflow/sand3d-objaverse`
- `License`: `CC-BY-4.0`
- `Attribution`: Author name and source link

---

## 🎮 Multi-Engine Support (Godot, Unreal, GameMaker)

The exported `.glb` files are standard binary glTF 2.0 with embedded PBR materials:
- **Godot 4:** Drag `.glb` directly into your Godot project `assets/models/` folder.
- **Unreal Engine 5:** Import directly via Interchange / glTF Importer.
- **GameMaker Studio 3D:** Load via vertex buffer or 3D model loaders.

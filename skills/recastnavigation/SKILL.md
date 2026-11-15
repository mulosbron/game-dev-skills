---
name: recastnavigation
description: Recast & Detour C++ navmesh generation, pathfinding, tile cache, and crowd simulation guidance. Use when integrating Recast voxel heightfields, Detour dtNavMesh/dtNavMeshQuery, DetourTileCache dynamic obstacles, DetourCrowd steering/avoidance, coordinate system conventions, or CMake options.
---

# Recast Navigation

Industry-standard C++98 navigation mesh toolset (v1.6.0, ZLib license) with zero STL, RTTI, or C++ exception dependencies (`CMakeLists.txt` compiles with `/GR- /EHs-c-` on MSVC and `-fno-rtti -fno-exceptions` elsewhere).

## Coordinate System & Winding Conventions

- **Coordinate System:** **Right-handed Y-up** (`+Y` is up). Convert Z-up engines (e.g. `(x, y, z)` -> `(x, z, -y)` or consistent right-handed swizzle) before passing geometry and transforms.
- **Triangle Winding:** Input triangles MUST be wound **clockwise (CW)** when viewed from above (`Docs/_3_FAQ.md`). Counter-clockwise ground triangles are treated as undersides and ignored/culled from walkable areas.

## CMake Targets & Options

Requires **CMake >= 3.15**. Exported CMake targets: `RecastNavigation::Recast`, `RecastNavigation::Detour`, `RecastNavigation::DetourTileCache`, `RecastNavigation::DetourCrowd`, plus `DebugUtils`.

| CMake Option / Define | Default | Effect |
| :--- | :--- | :--- |
| `RECASTNAVIGATION_DEMO` | `ON` | Build SDL/OpenGL `RecastDemo` application |
| `RECASTNAVIGATION_TESTS` | `ON` | Build Catch2 unit test suite |
| `RECASTNAVIGATION_EXAMPLES` | `ON` | Build example programs |
| `RECASTNAVIGATION_DT_POLYREF64` (`DT_POLYREF64`) | `OFF` | Use 64-bit `dtPolyRef` / `dtTileRef` for massive multi-tile worlds |
| `RECASTNAVIGATION_DT_VIRTUAL_QUERYFILTER` (`DT_VIRTUAL_QUERYFILTER`) | `OFF` | Enable virtual methods on `dtQueryFilter` so custom filters can subclass it |
| `RECASTNAVIGATION_ENABLE_ASSERTS` (`RC_DISABLE_ASSERTS`) | Debug only | Enable/disable `rcAssert` / `dtAssert` |
| `RECASTNAVIGATION_ENABLE_FAST_MATH` (`RC_FAST_MATH`) | `OFF` | Enable `/fp:fast` / `-ffast-math` fast math optimizations |

## Recast Navmesh Generation (`Recast.h`)

Configure `rcConfig` (note: agent dimensions like `walkableHeight`, `walkableClimb`, `walkableRadius` and `borderSize`/`tileSize` are specified in **voxel units**, derived from `cs` cell size and `ch` cell height):

- **Key `rcConfig` Fields:** `cs`, `ch`, `tileSize`, `borderSize`, `walkableSlopeAngle` (degrees), `walkableHeight`, `walkableClimb`, `walkableRadius`, `maxEdgeLen`, `maxSimplificationError`, `minRegionArea`, `mergeRegionArea`, `maxVertsPerPoly` (<= `DT_VERTS_PER_POLYGON`), `detailSampleDist`, `detailSampleMaxError`.
- **Solo & Tiled Build Pipeline:**
  1. Compute grid dimensions (`rcCalcGridSize`) and allocate `rcHeightfield` (`rcAllocHeightfield` / `rcCreateHeightfield`). For **tiled** builds, expand tile `bmin`/`bmax` horizontally by `borderSize * cs` before rasterizing neighbor triangles.
  2. Mark walkable slope (`rcMarkWalkableTriangles`) and voxelize triangles (`rcRasterizeTriangles`).
  3. Clean overhanging/unwalkable spans: `rcFilterLowHangingWalkableObstacles`, `rcFilterLedgeSpans`, `rcFilterWalkableLowHeightSpans`.
  4. Compact & erode: `rcBuildCompactHeightfield` -> `rcErodeWalkableArea` (shrinks walkable area by `walkableRadius`).
  5. Partition regions (choose one):
     - **Watershed (best quality, solo/off-line):** `rcBuildDistanceField` -> `rcBuildRegions`.
     - **Monotone (fastest, good for streaming/tiled):** `rcBuildRegionsMonotone`.
     - **Layers (2.5D overlapping slabs for tile cache):** `rcBuildLayerRegions` / `rcBuildHeightfieldLayers`.
  6. Extract polygons: `rcBuildContours` (`rcContourSet`) -> `rcBuildPolyMesh` (`rcPolyMesh`) -> `rcBuildPolyMeshDetail` (`rcPolyMeshDetail`). Free intermediates with `rcFree*`.

## Detour NavMesh & Path Queries (`DetourNavMesh.h`, `DetourNavMeshQuery.h`)

- **Packaging (`DetourNavMeshBuilder.h`):** Populate `dtNavMeshCreateParams` from `rcPolyMesh` + `rcPolyMeshDetail` (plus optional off-mesh connections and area/flag arrays), then call `dtCreateNavMeshData`.
- **Initialization:**
  - *Solo mesh:* `dtNavMesh::init(data, dataSize, DT_TILE_FREE_DATA)`.
  - *Tiled mesh:* `dtNavMesh::init(&dtNavMeshParams)` (`orig`, `tileWidth`, `tileHeight`, `maxTiles`, `maxPolys`), then stream tiles via `addTile` / `removeTile`.
- **Querying (`dtNavMeshQuery`):**
  - Initialize via `dtNavMeshQuery::init(navMesh, maxNodes)` (`maxNodes` max `65535`).
  - Configure `dtQueryFilter` (include/exclude poly flags and per-area traversal costs; subclassing requires `-DRECASTNAVIGATION_DT_VIRTUAL_QUERYFILTER=ON`).
  - Standard flow: `findNearestPoly` (start & end points + half-extents) -> `findPath` (outputs `dtPolyRef` corridor) -> `findStraightPath` (string-pulls funnel waypoints).
  - Additional tools: time-sliced queries (`initSlicedFindPath`, `updateSlicedFindPath`, `finalizeSlicedFindPath`), local clamping (`moveAlongSurface`), line-of-sight (`raycast`), and `findRandomPoint` / `findRandomPointAroundCircle`.

## DetourTileCache & Dynamic Obstacles (`DetourTileCache.h`, `DetourTileCacheBuilder.h`)

Rebuilds individual compressed 2.5D tiles at runtime without re-voxelizing raw scene geometry:

- **Offline Layer Generation:** Build `rcHeightfieldLayerSet` via `rcBuildHeightfieldLayers`, compress layers with `dtBuildTileCacheLayer` (using a `dtTileCacheCompressor`), and feed into `dtTileCache::init(&dtTileCacheParams, talloc, tcomp, tmproc)` + `dtTileCache::addTile`.
- **Runtime Obstacles:** Call `addObstacle` (cylinder), `addBoxObstacle` (AABB or Y-axis rotated OBB), or `removeObstacle`.
- **Frame Tick:** Call `dtTileCache::update(dt, navMesh, &upToDate)` each frame to process deferred obstacle requests and regenerate affected `dtNavMesh` tiles.

## DetourCrowd Local Steering (`DetourCrowd.h`)

- Initialize `dtCrowd::init(maxAgents, maxAgentRadius, navMesh)` and register up to `DT_CROWD_MAX_OBSTAVOIDANCE_PARAMS = 8` RVO/sampling profiles via `setObstacleAvoidanceParams`.
- Spawn agents with `addAgent(pos, &dtCrowdAgentParams)` (radius, height, maxAcceleration, maxSpeed, `updateFlags`, `obstacleAvoidanceType`, `separationWeight`).
- Common `UpdateFlags`: `DT_CROWD_ANTICIPATE_TURNS`, `DT_CROWD_OBSTACLE_AVOIDANCE`, `DT_CROWD_SEPARATION`, `DT_CROWD_OPTIMIZE_VIS`, `DT_CROWD_OPTIMIZE_TOPO`.
- Drive agents with `requestMoveTarget` / `requestMoveVelocity` / `resetMoveTarget`, step via `update(dt, debug)`, and read positions/velocities via `getActiveAgents`. Per-agent limits: `DT_CROWDAGENT_MAX_NEIGHBOURS = 6`, `DT_CROWDAGENT_MAX_CORNERS = 4`.

## Pitfalls

- Passing CCW triangles produces an empty `rcPolyMesh`; verify CW top-down triangle winding and Y-up conversion first.
- Mixing voxel units (`walkableHeight`, `walkableRadius`) with world-space meters (`cs`, `ch`) causes broken erosion or doorway filtering.
- Subclassing `dtQueryFilter` silently fails unless `RECASTNAVIGATION_DT_VIRTUAL_QUERYFILTER=ON` (`DT_VIRTUAL_QUERYFILTER`) is defined consistently across library and application builds.

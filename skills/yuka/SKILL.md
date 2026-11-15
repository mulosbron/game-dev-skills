---
name: yuka
description: Zero-dependency, engine-agnostic JavaScript Game AI library (v0.7.8). Use when implementing game entity loops, steering behaviors and Vehicles, finite state machines (FSM), Think/Goal/GoalEvaluator AI, NavMesh or Graph A* pathfinding, Vision/MemorySystem perception, Triggers, fuzzy logic, or JSON save/load.
---

# Yuka

Zero-dependency, engine-agnostic JavaScript Game AI library (`yuka` v0.7.8, MIT; `WorldUp = new Vector3(0, 1, 0)`; bundles `build/yuka.js`, `build/yuka.min.js`, `build/yuka.module.js`, ESM entry `src/yuka.js`).

## Core Loop, Entities & Messaging

```js
import * as YUKA from "yuka";

const time = new YUKA.Time();
const entityManager = new YUKA.EntityManager();

const entity = new YUKA.GameEntity();
entity.setRenderComponent(mesh, (e, renderComp) => {
  renderComp.matrix.copy(e.worldMatrix);
});
entityManager.add(entity);

function animate() {
  const delta = time.update().getDelta(); // seconds
  entityManager.update(delta);
}
```

- **`Time`**: `update()`, `getDelta()` (seconds), `getElapsed()` (seconds), `setFixedDelta(sec)` + `enableFixedDelta()` / `disableFixedDelta()`, `setTimescale(scale)`, `reset()`. Hooks `document` `visibilitychange` to prevent huge delta spikes on tab resume; call `time.dispose()` when tearing down.
- **`EntityManager`**: `add(entity)`, `remove(entity)`, `clear()`, `getEntityByName(name)`, `update(delta)`. Per update it calls `start()` once + `update(delta)` + children updates, computes neighborhoods (`entity.updateNeighborhood`, `neighborhoodRadius`, `neighbors`, optional `spatialIndex` = `CellSpacePartitioning`), syncs render components, runs `Trigger.check(entity)` after transforms update, and dispatches `MessageDispatcher` telegrams.
- **`GameEntity`**: `name`, `active`, `children`/`parent`, `position` (`Vector3`), `rotation` (`Quaternion`), `scale` (`Vector3`), `forward` `(0,0,1)`, `up` `(0,1,0)`, `boundingRadius`, `maxTurnRate` (`Math.PI`), `canActivateTrigger` (`true`), `worldMatrix` (auto-updated on access — `updateWorldMatrix()` is deprecated), `lookAt(target)`, `rotateTo(target, delta, tolerance)`, `getWorldPosition(res)`, `getWorldDirection(res)`.
- **Messaging**: `entity.sendMessage(receiver, msg, delayMs = 0, data = null)` (note: `delay` is in **milliseconds**) delivers to `receiver.handleMessage(telegram)`.
- **`MovingEntity`** (extends `GameEntity`): adds `velocity`, `maxSpeed`, `updateOrientation` (`true`), `getSpeed()`, `getSpeedSquared()`.

## Vehicles & Steering Behaviors

- **`Vehicle`** (extends `MovingEntity`): `mass = 1`, `maxForce = 100`, `steering = new SteeringManager(this)`, `smoother = null` (`Smoother` smooths orientation only, not position).
- **`SteeringManager`**: `add(behavior)`, `remove(behavior)`, `clear()`. Evaluates active behaviors in insertion order weighted by `behavior.weight` until `vehicle.maxForce` is exhausted.
- **Built-in behaviors**:
  - Target / velocity: `SeekBehavior`, `FleeBehavior`, `ArriveBehavior`, `PursuitBehavior`, `EvadeBehavior`, `OffsetPursuitBehavior`, `InterposeBehavior`.
  - Exploration / pathing: `WanderBehavior`, `FollowPathBehavior` (`Path`), `OnPathBehavior`, `ObstacleAvoidanceBehavior`.
  - Group flocking: `SeparationBehavior`, `AlignmentBehavior`, `CohesionBehavior`.

## Finite State Machines & Goal-Driven AI

- **Finite State Machine (`StateMachine(owner)`)**:
  - Register states via `add(id, state)`, `remove(id)`, `get(id)`; transition via `changeTo(id)`, `revert()`, `in(id)`; optional `globalState`; drive with `update()` and `handleMessage(telegram)`.
  - Subclass `State`: implement `enter(owner)`, `execute(owner)`, `exit(owner)`, and `onMessage(owner, telegram)` (return `true` if handled).
- **Goal-Driven AI (`Think` / `Goal` / `GoalEvaluator`)**:
  - `Think(owner)` extends `CompositeGoal` -> `Goal`. Register evaluators via `think.addEvaluator(evaluator)` (`GoalEvaluator(characterBias)` implements `calculateDesirability(owner)` and `setGoal(owner)`).
  - Calling `think.execute()` calls `arbitrate()` when inactive and runs `executeSubgoals()`.
  - `CompositeGoal`: `addSubgoal`, `removeSubgoal`, `clearSubgoals`, `currentSubgoal`, `executeSubgoals`.
  - `Goal.STATUS`: `INACTIVE`, `ACTIVE`, `COMPLETED`, `FAILED`, plus `replanIfFailed()`, `activateIfInactive()`.

## Graph Search & NavMesh

- **`Graph` & Search**:
  - `Graph`: `digraph` flag, `addNode(Node)`, `addEdge(Edge)`, `removeNode`, `removeEdge`, `getNode`, `getEdge`, `getEdgesOfNode`.
  - Algorithms & helpers: `AStar(graph, source, target)` (`search()`, `found`, `getPath()`, `heuristic = HeuristicPolicyEuclid`), `Dijkstra`, `BFS`, `DFS`, `PriorityQueue`, `GraphUtils`, `NavNode`, `NavEdge`, `CostTable`.
- **`NavMesh`**:
  - Build from geometry with `navMesh.fromPolygons(polygons)` (`mergeConvexRegions = true`, `epsilonCoplanarTest = 1e-3`, `epsilonContainsTest = 1`), or load glTF/glb with `new NavMeshLoader().load(url, options)` / `.parse(arrayBuffer, url, options)` (for Node.js, use `.glb` with embedded buffers; interleaved vertex data is not supported).
  - For large meshes, assign `navMesh.spatialIndex` (`CellSpacePartitioning`) and call `updateSpatialIndex()`.
  - Queries: `findPath(from, to)` (A* + `Corridor` string pulling -> `Vector3[]`; falls back to `getClosestRegion` if outside), `getRegionForPoint(point, epsilon)`, `getClosestRegion(point)`, `getRandomRegion()`, and `clampMovement(currentRegion, startPos, endPos, clampPosition)` (slides along border edges and returns the new `Polygon` region).

## Perception, Triggers & Fuzzy Logic

- **`Vision(owner)`**: `fieldOfView = Math.PI`, `range = Infinity`, `addObstacle(entity)` (obstacles must implement `lineOfSightTest(ray, intersectionPoint)`), `visible(point)`.
- **`MemorySystem(owner)`**: `memorySpan = 1` (seconds), `createRecord(entity)`, `getRecord(entity)`, `hasRecord(entity)`, `deleteRecord(entity)`, `getValidMemoryRecords(currentTime, result)` -> `MemoryRecord[]`.
- **`Trigger(region)`**: subclass and implement `execute(entity)`. Regions: `SphericalTriggerRegion`, `RectangularTriggerRegion` (extend `TriggerRegion`). `canActivateTrigger` defaults `false` on `Trigger` itself and `true` on `GameEntity`.
- **Fuzzy Logic**:
  - `FuzzyModule`: `addFLV(name, flv)`, `addRule(rule)`, `fuzzify(name, value)`, `defuzzify(name, FuzzyModule.DEFUZ_TYPE.MAXAV | CENTROID)`.
  - Components: `FuzzyVariable`, `FuzzyRule`, `FuzzyCompositeTerm`, fuzzy sets (`TriangularFuzzySet`, `LeftShoulderFuzzySet`, `RightShoulderFuzzySet`, `LeftSCurveFuzzySet`, `RightSCurveFuzzySet`, `NormalDistFuzzySet`, `SingletonFuzzySet`), and operators (`FuzzyAND`, `FuzzyOR`, `FuzzyVERY`, `FuzzyFAIRLY`).

## JSON Save / Load

- `entityManager.toJSON()` / `entityManager.fromJSON(json)` serializes and restores entities (`GameEntity`, `MovingEntity`, `Vehicle`, `Trigger`), `SteeringManager`, `MessageDispatcher`, and cross-entity UUID links via `resolveReferences(entitiesMap)`.
- `Graph`, `State`, `Vision`, `MemorySystem`, `Smoother`, and `Path` also implement `toJSON` / `fromJSON`.
- **Custom classes**: Register constructors with `registerType(typeName, Constructor)` on `EntityManager`, `SteeringManager`, `StateMachine`, `Think`, and `Trigger` before calling `fromJSON(json)`, and override `toJSON()`, `fromJSON(json)`, and `resolveReferences(entitiesMap)` as needed.

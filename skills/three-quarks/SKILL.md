---
name: three-quarks
description: Batched GPU/CPU particle system and VFX engine for Three.js (v0.17.1). Use when building instanced particle systems, ribbon trails, mesh surface emitters, particle behaviors, Quarks JSON loading/serialization, node-graph VFX (CPU or WebGPU), or integrating with Three.js and React Three Fiber.
---

# three.quarks

Batched GPU/CPU particle system and VFX engine for Three.js (`three.quarks` v0.17.1, `quarks.core` v0.17.1, `quarks.r3f` v0.17.1, `quarks.nodes` v0.17.1, MIT; requires `three >= 0.182.0`).

## Core Setup & Render Loop

Add one `BatchedRenderer` to your Three.js scene (`BatchedParticleRenderer` is a deprecated alias for `BatchedRenderer`). It groups `ParticleSystem` instances sharing `material`, `renderMode`, `uTileCount`, `vTileCount`, `blendTiles`, `softParticles`, `softNearFade`, `softFarFade`, `instancingGeometry`, `renderOrder`, and `layers` into shared `SpriteBatch` (`InstancedBufferGeometry`) or `TrailBatch` meshes (`VFXBatch` extends `THREE.Mesh`, `frustumCulled = false`).

```ts
import {
  BatchedRenderer,
  ParticleSystem,
  ConstantValue,
  IntervalValue,
  PointEmitter,
  RenderMode,
} from "three.quarks";

const batchRenderer = new BatchedRenderer();
scene.add(batchRenderer);

const ps = new ParticleSystem({
  duration: 5,
  looping: true,
  startLife: new IntervalValue(1, 2),
  startSpeed: new IntervalValue(2, 5),
  startSize: new ConstantValue(0.3),
  emissionOverTime: new ConstantValue(30),
  shape: new PointEmitter(),
  material,
  renderMode: RenderMode.BillBoard,
});

scene.add(ps.emitter); // ParticleEmitter (Object3D)
batchRenderer.addSystem(ps);

// Inside render loop before renderer.render(scene, camera):
batchRenderer.update(delta);
```

- **Key `ParticleSystem` options**: `duration`, `looping`, `prewarm`, `autoDestroy`, `startLife`, `startSpeed`, `startSize`, `startRotation`, `startLength`, `startColor`, `emissionOverTime`, `emissionOverDistance`, `emissionBursts`, `onlyUsedByOther`, `shape`, `material`, `instancingGeometry`, `renderMode`, `rendererEmitterSettings`, `behaviors`, `worldSpace`, `speedFactor`, `uTileCount`, `vTileCount`, `startTileIndex`, `blendTiles`, `softParticles`, `softNearFade`, `softFarFade`, `renderOrder`, `layers`.
- **Batch & lifecycle control**:
  - Call `batchRenderer.updateSystem(ps)` after mutating batch-keyed settings, `batchRenderer.deleteSystem(ps)` to remove, and `batchRenderer.setDepthTexture(depthTexture)` when using soft particles.
  - Control playback with `ps.play()`, `ps.pause()`, `ps.stop()`, `ps.restart()`, `ps.endEmit()`, `ps.addBehavior(b)`, `ps.clone()`.
  - Events emitted on `ps`: `"emitEnd"`, `"destroy"`, `"particleDied"`.

## Render Modes & Ribbon Trails

- `RenderMode.BillBoard` — camera-facing instanced quads (`SpriteBatch`).
- `RenderMode.StretchedBillBoard` — velocity-stretched quads (`rendererEmitterSettings: { speedFactor, lengthFactor }`).
- `RenderMode.Mesh` — instanced `instancingGeometry` (`MeshSettings`).
- `RenderMode.Trail` — GPU/CPU ribbon trails rendered by `TrailBatch` (`rendererEmitterSettings` accepts `TrailSettings`: `{ startLength: ValueGenerator | FunctionValueGenerator, followLocalOrigin: boolean }`; commonly paired with `WidthOverLength`).
- `RenderMode.HorizontalBillBoard` / `RenderMode.VerticalBillBoard`.

## Emitter Shapes, Generators & Behaviors

- **Emitter shapes** (`quarks.core` + `three.quarks`): `PointEmitter`, `ConeEmitter`, `SphereEmitter`, `HemisphereEmitter`, `CircleEmitter`, `DonutEmitter`, `RectangleEmitter`, `GridEmitter`, and `MeshSurfaceEmitter(geometry?)` (`three.quarks`, registered via `MeshSurfaceEmitterPlugin` — requires indexed `BufferGeometry`, samples triangles proportional to area and emits along face normal).
- **Value, color & rotation generators**:
  - Value: `ConstantValue`, `IntervalValue`, `Bezier` + `PiecewiseBezier`, `ContinuousLinearFunction`.
  - Color: `ConstantColor`, `ColorRange`, `RandomColor`, `Gradient`, `RandomColorBetweenGradient`.
  - Rotation / Vec3: `AxisAngleGenerator`, `EulerGenerator`, `RandomQuatGenerator`, `Vector3Function`.
- **Behaviors**:
  - Over-life / length: `ColorOverLife`, `SizeOverLife`, `RotationOverLife`, `Rotation3DOverLife`, `SpeedOverLife`, `ForceOverLife`, `OrbitOverLife`, `FrameOverLife` (texture atlas flipbook), `WidthOverLength` (trails), `LimitSpeedOverLife`.
  - Forces & environment: `ApplyForce`, `GravityForce`, `ChangeEmitDirection`, `TurbulenceField`, `Noise`, `ApplySequences` (`TextureSequencer`), `ApplyCollision` (`setPhysicsResolver`).
  - Speed-driven & sub-emitters: `ColorBySpeed`, `SizeBySpeed`, `RotationBySpeed`, `EmitSubParticleSystem` (`SubParticleEmitMode`).

## JSON Serialization, Loading & Prefabs

- **System JSON (`version: "3.0"`)**: Serialize with `ps.toJSON(meta, { useUrlForImage })` and deserialize with `ParticleSystem.fromJSON(json, meta, dependencies)`.
- **`QuarksLoader`** (extends `THREE.ObjectLoader`): `loader.load(url, (effect) => ...)` or `loader.parse(json)` instantiates `ParticleEmitter` and `QuarksPrefab` hierarchies and calls `linkReference(object)` so `EmitSubParticleSystem` references resolve automatically.
- **`QuarksUtil`**: Helpers for loaded hierarchies: `addToBatchRenderer(obj, batchRenderer)`, `play(obj)`, `pause(obj)`, `stop(obj)`, `restart(obj)`, `endEmit(obj)`, `setAutoDestroy(obj, value)`, `runOnAllParticleEmitters(obj, fn)`.
- **`QuarksPrefab`** (`THREE.Group`): Timeline sequencer combining Three.js animation clips (`addThreeAnimation(target, clip, startTime, duration, loop)`) and particle emitters (`addParticleSystemAnimation(emitter, startTime, duration, loop)`).

## React Three Fiber (`quarks.r3f`) & Node Graphs (`quarks.nodes`)

- **React Three Fiber (`quarks.r3f`, `react >= 18`, `@react-three/fiber >= 8`)**:
  - Wrap `<Canvas>` children in `<QuarksProvider>` — creates a singleton `BatchedRenderer`, adds it to the scene, drives `update(delta)` in `useFrame`, and disposes batches on unmount.
  - Use `<ParticleSystem>` (props accept numbers, `[min, max]`, `{ r, g, b, a }`, or generators; ref exposes `play()`, `pause()`, `restart()`, `stop()`, `system`, `emitter`), `<QuarksEffect url="..." />` (uses `Suspense`; call `QuarksEffect.preload(url)`), and hooks `useQuarks()`, `useParticleSystem(props)`, `useQuarksEffect(url)` (`.preload(url)`).
- **Node-graph VFX (`quarks.nodes`, experimental)**:
  - Build graphs with `NodeGraph` (`addNode`, `addWire`, `deleteNode`, `deleteWire`) and `NodeTypes` (`OutputNodeTypeNames`).
  - Execute on CPU via `NodeGraphBehavior` (`Interpreter.Instance.run(...)`) or `NodeVFX({ emissionGraph, updateGraph, ... })`, or compile to WebGPU compute via `WebGPUCompiler` + `WebGPURenderer` (`initWebGPU`).
  - Note: `NodeGraph.toJSON()` and `NodeGraph.clone()` throw `'not implemented'`.

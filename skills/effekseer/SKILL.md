---
name: effekseer
description: Effekseer multi-platform 3D/2D particle VFX authoring and runtime guidance. Use when integrating C++ Manager/Renderer for DX11/DX12/Vulkan/OpenGL/Metal, loading .efkefc/.efk effects, configuring LLGI command lists/memory pools, choosing Godot/Unity/Unreal/WebGL/WebGPU runtimes, setting CMake/build.py flags, or optimizing culling and draw-call batching.
---

# Effekseer

Multi-platform particle VFX authoring tool and runtime (`README.md` notes the `master` branch is `1.8 (WIP)` and should not be used in production; target tagged releases such as `1.7x` / `1.6x`). Supports C++ (`DX9`, `DX11`, `DX12`, `Vulkan`, `OpenGL`, `Metal`, `WebGPU`) as well as official plugins/runtimes for **Unity**, **Unreal Engine (`EffekseerForUE`)**, **Godot (`EffekseerForGodot3`)**, **WebGL**, **Cocos2d-x**, and **DX Library**.

## Asset Formats & Authoring Pipeline

- **`.efkefc` (Recommended, 1.6+):** Modern container format (read by `EfkEfcFactory`) packing `INFO`, editor data, and runtime data chunks. *Note (`Effekseer.EfkEfcFactory.h`):* files saved in 1.7+ store both normal and distortion maps with a single linear flag, so `EfkEfcProperty::GetNormalImages()` returns both while `GetDistortionImages()` remains empty.
- **`.efk` (Legacy):** Runtime-only binary export loaded by `EffectFactory`.
- Paths passed to `Effekseer::Effect::Create(manager, path, magnification, materialPath)` use UTF-16 (`const char16_t*`, e.g., `u"Laser01.efkefc"`).

## C++ Runtime Lifecycle (`Effekseer.h`, `EffekseerRenderer.Renderer.h`)

1. **Create Manager & Renderer:**
   ```cpp
   auto efkManager = Effekseer::Manager::Create(instanceMax); // optional autoFlip
   ```
   Create a backend renderer (e.g., `EffekseerRendererDX11::Renderer::Create(...)`, `EffekseerRendererGL::Renderer::Create(...)`, or graphics-device + `Create(...)` for DX12/Vulkan/Metal).
2. **Attach Modules & Match Coordinate System:**
   - Wire renderers: `SetSpriteRenderer`, `SetRibbonRenderer`, `SetRingRenderer`, `SetTrackRenderer`, `SetModelRenderer` from `efkRenderer->Create*Renderer()`.
   - Wire loaders: `SetTextureLoader`, `SetModelLoader`, `SetMaterialLoader` from `efkRenderer`, plus `SetCurveLoader(Effekseer::MakeRefPtr<Effekseer::CurveLoader>())`.
   - **Coordinate System:** Effekseer defaults to `Effekseer::CoordinateSystem::RH`. Call `efkManager->SetCoordinateSystem(Effekseer::CoordinateSystem::LH)` for left-handed engines (must match your camera/projection handedness).
   - **Optional GPU Particles:** Call `efkManager->SetGpuParticleFactory(...)` and `SetGpuParticleSystem(...)` from `efkRenderer`.
3. **Playback & Control:**
   - `auto handle = efkManager->Play(effect, x, y, z);` (or `Play(PlayParameter)`).
   - Transform & control per handle: `SetLocation`, `AddLocation`, `SetRotation`, `SetScale`, `SetMatrix`, `SetBaseMatrix`, `SetTargetLocation`, `SetAllColor`, `SetDynamicInput`, `SendTrigger`, `SetLayer`, `SetGroupMask`, `SetTimeScaleByGroup`, `StopEffect`.
4. **Per-Frame Update & Draw:**
   - Pass camera world position for distance sorting/LOD via `SetLayerParameter(layer, layerParam)` (`ViewerPosition`).
   - Advance simulation: `efkManager->Update(deltaFrame)` or `Update(UpdateParameter)` (**time unit: `1.0f == 1/60` second**).
   - For GPU particles, wrap `efkManager->Compute()` inside a compute pass before rendering.
   - Render: `efkRenderer->SetProjectionMatrix(...)`, `SetCameraMatrix(...)`, `efkRenderer->BeginRendering()` -> `efkManager->Draw(drawParam)` (or `DrawBack` / `DrawFront` / `DrawHandle`) -> `efkRenderer->EndRendering()`.

## Backend Rendering Differences

- **OpenGL & DirectX 11:** Manage GPU state directly; call `efkRenderer->SetRestorationOfStatesFlag(true)` when sharing context state with custom engine passes.
- **DirectX 12, Vulkan & Metal (`EffekseerRendererLLGI`):** Require explicit per-frame memory pools and command lists (`<EffekseerRendererLLGI/Common.h>`):
  - Init once: `EffekseerRenderer::CreateSingleFrameMemoryPool(efkRenderer->GetGraphicsDevice())` and `EffekseerRenderer::CreateCommandList(graphicsDevice, memoryPool)`.
  - Each frame: `memoryPool->NewFrame()` -> `EffekseerRenderer<API>::BeginCommandList(cmdList, nativeCmdList)` -> `efkRenderer->SetCommandList(cmdList)` -> `BeginRendering` / `Draw` / `EndRendering` -> `efkRenderer->SetCommandList(nullptr)` -> `EffekseerRenderer<API>::EndCommandList(cmdList)` (and `BeginRenderPass` / `BeginComputePass` on Metal).

## Build System (`CMakeLists.txt`, `Dev/Cpp/CMakeLists.txt`, `build.py`)

Requires **CMake >= 3.15** (`3.23+` recommended for Editor/tests) and **C++17**.

- **`build.py`:** Orchestrates full C++ CMake + .NET 9 Editor (`Effekseer.csproj`) builds (`python build.py from_ci` sets `-DFROM_CI=ON`; respects `IGNORE_BUILD`, `X86`, `PACKAGEING_FOR_MAC`). Use `release_cpp.py` when packaging only the C++ runtime.
- **Key CMake Flags:**
  - *Graphics Backends:* `BUILD_GL` (`ON`), `BUILD_DX9`/`BUILD_DX11`/`BUILD_DX12` (`ON` on WIN32), `BUILD_METAL` (`ON` on Apple), `BUILD_VULKAN` (`OFF`), `BUILD_WEBGPU` (`OFF`), `USE_OPENGLES2` / `USE_OPENGLES3` / `USE_OPENGL3`.
  - *Components & Plugins:* `BUILD_VIEWER`, `BUILD_EDITOR`, `BUILD_EXAMPLES` (`ON`), `BUILD_TOOLS` (`ON`), `BUILD_TEST`, `BUILD_UNITYPLUGIN`, `BUILD_UNITYPLUGIN_FOR_IOS`, `NETWORK_ENABLED` (`ON`), `USE_LIBPNG_LOADER`, `USE_MSVC_RUNTIME_LIBRARY_DLL` (`OFF`).
  - *Audio & Profiling:* `USE_OPENAL`, `USE_XAUDIO2`, `USE_DSOUND`, `USE_OSM`, `BUILD_WITH_EASY_PROFILER` (`OFF`).

## Culling, Sorting & Batching Best Practices

- **Frustum & Layer Culling (`Effekseer.Manager.cpp`):**
  - Populate `DrawParameter::ViewProjectionMatrix`, `CameraPosition`, `CameraFrontDirection`, `CameraCullingMask` (bitmask matched against effect layer bits), and `ZNear` / `ZFar`.
  - Sphere frustum culling in `ManagerImplemented::CanDraw` only activates if `ZNear != ZFar` **and** the `.efkefc` effect has `Culling.Shape == CullingShape::Sphere` authored in the editor. Query per-handle visibility via `GetIsCulled(handle, drawParameter)`.
- **Draw-Call Batching (`EffekseerRenderer.StandardRenderer.h`):**
  - Profile draw calls using `efkRenderer->GetDrawCallCount()` and `ResetDrawCallCount()`, and enable `DrawParameter::IsSortingEffectsEnabled` when back-to-front ordering across handles is required.
  - Consecutive sprites/ribbons flush a new draw call whenever `StandardRendererState` differs (`AlphaBlend`, `CullingType`, `DepthTest`/`DepthWrite`, `Distortion`, `Refraction`, flipbook, soft particle distances, custom `MaterialType` / uniforms / gradients, `LocalTime`, `Maginification`, collector shaders/textures, or `RenderingUserData` mismatch). Share textures/materials, keep `Maginification` uniform, and avoid unique `RenderingUserData` instances per emitter node.

## Pitfalls

- Passing `ZNear == ZFar` (default `0.0f`) disables Effekseer's built-in frustum sphere culling even on effects with culling bounds authored.
- Forgetting `deltaFrame` is scaled to 60 FPS (`deltaSeconds * 60.0f`) makes effects run 60x too slow if you pass raw frame delta seconds.
- Production builds should check out a release branch/tag rather than `master` (1.8 WIP).

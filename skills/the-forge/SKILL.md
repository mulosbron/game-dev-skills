---
name: the-forge
description: ConfettiFX The-Forge cross-platform low-level C/C++ rendering framework guidance. Use when integrating IGraphics/IResourceLoader, ring buffers, descriptor sets, Forge Shading Language (.fsl / SRT), D3D12/Vulkan/Metal backends, Visibility Buffer, IProfiler/IUI, or PRE_BUILD asset setup.
---

# The-Forge (ConfettiFX)

Cross-platform low-level C/C++ rendering framework (Apache-2.0 for desktop/mobile; console backends under commercial license). Release 1.64+ development continues on Codeberg; Release 1.63 adds Triangle Visibility Buffer with Programmable MSAA.

## Core Architecture & Header Clarification

- **No `IRenderer.h` or `Renderer.h`:** Despite legacy references in older docs/comments, the low-level C99 `extern "C"` graphics API lives in `Common_3/Graphics/Interfaces/IGraphics.h`.
- **Supported Backends (`RendererApi`):**
  - `RENDERER_API_D3D12`: Windows 10/11 (DX12 + DXR).
  - `RENDERER_API_VULKAN`: Linux / Steam Deck, Android Pie+, Quest 2 (Vulkan 1.1 + `VK_KHR_ray_query` / OpenXR). *Note: Windows Vulkan runtime was removed in Release 1.59, and DirectX 11 was removed in Release 1.61.*
  - `RENDERER_API_METAL`: macOS, iOS, iPadOS.
  - Console APIs (`RENDERER_API_ORBIS`, `RENDERER_API_PROSPERO`, Switch/Xbox) require a separate console license.
- **Bundled Ecosystem:** Includes Ozz Animation, Vectormath (+NEON / double precision), VMA / D3D12MA, `flecs` ECS, Lua, Dear ImGui, and custom C FileSystem/Input layers.

## Application & Rendering Lifecycle

1. **App Entry (`Common_3/Application/Interfaces/IApp.h`):** Subclass `IApp` implementing `Init`, `Exit`, `Load(ReloadDesc*)`, `Unload(ReloadDesc*)`, `Update(float)`, `Draw()`, and register with `DEFINE_APPLICATION_MAIN(YourApp)`.
2. **Graphics Device (`Common_3/Graphics/Interfaces/IGraphics.h`):**
   - Context & device: `initRendererContext` -> `initRenderer` (cleanup: `exitRenderer` / `exitRendererContext`).
   - Queues & swapchain: `initQueue` (`QUEUE_TYPE_GRAPHICS | COMPUTE | TRANSFER`), `addSwapChain`, `initFence`, `initSemaphore`.
   - Command recording: `initCmdPool` -> `initCmd` -> `resetCmdPool` -> `beginCmd` -> `cmdResourceBarrier` -> `cmdBindRenderTargets` -> `cmdSetViewport` / `cmdSetScissor` -> `cmdBindPipeline` -> `cmdBindDescriptorSet` -> `cmdBindIndexBuffer` / `cmdBindVertexBuffer` -> `cmdDraw*` / `cmdDispatch` / `cmdExecuteIndirect` -> `endCmd`.
   - Submission: `acquireNextImage` -> `queueSubmit` -> `queuePresent`.
3. **Async Resource Loading (`Common_3/Resources/ResourceLoader/Interfaces/IResourceLoader.h`):**
   - Initialize via `initResourceLoaderInterface` (`exitResourceLoaderInterface` on shutdown).
   - Load resources with `addResource`: `BufferLoadDesc`, `TextureLoadDesc` (`TEXTURE_CONTAINER_DEFAULT | _DDS | _KTX | _GNF`), `GeometryLoadDesc` (`Geometry`, `GeometryData`, `GeometryBuffer` via `BufferChunkAllocator` / `addGeometryBufferPart`, `GeometryMeshlets`).
   - Stream updates via `beginUpdateResource` / `endUpdateResource` (`BufferUpdateDesc` / `TextureUpdateDesc`).
   - Synchronize async transfers using `SyncToken` (`waitForToken`, `isTokenCompleted`, `allResourceLoadsCompleted`, `waitForAllResourceLoads`, `getLastSemaphoreSubmitted`).
   - Compile shaders and root signatures with `addShader`, `initRootSignature` / `exitRootSignature`, and `loadPipelineCache` / `savePipelineCache`.
4. **Ring Buffers (`Common_3/Utilities/RingBuffer.h`):**
   - **Dynamic GPU buffers:** `GPURingBuffer` (`addGPURingBuffer`, `addUniformGPURingBuffer`, `getGPURingBufferOffset`, `resetGPURingBuffer`, `removeGPURingBuffer`) for per-frame constant/vertex staging without mid-frame stalls.
   - **Per-frame command ring:** `GpuCmdRing` (`initGpuCmdRing`, `getNextGpuCmdRingElement`, `exitGpuCmdRing`) cycles `GpuCmdRingElement` pools/fences cleanly (`MAX_GPU_CMD_POOLS_PER_RING = 64`, `MAX_GPU_CMDS_PER_POOL = 4`).

## Forge Shading Language (FSL 2) & Descriptor Sets

Introduced in Release 1.61, FSL 2 unifies C++ descriptor layout and shader bindings via shared Shader Resource Table (`.srt.h`) headers (`Common_3/Graphics/FSL/`):

- **Shared SRT Header (`Global.srt.h`):**
  - Wrap set declarations in `BEGIN_SRT` (or `BEGIN_SRT_NO_AB` when opting out of Metal Argument Buffers).
  - Declare update-frequency sets (`SET_Persistent = 0`, `SET_PerFrame = 1`, `SET_PerBatch = 2`, `SET_PerDraw = 3`) with `BEGIN_SRT_SET(Persistent)` / `END_SRT_SET(Persistent)`.
  - Inside sets, declare bindings using `DECL_TEXTURE`, `DECL_SAMPLER`, `DECL_CBUFFER`, `DECL_BUFFER`, `DECL_RWBUFFER`, `DECL_RWTEXTURE`.
- **C++ Binding (`IGraphics.h` + `fsl_srt.h`):**
  - Allocate sets using `SRT_SET_DESC(SRTType, Persistent, ...)` with `addDescriptorSet`.
  - Populate `DescriptorData` indices via `SRT_RES_IDX(SRTType, Persistent, ResName)`, update with `updateDescriptorSet`, and bind with `cmdBindDescriptorSet`.
- **Shader Files (`.fsl`, `.h.fsl`) & Compilation (`Common_3/Tools/ForgeShadingLanguage/fsl.py`):**
  - Declare `ROOT_SIGNATURE(DefaultRootSignature)` (or `ComputeRootSignature`), define `STRUCT(...)` / `DATA(...)` blocks, and write entry points with `VS_MAIN` / `PS_MAIN` / `CS_MAIN` bounded by `INIT_MAIN` and `RETURN(...)`.
  - List shaders in `shaders.list` and invoke `fsl.py` (`-d` generated FSL output, `-b` binary output, `-i` intermediate output, `-l` target languages, `-I` include paths, `--compile`, `--debug`, `--rootSignature`, `--incremental`, `--mp`, `--reloadServerPort`, `--cache-args`), dispatching to FXC/DXC, Vulkan glslang, and Metal tools.

## Visibility Buffer, Profiler, UI & Asset Setup

- **Visibility Buffer (`Common_3/Renderer/Interfaces/IVisibilityBuffer.h`, `IVisibilityBuffer2.h`):**
  - `initVisibilityBuffer` / `exitVisibilityBuffer` manage `VBMeshInstance` and `FilterContainer`.
  - Supports async-compute skinning via aliased heaps (`initVBAsyncComputePreSkinVertexBuffers` / `cmdVisibilityBufferPreSkinVertexesPass`) and GPU triangle culling/filtering (`updateVBMeshFilterGroups` + `cmdVBTriangleFilteringPass` / `cmdVisibilityBufferTriangleFilteringPass`).
- **Profiler (`Common_3/Application/Interfaces/IProfiler.h`):**
  - `initProfiler` / `loadProfilerUI` / `flipProfiler` / `dumpProfileData` / `exitProfiler`.
  - Instrument CPU scopes (`PROFILER_SET_CPU_SCOPE`) and GPU frames/passes (`cmdBeginGpuFrameProfile`, `cmdBeginGpuTimestampQuery` / `cmdEndGpuTimestampQuery`, `cmdDrawGpuProfile`, `cmdDrawCpuProfile`).
- **UI (`Common_3/Application/Interfaces/IUI.h`):**
  - Dear ImGui wrapper: `initUserInterface` -> `loadUserInterface` -> `cmdDrawUserInterface` (`unloadUserInterface` / `exitUserInterface`), adding panels/controls via `uiAddComponent`, `uiAddComponentWidget`, `uiSetWidgetOnEditedCallback`, `uiIsFocused`, and `uiToggleActive`.
- **PRE_BUILD Assets (`PRE_BUILD.bat` / `PRE_BUILD.command`):**
  - Run before building unit tests: fetches `http://www.conffx.com/Art.zip` (`Tools/wget` + `Tools/7z` on Windows; `curl` + `unzip` on macOS/Linux) and extracts `Art/ZipFilesDds` and `Art/ZipFilesKtx` into `Examples_3/Unit_Tests/UnitTestResources`.

## Pitfalls

- Do not look for `IRenderer.h` or `Renderer.h`; use `Common_3/Graphics/Interfaces/IGraphics.h`.
- Do not target Vulkan or DX11 on Windows using modern The-Forge runtimes (removed in 1.59 and 1.61); use `RENDERER_API_D3D12` on Windows.
- Always run `PRE_BUILD.bat` (Windows) or `PRE_BUILD.command` (macOS/Linux) before running `Examples_3/Unit_Tests`, or DDS/KTX test assets will be missing.

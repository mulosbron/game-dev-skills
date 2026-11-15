---
name: limboai
description: C++ Behavior Trees (BTPlayer, BehaviorTree, BTTask/BTAction/BTCondition), Hierarchical State Machines (LimboHSM, LimboState, BTState), and Blackboard system for Godot 4. Use when building modular game AI in Godot 4 with LimboAI, authoring custom BT tasks or HSM states in GDScript/C#, configuring BlackboardPlan scopes/mappings, or troubleshooting module vs GDExtension setup.
---

# LimboAI (Behavior Trees & HSM for Godot 4)

Open-source C++ Godot 4 plugin combining **Behavior Trees (BT)**, **Hierarchical State Machines (HSM)**, and a scoped **Blackboard** system, with a visual BT editor and runtime debugger.

## Behavior Trees (`BTPlayer` & `BehaviorTree`)

- **Core Nodes/Resources:**
  - `BehaviorTree` (`Resource`): Reusable tree asset containing a root `BTTask` and a default `BlackboardPlan`.
  - `BTPlayer` (`Node`): Instantiates and ticks a `BehaviorTree` at runtime. Key properties: `behavior_tree`, `active`, `update_mode` (`IDLE`, `PHYSICS`, `MANUAL`—call `bt_player.update(delta)` manually), `agent_node` (defaults to `".."`—setting after instantiation has no effect), `blackboard_plan` (per-scene overrides), `monitor_performance`.
  - `BTInstance`: Created by `BehaviorTree.instantiate(agent, blackboard, owner, custom_scene_root)` when driving trees manually or swapping via `bt_player.set_bt_instance()`. Call `bt_player.set_scene_root_hint(root)` before adding dynamic `BTPlayer` nodes to the tree.
  - `BehaviorTreeView`: Control node to visualize a live `BTInstance` in-game.
- **Task Status (`BT.Status`):** `FRESH`, `RUNNING`, `FAILURE`, `SUCCESS`.
- **Execution Order (`BTTask.execute`):** If status != `RUNNING` -> `_enter()` -> `_tick(delta)` -> if result != `RUNNING` -> `_exit()`. `abort()` recursively exits `RUNNING` tasks and resets status to `FRESH`. `bt_player.restart()` aborts running tasks **without** resetting the `Blackboard`.

### Essential Built-in Tasks
- **Composites (`BTComposite`):**
  - `BTSequence` / `BTSelector`: Standard sequential execution; resumes directly at a `RUNNING` child on the next tick.
  - `BTDynamicSequence` / `BTDynamicSelector`: Re-evaluates preceding children **from index 0 every tick**; if a higher-priority condition changes, aborts the remembered `RUNNING` child. Use these for reactive interrupts!
  - `BTParallel`: Runs all children sequentially in one tick (NOT multithreaded); finishes based on `num_failures_required` (checked first) / `num_successes_required` and `repeat`.
  - `BTRandomSequence`, `BTRandomSelector`, `BTProbabilitySelector`.
- **Decorators (`BTDecorator`, single child):** `BTInvert`, `BTAlwaysSucceed`, `BTAlwaysFail`, `BTRepeat`, `BTRepeatUntilSuccess`, `BTRepeatUntilFailure`, `BTRunLimit`, `BTCooldown`, `BTDelay`, `BTTimeLimit`, `BTProbability`, `BTForEach`, `BTNewScope` (isolated blackboard scope), `BTSubtree` (runs external `BehaviorTree` with own scope).
- **Actions & Conditions:** `BTWait`, `BTWaitTicks`, `BTRandomWait`, `BTPlayAnimation`, `BTAwaitAnimation`, `BTPauseAnimation`, `BTStopAnimation`, `BTCallMethod`, `BTSetAgentProperty`, `BTCheckAgentProperty`, `BTSetVar`, `BTCheckVar`, `BTCheckTrigger`, `BTEvaluateExpression`, `BTConsolePrint`.

### Custom Tasks in GDScript / C#
Place scripts in `res://ai/tasks/` (configurable in **Project Settings -> Limbo AI** with Advanced Settings on); subdirectories become editor task categories. **Extend `BTAction`, `BTCondition`, `BTDecorator`, or `BTComposite`** (never `BTTask` directly), and include `@tool` if overriding `_generate_name()` or `_get_configuration_warnings()`.

```gdscript
@tool
extends BTCondition

@export var distance_max: float = 150.0
@export var target_var: StringName = &"target" # "_var" suffix enables BlackboardPlan picker

var _max_sq: float

func _generate_name() -> String:
    return "InRange <= %.1f (%s)" % [distance_max, LimboUtility.decorate_var(target_var)]

func _setup() -> void:
    _max_sq = distance_max * distance_max

func _tick(_delta: float) -> Status:
    var target = blackboard.get_var(target_var, null) # leave untyped in case instance freed
    if not is_instance_valid(target):
        return FAILURE
    return SUCCESS if agent.global_position.distance_squared_to(target.global_position) <= _max_sq else FAILURE
```

- Accessing scene nodes inside tasks: use `scene_root.get_node(path)`, exported `BBNode` (`param.get_value(scene_root, blackboard)`), or `NodePath` variables in `BlackboardPlan` (auto-resolved to `Node` instances when `BlackboardPlan.prefetch_nodepath_vars = true`).

## Hierarchical State Machines (`LimboHSM`, `LimboState`, `BTState`)

LimboAI HSMs have **no GUI graph editor**—states are `Node` children (`LimboState`, nested `LimboHSM`, or `BTState`) wired in code.

```gdscript
@onready var hsm: LimboHSM = $LimboHSM
@onready var idle: LimboState = $LimboHSM/Idle
@onready var chase: BTState = $LimboHSM/Chase # runs a BehaviorTree when active

func _ready() -> void:
    hsm.add_transition(idle, chase, &"target_spotted")
    hsm.add_transition(chase, idle, chase.failure_event) # default &"failure" (&"success" on success)
    hsm.add_transition(hsm.ANYSTATE, idle, &"reset", func() -> bool: return can_reset)
    hsm.initial_state = idle
    hsm.initialize(self) # calls _setup() on HSM and all substates
    hsm.set_active(true)
```

- **State Lifecycle:** `_setup()` (once on `initialize`), `_enter()` (`get_cargo()` available here only), `_update(delta)`, `_exit()` (note: `_exit()` is **not** called if freed synchronously via `free()`, only via transitions or `queue_free()`).
- **Events & Guards:** `dispatch(event, cargo)` propagates **leaf -> root** and stops when consumed by a matching transition or an `add_event_handler(event, callable)` returning `true`. State-wide entry guards use `state.set_guard(callable)`.
- **Single-File Prototyping:** Chain `LimboState.new().named("Idle").call_on_enter(...).call_on_update(...).call_on_exit(...)`.
- **`BTState`:** Hosts a `BehaviorTree` inside an HSM state; automatically dispatches `success_event` (`&"success"`) or `failure_event` (`&"failure"`) when the tree finishes. Call `bt_state.set_scene_root_hint(self)` before `hsm.initialize()` if constructed dynamically in code.

## Blackboard & `BlackboardPlan`

- **API:** `set_var(name, value)` (always writes to **current scope**, never mutating parent scopes), `get_var(name, default, complain)` (walks up parent scopes until found), `has_var(name)`, `erase_var(name)`, `top()` (root blackboard for multi-agent shared groups), `bind_var_to_property(var, obj, prop, create)`, `link_var(var, target_bb, target_var, create)`.
- **GDScript Freed-Object Trap:** Do **not** type-annotate `var obj: Node2D = blackboard.get_var(...)` if the stored node might be freed—use untyped `var obj = blackboard.get_var(...)` + `is_instance_valid(obj)`.
- **Scopes & Mapping:** `BTNewScope`, `BTSubtree`, `LimboHSM`, `BTState`, and `LimboState` with non-empty `BlackboardPlan` create child scopes. To share variables cleanly across `BTState` <-> `LimboHSM` or `BTSubtree` <-> parent BT, declare the variables in both `BlackboardPlan`s and use Inspector **Mapping** (bidirectional shared reference, zero polling) or `bt_bb.link_var("a", hsm_bb, "b")`.

## Module vs. GDExtension & Debugging

- **Live Debugger:** **Bottom Panel -> Debugger -> LimboAI** shows live tree execution; click any task or node in Remote Scene Tree to inspect and edit its `Blackboard` across all scopes at runtime.
- **Module vs. GDExtension:**
  - *Module:* Place repo at `modules/limboai`, build Godot + custom export templates. Required for full C# support (`GodotSharp/Tools/nupkgs/` local NuGet source).
  - *GDExtension:* Build via `scons target=editor --project=DIR` (clones `godot-cpp` automatically). **Limitations:** No editor doc tooltips, no custom `BBParam` inspector property editor, and C# bindings are not verified/supported out of the box.

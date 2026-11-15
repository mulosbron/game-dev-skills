---
name: dialogic
description: Dialogic 2 narrative and visual novel addon for Godot 4.5+ (timelines .dtl, characters .dch, portraits, variables, glossary, signals, text effects, styles/layouts, save/load). Use when authoring or integrating Dialogic timelines, subsystems, custom portraits/layouts, inline BBCode effects, or game save synchronization.
---

# Dialogic 2 (Godot 4.5+)

Narrative, dialogue, and visual-novel framework for Godot 4 (`addons/dialogic`, checked against `2.0-Alpha-21 WIP`, **requires Godot 4.5+**). Enabling the plugin registers the **`Dialogic`** autoload (`DialogicGameHandler`) and attaches modular `DialogicSubsystem` children (`Text`, `VAR`, `Portraits`, `Choices`, `Glossary`, `Styles`, `Save`, `Inputs`, `Audio`, `Backgrounds`, `History`, `Jump`, `Expressions`, `Animations`, `Settings`, `Voice`, `Wait`).

> **API stability rule:** Methods and properties prefixed with `_` (e.g., `_clear_state`, `_get_state`) are private internal APIs and may change without notice.

## Starting, Controlling & Ending Dialogue

- **`Dialogic.start(timeline, label_or_idx = "") -> Node`:** Ensures an active UI layout exists via `Dialogic.Styles.load_style()`, then starts the timeline and returns the root layout node (`DialogicLayoutBase`). Pass either a loaded `DialogicTimeline`, a `res://...dtl` path, or a short timeline identifier (`"intro"`).
- **`Dialogic.start_timeline(timeline, label_or_idx = "")`:** Starts timeline execution **without** spawning a layout (use when mounting custom HUD nodes already in the scene).
- **`Dialogic.preload_timeline(timeline_resource)`:** Parses `.dtl` text into `DialogicEvent` nodes ahead of time.
- **`Dialogic.end_timeline(skip_ending := false)`:** Plays `dialog_ending_timeline` (defaults to `[clear]`) unless `skip_ending = true`, clears timeline state, and either `queue_free()`s (`dialogic/layout/end_behaviour == 0`) or `.hide()`s (`1`) the active layout node.
- **Pausing & clearing:** Set `Dialogic.paused = true` (pauses timers, animations, and subsystem ticks); call `Dialogic.clear(ClearFlags.FULL_CLEAR | KEEP_VARIABLES | TIMELINE_INFO_ONLY)` when resetting manually.

```gdscript
func start_npc_chat(timeline_id: String, entry_label: String = "") -> void:
	Dialogic.signal_event.connect(_on_dialogic_signal, CONNECT_ONE_SHOT)
	Dialogic.timeline_ended.connect(_on_dialog_finished, CONNECT_ONE_SHOT)
	Dialogic.start(timeline_id, entry_label)
```

## Timelines (`.dtl`) & Characters (`.dch`)

- **Resource directory mapping:** `DialogicResourceUtil` caches unique short identifiers for `.dtl` and `.dch` files in `ProjectSettings` (`dialogic/directories/dtl_directory` and `dch_directory`). When referencing resources from disk in code, use `DialogicResourceUtil.get_timeline_resource("name")` or `DialogicResourceUtil.get_character_resource("name")`.
- **`.dtl` text format (plain text, `DialogicTimeline`):**
  - **Speech:** `Speaker: Hello!` or `Speaker (happy): Hello!`; quote names with spaces (`"Sir Bob" (sad): ...`); escape literal colons (`\:`) and multiline wraps (`\` at line end). Split one event into multiple clicks with `[n]` or append-in-place with `[n+]`.
  - **Stage direction (`join` / `update` / `leave`):**
    ```text
    join Hero (neutral) left [animation="Fade In" length="0.4" wait="true"]
    update Hero (smug) center [move_time="0.5" mirrored="true" z_index="2"]
    leave --All--
    ```
  - **Choices & flow:** Choices (`- Option text [if {has_key}]`) and conditionals (`if {score} > 5:`, `elif ...:`, `else:`) scope child events by **tab indentation** (`DialogicConditionEvent` / `DialogicChoiceEvent`). Labels and jumps use `label intro (Intro Section)` and `jump other_timeline/intro`.
  - **Logic & signals:** `set {player_gold} += 50`, `do GameState.give_item("potion", @player_count)`, `[signal arg="unlock_door"]` (or Dictionary JSON via shortcode `arg_type="dictionary"`), `[style name="BubbleStyle"]`.

### Characters (`.dch`) & Portraits
- **`DialogicCharacter` properties:** `display_name`, `nicknames`, `color`, `scale`, `offset`, `mirror`, `default_portrait`, `portraits` dictionary, and `custom_info` (including typing `sound_moods` + `sound_mood_default`).
- **Containers (`DialogicNode_PortraitContainer`):** Placed inside layouts with `mode = POSITION` (`container_ids` e.g. `"left"`, `"center"`, `"1"`) or `mode = SPEAKER` (`portrait_prefix` e.g. `"Faces/"`), plus `size_mode` (`KEEP`, `FIT_STRETCH`, `FIT_IGNORE_SCALE`, `FIT_SCALE_HEIGHT`).
- **Custom portrait scenes:** Extend `DialogicPortrait` (`class_name DialogicPortrait`) and override `_should_do_portrait_update()`, `_update_portrait()`, `_get_covered_rect()`, `_set_mirror()`, and `_set_extra_data(data)`.
- **Code control (`Dialogic.Portraits`):** `join_character(...)`, `move_character(...)`, `change_character_portrait(...)`, `animate_character(...)`, `leave_character(...)`, `leave_all_characters()`, `is_character_joined()`, `get_joined_characters()`.

## Variables, Expressions & Glossary

- **Variables (`Dialogic.VAR`):**
  - Access nested folders naturally via `VariableFolder` (`Dialogic.VAR.Player.hp = 100`) or safely with path strings: `Dialogic.VAR.set_variable("Player.hp", 100)` / `Dialogic.VAR.get_variable("Player.hp", default)`.
  - Inline substitution in text uses curly braces: `Hello {Player.name}` and direct autoload reads `{Game.coins}`.
  - Inside `if` / `set` / expressions (`Dialogic.Expressions`), Godot's `Expression` class evaluates autoload names plus helper wrappers `range()` (`d_range`) and `len()` (`d_len`). Escape literal braces with `\{`.
- **Glossary (`Dialogic.Glossary`):**
  - Configured `.tres` (`DialogicGlossary`) files in `dialogic/glossary/glossary_files` scan revealed text and automatically wrap matched terms in RichText `[url="entry_key"][color=...]word[/color][/url]`.
  - Connect to `Dialogic.Text.meta_hover_started` / `meta_hover_ended` / `meta_clicked`, then fetch translated & variable-parsed card data via `var entry := Dialogic.Glossary.get_entry(str(meta))` (`{title, text, extra, color}`).
  - Override per-term colors dynamically via `Dialogic.Glossary.color_overrides[key] = Color(...)`. Note that `dialogic/text/autocolor_names` also pushes character colors into `color_overrides`.

## Signals, Text Effects & Modifiers

### Key Signals
- **`Dialogic` autoload:** `timeline_started`, `timeline_ended`, `event_handled(resource)`, `state_changed(new_state: DialogicGameHandler.States)`, `dialogic_paused`, `dialogic_resumed`, `signal_event(argument: Variant)` (from Signal event), `text_signal(argument: String)` (from inline `[signal=...]` text effect).
- **Subsystems:**
  - `Dialogic.Text`: `about_to_show_text(info)`, `text_started(info)`, `text_finished(info)`, `speaker_updated(character)`, `textbox_visibility_changed(visible)`, `meta_clicked(meta)`, `meta_hover_started(meta)`, `meta_hover_ended(meta)`.
  - `Dialogic.Choices`: `question_shown(info)`, `choice_selected(info)`, `invalid_question_reached`.
  - `Dialogic.Portraits`: `character_joined(info)`, `character_left(info)`, `character_portrait_changed(info)`, `character_moved(info)`.
  - `Dialogic.VAR`: `variable_changed(info)`, `variable_was_set(info)`.
  - `Dialogic.Save`: `saved(info)`, `loaded(info)`.
  - `Dialogic.Inputs`: `dialogic_action_priority` (set `Dialogic.Inputs.action_was_consumed = true` to intercept advance input), `dialogic_action`, `autoskip_timer_finished`.

### Built-in Inline Text Effects & Modifiers
Effects strip out of `DialogicNode_DialogText` (`RichTextLabel`) and execute when that character index is reached:
- **Timing & pacing:** `[pause=0.5]` (scaled by speed), `[pause=0.5!]` (absolute seconds), `[speed=2.0]` (multiplier), `[lspeed=0.05!]` (absolute delay per letter), `[br]` (line break), `dialogic/text/autopauses`.
- **Events & branching inside text:** `[signal=my_arg]` (emits `Dialogic.text_signal`), `[mood=angry]` (switches typing sound mood), `[portrait=happy]`, `[extra_data=...]`, `[aa]` (auto-advance), `[ns]` (no skip), `[nrs]` (no reveal skip), `[input]` (wait input), `[if {var} yes / no]`, and `<option A/option B>` (random pick).
- **Custom Godot `RichTextEffect`s:** Add resource paths (comma-separated) in Project Settings `dialogic/text/custom_bbcode_effects`.

## Styles & Layouts

- Built-in templates live under `addons/dialogic/Modules/DefaultLayoutParts/` (`Base_Default`, `Base_TextBubble`, `Style_VN_Default`, `Style_SpeakerTextbox`, `Style_TextBubbles`, plus composable `Layer_*` parts).
- Custom layouts extend `DialogicLayoutBase` (`_apply_export_overrides()`, `_get_persistent_info()`, `_load_persistent_info()`) with `DialogicLayoutLayer` children (and `DialogicNode_StyleLayer` for visibility switching).
- Switch styles dynamically with `Dialogic.Styles.change_style("StyleName")` (calls `load_style(..., state_reload = true)`). Styles sharing the same inherited base scene update exported overrides in place without tearing down nodes.

## Save / Load Integration

1. **Custom save file integration (`DialogicGameHandler`):**
   ```gdscript
   # Saving into your own Resource / Dictionary wrapper:
   var dialogic_state: DialogicSaveState = Dialogic.get_full_state()
   # Restoring (await because clear() & style layout setup yield):
   await Dialogic.load_full_state(dialogic_state)
   ```
   `DialogicSaveState` (`@export timeline`, `@export event_index`, `@export subsystems`) collects every `DialogicSubsystem`'s `@export` state properties plus `_pack_extra_state()`.
2. **Built-in slot manager (`Dialogic.Save`):**
   - Stores slots in `user://dialogic/saves/<slot_name>/` (`state.txt`, `info.txt`, `thumbnail.png`) and `global_info.txt`.
   - **Screenshot before opening pause/save UI:** Call `Dialogic.Save.take_thumbnail()` while gameplay is visible, then pass `Dialogic.Save.ThumbnailMode.STORE_ONLY` to `Dialogic.Save.save(slot_name, false, ThumbnailMode.STORE_ONLY, {"label": "Ch. 1"})`.
   - Load via `Dialogic.Save.load(slot_name)`; enumerate with `get_slot_names()`, `has_slot()`, `get_slot_info()`, `get_slot_thumbnail()`, `delete_slot()`, `set_global_info()` / `get_global_info()`.
   - Configure automatic checkpoints via `autosave_enabled`, `autosave_mode` (`ON_TIMELINE_JUMPS`, `ON_TIMER`, `ON_TEXT_EVENT`), and optional export encryption (`dialogic/save/encryption_password` + `dialogic/save/encryption_on_exports_only`).

## Troubleshooting & Caveats

- **Godot version mismatch:** Dialogic 2 (`2.0-Alpha-21+`) targets **Godot 4.5+**.
- **`Dialogic` autoload inside `@tool` scripts:** Editor plugins cannot reference the runtime `Dialogic` autoload directly; guard with `Engine.is_editor_hint()` or `DialogicUtil.autoload()`.
- **Exported builds:** `export_plugin.gd` strips `.png` and `.tff` assets inside `/Editor`, `/Modules`, and `/Example Assets/portraits`—store custom portraits/fonts outside `addons/dialogic`.
- **Renamed/moved `.dtl` or `.dch` files outside Dialogic UI:** Call `DialogicResourceUtil.update()` in editor if short identifiers go stale.

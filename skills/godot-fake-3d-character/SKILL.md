---
name: godot-fake-3d-character
description: >-
  Technique for creating fake 3D (Fake 3D / 2.5D) top-down puppet characters in Godot 4 using only 2D nodes
  (Node2D, Sprite2D, RemoteTransform2D, Line2D). Used in top-down games to build smoothly rotating characters
  with a sense of depth, procedural limbs (Line2D), and dynamic Z-sorting layers without needing 3D models
  or hundreds of sprite animation frames.
---

# Godot Fake 3D Top-Down Character System (2D Puppet Technique)

This technique cleverly uses Godot's 2D transform parenting hierarchy and the `RemoteTransform2D` node to create a **puppet character that rotates like 3D and has depth**, built entirely from 2D nodes.

Without needing 3D modeling or drawing separate sprites for every angle, it delivers a seamless 2.5D illusion for rounded, stylized characters (*ducks, slimes, tiny robots, chibi characters*).

---

## 1. Core Principle and Mathematical Logic

The illusion relies on three simple facts:

1. **Camera Angle (Y-Axis Compression):** When the Y scale of a parent node (`Rig`) is reduced (such as `scale.y = 0.5`), every point rotating on the plane beneath it traces an **ellipse** on the 2D screen. This ellipse matches the 3D perspective produced by an isometric or top-down angled camera.
2. **Height / Elevation:** Changing a point's Y position (`position.y`) moves that point up or down in the virtual 3D world.
3. **Escaping Parenting (`RemoteTransform2D`):** If sprites were placed directly under this squashed `Rig`, the sprites themselves would look squashed. By setting `update_scale = false` and `update_rotation = false` on `RemoteTransform2D`, **only the computed (x, y) position** is transferred to the external `Visual` sprite; the sprite's own original scale and aspect ratio remain intact.

```
       [Virtual 3D Space: Rig]                    [Screen Drawing: Visual]
  Rig (scale.y = 0.5) [Camera Angle]
     └── Anchor (rotation = angle)
           └── HeightOffset (position.y = -height)
                 └── RemoteTransform2D (sends POSITION ONLY!) ──> Sprite2D (Unsquashed, clean sprite)
```

---

## 2. Scene Tree Architecture (Visual & Rig Separation)

Always split the character node into two main groups:
- **`Visual`**: Holds the draw order (Z-Index / Y-Sort) and sprites.
- **`Rig`**: Computes angles, heights, and positions in virtual 3D space.

```text
Duck (CharacterBody2D or Node2D) - duck.gd
├── Visual (Node2D)
│   ├── ShadowSprite (Sprite2D - fixed ground shadow)
│   ├── FootSpriteL (Sprite2D)
│   ├── FootSpriteR (Sprite2D)
│   ├── LegLineL (Line2D - leg connector)
│   ├── LegLineR (Line2D - leg connector)
│   ├── BodySprite (Sprite2D)
│   ├── NeckLine (Line2D - flexible neck connector)
│   └── HeadGroup (Node2D)
│       ├── HeadSprite (Sprite2D)
│       ├── EyesSprite (Sprite2D)
│       └── BeakSprite (Sprite2D)
└── Rig (Node2D) -> [scale = Vector2(1.0, 0.5)]
    ├── FootAnchorL (Node2D)
    │   └── PlaneResult (RemoteTransform2D -> %FootSpriteL)
    ├── FootAnchorR (Node2D)
    │   └── PlaneResult (RemoteTransform2D -> %FootSpriteR)
    ├── BodyAnchor (Node2D, position.y = -10)
    │   └── PlaneResult (RemoteTransform2D -> %BodySprite)
    └── NeckPositionCopy (Node2D - copies Body's position)
        └── HeadHeightOffset (Node2D, position.y = -25)
            └── HeadAnchor (Node2D)
                ├── HeadPlane (RemoteTransform2D -> %HeadGroup)
                ├── EyesAnchor (Node2D)
                │   └── PlaneResult (RemoteTransform2D -> %EyesSprite)
                └── BeakAnchor (Node2D)
                    └── PlaneResult (RemoteTransform2D -> %BeakSprite)
```

> [!IMPORTANT]
> On every `RemoteTransform2D` node used as `PlaneResult`, set in the Inspector:
> - `Update Position` = **ON**
> - `Update Rotation` = **OFF** (if a script controls the sprite's own rotation)
> - `Update Scale` = **OFF** (REQUIRED to prevent the Rig's 0.5 Y-scale from squashing the sprite!)

---

## 3. GDScript Logic (`duck.gd`)

The main controller managing rotation, Z-Index depth sorting, and leg angles:

```gdscript
extends CharacterBody2D

# Inspector setting from 0 to 360 degrees (stored internally as radians)
@export_range(0.0, 360.0, 0.1, "radians") var direction: float = 0.0: set = _set_direction

# Visual Nodes
@onready var foot_sprite_l: Sprite2D = %FootSpriteL
@onready var foot_sprite_r: Sprite2D = %FootSpriteR
@onready var body_sprite: Sprite2D = %BodySprite
@onready var head_group: Node2D = %HeadGroup
@onready var beak_sprite: Sprite2D = %BeakSprite
@onready var eyes_sprite: Sprite2D = %EyesSprite

# Anchor Nodes to Rotate Inside the Rig
@onready var foot_anchor_l: Node2D = %FootAnchorL
@onready var foot_anchor_r: Node2D = %FootAnchorR
@onready var body_anchor: Node2D = %BodyAnchor
@onready var head_anchor: Node2D = %HeadAnchor
@onready var beak_anchor: Node2D = %BeakAnchor

@onready var all_anchors: Array[Node2D] = [
    foot_anchor_l, foot_anchor_r, body_anchor, head_anchor, beak_anchor
]

func _set_direction(value: float) -> void:
    if not is_inside_tree():
        direction = value
        return
        
    direction = value
    
    # Wrap angle between 0.0 and TAU (2*PI)
    var angle: float = wrapf(direction, 0.0, TAU)
    
    # 1. Rotate all anchor nodes to the same angle
    for anchor in all_anchors:
        anchor.rotation = angle
        
    # 2. Give foot sprite rotations a subtle offset (for an expressive waddle walk)
    foot_sprite_l.rotation = angle + 0.3
    foot_sprite_r.rotation = angle - 0.3
    
    # 3. Face and Body Z-Index Sorting (When Character Faces Away)
    # When facing north/up (away from camera), facial features must stay behind the body:
    # Between PI / 2 (90°) and 3 * PI / 2 (270°) faces up
    var is_facing_north: bool = angle > (PI * 0.5) and angle < (PI * 1.5)
    
    if is_facing_north:
        beak_sprite.z_index = -1
        eyes_sprite.z_index = -1
        head_group.z_index = 0
        body_sprite.z_index = 1
    else:
        beak_sprite.z_index = 2
        eyes_sprite.z_index = 2
        head_group.z_index = 1
        body_sprite.z_index = 0
```

---

## 4. Dynamic Limbs & Stretching: `Line2D` (`limb_line_2d.gd`)

Instead of drawing sprites for the neck, legs, or arms, using a `Line2D` that stretches dynamically between two rig points dramatically improves squash & stretch and natural movement.

```gdscript
# limb_line_2d.gd
extends Line2D

@export var start_node: Node2D
@export var end_node: Node2D

func _ready() -> void:
    top_level = true # Draw in global coordinates, independent of local transform
    width = 6.0
    default_color = Color("e0a526") # Leg / neck color
    round_precision = 8
    begin_cap_mode = Line2D.LINE_CAP_ROUND
    end_cap_mode = Line2D.LINE_CAP_ROUND

func _process(_delta: float) -> void:
    if is_instance_valid(start_node) and is_instance_valid(end_node):
        clear_points()
        add_point(start_node.global_position)
        add_point(end_node.global_position)
```

---

## 5. Character Design (Art & Rigging Rules)

Follow these graphic design rules to apply this technique successfully:

1. **Rounded and Organic Forms:** Spheres, ellipses, cylinders, and softly curved designs hold their silhouette as the angle changes. Sharp-cornered boxes look fake in this technique because there are no real 3D polygon edges.
2. **Character Mockup & Part Splitting (Figma / Inkscape / Photoshop):**
   - Draw the character from a slightly elevated (30°–45° oblique) perspective.
   - Export parts as separate PNGs:
     - `body.png`
     - `head.png`
     - `beak.png` (or nose/mouth)
     - `eye.png`
     - `foot_left.png`, `foot_right.png`
     - `shadow.png` (semi-transparent black ellipse)
3. **Animation (Tween & Wobble):**
   - Gently bounce `BodyAnchor.position.y` with a tween while walking (`bobbing`).
   - Move the foot anchors (`FootAnchorL`, `FootAnchorR`) alternately forward and backward for a natural top-down walk feel.

---

## 7. Humanoid Character Adaptation: Hair, Arms, Legs, and Face

When applying this technique to humanoid characters (2 arms, 2 legs, torso, head, face, and hair), follow this critical design and layer architecture:

### 1. Style Rule (Proportions)
- Realistic (anatomical) human forms can look awkward under this math.
- This technique shines most with **Chibi / Stylized / Cartoon** humanoid proportions (*Animal Crossing, Zelda: Minish Cap / Link's Awakening, Fall Guys, Cult of the Lamb* style).
- A round head form, cylindrical/rounded torso, and slightly exaggerated hair volumes yield great results.

### 2. Humanoid Character Parts (PNG Exports)
Split a single drawing (slightly top-down/front view) into these parts:
- `shadow.png` (Ground ellipse shadow)
- `foot_l.png`, `foot_r.png` (Shoes)
- `torso.png` (Torso / Outfit)
- `arm_l.png`, `arm_r.png` or `hand_l.png`, `hand_r.png` (Hands / Arms)
- `head_base.png` (Skin-toned round head base)
- `face.png` (Eyes, eyebrows, mouth in a single group)
- `hair_front.png` (Front hair / Bangs)
- `hair_back.png` (Back hair / Nape / Back hair volume — **Critical Part!**)

### 3. Humanoid Rig Hierarchy
```text
HumanRig (Node2D, scale = Vector2(1.0, 0.5))
├── FeetLayer (position.y = 0)
│   ├── FootAnchorL ──> RemoteTransform2D ──> FootL
│   └── FootAnchorR ──> RemoteTransform2D ──> FootR
├── TorsoLayer (position.y = -18)
│   ├── TorsoAnchor ──> RemoteTransform2D ──> Torso
│   ├── ShoulderL (position.x = -12) ──> ArmAnchorL ──> HandL
│   └── ShoulderR (position.x = +12) ──> ArmAnchorR ──> HandR
└── HeadLayer (position.y = -40)
    └── HeadAnchor (rotation = angle)
        ├── HairBackAnchor (position.y = +4) ──> RemoteTransform2D ──> HairBack
        ├── HeadBaseAnchor ──> RemoteTransform2D ──> HeadBase
        ├── FaceAnchor (position.y = -4) ──> RemoteTransform2D ──> FaceGroup
        └── HairFrontAnchor (position.y = -6) ──> RemoteTransform2D ──> HairFront
```

### 4. Hair & Arm Z-Index Logic for Humanoids (Front vs Back)

The biggest visual trick showing that a humanoid character has turned away is the layer ordering of **Back Hair (`hair_back`)** and **Face (`face`)**:

```gdscript
func update_human_sorting(angle: float) -> void:
    # Character is facing back/north (between PI/2 and 3*PI/2)
    var is_facing_back: bool = angle > (PI * 0.5) and angle < (PI * 1.5)
    
    if is_facing_back:
        face_group.visible = false            # Face is hidden from behind
        hair_front.z_index = 0
        head_base.z_index = 1
        hair_back.z_index = 2                 # Back hair moves ABOVE the head, covering the back of the head!
        torso.z_index = 1
    else:
        face_group.visible = true             # Face is visible
        hair_back.z_index = -1                # Back hair stays behind the head
        head_base.z_index = 0
        face_group.z_index = 1                # Face is above the head
        hair_front.z_index = 2                # Front hair/bangs are above the face
        torso.z_index = 0

    # Arm depth when facing sideways (East / West):
    # For example, between 0 and PI the right arm can be in front while the left arm stays behind the torso:
    if angle > 0 and angle < PI:
        hand_r.z_index = torso.z_index + 1
        hand_l.z_index = torso.z_index - 1
    else:
        hand_r.z_index = torso.z_index - 1
        hand_l.z_index = torso.z_index + 1
```

### 5. Two Options for Arms and Legs:
1. **Rayman / Animal Crossing Style (Floating Limbs):** Arms and legs are not drawn; only hands and feet float around the torso. Very easy to draw and gives a charming cartoon look.
2. **Line2D Joint Connector:** A `Line2D` (`top_level = true`) from the torso shoulder point to the hand draws a dynamic arm in skin or shirt color; wherever the hand moves, the arm stretches to follow.

---

## 8. Common Issues and Solutions

| Error / Symptom | Cause | Solution |
|---|---|---|
| **Sprite looks squashed/flattened** | `RemoteTransform2D` is copying scale | Set `update_scale = false`. |
| **Head detaches from the body** | Parenting chain is broken | Copy the neck/shoulder position to the head root via `RemoteTransform2D` (`NeckPositionCopy`). |
| **Beak stays in front of body when facing away** | Z-index is not updated | Apply `z_index = -1` inside `_set_direction` based on the angle range. |
| **Character jitters** | Conflict between `_process` and physics | If character movement uses `CharacterBody2D`, update direction from physics velocity: `direction = velocity.angle()`. |

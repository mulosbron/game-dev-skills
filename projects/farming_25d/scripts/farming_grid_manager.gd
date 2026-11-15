extends Node3D
class_name FarmingGridManager

## 3D Grid Farming Manager for Retro 2.5D FPS
## Handles 1x1m soil state machine (Dry -> Tilled -> Wet -> Planted)
## Instantiates 2D Y-Billboard crop sprites that grow and can be harvested.

signal crop_planted(grid_pos: Vector2i, crop_name: String)
signal crop_harvested(grid_pos: Vector2i, crop_name: String)

enum SoilState {
    GRASS,
    TILLED,
    WET
}

class SoilCell:
    var state: SoilState = SoilState.GRASS
    var crop_name: String = ""
    var growth_stage: int = 0 # 0 to 5
    var max_stage: int = 5
    var crop_node: Sprite3D = null

var grid: Dictionary = {} # Vector2i -> SoilCell

# Preloaded soil textures
var tex_tilled = preload("res://sprites_2d/textures_3d/tex_soil_tilled_32x32.png")
var tex_wet = preload("res://sprites_2d/textures_3d/tex_soil_wet_32x32.png")

# Crop stage textures lookup (11 crops x 6 stages)
var crop_catalog = {
    "bugday": [
        preload("res://sprites_2d/crops/crop_bugday_stage_00.png"),
        preload("res://sprites_2d/crops/crop_bugday_stage_01.png"),
        preload("res://sprites_2d/crops/crop_bugday_stage_02.png"),
        preload("res://sprites_2d/crops/crop_bugday_stage_03.png"),
        preload("res://sprites_2d/crops/crop_bugday_stage_04.png"),
        preload("res://sprites_2d/crops/crop_bugday_stage_05.png")
    ],
    "domates": [
        preload("res://sprites_2d/crops/crop_domates_stage_00.png"),
        preload("res://sprites_2d/crops/crop_domates_stage_01.png"),
        preload("res://sprites_2d/crops/crop_domates_stage_02.png"),
        preload("res://sprites_2d/crops/crop_domates_stage_03.png"),
        preload("res://sprites_2d/crops/crop_domates_stage_04.png"),
        preload("res://sprites_2d/crops/crop_domates_stage_05.png")
    ],
    "havuc": [
        preload("res://sprites_2d/crops/crop_havuc_stage_00.png"),
        preload("res://sprites_2d/crops/crop_havuc_stage_01.png"),
        preload("res://sprites_2d/crops/crop_havuc_stage_02.png"),
        preload("res://sprites_2d/crops/crop_havuc_stage_03.png"),
        preload("res://sprites_2d/crops/crop_havuc_stage_04.png"),
        preload("res://sprites_2d/crops/crop_havuc_stage_05.png")
    ],
    "kabak": [
        preload("res://sprites_2d/crops/crop_kabak_stage_00.png"),
        preload("res://sprites_2d/crops/crop_kabak_stage_01.png"),
        preload("res://sprites_2d/crops/crop_kabak_stage_02.png"),
        preload("res://sprites_2d/crops/crop_kabak_stage_03.png"),
        preload("res://sprites_2d/crops/crop_kabak_stage_04.png"),
        preload("res://sprites_2d/crops/crop_kabak_stage_05.png")
    ]
}

func _ready() -> void:
    add_to_group("farming_manager")

func world_to_grid(world_pos: Vector3) -> Vector2i:
    return Vector2i(int(floor(world_pos.x)), int(floor(world_pos.z)))

func grid_to_world(grid_pos: Vector2i) -> Vector3:
    return Vector3(grid_pos.x + 0.5, 0.05, grid_pos.y + 0.5)

func handle_tile_interaction(hit_point: Vector3, tool_type: FPSPlayer.ItemType) -> void:
    var gpos = world_to_grid(hit_point)
    if not grid.has(gpos):
        grid[gpos] = SoilCell.new()
        
    var cell: SoilCell = grid[gpos]
    
    match tool_type:
        FPSPlayer.ItemType.HOE:
            # Till the ground
            if cell.state == SoilState.GRASS:
                cell.state = SoilState.TILLED
                _spawn_soil_decal(gpos, tex_tilled)
                
        FPSPlayer.ItemType.WATERING_CAN:
            # Water tilled ground
            if cell.state == SoilState.TILLED:
                cell.state = SoilState.WET
                _spawn_soil_decal(gpos, tex_wet)
                
        FPSPlayer.ItemType.SEED_PACKET:
            # Plant crop if tilled or wet and empty
            if (cell.state == SoilState.TILLED or cell.state == SoilState.WET) and cell.crop_name == "":
                plant_crop(gpos, "bugday")
                
        FPSPlayer.ItemType.SCYTHE:
            # Harvest crop if mature
            if cell.crop_name != "" and cell.growth_stage >= cell.max_stage:
                harvest_crop(gpos)

func handle_secondary_interaction(hit_point: Vector3) -> void:
    var gpos = world_to_grid(hit_point)
    if grid.has(gpos):
        var cell: SoilCell = grid[gpos]
        if cell.crop_name != "" and cell.growth_stage >= cell.max_stage:
            harvest_crop(gpos)
        elif (cell.state == SoilState.TILLED or cell.state == SoilState.WET) and cell.crop_name == "":
            plant_crop(gpos, "domates")

func plant_crop(gpos: Vector2i, crop_name: String) -> void:
    var cell: SoilCell = grid[gpos]
    cell.crop_name = crop_name
    cell.growth_stage = 0
    
    # Spawn 2D Billboard Sprite3D
    var sprite = Sprite3D.new()
    sprite.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y # Pure Y-Billboard
    sprite.centered = true
    sprite.offset.y = 16.0 # Bottom-center grounding
    sprite.pixel_size = 0.03
    sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    
    if crop_catalog.has(crop_name):
        sprite.texture = crop_catalog[crop_name][0]
        
    sprite.position = grid_to_world(gpos)
    add_child(sprite)
    cell.crop_node = sprite
    emit_signal("crop_planted", gpos, crop_name)

func advance_day() -> void:
    # Grow all planted crops by 1 stage
    for gpos in grid.keys():
        var cell: SoilCell = grid[gpos]
        if cell.crop_name != "" and cell.growth_stage < cell.max_stage:
            if cell.state == SoilState.WET:
                cell.growth_stage += 1
                cell.state = SoilState.TILLED # Absorbed water
                if cell.crop_node and crop_catalog.has(cell.crop_name):
                    cell.crop_node.texture = crop_catalog[cell.crop_name][cell.growth_stage]

func harvest_crop(gpos: Vector2i) -> void:
    var cell: SoilCell = grid[gpos]
    var harvested_crop = cell.crop_name
    
    # Remove crop sprite
    if cell.crop_node:
        cell.crop_node.queue_free()
        cell.crop_node = null
        
    cell.crop_name = ""
    cell.growth_stage = 0
    emit_signal("crop_harvested", gpos, harvested_crop)

func _spawn_soil_decal(gpos: Vector2i, texture: Texture2D) -> void:
    # Simple quad mesh on the ground
    var mesh_inst = MeshInstance3D.new()
    var quad = QuadMesh.new()
    quad.size = Vector2(1.0, 1.0)
    quad.orientation = PlaneMesh.FACE_Y
    mesh_inst.mesh = quad
    
    var mat = StandardMaterial3D.new()
    mat.albedo_texture = texture
    mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    mat.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
    mesh_inst.material_override = mat
    
    mesh_inst.position = Vector3(gpos.x + 0.5, 0.01, gpos.y + 0.5)
    add_child(mesh_inst)

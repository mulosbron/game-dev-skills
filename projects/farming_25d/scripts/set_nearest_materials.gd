# set_nearest_materials.gd - EditorScript to batch set all materials to Nearest filter
@tool
extends EditorScript

const ROOT := "res://"

func _run() -> void:
	_scan(ROOT)
	print("Godot Pixel Tool: All BaseMaterial3D resources updated to Nearest filter.")

func _scan(path: String) -> void:
	var dir := DirAccess.open(path)
	if dir == null:
		return
	dir.list_dir_begin()
	var fname := dir.get_next()
	while fname != "":
		var full := path.path_join(fname)
		if dir.current_is_dir() and not fname.begins_with(".") and fname != ".godot":
			_scan(full)
		elif fname.ends_with(".tres") or fname.ends_with(".material"):
			var res := load(full)
			if res is BaseMaterial3D:
				res.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
				ResourceSaver.save(res, full)
				print("[ok] Nearest filter applied: ", full)
		fname = dir.get_next()

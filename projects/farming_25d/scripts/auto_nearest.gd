# auto_nearest.gd - Runtime node that forces Nearest filter across all MeshInstance3D nodes
extends Node

func _ready() -> void:
	_apply(get_tree().current_scene)

func _apply(node: Node) -> void:
	if node is MeshInstance3D:
		var mi := node as MeshInstance3D
		for i in mi.get_surface_override_material_count():
			var m := mi.get_surface_override_material(i)
			if m is BaseMaterial3D:
				m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
		if mi.mesh:
			for i in mi.mesh.get_surface_count():
				var m2 := mi.mesh.surface_get_material(i)
				if m2 is BaseMaterial3D:
					m2.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	for c in node.get_children():
		_apply(c)

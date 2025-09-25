import json
import jsonpatch
from jsonpointer import resolve_pointer

def replace_from_map(json, path, node_type, attr, attr_map):
	node = resolve_pointer(json, path)
	if node['type'] == node_type:
		attr_path = path + attr
		current_val = resolve_pointer(json, attr_path)
		new_val = attr_map[current_val]
		jsonpatch.apply_patch(json, [{'op': 'replace', 'path': attr_path, 'value': new_val}], in_place=True)

	if not 'content' in node:
		return

	for i, child in enumerate(node['content']):
		replace_from_map(json, path + f'/content/{i}', node_type, attr, attr_map)


import json
import jsonpatch
from jsonpointer import resolve_pointer

def replace_from_map(json, path, node_type, attr, attr_map):
	node = resolve_pointer(json, path)
	if node['type'] == node_type:
		attr_path = path + attr
		current_val = resolve_pointer(json, attr_path)
		if current_val in attr_map:
			new_val = attr_map[current_val]
			jsonpatch.apply_patch(json, [{'op': 'replace', 'path': attr_path, 'value': new_val}], in_place=True)

	if not 'content' in node:
		return

	for i, child in enumerate(node['content']):
		replace_from_map(json, path + f'/content/{i}', node_type, attr, attr_map)

def replace_mentions(json, path, mention_type, mentions_map, alt_prefix):
	node = resolve_pointer(json, path)
	if node['type'] == 'mention' and mention_type == node['attrs']['type']:
		attr_path = path + '/attrs/modelId'
		current_val = resolve_pointer(json, attr_path)
		if current_val in mentions_map.keys():
			new_val = mentions_map[current_val]
			jsonpatch.apply_patch(json, [{'op': 'replace', 'path': attr_path, 'value': new_val}], in_place=True)
		else:
			new_val = alt_prefix + current_val
			label = resolve_pointer(json, path + '/attrs/label')
			jsonpatch.apply_patch(json, [{'op': 'replace', 'path': path, 'value': {"type": "text", "marks": [{"type": "link", "attrs": {"href": new_val}}], "text": label}}], in_place=True)

	if not 'content' in node:
		return

	for i, child in enumerate(node['content']):
		replace_mentions(json, path + f'/content/{i}', mention_type, mentions_map, alt_prefix)


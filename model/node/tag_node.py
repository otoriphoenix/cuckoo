from .node import Node

"""
General non-text nodes
"""
class TagNode(Node):
	attrs: dict
	children: list[Node]
	#allowed_children #tuple

	def __init__(self, node_type, group, allowed_children, children, attrs = None):
		self.node_type = node_type
		self.group = group
		self.allowed_children = allowed_children
		self.attrs = attrs
		self.children = children

	def __str__(self):
		return f"{self.node_type}[group={self.group}, children={[str(c) for c in self.children]}"

	def toJson(self):
		baseJson = {
			"type": self.node_type,
			}
		if len(self.children) > 0:
			baseJson["content"] = []
			for child in self.children:
				baseJson["content"].append(child.toJson())
		if self.attrs:
			baseJson["attrs"] = self.attrs
		return baseJson

	def validate(self):
		# All valid children get added to the list
		valid_group = [str(c) for c in self.children if c.group in self.allowed_children[0].split(' ')]
		#print(valid_group)

		# Check if the minimum contraint of children is met
		# and there are no invalid children
		v = len(valid_group)

		valid_child = [c for c in self.children if c.validate()]
		v2 = len(valid_child)

		is_valid = v >= self.allowed_children[1] and v == len(self.children) and v2 == v
		if not is_valid:
			print(valid_group)
		#	print(self)
		#	print([c.node_type for c in self.children if not c.validate()] + [c.node_type for c in self.children if not c.group in self.allowed_children[0].split(' ')])
		return is_valid



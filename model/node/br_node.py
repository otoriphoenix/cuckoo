from .node import Node

class BrNode(Node):
	def __init__(self):
		self.node_type = "br"
		self.group = "inline"

	def toJson(self):
		baseJson = {
			"type": self.node_type
		}
		return baseJson

	def validate(self, path):
		return True

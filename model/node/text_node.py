from .node import Node
from ..mark import Mark

class TextNode(Node):
	content: str
	marks: list[Mark]

	def __init__(self, content, marks):
		self.node_type = "text"
		self.content = str(content)
		self.marks = marks
		self.group = "inline"
		self.allowed_children = ()

	def __str__(self):
		return f"TextNode[content={self.content}]"

	def toJson(self):
		baseJson = {
			"type": self.node_type,
			"text": self.content
		}

		if len(self.marks) > 0:
			baseJson["marks"] = []
			for mark in self.marks:
				baseJson["marks"].append(mark.toJson())

		if self.hasMark('link'):
			baseJson["text"] = baseJson["text"].strip()

		return baseJson

	def hasMark(self, markName):
		for mark in self.marks:
			if mark.mark_type == markName:
				return True
		return False

	def validate(self, path):
		return True

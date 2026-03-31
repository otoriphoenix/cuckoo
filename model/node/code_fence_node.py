from .node import Node

"""
General non-text nodes
"""


class CodeFenceNode(Node):
    lang: str
    children: list[Node]

    def __init__(self, children, lang):
        self.node_type = "code_fence"
        self.group = "block"
        self.lang = lang
        self.children = children

    def toJson(self):
        baseJson = {
            "type": self.node_type,
            "attrs": {
                "language": self.lang
            }
        }
        if len(self.children) > 0:
            baseJson["content"] = []
            for child in self.children:
                baseJson["content"].append(child.toJson())
        return baseJson

    def validate(self, path):
        # All valid children get added to the list
        valid_group = [
            str(c)
            for c in self.children
            if c.node_type in ["text", "br"]
        ]
        return len(valid_group) == len(self.children)

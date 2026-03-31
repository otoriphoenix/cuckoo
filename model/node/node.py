from abc import ABC, abstractmethod

"""
Abstract base class for all node types in Outline.
Should mirror the Outline source code.
"""
inline_node_names = []


class Node(ABC):
    node_type: str
    group: str

    @abstractmethod
    def toJson(self):
        """
        Generate the JSON representation of a node.
        """
        pass

    @abstractmethod
    def validate(self, path):
        # for t, m in allowed_children:
        pass

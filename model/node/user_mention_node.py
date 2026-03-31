from .node import Node

"""
Node for a user mention.
Known issue: any marks applied to the text are lost.
This is intentional, since the mentions are either an own node
or a link text, which Outline most of the time doesn't apply formatting to.
"""
class UserMentionNode(Node):
	outlineUid: str
	confluenceUid: str

	def __init__(self, content, confluenceUid):
		self.node_type = 'user_mention'
		self.group = 'inline'
		self.outlineUid = None
		self.confluenceUid = confluenceUid

	def toJson(self):
		# TODO adapt based on outlineUid - if outlineUid is set, return a mention
		if self.outlineUid:
			return {
				"type": "mention",
				"attrs": {"type": "user", "modelId": self.outlineUid, "label": self.content}
			}

		#TODO return link to confluence if uid not set
		baseJson = {
			"type": "text",
			"marks": [{"type": "link", "href": self.confluenceUid}]
			}
		return baseJson

	"""
	Expects a map from Confluence user IDs to Outline user IDs
	"""
	def patchUid(self, confluenceUids):
		if self.confluenceUid in confluenceUids.keys():
			self.outlineUid = confluenceUids[self.confluenceUid]

	def setOutlineUid(self, outlineUid):
		self.outlineUid = outlineUid

	def validate(self):
		return True

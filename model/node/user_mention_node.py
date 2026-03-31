from .node import Node


from dotenv import load_dotenv
import os

load_dotenv()
CONFLUENCE_BASE_URL = os.getenv('CONFLUENCE_SRC', 'https://confluence.example.com')

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
		self.content = content

	def toJson(self):
		# TODO adapt based on outlineUid - if outlineUid is set, return a mention
		if self.outlineUid:
			return {
				"type": "mention",
				"attrs": {"type": "user", "modelId": self.outlineUid, "label": self.content}
			}

		baseJson = {
			"type": "text",
			"text": self.content,
			"marks": [{"type": "link", "attrs": {"href": f"{CONFLUENCE_BASE_URL}/display/~{self.confluenceUid}"}}]
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

	def validate(self, path):
		return True

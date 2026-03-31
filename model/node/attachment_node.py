from .node import Node
from dotenv import load_dotenv

import os

load_dotenv()
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_SRC", "https://confluence.example.com")

"""
Node for a non-image attachment.
Known issue: any marks applied to the text are lost.
This is intentional, since these are either an own node
or a link text, which Outline most of the time doesn't apply formatting to.
"""


class AttachmentNode(Node):
    title: str
    outlineAid: str
    confluenceAid: str
    confluenceDoc: str  # TODO do you need this?
    outlineDoc: str  # TODO user uid? maybe this is unnecessary -> this could work on document/space level
    size: int

    """
	# Down here so I can remove contents, since an attachment node doesn't have them
	if tag_type == 'attachment':
		# Link put together manually due to how attachment links look
		# (under the assumption that Confluence always generates them like this)
		# Third part of the first split is the filename, with possible attributes attached
		# First part of the second split is the full filename
		# Last part of the third split yields the suffix
		suffix = tag['href'].split('/')[4].split('?')[0].split('.')[-1]
		attrs["href"] = 'attachments/' + tag["data-linked-resource-container-id"] + '/' + tag['data-linked-resource-id'] + '.' + suffix
		attrs["title"] = tag["aria-label"] if "aria-label" in tag.attrs and tag["aria-label"] != '' else None
		attrs["id"] = None
		contents = []
		"""

    def __init__(self, title, confluenceAid, confluenceDoc):
        self.title = title
        self.node_type = "attachment"
        self.group = "block"
        self.outlineAid = None
        self.outlineDoc = None
        self.confluenceAid = confluenceAid
        self.confluenceDoc = confluenceDoc

    def toJson(self):
        # TODO adapt based on outlineAid - if outlineAid is set, return an attachment
        # baseJson = {
        # 	"type": self.node_type,
        # 	"attrs": self.attrs,
        # 	"children": self.children,
        # 	}
        if self.outlineAid:
            baseJson = {
                "type": "attachment",
                "attrs": {
                    "id": None,
                    "href": f"/api/attachments.redirect?id={self.outlineAid}",
                    "title": self.title,
                    "size": self.size,
                },
            }

        else:
            baseJson = {
                "type": "text",
                "marks": [
                    {
                        "type": "link",
                        "attrs": {
                            "href": f"{CONFLUENCE_BASE_URL}/download/attachments/{self.confluenceDoc}/{self.confluenceAid}"
                        },
                    }
                ],
                "text": self.title,
            }
        return baseJson

    def patchData(self, confluenceAids):
        print(self.confluenceAid, self.confluenceAid in confluenceAids.keys())
        if self.confluenceAid in confluenceAids.keys():
            self.outlineAid = confluenceAids[self.confluenceAid]["id"]
            self.size = confluenceAids[self.confluenceAid]["size"]
            print(self.toJson())

    def setOutlineAid(self, outlineAid):
        self.outlineAid = outlineAid

    def validate(self, path):
        return True

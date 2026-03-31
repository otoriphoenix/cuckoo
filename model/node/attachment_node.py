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
    confluenceDoc: str
    size: int

    def __init__(self, title, confluenceAid, confluenceDoc):
        self.title = title
        self.node_type = "attachment"
        self.group = "block"
        self.outlineAid = None
        self.confluenceAid = confluenceAid
        self.confluenceDoc = confluenceDoc

    def toJson(self):
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
        if self.confluenceAid in confluenceAids.keys():
            self.outlineAid = confluenceAids[self.confluenceAid]["id"]
            self.size = confluenceAids[self.confluenceAid]["size"]

    def setOutlineAid(self, outlineAid):
        self.outlineAid = outlineAid

    def validate(self, path):
        return True

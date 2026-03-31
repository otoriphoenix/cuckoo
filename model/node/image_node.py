from .node import Node
from dotenv import load_dotenv

import os

load_dotenv()
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_SRC", "https://confluence.example.com")


class ImageNode(Node):
    alt: str | None
    outlineIid: str
    confluenceLink: str
    confluenceAid: str
    width: int
    height: int

    def __init__(self, confluenceLink, width, height, alt):
        self.node_type = "image"
        self.group = "inline"
        self.outlineIid = None
        self.confluenceAid = confluenceLink.split("/")[-1]
        self.confluenceLink = confluenceLink
        self.width = width
        self.height = height
        self.alt = alt

    def toJson(self):
        if self.outlineIid:
            baseJson = {
                "type": "image",
                "attrs": {
                    "src": f"/api/attachments.redirect?id={self.outlineIid}",
                    "width": self.width,
                    "height": self.height,
                    "alt": self.alt,
                },
            }

        else:
            alt = self.alt if self.alt and len(self.alt) > 0 else "(Image on Confluence)"
            baseJson = {
                "type": "text",
                "marks": [
                    {
                        "type": "link",
                        "attrs": {
                            "href": f"{CONFLUENCE_BASE_URL}/{self.confluenceLink}"
                        },
                    }
                ],
                "text": alt,
            }
        return baseJson

    def patchAid(self, confluenceAids):
        if self.confluenceAid in confluenceAids.keys():
            self.outlineIid = confluenceAids[self.confluenceAid]

    def validate(self, path):
        return True

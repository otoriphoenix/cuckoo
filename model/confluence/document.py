from bs4 import BeautifulSoup, Tag
from minify_html import minify

from ..node.node import Node
from ..node.tag_node import TagNode
from ..factories import *

import request_wrapper as call
import os
import time
import json

# Class to help import a Confluence document into Outline
class ConfluenceDocument:
	title: str
	filename: str
	collection: str
	parent_id: str | None
	attachments: dict
	doc_id: str | None
	confluence_slug: str
	_raw_content: str
	_html_content: BeautifulSoup
	_node_content: Node
	_json_content: dict

	def __init__(self, title, filename, collection, parent_id):
		self.doc_id = None
		self.title = title
		self.file = filename # we might need this to fix up links in the collections later
		self.collection = collection
		self.parent = parent_id
		self.attachments = {}
		# To know where the attachments lie.
		# Technically, this is given by their links?
		self.confluence_slug = filename[:-5].split("_")[-1]
		with open(f"{os.getenv('CONFLUENCE_TMP')}/{self.collection.shortname}/{self.file}", "r") as content:
			self.set_content(content.read(), "raw")

	def get_content(self, content_format="node"):
		match content_format:
			case "raw":
				return self._raw_content
			case "html":
				return self._html_content
			case "json":
				return self._json_content
			case _:
				return self._node_content

	def set_content(self, content, content_format="node"):
		match content_format:
			case "raw":
				self._raw_content = content
			case "html":
				self._html_content = content
			case "json":
				self._json_content = content
			case _:
				self._node_content = content

	# Returns the document id, so nested documents can set their parentDocumentId
	# Also returns content as JSON
	def import_doc(self, home=False):
		print(self.confluence_slug)
		self.preprocess_html()
		self.clean_html()
		self.convert_html()
		self.fake_upload()
		self.upload_attachments()
		self.fix_attachment_ids(self.get_content())
		self.merge_textleaves(self.get_content())
		self.wrap_nodes(self.get_content())
		self.validate()
		self.convert_to_json()
		if home:
			self.make_space_description()
		return self.doc_id, self.get_content("json")

	# For the nasty html best replaced before parsing
	def preprocess_html(self):
		self.set_content(minify(self._raw_content), "raw")
		self.set_content(self._raw_content.replace(r"<p><br></p>", ""), "raw")
		self.set_content(self._raw_content.replace(r"<p></p>", ""), "raw")
		self.set_content(self._raw_content.replace(u'\xa0', ' '), "raw")
		self.set_content(self._raw_content.replace('&nsbp;', ' '), "raw")
		self.set_content(BeautifulSoup(self._raw_content, 'lxml'), "html")

	# Removes superflous HTML, translates some tag names and gives us a dict of attachments
	def clean_html(self):
		soup = self.get_content("html")
		# Extracts the attachment list for further processing
		attached = soup.find(id="attachments")
		if attached:
			attached = attached.parent.parent.extract()
			attached = attached.find(class_="greybox")
			attached = attached.find_all("a")

			for attachment in attached:
				key = attachment["href"].split("/")[-1]
				self.attachments[key] = ""
				attachment.decompose()

		# Remove breadcrumbs
		breadcrumbs = soup.find(id="main-header")
		breadcrumbs.decompose()

		# Format Confluence export metadata nicely and remove Atlassian link
		footer = soup.find(id="footer")
		footer.find(id="footer-logo").decompose()
		footer.section.p.unwrap()
		footer.section.unwrap()
		footer.smooth()
		footer = footer.extract()
		metadata = soup.find(class_="page-metadata")
		if metadata.span:
			metadata.span.replace_with(metadata.span.get_text(strip=True))
		if metadata.span:
			metadata.span.replace_with(metadata.span.get_text(strip=True))
		metadata.smooth()
		metadata = metadata.wrap(soup.new_tag('em'))
		metadata.append(soup.new_tag('br'))
		metadata.append(footer)
		metadata = metadata.wrap(soup.new_tag('p'))

		# These don't seem to have an Outline equivalent, so we remove them
		colgroups = soup.find_all('colgroup')
		for colgroup in colgroups:
			colgroup.decompose()

		# Remove tiny Jira icons
		jira_keys = soup.find_all(class_="jira-issue-key")
		for jira_key in jira_keys:
			if jira_key.img:
				jira_key.img.decompose()

		# Fixes emojis inserted via :<emoji_name>:
		# I like this code:
		# - the unicode hex is given in an HTML attribute
		# - it's a simple conversion
		# ...or at least it would be IF THERE WASN'T A SECOND TYPE OF EMOTICON
		emojis = soup.find_all(class_="emoticon")
		for emoji in emojis:
			if "data-emoji-id" in emoji:
				emoji.replace_with(chr(int(emoji["data-emoji-id"], 16)))
			else: # It's a bloody different type of emoticon.
				emoji.replace_with(emoji["alt"])

		# Recent space activity fix
		activity = soup.find('div', class_='recently-updated recently-updated-social')
		if activity:
			updates = soup.find_all('ul', class_='update-items')
			for update in updates:
				person = update.div.extract()
				update.insert_before(person)

		attached = soup.find_all('span', class_='confluence-embedded-file-wrapper')
		for attach in attached:
			if attach.parent.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
				attach.parent.unwrap()

		argh = ['p p', 'h1 p', 'h2 p', 'h3 p', 'h4 p', 'h5 p', 'h6 p']
		for a in argh:
			p_in_aaa = soup.select(a)
			for p_in_p in p_in_aaa:
				p_in_p.unwrap()

	# The heavy loading is done in a different file as to make this class easier to read
	def convert_html(self):
		self.set_content(node_factory(self.get_content("html").find("body"), []), "node")

	def upload_attachments(self):
		for attached_file in self.attachments.keys():
			filepath = f"{os.getenv('CONFLUENCE_TMP')}/{self.collection.shortname}/attachments/{self.confluence_slug}/{attached_file}"
			if not os.path.exists(filepath):
				continue
			file_id, file_size = call.attach(filepath, self.doc_id, 'documentAttachment')
			self.attachments[attached_file] = file_id

	def fix_attachment_ids(self, root_node):
		if root_node.node_type == "attachment":
			root_node.patchAid(self.attachments)
			return

		if root_node.node_type == "image":
			root_node.patchAid(self.attachments)
			return

		if root_node.node_type in ["br", "text", "user_mention"]:
			return

		for child in root_node.children:
			self.fix_attachment_ids(child)

	# Sets the content of the document as the description of the collection
	# Actually doing that needs to be done at collection level to ensure proper formatting
	# To let the collection know about this, we just remove the document and its ID
	def make_space_description(self):
		call.json_endpoint("documents.delete", {"id": self.doc_id})
		self.doc_id = None

	# Creates a document with the given title.
	# This gets a mangled version in place as a base for if the import fails.
	def fake_upload(self):
		answer = call.import_html(self.title, str(self.get_content("html")), self.collection.id, self.parent)
		self.doc_id = answer['id']

	def convert_to_json(self):
		self.set_content(self.get_content("node").toJson(), "json")

	def merge_textleaves(self, node):
		inlined = ["br", "text", "user_mention", "image", "attachment"]
		if node.node_type in inlined:
			return

		if len(node.children) == 0:
			return

		for child in node.children:
			self.merge_textleaves(child)

		# thanks Mistral
		children_merged = []
		current = node.children[0]

		for child in node.children[1:]:
			if child.node_type == "text" and current.node_type == "text":
				current.content += child.content
			else:
				children_merged.append(current)
				current = child
		children_merged.append(current)

		node.children = children_merged

	def wrap_nodes(self, node):
		inlined = ["br", "text", "user_mention", "image", "attachment"]
		if node.node_type in inlined:
			return

		# Already wrapped
		if node.node_type in ["heading", "paragraph"]:
			return

		# check if applicable
		if not type(node) is TagNode:
			return

		for child in node.children:
			self.wrap_nodes(child)

		children_wrapped = []
		collector = []
		for child in node.children:
			if child.node_type in inlined:
				collector.append(child)
			else:
				# Clear out collector with wrapped nodes
				if len(collector) > 0:
					children_wrapped.append(produce_paragraph(collector))
					collector = []
				children_wrapped.append(child)

		if len(collector) > 0:
			children_wrapped.append(produce_paragraph(collector))
		node.children = children_wrapped


	def validate(self):
		if not self.get_content().validate():
			raise Exception("Validation Error!")

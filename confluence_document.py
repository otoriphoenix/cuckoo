from convert_html import html_to_json
from json_helper import replace_from_map, add_from_map
import request_wrapper as call
import os
import time
import json

# Class to help import a Confluence document into Outline
class ConfluenceDocument:
	def __init__(self, title, filename, collection, parent_id):
		self.collection = collection
		self.title = title
		self.file = filename # we might need this to fix up links in the collections later
		with open(f"{os.getenv('CONFLUENCE_TMP')}/{self.collection.shortname}/{self.file}", "r") as content:
			self.content = content.read()
		self.parent = parent_id
		self.id = None
		# To know where the attachments lie.
		# Technically, this is given by their links?
		self.confluence_slug = filename[:-5].split("_")[-1]

	# Returns the document id, so nested documents can set their parentDocumentId
	# Also returns content as JSON
	def handle(self, home=False):
		print(self.confluence_slug)
		self.preprocess_html()
		self.convert_html()
		self.fake_upload()
		for attached_file in self.attachments.keys():
			file_id, file_size = call.attach(f"{os.getenv('CONFLUENCE_TMP')}/{self.collection.shortname}/attachments/{self.confluence_slug}/{attached_file}", self.id, 'documentAttachment')
			self.attachments[attached_file] = {"id": file_id, "size": file_size}
			time.sleep(1)
			#break # For debugging purposes. Disabled in prod.
		self.postprocess()
		if home:
			self.make_space_description()
		return self.id, self.content

	# For the nasty html best replaced before parsing
	def preprocess_html(self):
		self.content = self.content.replace(r"<p><br></p>", "")
		self.content = self.content.replace(u'\xa0', ' ')
		self.content = self.content.replace('&nsbp;', ' ')

	# The heavy loading is done in a different file as to make this class easier to read
	def convert_html(self):
		self.content, self.attachments = html_to_json(self.content)

	# Sets the content of the document as the description of the collection
	# Actually doing that needs to be done at collection level to ensure proper formatting
	# To let the collection know about this, we just remove the document and its ID
	def make_space_description(self):
		call_json_endpoint("documents.delete", {"id": self.id})
		self.id = None

	# Creates a document with the given title.
	# This does not get the content in place yet!
	def fake_upload(self):
		answer = call.json_endpoint('documents.create', {
			"title": self.title,
			"text": "Placeholder created by Cuckoo",
			"collectionId": self.collection.id,
			"parentDocumentId": self.parent,
			"publish": True
		})
		self.id = answer['id']

	# Replaces some Confluence IDs/locations with the Outline equivalents
	def postprocess(self):
		attachment_path = 'attachments/' + self.confluence_slug
		attachment_map = {}
		# Map image links
		replace_from_map(self.content, '', 'image', '/attrs/src', attachment_map)
		# Add the sizes
		for key, value in self.attachments.items():
			attachment_map[f'{attachment_path}/{key}'] = value["size"]
		add_from_map(self.content, '', 'attachment', '/attrs/href', '/attrs/size', attachment_map)
		# Map other attachments
		for key, value in self.attachments.items():
			attachment_map[f'{attachment_path}/{key}'] = f'/api/attachments.redirect?id={value["id"]}'
		replace_from_map(self.content, '', 'attachment', '/attrs/href', attachment_map)

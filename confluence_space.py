import request_wrapper as call
from confluence_document import ConfluenceDocument
from bs4 import BeautifulSoup
import os
import time
import zipfile
import jsonpatch
import json
import shutil
from json_helper import replace_mentions

# Class to help import a Confluence space as an Outline collection
class ConfluenceSpace:
	def __init__(self, shortname, users):
		self.shortname = shortname
		self.users = users

	# Creates the space if it doesn't exist and starts processing the pages listed in index.html
	# Flow:
	# - create space with name
	# - space name from index.html
	# - index.html gives hierarchy
	# - iterate over hierarchy
	# - if in top level list: feed into collection with space name
	# - if in sublist: give document parent id, while iterating
	def import_space(self, home_is_description = False):
		space_index = BeautifulSoup(open(f"{os.getenv('CONFLUENCE_TMP')}/{self.shortname}/index.html", "r"), 'lxml')
		space_details = space_index.find(id="main-content").find("table").find_all("td")
		self.name = space_details[1].string
		self.name = self.name + f" [{self.shortname}]"
		self.create_collection()
		self.documents = {}
		self.description = None # None yields the standard Cuckoo Importer message

		page_tree = space_index.find("ul")
		pages = page_tree.find_all("li", recursive=False)
		self.process_home = home_is_description
		self.process_pages(pages)
		self.export_import()

	def create_collection(self):
		answer = call.json_endpoint("collections.create", {
			"name": self.name,
			"description": f"Imported with Cuckoo Importer v1.1.0\n\n© Sascha Bacher",
			"permission": None,
			"sharing": False
		})
		self.id = answer["id"]

	# Iterates recursively over the document tree, creating pages as it progresses
	def process_pages(self, pages, parent = None):
		for page in pages:
			document_name = page.a['href']
			document_title = page.a.string
			print(f"Processing \"{document_title}\", parent: {parent}, internal name: {document_name} ...")

			document_id, document_content = ConfluenceDocument(document_title, document_name, self, parent).handle(self.process_home)
			if self.process_home and not document_id:
				self.process_home = False
				self.description = document_content
			if document_id:
				self.documents[document_name] = {"outlineID": document_id, "outlineContent": document_content}
			#return #for debugging purposes, stop after 1 document. Disabled in prod.

			# Avoid rate limit
			time.sleep(15)

			nested = page.find_all("ul", recursive = False)
			for n in nested:
				self.process_pages(n.find_all("li", recursive = False), document_id)
			print(f"Processed \"{document_title}\"")

	# Exports and deletes the collection from Outline, applies magic and reimports the collection into Outline
	# Done at collection level since one collection is put into one json file anyway
	def export_import(self):
		auth = f"Bearer {os.getenv('API_TOKEN')}"
		answer = call.json_endpoint("collections.export", {"format": "json",
			"id": self.id, "includeAttachments": True})
		file_op = answer["fileOperation"]
		file_id = file_op["id"]
		while not file_op["state"] == "complete":
			file_op = call.json_endpoint("fileOperations.info", {"id": file_id})
			time.sleep(2)

		export_file = call.fetch_file(file_id)
		with open(f'{os.getenv("OUTLINE_TMP")}/{self.shortname}-raw.zip', 'wb') as target_file:
			target_file.write(export_file)

		with zipfile.ZipFile(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}-raw.zip", "r") as zip_ref:
			zip_ref.extractall(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}")
		self.json = open(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}/{self.name}.json", "r").read()
		self.json = json.loads(self.json)

		# We have the file, so we delete it from the server as to not pollute it
		answer = call.json_endpoint("fileOperations.delete", {"id": file_id})

		# Then we delete the collection
		answer = call.json_endpoint("collections.delete", {"id": self.id})
		call.json_endpoint("documents.empty_trash", {})

		# We work our magic...
		self.praise_the_whale()

		# ...zip the file again...
		path = os.path.join(os.getenv('OUTLINE_TMP') , self.shortname)
		shutil.make_archive(path, 'zip', path)

		# ...and reimport the collection
		import_file_id = call.attach(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}.zip", None, "workspaceImport")
		answer = call.json_endpoint("collections.import", {"attachmentId": import_file_id, "format": "json", "permission": None, "sharing": False})

	def praise_the_whale(self):
		doc_id_map = {key[:-5].split("_")[-1]: self.documents[key]['outlineID'] for key in self.documents}
		for doc_name, document in self.documents.items():
			jsonpatch.apply_patch(self.json, [{"op": 'replace', 'path': f"/documents/{document['outlineID']}/data", 'value': document['outlineContent']}], in_place=True)
			replace_mentions(self.json, f"/documents/{document['outlineID']}/data", 'user', self.users, f'{os.getenv("CONFLUENCE_SRC")}/display/~')
			# Technically, this would work. However, Outline assigns new IDs on import without updating these references, so it's disabled for now. (https://github.com/outline/outline/issues/9584)
			replace_mentions(self.json, f"/documents/{document['outlineID']}/data", 'document', {}, f'{os.getenv("CONFLUENCE_SRC")}/spaces/{self.shortname}/pages/')
		if self.description:
			jsonpatch.apply_patch(self.json, [{"op": 'replace', 'path': "/collection/data", 'value': self.description}], in_place=True)
		self.json = json.dumps(self.json)
		with open(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}/{self.name}.json", 'w') as outfile:
			outfile.write(self.json)

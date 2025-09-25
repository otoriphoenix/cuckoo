import request_wrapper as call
from confluence_document import ConfluenceDocument
from bs4 import BeautifulSoup
import os
import time
import zipfile
import jsonpatch
import json
import shutil

# Class to help import a Confluence space as an Outline collection
class ConfluenceSpace:
	def __init__(self, shortname):
		self.shortname = shortname

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
		self.description = None # None for the standard Cuckoo Importer message

		page_tree = space_index.find("ul")
		pages = page_tree.find_all("li", recursive=False)
		self.process_home = home_is_description
		self.process_pages(pages)
		self.export_import()

	def create_collection(self):
		answer = call.json_endpoint("collections.create", {
			"name": self.name,
			"description": f"Imported with Cuckoo Importer v1.0.0\n\n© Sascha Bacher",
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
		#NOTE: json structure of collection export is ["documents"][<document_id>]["data"] - this gives prosemirror contents
		#NOTE: contents are ordered hierarchically! might be difficult to replicate, need to figure out how to do that
		#NOTE: data-actorId in mentions is the uploading user -> is optional! not always in prosemirror data
		#NOTE: modelId in mentions is mentioned user, this is reflected in the generated link => only relevant attribute!!!
		#NOTE: id is id of mention itself, should be unique on page but can be replicated across multiple pages -> this can be null and still work with the import, as a new one is generated on import!
		#NOTE: if this is set through md postprocessing (as opposed to json prosemirror data), outline will automatically correct this - however, this gets immediately fucked over by tables
		#NOTE: for export-import:
		# - create attachment with preset workspaceImport (ex. {"preset":"workspaceImport","contentType":"application/zip","size":2031516,"name":"Sascha-Test-export.json.zip"})

		# note: collections.update - id,permission (read/read_write/null/admin)
		#			 collections.add_user for specific user, same scheme + userId -> we should add at least one admin to each collection!
		#		collections.add_group for groups (like admins), same scheme + groupId
		#			 ACL list for spaces (with shortname)? possibly via groups
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

		# We work our magic...
		self.praise_the_whale()

		# ...zip the file again...
		path = os.path.join(os.getenv('OUTLINE_TMP') , self.shortname)
		shutil.make_archive(path, 'zip', path)

		# ...and reimport the collection
		import_file_id = call.attach(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}.zip", None, "workspaceImport")
		answer = call.json_endpoint("collections.import", {"attachmentId": import_file_id, "format": "json", "permission": None, "sharing": False})

	def praise_the_whale(self):
		patches = []
		for doc_name, document in self.documents.items():
			patches.append({"op": 'replace', 'path': f"/documents/{document['outlineID']}/data", 'value': document['outlineContent']})
		if self.description:
			patches.append({"op": 'replace', 'path': "/collection/data", 'value': self.description})
		jsonpatch.apply_patch(self.json, patches, in_place=True)
		#self.json = praise_the_whale(self.json)
		self.json = json.dumps(self.json)
		with open(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}/{self.name}.json", 'w') as outfile:
			outfile.write(self.json)

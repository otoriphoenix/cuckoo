import re
import requests
from bs4 import BeautifulSoup, NavigableString
import zipfile
import os
import sys
import time
import json
import magic
from whale import praise_the_whale
from dotenv import load_dotenv

__version__ = "1.0.0"

load_dotenv()
HOME_IS_DESCRIPTION = (os.getenv('HOME_IS_DESCRIPTION', 'False') == 'True')
# To make sure Outline can read this, we put auth into a variable first
auth = f"Bearer {os.getenv('API_TOKEN')}"

# Load the already known user list. Currently, this is maintained manually.
users = json.loads(open("users.json", "r").read())

#----------------
# Helper section
#----------------
# Tiny helper to extract the zip files
#TODO replace with unzip
def open_zip(zip_name):
	with zipfile.ZipFile(zip_name, "r") as zip_ref:
		zip_ref.extractall(os.getenv('CONFLUENCE_TMP'))

def not_br(tag):
	return tag and tag.name != "br" and tag.class_ != "confluenceTd" and tag.name != "tr" and tag.name != "td" and tag.name != "th" and tag.name != 'span'

# POST request to an endpoint expecting JSON. Most common call with this API.
def call_json_endpoint(endpoint, json_data):
	answer_raw = None
	while not answer_raw:
		answer_raw = requests.post(f"{os.getenv(OUTLINE_API)}/{endpoint}",
		headers={
			"Content-Type": "application/json",
			"Authorization": auth
		}, json=json_data)


		#if answer_raw.status_code == 429:
			#time.sleep(float(answer_raw.headers['Retry-After'])/1000)
		#	continue

		answer = json.loads(answer_raw.text)
		if answer["ok"] == False:
			raise Exception(f"Error calling {endpoint}!\n{answer['status']}: {answer['message']}")
	if "data" in answer:
		return answer["data"]

# Attaches a file to the given document.
# There need not be a document this attachment belongs to, but it is often the case
def attach(filepath, document_id = None, preset = None):
	filename = filepath.split('/')[-1]
	mime = magic.from_file(filepath, mime = True)
	filesize = os.path.getsize(filepath)
	#NOTE: preset setting exists - can be documentAttachment or workspaceImport, seems optional
	upload_meta = {
		"name": filename,
		"documentId": document_id,
		"contentType": mime,
		"size": filesize,
		#"preset": "documentAttachment"
	}
	if not document_id:
		del upload_meta["documentId"]

	if preset:
		upload_meta["preset"] = preset

	answer = call_json_endpoint("attachments.create", upload_meta)
	file_id = answer["attachment"]["id"]
	attachment_meta = answer["form"]
	answer_raw = requests.post(f"{os.getenv(OUTLINE_API)}/files.create",
		headers={"Authorization": auth},
		data=attachment_meta,
		files={"file": (filename, open(filepath, "rb"), mime)})

	answer = json.loads(answer_raw.text)
	print(answer)
	if answer["ok"] == False:
		if answer_raw.status_code == 429:
			print(answer_raw.headers['Retry-After'])
		raise Exception(f"Error uploading attachment!\n{answer['status']}: {answer['message']}")
	return file_id

#TODO maybe define OutlineFile class?


#-----------------
# Classes section
#-----------------

# Class to help import a Confluence document into Outline
class ConfluenceDocument:
	def __init__(self, title, filename, collection, parent_id):
		self.collection = collection
		self.title = title
		self.file = filename # we might need this to fix up links in the collections later
		self.content = open(f"{os.getenv('CONFLUENCE_TMP')}/{self.collection.shortname}/{self.file}", "r").read()
		self.parent = parent_id
		self.id = None
		# To know where the attachments lie.
		# Technically, this is given by their links?
		self.confluence_slug = filename[:-5].split("_")[-1]

	# Returns the document id, so nested documents can set their parentDocumentId
	def handle(self, home=False):
		print(self.confluence_slug)
		self.pre_preprocess()
		self.preprocess_html()
		self.upload_file()
		for attached_file in self.attachments.keys():
			self.attachments[attached_file] = attach(f"{os.getenv('CONFLUENCE_TMP')}/{self.collection.shortname}/attachments/{self.confluence_slug}/{attached_file}", self.id)
			time.sleep(1)
			#break
		print(self.content)
		self.postprocess()
		if home:
			self.make_space_description()
		return self.id

	# Common helper
	def fake_tag(self, tag, fake_start, fake_end, wrap_brs=False):
		brs = tag.find_all("br")
		for br in brs:
			if wrap_brs:
				br.insert_before(fake_end)
				br.insert_after(fake_start)
			else:
				br.replace_with("⟨br/⟩")
		tag.insert(0, fake_start)
		tag.append(fake_end)
		tag.smooth()
		tag.unwrap()

	# For the nasty html best replaced before parsing
	def pre_preprocess(self):
		self.content = self.content.replace("\n", "")
		self.content = self.content.replace(r"<p><br></p>", "")
		self.content = self.content.replace(r"<p></p>", "<br>")
		self.content = self.content.replace(r'<div class="columnLayout single" data-layout="single"><div class="cell normal" data-type="normal"><div class="innerCell"><p><br></p></div></div></div>', "")
		self.content = self.content.replace(u'\xa0', ' ')
		self.content = self.content.replace('&nsbp;', ' ')

	# Tightly coupled with post processing, this involves
	# cursed invocations to the Benevolent Whale
	# Using angle brackets to prevent markdown fuckups, as we do want some postprocessing
	# Yes, this looks extremely cursed
	# However, angle brackets are not part of ASCII, so they don't carry semantic meaning in markdown
	# - this enables me to do some *extremely* cursed stuff
	def preprocess_html(self):
		# We're eating well tonight
		soup = BeautifulSoup(self.content, 'lxml')

		#-----------------
		# PART I: Removal
		#-----------------

		self.attachments = {}
		# Extracts the attachment list for further processing
		attachments = soup.find(id="attachments")
		if attachments:
			attachments = attachments.parent.parent.extract()
			attachments = attachments.find(class_="greybox")
			attachments = attachments.find_all("a")

			for attachment in attachments:
				key = attachment["href"].split("/")[-1]
				self.attachments[key] = ""
			print(self.attachments.keys())

		# Remove breadcrumbs + superfluous title
		breadcrumbs = soup.find(id="main-header")
		breadcrumbs.extract()

		# Format Confluence export metadata nicely and remove Atlassian link
		footer = soup.find(id="footer")
		footer.find(id="footer-logo").decompose()
		footer.section.p.unwrap()
		footer.section.unwrap()
		footer.smooth()
		print(footer.contents)
		footer.string = "⟨i⟩" + footer.get_text(strip=True) + "⟨/i⟩"
		footer = footer.extract()
		metadata = soup.find(class_="page-metadata")
		if metadata.span:
			metadata.span.unwrap()
		if metadata.span:
			metadata.span.unwrap()
		metadata.smooth()
		metadata.string = "⟨i⟩" + metadata.get_text(strip=True) + "⟨/i⟩"
		metadata.append(footer)

		# Tags that fuck up any given import
		# Includes the following:
		# - Remove the profile-full tables to resolve display issues
		#   These are empty anyways, so it's fine
		# - profile picture for vcards - not really necessary to display
		#   They're more of eye candy than important content
		# - Remove certain divs
		bad_tags = {
			"span": ["aui-avatar"],
			"div": ["update-item-icon", "update-item-profile", "more-link-container"],
			"table": ["profile-full"],
		}
		for name, classes in bad_tags.items():
			for clazz in classes:
				bad_tags = soup.find_all(name=name, class_=clazz)
				for bad_tag in bad_tags:
					bad_tag.decompose()

		# Empty paragraph that needs special handling
		profiles = soup.find_all(class_="profile-macro")
		for profile in profiles:
			if profile.parent.p:
				profile.parent.p.decompose()

		tds = soup.find_all(class_="confluenceTd")
		for td in tds:
			if td.content and len(td.content) == 1 and td.content[0].name and td.content[0].name == "br":
				td.content[0].decompose()

		# Remove tiny Jira icons
		jira_keys = soup.find_all(class_="jira-issue-key")
		for jira_key in jira_keys:
			if jira_key.img:
				jira_key.img.decompose()

		# TODO lists in tables
		# TODO attachments that aren't images

		#-----------------------
		# PART II: Replacements
		#-----------------------

		# Fixes emojis inserted via :<emoji_name>:
		# I like this code:
		# - the unicode hex is given in an HTML attribute
		# - it's a simple conversion
		emojis = soup.find_all(class_="emoticon")
		for emoji in emojis:
			emoji.replace_with(chr(int(emoji["data-emoji-id"], 16)))

		# Attachments
		# TODO fix image scale
		attachment_refs = soup.find_all("img", {"data-linked-resource-type": "attachment"})
		for attachment_ref in attachment_refs:
			attachment_name = attachment_ref['src'].split("/")[-1]
			self.fake_tag(attachment_ref, f"⟨image({attachment_name})/⟩", "")

		#TODO make sure this works!
		attachment_refs = soup.find_all({"data-linked-resource-type": "attachment"})
		for attachment_ref in attachment_refs:
			attachment_name = attachment_ref['src'].split("/")[-1]
			self.fake_tag(attachment_ref, f"⟨file({attachment_name})⟩", "⟨/file⟩")

		# Headings in tables
		tables = soup.find_all("table")
		for table in tables:
			for i in range(1,5):
				headings = table.find_all(f"h{i}")
				for heading in headings:
					self.fake_tag(heading, f"⟨h{i}⟩", f"⟨/h{i}⟩")


		# Work around bold text not displaying properly
		bolds = soup.find_all("strong")
		for bold in bolds:
			self.fake_tag(bold, "⟨b⟩", "⟨/b⟩", True)

		# Work around italic text not displaying properly
		italics = soup.find_all("em")
		for italic in italics:
			self.fake_tag(italic, "⟨i⟩", "⟨/i⟩", True)

		# Mentions first, since these are special links
		mentions = soup.find_all("a", class_="confluence-userlink")
		for mention in mentions:
			# Only convert users for whom we know the Outline UUID to Outline mentions
			if mention["data-username"] in users:
				self.fake_tag(mention, "⟨mention(" + users[mention["data-username"]] + ")⟩", "⟨/mention⟩")
			else:
				if mention['href'].startswith('/'):
					href = CONFLUENCE_SRC + mention["href"].strip()
				else:
					href = mention["href"].strip()
				self.fake_tag(mention, "⟨a(" + href +")⟩", "⟨/a⟩")

		# Other link fixes since not all links are created equal
		link_classes = ["email", "jira-issue-key", "external-link"]
		for lc in link_classes:
			links = soup.find_all("a")
			for a in links:
				if a['href'].startswith('/'):
					href = CONFLUENCE_SRC + a["href"].strip()
					self.fake_tag(a, "⟨a(" + href +")⟩", "⟨/a⟩")
				# Assume document relation
				elif a['href'].endswith('.html'):
					href = a["href"].strip()
					self.fake_tag(a, "⟨doc(" + href +")⟩", "⟨/doc⟩")
				else:
					href = a["href"].strip()
					self.fake_tag(a, "⟨a(" + href +")⟩", "⟨/a⟩")

		# Process task lists
		tasklists = soup.find_all("ul", class_="inline-task-list")
		for tasklist in tasklists:
			tasks = tasklist.find_all("li")
			for task in tasks:
				if task.has_attr("class"):
					self.fake_tag(task, "⟨x⟩", '⟨/task⟩')
				else:
					self.fake_tag(task, "⟨ ⟩", '⟨/task⟩')
			#for i in range(0,len(tasks)):
			#	if tasks[i].has_attr("class"):
			#		tasks[i].insert(0, " ⟨x⟩ ")
			#	else:
			#		tasks[i].insert(0, " ⟨ ⟩ ")
			self.fake_tag(tasklist, "⟨tasks⟩", "⟨/tasks⟩")

		# Process info blocks and similar
		# Disabled until i find time to implement complex tag sibling searches
		#infos = soup.find_all('div', class_="confluence-information-macro-information")
		#for info in infos:
		#	self.fake_tag(info, '⟨info⟩', '⟨/info⟩')

		# TODO lists in tables
		# TODO code blocks

		# Remove empty divs
		# Needs to be here as to not break other code
		for x in soup.find_all(name=not_br):
			if len(x.get_text(strip=True)) == 0:
				x.extract()

		# Finally, make a string again
		self.content = soup.encode(formatter="html5")
		#print(self.content)
		return

	# Not much done here, as too much gets fucked up by tables
	def postprocess(self):
		# Fixes erroneously generated formatting
		self.content = self.content.replace(r"!!", r"\!\!")

		# Get attachment ids into document
		for attach_name, attach_id in self.attachments.items():
			self.content = self.content.replace("⟨image(" + attach_name + ")/⟩", "⟨image(" + attach_id + ")/⟩")
			self.content = self.content.replace("⟨file(" + attach_name + ")⟩", "⟨file(" + attach_id + ")⟩")

		call_json_endpoint("documents.update", {"id": self.id, "text": self.content})

	# Sets the content of the document as the description of the collection
	# Deletes the document afterwards
	def make_space_description(self):
		# We first set the space description to the same markdown we got from importing the document
		call_json_endpoint("collections.update", {"id": self.collection.id, "description": self.content})

		# Afterwards, we destroy the created document
		call_json_endpoint("documents.delete", {"id": self.id})

		# Finally, we have this reflect in the ID
		self.id = None

	# Imports the document into Outline
	# Returns the resulting markdown to be used in postprocessing
	def upload_file(self):
		answer_raw = requests.post(f"{os.getenv('OUTLINE_API')}/documents.import",
			headers={
				# I'm not allowed to set this header myself when using the library
				# because Outline will throw a hissyfit
				#"Content-Type": "multipart/form-data",
				"Authorization": auth
			},
			data={
				"parentDocumentId": self.parent,
				"collectionId": self.collection.id,
				"publish": "true" # and I'm not allowed to use a PYTHON TRUE HERE
			},
			files={
				"file": (self.title, self.content, 'text/html') # this was so much work
			}
		)
		answer = json.loads(answer_raw.text)
		print(answer)
		if answer["ok"] == False:
			raise Exception(f"Error uploading file!\n{answer['status']}: {answer['message']}")
		self.id = answer["data"]["id"]
		self.content = answer["data"]["text"]
		return


# Class to help import a Confluence space as an Outline collection
class ConfluenceSpace:
	def __init__(self, shortname):
		self.shortname = shortname
		# Default description
		#self.description = {
		#	"type": "doc",
		#	"content": [
		#		{
		#			"type": "paragraph",
		#			"content": [
		#				{
		#					"text": f"Imported with Cuckoo Importer v{__version__}",
		#					"type": "text"
		#				}
		#			]
		#		},
		#		{
		#			"type": "paragraph",
		#			"content": [
		#				{
		#					"text": "© Sascha Bacher",
		#					"type": "text"
		#				}
		#			]
	#			}
	#		]
	#	}

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
		#print(self.name)

		page_tree = space_index.find("ul")
		pages = page_tree.find_all("li", recursive=False)
		self.process_home = home_is_description
		self.process_pages(pages)
		self.export_import()

	def create_collection(self):
		answer = call_json_endpoint("collections.create", {
			"name": self.name,
			"description": f"Imported with Cuckoo Importer v{__version__}\n\n© Sascha Bacher",
			"permission": None,
			"sharing": False
		})
		self.id = answer["id"]
		self.description = answer["description"]

	# Iterates recursively over the document tree, creating pages as it progresses
	def process_pages(self, pages, parent = None):
		for page in pages:
			document_name = page.a['href']
			document_title = page.a.string
			print(f"Processing \"{document_title}\", parent: {parent}, internal name: {document_name} ...")

			document_id = ConfluenceDocument(document_title, document_name, self, parent).handle(self.process_home)
			if self.process_home and not document_id:
				self.process_home = False
			self.documents[document_name] = document_id
			#return #TODO for debugging purposes, stop after 1 document. Disable in prod.

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

		answer = call_json_endpoint("collections.export", {"format": "json",
			"id": self.id, "includeAttachments": True})
		file_op = answer["fileOperation"]
		file_id = file_op["id"]
		while not file_op["state"] == "complete":
			file_op = call_json_endpoint("fileOperations.info", {"id": file_id})
			time.sleep(2)

		# The documentation tried to sell me this as a POST request...
		os.system(f'wget --header="Content-Type: application/json" --header="Authorization: {auth}" -O {os.getenv("OUTLINE_TMP")}/{self.shortname}-raw.zip {os.getenv("OUTLINE_API")}/fileOperations.redirect?id={file_id}')

		with zipfile.ZipFile(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}-raw.zip", "r") as zip_ref:
			zip_ref.extractall(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}")
		self.json = open(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}/{self.name}.json", "r").read()

		# We have the file, so we delete it from the server as to not pollute it
		answer = call_json_endpoint("fileOperations.delete", {"id": file_id})

		# Then we delete the collection
		answer = call_json_endpoint("collections.delete", {"id": self.id})

		# We work our magic...
		self.praise_the_whale()

		# ...zip the file again...
		os.system(f"cd {os.getenv('OUTLINE_TMP')}/{self.shortname} && zip -r {os.getenv('OUTLINE_TMP')}/{self.shortname}.zip .")

		# ...and reimport the collection
		import_file_id = attach(f"{os.getenv('OUTLINE_TMP')}/{self.shortname}.zip", None, "workspaceImport")
		answer = call_json_endpoint("collections.import", {"attachmentId": import_file_id, "format": "json", "permission": None, "sharing": False})

	#TODO add praise
	def praise_the_whale(self):
		self.json = self.json.replace(r'⟨i⟩⟨/i⟩', '')
		self.json = self.json.replace(r'⟨b⟩⟨/b⟩', '')
		for doc_name, doc_id in self.documents.items():
			self.json = self.json.replace(r'⟨doc('+doc_name+')⟩', r'⟨doc('+doc_id+')⟩')
		print(self.json[:20])
		# to replace 1 string with multiple:
		# - determine position
		# - split by tag
		# - prepare new slice
		# - replace with last slice element
		# - insert slice elements at position in reverse order
		self.json = praise_the_whale(self.json)
		open(f"{os.getenv('CONFLUENCE_TMP')}/{self.shortname}/{self.name}.json", 'w').write(self.json)

# note: collections.update - id,permission (read/read_write/null/admin)
#			 collections.add_user for specific user, same scheme + userId -> we should add at least one admin to each collection!
#		collections.add_group for groups (like admins), same scheme + groupId
#			 ACL list for spaces (with shortname)? possibly via groups

# Step 1: Extract all requested space exports to temporary location
#		 Now, every space resides in a folder. The folder name matches the space's shortname
# Step 2: For each space, create a ConfluenceSpace object
# Step 3: Invoke the necessary method(s) for import
# Step 4: Profit
# Clear tmp directories
os.system(f"rm -r {os.getenv('CONFLUENCE_TMP')}")
os.system(f"rm -r {os.getenv('OUTLINE_TMP')}")
os.system(f"mkdir {os.getenv('OUTLINE_TMP')}")
space_zips = sys.argv[1:]
for zip_file in space_zips:
	open_zip(zip_file)
spaces = os.listdir(os.getenv('CONFLUENCE_TMP'))
for space in spaces:
	ConfluenceSpace(space).import_space(HOME_IS_DESCRIPTION)

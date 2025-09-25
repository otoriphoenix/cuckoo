from convert_html import html_to_json

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
		self.preprocess_html()
		self.convert_html()
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

	# For the nasty html best replaced before parsing
	def preprocess_html(self):
		self.content = self.content.replace("\n", "")
		self.content = self.content.replace(r"<p><br></p>", "")
		self.content = self.content.replace(r"<p></p>", "<br>")
		self.content = self.content.replace(u'\xa0', ' ')
		self.content = self.content.replace('&nsbp;', ' ')

	def convert_html(self):
		self.content, self.attachments = html_to_json(self.content)

	# Not much done here, as too much gets fucked up by tables
	def postprocess(self):
		# Fixes erroneously generated formatting
		self.content = self.content.replace(r"!!", r"\!\!")

		# Get attachment ids into document
		for attach_name, attach_id in self.attachments.items():
			self.content = self.content.replace("⟨image(" + attach_name + ")/⟩", "⟨image(" + attach_id + ")/⟩")
			self.content = self.content.replace("⟨file(" + attach_name + ")⟩", "⟨file(" + attach_id + ")⟩")

		call_json_endpoint("documents.update", {"id": self.id, "text": self.content})
		return


	# Sets the content of the document as the description of the collection
	# Deletes the document afterwards
	def make_space_description(self):
		# We first set the space description to the same markdown we got from importing the document
		call_json_endpoint("collections.update", {"id": self.collection.id, "description": self.content})

		# Afterwards, we destroy the created document
		call_json_endpoint("documents.delete", {"id": self.id})

		# Finally, we have this reflect in the ID
		self.id = None

	# Creates a document with the given title.
	# This does not get the content in place yet!
	def fake_upload(self):
		pass

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

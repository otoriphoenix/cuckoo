import requests
import os
import json
import magic

# Wraps common API calls
# POST request to an endpoint expecting JSON. Most common call with this API.
def json_endpoint(endpoint, json_data):
	auth = f"Bearer {os.getenv('API_TOKEN')}"
	answer_raw = None
	while not answer_raw:
		answer_raw = requests.post(f"{os.getenv('OUTLINE_API')}/{endpoint}",
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
# Returns the file's ID
def attach(filepath, document_id = None, preset = None):
	auth = f"Bearer {os.getenv('API_TOKEN')}"
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

	answer = json_endpoint("attachments.create", upload_meta)
	file_id = answer["attachment"]["id"]
	attachment_meta = answer["form"]
	answer_raw = requests.post(f"{os.getenv('OUTLINE_API')}/files.create",
		headers={"Authorization": auth},
		data=attachment_meta,
		files={"file": (filename, open(filepath, "rb"), mime)})

	answer = json.loads(answer_raw.text)
	#print(answer)
	if answer["ok"] == False:
		if answer_raw.status_code == 429:
			print(answer_raw.headers['Retry-After'])
		raise Exception(f"Error uploading attachment!\n{answer['status']}: {answer['message']}")
	return file_id, filesize

# Downloads a file from a file operation.
# Returns the file content as bytes
def fetch_file(file_id):
	auth = f"Bearer {os.getenv('API_TOKEN')}"
	# The documentation tried to sell me this as a POST request...
	file = requests.get(f'{os.getenv("OUTLINE_API")}/fileOperations.redirect?id={file_id}',
		headers={
			"Authorization": auth,
			"Content-Type": "application/json"
		}, allow_redirects=True
	)
	if file.status_code != 200:
		raise Exception(f"Error downloading file!\n{file.status_code}")
	return file.content

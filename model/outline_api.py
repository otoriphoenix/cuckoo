import os
import requests
from magic import from_file

from dotenv import load_dotenv

load_dotenv()


def _get_url(endpoint: str) -> str:
    return f"{os.getenv('OUTLINE_API')}/{endpoint}"


def _get_auth():
    return f"Bearer {os.getenv('API_TOKEN')}"


def _is_ok_else_throw(endpoint: str, response_json: dict):
    if not response_json["ok"]:
        raise Exception(
            f"Error calling {endpoint}!\n{response_json['status']}: {response_json['message']}"
        )


def delete_collection(collection_id: str):
    headers = {"Authorization": _get_auth(), "Content-Type": "application/json"}
    json_data = {"id": collection_id}
    response = requests.post(
        _get_url("collections.delete"), headers=headers, json=json_data
    )
    response_json = response.json()
    _is_ok_else_throw("collections.delete", response_json)


def export_collection(collection_id: str) -> tuple[str, str]:
    headers = {"Authorization": _get_auth(), "Content-Type": "application/json"}
    json_data = {"format": "json", "id": collection_id, "includeAttachments": True}
    response = requests.post(
        _get_url("collections.export"), headers=headers, json=json_data
    )
    response_json = response.json()
    _is_ok_else_throw("collections.export", response_json)
    file_operation = response_json["data"]["fileOperation"]
    return file_operation["id"], file_operation["state"]


def create_collection(name: str) -> str:
    headers = {"Authorization": _get_auth(), "Content-Type": "application/json"}
    json_data = {
        "name": name,
        "description": f"Imported with Cuckoo Importer v1.0.0\n\n© Sascha Bacher",
        "permission": None,
        "sharing": False,
    }
    response = requests.post(
        _get_url("collections.create"), headers=headers, json=json_data
    )
    response_json = response.json()
    _is_ok_else_throw("collections.create", response_json)
    return response_json["data"]["id"]


def import_collection(attachment_id: str):
    headers = {"Authorization": _get_auth(), "Content-Type": "application/json"}
    json_data = {
        "attachmentId": attachment_id,
        "format": "json",
        "permission": None,
        "sharing": False,
    }
    response = requests.post(
        _get_url("collections.import"), headers=headers, json=json_data
    )
    response_json = response.json()
    _is_ok_else_throw("collections.import", response_json)


def create_file(filename, filepath, mime, form_data):
    headers = {"Authorization": _get_auth()}
    response = requests.post(
        _get_url("files.create"),
        headers=headers,
        data=form_data,
        files={"file": (filename, open(filepath, "rb"), mime)},
    )
    response_json = response.json()
    _is_ok_else_throw("files.create", response_json)


def get_file_operation_state(file_id: str) -> str:
    headers = {"Authorization": _get_auth(), "Content-Type": "application/json"}
    json_data = {"id": file_id}
    response = requests.post(
        _get_url("fileOperations.info"), headers=headers, json=json_data
    )
    response_json = response.json()
    _is_ok_else_throw("fileOperations.info", response_json)
    return response_json["data"]["state"]


def fetch_file(file_id: str):
    # The documentation tried to sell me this as a POST request...
    headers = {"Authorization": _get_auth(), "Content-Type": "application/json"}
    file = requests.get(
        _get_url(f"fileOperations.redirect?id={file_id}"),
        headers=headers,
        allow_redirects=True,
    )
    if file.status_code != 200:
        raise Exception(f"Error downloading file!\n{file.status_code}")
    return file.content


def delete_document(doc_id):
    headers = {"Authorization": _get_auth(), "Content-Type": "application/json"}
    json_data = {"id": doc_id}
    response = requests.post(
        _get_url("documents.delete"), headers=headers, json=json_data
    )
    response_json = response.json()
    _is_ok_else_throw("documents.delete", response_json)


def delete_file(file_id: str):
    headers = {"Authorization": _get_auth(), "Content-Type": "application/json"}
    json_data = {"id": file_id}
    response = requests.post(
        _get_url("fileOperations.delete"), headers=headers, json=json_data
    )
    response_json = response.json()
    _is_ok_else_throw("fileOperations.delete", response_json)


def create_attachment(filename, filesize, mime, **kwargs):
    headers = {"Authorization": _get_auth(), "Content-Type": "application/json"}
    json_data = {
        "name": filename,
        "contentType": mime,
        "size": filesize,
    }
    if "preset" in kwargs.keys():
        json_data["preset"] = kwargs["preset"]

    if "document_id" in kwargs.keys():
        json_data["documentId"] = kwargs["document_id"]

    response = requests.post(
        _get_url("attachments.create"), headers=headers, json=json_data
    )
    response_json = response.json()
    _is_ok_else_throw("attachments.create", response_json)
    return response_json["data"]["attachment"]["id"], response_json["data"]["form"]


def attach_workspace_import(filepath):
    filename = filepath.split("/")[-1]
    mime = from_file(filepath, mime=True)
    filesize = os.path.getsize(filepath)
    file_id, attachment_meta = create_attachment(
        filename, filesize, mime, preset="workspaceImport"
    )
    create_file(filename, filepath, mime, attachment_meta)
    return file_id, filesize


def attach_file(filepath, doc_id):
    filename = filepath.split("/")[-1]
    mime = from_file(filepath, mime=True)
    filesize = os.path.getsize(filepath)
    file_id, attachment_meta = create_attachment(
        filename, filesize, mime, preset="documentAttachment", document_id=doc_id
    )
    create_file(filename, filepath, mime, attachment_meta)
    return file_id, filesize


def import_document(filename, content, parent_id, collection_id):
    headers = {"Authorization": _get_auth()}
    form_data = {
        "name": filename,
        "parentDocumentId": parent_id,
        "collectionId": collection_id,
        "publish": "true",
    }
    response = requests.post(
        _get_url("documents.import"),
        headers=headers,
        data=form_data,
        files={"file": (filename, content, "text/html")},
    )
    response_json = response.json()
    _is_ok_else_throw("documents.import", response_json)
    return response_json["data"]["id"]

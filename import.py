import zipfile
import os
import sys
import shutil
import json
from dotenv import load_dotenv
from confluence_space import ConfluenceSpace

load_dotenv()
HOME_IS_DESCRIPTION = (os.getenv('HOME_IS_DESCRIPTION', 'False') == 'True')
# To make sure Outline can read this, we put auth into a variable first
auth = f"Bearer {os.getenv('API_TOKEN')}"

# Load the already known user list. Currently, this is maintained manually.
users = {}
if os.getenv('USER_MAPPING') != '':
	with open(os.getenv('USER_MAPPING'), "r") as user_map:
		users = user_map.read()
	users = json.loads(users)

# Clear tmp directories
os.system(f"rm -r {os.getenv('CONFLUENCE_TMP')}")
os.system(f"rm -r {os.getenv('OUTLINE_TMP')}")
os.system(f"mkdir {os.getenv('OUTLINE_TMP')}")
# Step 1: Extract all requested space exports to temporary location
#		 Now, every space resides in a folder. The folder name matches the space's shortname
# Step 2: For each space, create a ConfluenceSpace object
# Step 3: Invoke the necessary method(s) for import
# Step 4: Profit
space_zips = sys.argv[1:]
for zip_file in space_zips:
	with zipfile.ZipFile(zip_file, "r") as zip_ref:
		zip_ref.extractall(os.getenv('CONFLUENCE_TMP'))
spaces = os.listdir(os.getenv('CONFLUENCE_TMP'))
for space in spaces:
	ConfluenceSpace(space, users).import_space(HOME_IS_DESCRIPTION)

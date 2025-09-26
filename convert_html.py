import re
from bs4 import BeautifulSoup, NavigableString
from jsonpointer import resolve_pointer
import jsonpatch
from minify_html import minify

# The magic needed to translate the HTML output of a standard Confluence instance (Data Center license)
# into Outline's JSON format.

text_type_nodes = ["text", "br", "mention"]

def checklist_predicate(tag):
	return tag and tag.name == 'ul' and 'data-inline-tasks-content-id' in tag.attrs

def task_item_predicate(tag):
	return tag and tag.name == 'li' and 'data-inline-task-id' in tag.attrs

def wrapper_tag_predicate(tag):
	return tag and tag.name in ['div', 'span', 'time', 'tbody']

# Tags that fuck up any given import
# Includes the following:
# - The profile-full tables to resolve display issues
#   These are empty anyways, so it's fine
# - profile picture for vcards - not really necessary to display
#   They're more of eye candy than important content
# - Certain divs
def bad_tag_predicate(tag):
	if not tag:
		return False

	if tag.name == 'input':
		return True

	bad_tags = {
		"span": ["aui-avatar"],
		"div": ["update-item-icon", "update-item-profile", "more-link-container"],
		"table": ["profile-full"],
	}
	if not tag.name in bad_tags.keys():
		return False

	if not 'class' in tag.attrs:
		return False
	for clazz in bad_tags[tag.name]:
		if clazz in tag['class']:
			return True
	return False

# Removes superflous HTML, translates some tag names and gives us a dict of attachments
def clean_html(soup):
	attachments = {}
	# Extracts the attachment list for further processing
	attached = soup.find(id="attachments")
	if attached:
		attached = attached.parent.parent.extract()
		#print(attached)
		attached = attached.find(class_="greybox")
		attached = attached.find_all("a")

		for attachment in attached:
			key = attachment["href"].split("/")[-1]
			attachments[key] = ""
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

	bad_tags = soup.find_all(bad_tag_predicate)
	for bad_tag in bad_tags:
		bad_tag.decompose()

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
	emojis = soup.find_all(class_="emoticon")
	for emoji in emojis:
		emoji.replace_with(chr(int(emoji["data-emoji-id"], 16)))

	# Recent space activity fix
	activity = soup.find('div', class_='recently-updated recently-updated-social')
	if activity:
		updates = soup.find_all('ul', class_='update-items')
		for update in updates:
			person = update.div.extract()
			update.insert_before(person)

	# Translate certain tag patterns to tag names
	tag_translation = {
		"div": {
			"confluence-information-macro-information": "c_info",
			"confluence-information-macro-tip": "c_tip",
			"confluence-information-macro-note": "c_success",
			"confluence-information-macro-warning": "c_warning",
		},
		"a": {
			"confluence-userlink": "user_mention",
		}
	}
	for tag_name, translation in tag_translation.items():
		for clazz, translated_name in translation.items():
			raw_tags = soup.find_all(name=tag_name, class_=clazz)
			for raw_tag in raw_tags:
				raw_tag.name = translated_name

	# Translate checklists + checklist items
	tasks = soup.find_all(task_item_predicate)
	for task in tasks:
		task.name = 'checkbox_item'

	tasklists = soup.find_all(checklist_predicate)
	for l in tasklists:
		l.name = 'checkbox_list'

	# Unwrap wrapper tags. Done at the end to avoid issues with other tags.
	wrappers = soup.find_all(wrapper_tag_predicate)
	for wrapper in wrappers:
		wrapper.unwrap()
		wrapper.smooth()

	# We need the attachments later, so let's pass them to the rest
	return attachments

def create_json(tag):
	# Just in case
	if not tag:
		return None

	if type(tag) is NavigableString:
		if tag.string == '':
			return None
		return {"type": "text", "text": tag.string}

	# This only handles text links properly, and doesn't apply inner formatting
	# That is intentional - Outline can't handle images as link "text", and changing the appearance of a link isn't that important
	if tag.name == 'a':
		# If there's no schema given, no slashes in th url and it ends in .html (before an anchor), assume local document link
		if 'href' in tag.attrs and not ':' in tag['href'] and not '/' in tag['href'] and '.html' in tag['href']:
			slug, _, anchor = tag['href'].partition('.html')
			slug = slug.split("_")[-1]
			return {"type": "mention", "attrs": {"type": "document", "modelId": slug + anchor, "label": tag.get_text()}}
		return {"type": "text", "marks": [{"type": "link", "attrs": {"href": tag['href'].strip()}}], "text": tag.get_text(strip=True)}

	if tag.name == 'user_mention':
		return {"type": "mention", "attrs": {"type": "user", "modelId": tag["data-username"], "label": tag.get_text()}}

	contents = []
	simple_type_map = {
		'body': 'doc',
		'p': 'paragraph',
		'li': 'list_item',
		'h1': 'heading',
		'h2': 'heading',
		'h3': 'heading',
		'h4': 'heading',
		'li': 'list_item',
		'ul': 'bullet_list',
		'ol': 'ordered_list',
		'button': 'paragraph', # Buttons wouldn't work so we make them a paragraph
		'b': 'strong',
		'i': 'em',
		'c_info': 'container_notice',
		'c_tip': 'container_notice',
		'c_warning': 'container_notice',
		'c_success': 'container_notice',
		'pre': 'code_fence',
		'img': 'image',
		'code': 'code_inline',
	}

	tag_type = simple_type_map[tag.name] if tag.name in simple_type_map.keys() else tag.name
	parsed = {"type": tag_type}
	attrs = {}

	if tag_type == 'image':
		attrs["src"] = tag['src']
		attrs["alt"] = tag['alt'] if 'alt' in tag.attrs and tag['alt'] != '' else None
		attrs["width"] = int(tag['width']) if 'width' in tag.attrs else 250
		attrs["height"] = int(tag['height']) if 'height' in tag.attrs else 250

	if tag_type == 'heading':
		attrs['level'] = int(tag.name[1])

	if tag_type  == 'container_notice':
		attrs['style'] = tag.name[2:]

	if tag_type in ['th', 'td']:
		attrs['colspan'] = int(tag['colspan']) if 'colspan' in tag.attrs else 1
		attrs['rowspan'] = int(tag['rowspan']) if 'rowspan' in tag.attrs else 1

		# Known issue: This will set alignment to the first specified one, not the last.
		# Since this HTML is generated by Confluence, we assume it not to set two different alignments
		# on the same table cell
		if 'style' in tag.attrs:
			align = re.match(r'text-align: ([a-zA-Z]+);', tag['style'])
			if align.group(1):
				align = align.group(1)
			else:
				align = None
		else:
			align = None # Set default null/None
		attrs['alignment'] = align

	for child in tag.children:
		child_json = create_json(child)
		if child_json:
			contents.append(child_json)

	if tag_type == 'paragraph' and len(contents) == 0:
		return None

	if tag_type == 'checkbox_item':
		attrs["checked"] = ("class" in tag.attrs and "checked" in tag['class'])

	if len(attrs.keys()) > 0:
		parsed.update({"attrs": attrs})
	if len(contents) > 0:
		parsed.update({"content": contents})
	return parsed

# Merges text leaves with equal formatting
# This is more of eye candy in the JSON than an actual requirement
# Returns a list of patches to be applied to the JSON. The patches must be applied separately.
# Otherwise, you get indexing problems
def merge_textleaves(json, path, bulk_patch):
	node = resolve_pointer(json, path)
	if not 'content' in node:
		return bulk_patch

	for i, _ in enumerate(node['content']):
		bulk_patch = merge_textleaves(json, path + f'/content/{i}', bulk_patch)

	children = []
	pointer = 0
	if has_textleaf(node['content']):
		for i, child in enumerate(node['content']):
			if not child['type']  == 'text':
				children.append(child)
				pointer += 2 # We need to skip the newly appended since it's not a text node
			else:
				# Empty text nodes are not allowed, so we remove them
				if child["text"] == '':
					continue
				# len is guaranteed to be >= to the pointer value if I wrote this correctly
				if len(children) <= pointer:
					children.append(child)
				elif equal_marks(child, children[pointer]):
					children[pointer]['text'] += child['text']
				else:
					children.append(child)
					pointer += 1
		bulk_patch.append({"op": 'replace', 'path': path + f"/content", 'value': children})
	return bulk_patch

def equal_marks(textleaf_1, textleaf_2):
	if not (('marks' in textleaf_1) == ('marks' in textleaf_2)):

		return False

	if 'marks' in textleaf_1:
		return textleaf_1['marks'] == textleaf_2['marks']
	return True

def unwrap_marked_text(json, path):
	node = resolve_pointer(json, path)
	if not 'content' in node:
		return

	if node['type'] in ['strong', 'em', 'code_inline']:
		mark_type = node['type']
		children = node['content']
		for child in children:
			marks = child['marks'] if 'marks' in child else []
			marks += [{'type': mark_type}]
			child.update({"marks": marks})
		expand_into_json_list(json, path, children)
		for i, _ in enumerate(node['content']):
			unwrap_marked_text(json, path)
		return

	for i, _ in enumerate(node['content']):
		unwrap_marked_text(json, path + f'/content/{i}')

def has_textleaf(node_content):
	for child in node_content:
		if child['type'] in text_type_nodes:
			return True
	return False

# Wraps text leaves in paragraphs
# Done since the JSON created by Outline only contains text leaves inside a heading or paragraph,
# and we don't want to cause the import to fail
# Returns a list of patches to be applied to the JSON. The patches must be applied separately.
# Otherwise, you get indexing problems
def wrap_textleaves(json, path, bulk_patch):
	node = resolve_pointer(json, path)
	if node['type'] in ['heading', 'paragraph'] or not 'content' in node:
		return bulk_patch

	for i, _ in enumerate(node['content']):
		bulk_patch = wrap_textleaves(json, path + f'/content/{i}', bulk_patch)

	children = []
	pointer = 0
	if has_textleaf(node['content']):
		for i, child in enumerate(node['content']):
			if not child['type'] in text_type_nodes:
				children.append(child)
				pointer += 1
			else:
				# len is guaranteed to be >= to the pointer value if I wrote this correctly
				if len(children) == pointer:
					children.append({'type': 'paragraph', 'content': []})
				children[pointer]['content'].append(child)
		bulk_patch.append({"op": 'replace', 'path': path + f"/content", 'value': children})
	return bulk_patch

# Replaces an element in a JSON list with n new elements.
def expand_into_json_list(json, path, new_elements):
	if len(new_elements) == 0:
		return

	new_elements = [{"op": 'add', 'path': path, 'value': element} for element in new_elements]

	new_elements[-1].update({"op": 'replace'})
	jsonpatch.apply_patch(json, new_elements[::-1], in_place=True)

def html_to_json(html_content):
	html_content = minify(html_content)
	soup = BeautifulSoup(html_content, 'lxml')
	attachments = clean_html(soup)
	json = create_json(soup.find('body'))
	unwrap_marked_text(json, '')
	bulk_patch = merge_textleaves(json, '', [])
	jsonpatch.apply_patch(json, bulk_patch, in_place=True)
	bulk_patch = wrap_textleaves(json, '', [])
	jsonpatch.apply_patch(json, bulk_patch, in_place=True)
	return json, attachments

import json
import re
from jsonpointer import resolve_pointer
import jsonpointer
import jsonpatch
import copy

# Done so we can handle link break links properly
def convert_to_text(children):
	content = ''
	for child in children:
		if child['type'] == 'br':
			content += '⟨br/⟩'
		else:
			content += child['text']
	return content

# thanks https://stackoverflow.com/questions/32796425/python-partition-string-with-regular-expressions
def re_partition(pattern, string):
	'''Function akin to partition() but supporting a regex
	:param pattern: regex used to partition the content
	:param content: string being partitioned
	'''

	matchm = re.search(pattern, string)

	if not matchm:
		return string, None, None

	return string[:matchm.start()], matchm, string[matchm.end():]

def convert_a(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']


	middle_tmpl = copy.deepcopy(json)
	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨a\((?P<link>.*?)\)⟩(?P<content>.*?)⟨/a⟩', json["text"])

	children = []
	if middle:
		middle_marks = default_marks + [{'type': 'link', 'attrs': {'href': middle.group('link')}}]
		json.update({'text': pre})
		middle_tmpl.update({'text': middle.group('content'), "marks": middle_marks})
		children.append(json)
		children.append(middle_tmpl)
		while post:
			pre, middle, post = re_partition(r'⟨a\((?P<link>.*?)\)⟩(?P<content>.*?)⟨/a⟩', post)
			if not middle:
				pre_tmpl = copy.deepcopy(json)
				pre_tmpl.update({'text': pre})
				children.append(pre_tmpl)
				break
			pre_tmpl = copy.deepcopy(json)
			middle_tmpl = copy.deepcopy(json)
			middle_marks = default_marks + [{'type': 'link', 'attrs': {'href': middle.group('link')}}]
			pre_tmpl.update({'text': pre})
			middle_tmpl.update({'text': middle.group('content'), "marks": middle_marks})
			children.append(pre_tmpl)
			children.append(middle_tmpl)

	if (len(children) == 0):
		children = [json]
		
	return children

def convert_images(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨image\((?P<link>.*?)\)/⟩', json["text"])
	middle_tmpl = copy.deepcopy(json)

	children = []
	if middle:
		json.update({'text': pre})
		middle_tmpl.update({'type': 'image', 'attrs': {'src': '/api/attachments.redirect?id=' + middle.group('link'), 'width': 250, 'height': 250}})
		children.append(json)
		children.append(middle_tmpl)
		while post:
			pre, middle, post = re_partition(r'⟨image\((?P<link>.*?)\)(?P<height>\(\d+\))?/⟩', post)
			if not middle:
				pre_tmpl = copy.deepcopy(json)
				pre_tmpl.update({'text': pre})
				children.append(pre_tmpl)
				break
			pre_tmpl = copy.deepcopy(json)
			middle_tmpl = copy.deepcopy({'type': 'image', 'attrs': {'src': '/api/attachments.redirect?id=' + middle.group('link'), 'width': 250, 'height': 250}})
			pre_tmpl.update({'text': pre})
			children.append(pre_tmpl)
			children.append(middle_tmpl)

	if (len(children) == 0):
		children = [json]
		
	return children

def convert_files(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	post = json['text']
	children = []
	while post:
		pre, middle, post = re_partition(r'⟨file\((?P<link>.*?)\)⟩⟨/file⟩', post)
		if not middle:
			pre_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			children.append(pre_tmpl)
			break
		pre_tmpl = copy.deepcopy(json)
		middle_tmpl = copy.deepcopy({'type': 'attachment', 'attrs': {'href': '/api/attachments.redirect?id=' + middle.group('link')}})
		#middle_marks = default_marks #[{'type': 'image', 'attrs': {'src': '/api/attachments.redirect?id=' + middle.group('link')}}]
		pre_tmpl.update({'text': pre})
		children.append(pre_tmpl)
		children.append(middle_tmpl)

	if (len(children) == 0):
		children = [json]
		
	return children

def convert_heading(json, level):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	middle_marks = default_marks

	middle_tmpl = copy.deepcopy(json)
	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨h'+level+'⟩(?P<content>.*?)⟨/h'+level+'⟩', json["text"])

	children = []
	if middle:
		json.update({'text': pre})
		middle_tmpl.update({'text': middle.group('content')})
		children.append(json)
		children.append({'type': 'heading', "attrs":{"level":level}, 'content': [middle_tmpl]})
		print(middle.group('content'))
		while post:
			pre, middle, post = re_partition(r'⟨h'+level+'⟩(?P<content>.*?)⟨/h'+level+'⟩', post)
			if not middle:
				pre_tmpl = copy.deepcopy(json)
				pre_tmpl.update({'text': pre})
				children.append(pre_tmpl)
				break
			pre_tmpl = copy.deepcopy(json)
			middle_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			middle_tmpl.update({'text': middle.group('content')})
			children.append(pre_tmpl)
			children.append({'type': 'heading', "attrs":{"level":level}, 'content': [middle_tmpl]})

	if (len(children) == 0):
		children = [json]

	pre, middle, post = children[0]['text'].partition(r'⟨/h'+level+'⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': pre})
		children[0].update({'text': post})
		children.insert(0, {'type': 'heading', "attrs":{"level":level}, 'content': [middle_tmpl]})

	pre, middle, post = children[0]['text'].partition(r'⟨h'+level+'⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': post})
		children[0].update({'text': pre})
		children.insert(1, {'type': 'heading', "attrs":{"level":level}, 'content': [middle_tmpl]})
		
	return children

def convert_h1(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	middle_marks = default_marks

	middle_tmpl = copy.deepcopy(json)
	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨h1⟩(?P<content>.*?)⟨/h1⟩', json["text"])

	children = []
	if middle:
		json.update({'text': pre})
		middle_tmpl.update({'text': middle.group('content')})
		children.append(json)
		children.append({'type': 'heading', "attrs":{"level":1}, 'content': [middle_tmpl]})
		print(middle.group('content'))
		while post:
			pre, middle, post = re_partition(r'⟨h1⟩(?P<content>.*?)⟨/h1⟩', post)
			if not middle:
				pre_tmpl = copy.deepcopy(json)
				pre_tmpl.update({'text': pre})
				children.append(pre_tmpl)
				break
			pre_tmpl = copy.deepcopy(json)
			middle_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			middle_tmpl.update({'text': middle.group('content')})
			children.append(pre_tmpl)
			children.append({'type': 'heading', "attrs":{"level":1}, 'content': [middle_tmpl]})

	if (len(children) == 0):
		children = [json]

	pre, middle, post = children[0]['text'].partition(r'⟨/h1⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': pre})
		children[0].update({'text': post})
		children.insert(0, {'type': 'heading', "attrs":{"level":1}, 'content': [middle_tmpl]})

	pre, middle, post = children[0]['text'].partition(r'⟨h1⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': post})
		children[0].update({'text': pre})
		children.insert(1, {'type': 'heading', "attrs":{"level":1}, 'content': [middle_tmpl]})
		
	return children

def convert_h2(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	middle_marks = default_marks

	middle_tmpl = copy.deepcopy(json)
	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨h2⟩(?P<content>.*?)⟨/h2⟩', json["text"])

	children = []
	if middle:
		json.update({'text': pre})
		middle_tmpl.update({'text': middle.group('content')})
		children.append(json)
		children.append({'type': 'heading', "attrs":{"level":2}, 'content': [middle_tmpl]})
		print(middle.group('content'))
		while post:
			pre, middle, post = re_partition(r'⟨h2⟩(?P<content>.*?)⟨/h2⟩', post)
			if not middle:
				pre_tmpl = copy.deepcopy(json)
				pre_tmpl.update({'text': pre})
				children.append(pre_tmpl)
				break
			pre_tmpl = copy.deepcopy(json)
			middle_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			middle_tmpl.update({'text': middle.group('content')})
			children.append(pre_tmpl)
			children.append({'type': 'heading', "attrs":{"level":2}, 'content': [middle_tmpl]})

	if (len(children) == 0):
		children = [json]

	pre, middle, post = children[0]['text'].partition(r'⟨/h2⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': pre})
		children[0].update({'text': post})
		children.insert(0, {'type': 'heading', "attrs":{"level":2}, 'content': [middle_tmpl]})

	pre, middle, post = children[0]['text'].partition(r'⟨h2⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': post})
		children[0].update({'text': pre})
		children.insert(1, {'type': 'heading', "attrs":{"level":2}, 'content': [middle_tmpl]})
		
	return children

def convert_h3(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	middle_marks = default_marks

	middle_tmpl = copy.deepcopy(json)
	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨h3⟩(?P<content>.*?)⟨/h3⟩', json["text"])

	children = []
	if middle:
		json.update({'text': pre})
		middle_tmpl.update({'text': middle.group('content')})
		children.append(json)
		children.append({'type': 'heading', "attrs":{"level":3}, 'content': [middle_tmpl]})
		print(middle.group('content'))
		while post:
			pre, middle, post = re_partition(r'⟨h3⟩(?P<content>.*?)⟨/h3⟩', post)
			if not middle:
				pre_tmpl = copy.deepcopy(json)
				pre_tmpl.update({'text': pre})
				children.append(pre_tmpl)
				break
			pre_tmpl = copy.deepcopy(json)
			middle_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			middle_tmpl.update({'text': middle.group('content')})
			children.append(pre_tmpl)
			children.append({'type': 'heading', "attrs":{"level":3}, 'content': [middle_tmpl]})

	if (len(children) == 0):
		children = [json]

	pre, middle, post = children[0]['text'].partition(r'⟨/h3⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': pre})
		children[0].update({'text': post})
		children.insert(0, {'type': 'heading', "attrs":{"level":3}, 'content': [middle_tmpl]})

	pre, middle, post = children[0]['text'].partition(r'⟨h3⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': post})
		children[0].update({'text': pre})
		children.insert(1, {'type': 'heading', "attrs":{"level":3}, 'content': [middle_tmpl]})
		
	return children

def convert_h4(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	middle_marks = default_marks

	middle_tmpl = copy.deepcopy(json)
	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨h4⟩(?P<content>.*?)⟨/h4⟩', json["text"])

	children = []
	if middle:
		json.update({'text': pre})
		middle_tmpl.update({'text': middle.group('content')})
		children.append(json)
		children.append({'type': 'heading', "attrs":{"level":4}, 'content': [middle_tmpl]})
		print(middle.group('content'))
		while post:
			pre, middle, post = re_partition(r'⟨h4⟩(?P<content>.*?)⟨/h4⟩', post)
			if not middle:
				pre_tmpl = copy.deepcopy(json)
				pre_tmpl.update({'text': pre})
				children.append(pre_tmpl)
				break
			pre_tmpl = copy.deepcopy(json)
			middle_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			middle_tmpl.update({'text': middle.group('content')})
			children.append(pre_tmpl)
			children.append({'type': 'heading', "attrs":{"level":4}, 'content': [middle_tmpl]})

	if (len(children) == 0):
		children = [json]

	pre, middle, post = children[0]['text'].partition(r'⟨/h4⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': pre})
		children[0].update({'text': post})
		children.insert(0, {'type': 'heading', "attrs":{"level":4}, 'content': [middle_tmpl]})

	pre, middle, post = children[0]['text'].partition(r'⟨h4⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': post})
		children[0].update({'text': pre})
		children.insert(1, {'type': 'heading', "attrs":{"level":4}, 'content': [middle_tmpl]})
		
	return children

def convert_b(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	middle_marks = default_marks + [{'type': 'strong'}]

	middle_tmpl = copy.deepcopy(json)
	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨b⟩(?P<content>.*?)⟨/b⟩', json["text"])

	children = []
	if middle:
		json.update({'text': pre})
		middle_tmpl.update({'text': middle.group('content'), "marks": middle_marks})
		children.append(json)
		children.append(middle_tmpl)
		while post:
			pre, middle, post = re_partition(r'⟨b⟩(?P<content>.*?)⟨/b⟩', post)
			if not middle:
				pre_tmpl = copy.deepcopy(json)
				pre_tmpl.update({'text': pre})
				children.append(pre_tmpl)
				break
			pre_tmpl = copy.deepcopy(json)
			middle_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			middle_tmpl.update({'text': middle.group('content'), "marks": middle_marks})
			children.append(pre_tmpl)
			children.append(middle_tmpl)

	if (len(children) == 0):
		children = [json]

	pre, middle, post = children[0]['text'].partition(r'⟨/b⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': pre, "marks": middle_marks})
		children[0].update({'text': post})
		children.insert(0, middle_tmpl)

	pre, middle, post = children[0]['text'].partition(r'⟨b⟩')
	if middle != '':
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': post, "marks": middle_marks})
		children[0].update({'text': pre})
		children.insert(1, middle_tmpl)
		
	return children

def convert_i(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	middle_marks = default_marks + [{'type': 'em'}]

	middle_tmpl = copy.deepcopy(json)
	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨i⟩(?P<content>.*?)⟨/i⟩', json["text"])

	children = []
	if middle:
		json.update({'text': pre})
		middle_tmpl.update({'text': middle.group('content'), "marks": middle_marks})
		children.append(json)
		children.append(middle_tmpl)
		while post:
			pre, middle, post = re_partition(r'⟨i⟩(?P<content>.*?)⟨/i⟩', post)
			if not middle:
				pre_tmpl = copy.deepcopy(json)
				pre_tmpl.update({'text': pre})
				children.append(pre_tmpl)
				break
			pre_tmpl = copy.deepcopy(json)
			middle_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			middle_tmpl.update({'text': middle.group('content'), "marks": middle_marks})
			children.append(pre_tmpl)
			children.append(middle_tmpl)

	if (len(children) == 0):
		children = [json]

	pre, middle, post = re_partition(r'⟨/i⟩', children[0]['text'])
	if middle:
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': pre, "marks": middle_marks})
		children[0].update({'text': post})
		children.insert(0, middle_tmpl)

	pre, middle, post = re_partition(r'⟨i⟩', children[0]['text'])
	if middle:
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': post, "marks": middle_marks})
		children[0].update({'text': pre})
		children.insert(1, middle_tmpl)
		
	return children

#{"type":"checkbox_list","content":[{"type":"checkbox_item","attrs":{"checked":false},"content":[{"type":"paragraph","

def convert_task_list(json):
	if json['type'] != 'text': return [json]

	#default_marks = []
	#if 'marks' in json:
	#	default_marks = json['marks']
	#
	#middle_marks = default_marks
#
#	post = json['text']
#	children = []
#	tasklist = {'type': 'checkbox_list', 'content' : []}
#	tasks = []
#	while post:
	#	pre, middle, post = re_partition(r'⟨(?P<checked>x| )⟩(?P<content>.*?)⟨\/task⟩', post)
	#	if not middle:
	#		pre_tmpl = copy.deepcopy(json)
	#		pre_tmpl.update({'text': pre})
	#		children.append(pre_tmpl)
	#		break
	#	pre_tmpl = copy.deepcopy(json)
	#	middle_tmpl = copy.deepcopy(json)
	#	task = middle.group('content')
		#print(task)
	#	if middle.group('checked') == 'x':
	#		item = {"type":"checkbox_item","attrs":{"checked":True}, 'content': []}
	#	else:
	#		item = {"type":"checkbox_item","attrs":{"checked":False}, 'content': []}
		#task = task[3:-7]
	#	middle_tmpl.update({'text': task})
	#	item.update({'content': [{'type': 'paragraph', 'content': [middle_tmpl]}]})
	#	tasks.append(item)
	#	tasklist = copy.deepcopy({'type': 'checkbox_list', 'content' : tasks)
		
	#	pre_tmpl.update({'text': pre})
	#	children.append(pre_tmpl)
	#	children.append(middle_tmpl)

	#if (len(children) == 0):
	#	children = [json]
	#	
	#return children

	###old method
	#if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	middle_marks = default_marks

	middle_tmpl = copy.deepcopy(json)
	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨tasks⟩(?P<content>.*?)⟨\/tasks⟩', json["text"])
	tasklist = {'type': 'checkbox_list', 'content' : []}
	tasks = []

	children = [json]
	if middle:
		json.update({'text': pre})
		_, middle, post = re_partition(r'⟨(?P<checked>x| )⟩(?P<content>.*?)⟨\/task⟩', middle.group('content'))
		if not middle: return children
		task = middle.group('content')
		#print(task)
		if middle.group('checked') == 'x':
			item = {"type":"checkbox_item","attrs":{"checked":True}, 'content': []}
		else:
			item = {"type":"checkbox_item","attrs":{"checked":False}, 'content': []}
		#task = task[3:-7]
		middle_tmpl.update({'text': task})
		item.update({'content': [{'type': 'paragraph', 'content': [middle_tmpl]}]})
		tasks.append(item)
		tasklist.update({'content': tasks})
		children.append(json)
		while post:
			_, middle, post = re_partition(r'⟨(?P<checked>x| )⟩(?P<content>.*?)⟨\/task⟩', post) # I can leave out pre due to how this is generated during preprocessing
			if not middle: break
			middle_tmpl = copy.deepcopy(json)
			task = middle.group('content')
			#print(task)
			if middle.group('checked') == 'x':
				item = {"type":"checkbox_item","attrs":{"checked":True}, 'content': []}
			else:
				item = {"type":"checkbox_item","attrs":{"checked":False}, 'content': []}
			#task = task[3:-7]
			middle_tmpl.update({'text': task})
			item.update({'content': [{'type': 'paragraph', 'content': [middle_tmpl]}]})
			tasks.append(item)
			tasklist.update({'content': tasks})
		children.append(tasklist)
		
	return children

#{"type":"mention","attrs":{"type":"document","label":"test2_edit","id":"f81e795e-3d71-4a69-96c0-1a1e21e93b16"}}

def convert_docref(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	post = json['text']
	children = []
	while post:
		pre, middle, post = re_partition(r'⟨doc\((?P<link>.*?)\)⟩(?P<content>.*?)⟨/doc⟩', post)
		if not middle:
			pre_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			children.append(pre_tmpl)
			break
		pre_tmpl = copy.deepcopy(json)
		middle_tmpl = copy.deepcopy({'type': 'mention', 'attrs': {'type': 'document', "label": middle.group('content'), 'modelId': middle.group('link')}})
		pre_tmpl.update({'text': pre})
		children.append(pre_tmpl)
		children.append(middle_tmpl)

	if (len(children) == 0):
		children = [json]
		
	return children

def convert_mention(json):
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	post = json['text']
	children = []
	while post:
		pre, middle, post = re_partition(r'⟨mention\((?P<user>.*?)\)⟩(?P<content>.*?)⟨/mention⟩', post)
		if not middle:
			pre_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			children.append(pre_tmpl)
			break
		pre_tmpl = copy.deepcopy(json)
		middle_tmpl = copy.deepcopy({'type': 'mention', 'attrs': {'type': 'user', "label": middle.group('content'), 'modelId': middle.group('user')}})
		pre_tmpl.update({'text': pre})
		children.append(pre_tmpl)
		children.append(middle_tmpl)

	if (len(children) == 0):
		children = [json]
		
	return children

def convert_info(json):
	
	if json['type'] != 'text': return [json]

	default_marks = []
	if 'marks' in json:
		default_marks = json['marks']

	middle_marks = default_marks + [{'type': 'em'}]

	middle_tmpl = copy.deepcopy(json)
	post_tmpl = copy.deepcopy(json)
	pre, middle, post = re_partition(r'⟨info⟩(?P<content>.*?)⟨/info⟩', json["text"])

	children = []
	if middle:
		json.update({'text': pre})
		middle_tmpl.update({'text': middle.group('content'), "marks": middle_marks})
		children.append(json)
		children.append(middle_tmpl)
		while post:
			pre, middle, post = re_partition(r'⟨info⟩(?P<content>.*?)⟨/info⟩', post)
			if not middle:
				pre_tmpl = copy.deepcopy(json)
				pre_tmpl.update({'text': pre})
				children.append(pre_tmpl)
				break
			pre_tmpl = copy.deepcopy(json)
			middle_tmpl = copy.deepcopy(json)
			pre_tmpl.update({'text': pre})
			middle_tmpl.update({'text': middle.group('content'), "marks": middle_marks})
			children.append(pre_tmpl)
			children.append(middle_tmpl)

	if (len(children) == 0):
		children = [json]

	pre, middle, post = re_partition(r'⟨/info⟩', children[0]['text'])
	if middle:
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': pre, "marks": middle_marks})
		children[0].update({'text': post})
		children.insert(0, middle_tmpl)

	pre, middle, post = re_partition(r'⟨info⟩', children[0]['text'])
	if middle:
		middle_tmpl = copy.deepcopy(json)
		middle_tmpl.update({'text': post, "marks": middle_marks})
		children[0].update({'text': pre})
		children.insert(1, middle_tmpl)
		
	return children

def handle_paragraph(node, path, tag_funcs):
	paragraph = resolve_pointer(node, path)
	if not 'content' in paragraph: return []
	#print(paragraph)
	content = paragraph['content']
	#tag_funcs = [convert_task_list, convert_b, convert_i, convert_a]
	for tag_func in tag_funcs:
		for i in range(len(content)):
			content[i] = tag_func(content[i])
		# flatten list
		# thanks https://stackoverflow.com/questions/952914/how-do-i-make-a-flat-list-out-of-a-list-of-lists
		content = [x for xs in content for x in xs]

	content = list(filter(lambda child: child["type"] != 'text' or (child['type'] == 'text' and child['text'] != ''), content)) #[content for child in content if child["type"] != 'text' or (child['type'] == 'text' and child['text'] != '')]
	
	#print(content)
	return content

def extract_special_tags(node):
	if not 'content' in node or node['type'] != 'paragraph':
		return []

	children = [{'type': 'paragraph', 'content': []}]
	pointer = 0
	for child in node['content']:
		if child['type'] == 'heading' or child['type'] == 'checkbox_list':
			children.append(child)
			children.append({'type': 'paragraph', 'content': []})
			pointer += 2
		else:
			children[pointer]['content'].append(child)
	return children

def fix_special_tags(node, path):
	if not "content" in resolve_pointer(node, path):
		return

	children = []
	for i in range(len(resolve_pointer(node, path + '/content'))):
		c = resolve_pointer(node, path + f"/content/{i}")
		if c['type'] == "paragraph":
			children = children + extract_special_tags(c)
		else:
			children.append(c)
	children = list(filter(lambda child: child["type"] != 'paragraph' or (child['type'] == 'paragraph' and child['content'] != []), children))
	jsonpatch.apply_patch(node, [{"op": 'replace', 'path': path + f"/content", 'value': children}], in_place=True)

	for i in range(len(resolve_pointer(node, path + "/content"))):
		fix_special_tags(node, path + f"/content/{i}")

def find_heading(node, path, tag_funcs):
	if not "content" in resolve_pointer(node, path):
		return

	#print(resolve_pointer(node, path + "/type"))
	if resolve_pointer(node, path + "/type") == "heading":
		for i in range(len(resolve_pointer(node, path + "/content"))):
			find_heading(node, path + f"/content/{i}", tag_funcs)
		#print(convert_to_text(resolve_pointer(node, path + "/content")))
		new_content = handle_paragraph(node, path, tag_funcs)
		jsonpointer.set_pointer(node, path + '/content', new_content)
		return node

	for i in range(len(resolve_pointer(node, path + "/content"))):
		find_heading(node, path + f"/content/{i}", tag_funcs)


def find_paragraph(node, path, tag_funcs):
	if not "content" in resolve_pointer(node, path):
		return

	#print(resolve_pointer(node, path + "/type"))
	if resolve_pointer(node, path + "/type") == "paragraph" or resolve_pointer(node, path + "/type") == "heading":
		for i in range(len(resolve_pointer(node, path + "/content"))):
			find_paragraph(node, path + f"/content/{i}", tag_funcs)
		#print(convert_to_text(resolve_pointer(node, path + "/content")))
		new_content = handle_paragraph(node, path, tag_funcs)
		jsonpointer.set_pointer(node, path + '/content', new_content)
		return node

	for i in range(len(resolve_pointer(node, path + "/content"))):
		find_paragraph(node, path + f"/content/{i}", tag_funcs)

def praise_the_whale(file):
	# Yes, this is somewhat inefficient. Why am I doing this?
	# Simple answer: robustness
	file = json.loads(file)
	for document in file['documents']:
		find_paragraph(file, f"/documents/{document}/data", [convert_h4, convert_h3, convert_h2, convert_h1])
		find_paragraph(file, f"/documents/{document}/data", [convert_task_list])
		fix_special_tags(file, f"/documents/{document}/data")
		find_paragraph(file, f"/documents/{document}/data", [convert_images, convert_files, convert_docref, convert_mention, convert_b, convert_i, convert_a])
		print(file['documents'][document]['data'])
		#find_heading(file, f"/documents/{document}/data", [convert_b, convert_i, convert_a])
	#for document in file['documents']:
	#	find_textleaf2(file, f"/documents/{document}/data")
	#print(file)
	content = json.dumps(file)
	content = content.replace('{"type": "text", "text": ""}, ', '')
	content = content.replace(', {"type": "text", "text": ""}', '')
	return content

if __name__ == '__main__':
	file = open("LS1 Admin Space [LS1ADMIN] (Imported).json", "r").read()
	#print(testfile['documents'].keys())
	content = praise_the_whale(file)
	open("test.json", "w").write(content)

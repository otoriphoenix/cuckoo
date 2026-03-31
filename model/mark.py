class Mark:
	mark_type: str
	attrs: dict

	def __init__(self, mark_type, attrs = None):
		self.mark_type = mark_type
		self.attrs = attrs

	def toJson(self):
		baseJson =  {
			"type": self.mark_type
		}

		if self.attrs:
			baseJson["attrs"] = self.attrs

		return baseJson

# from urllib import request


class CloudCam:
	def __init__(self, ip, port):
		self.ip = ip
		self.port = port

	def send(self, command):
		if command:
			url = "http://{0}:{1}/webui?command=ptz{2}".format(self.ip, self.port, command)
			# TODO: need to debug 4
	#		request.urlopen(url)
		else:
			url = 'none'
		return url

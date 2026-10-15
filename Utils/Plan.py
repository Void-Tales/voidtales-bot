# 📦 Built-in modules
import gzip
import json
import urllib.parse
import urllib.request
import http.cookiejar

# 📥 Custom modules
from Utils.Env import LoadEnv

# ⚙️ Settings
from Config import FuzzyMatchingThreshold


class PlanAPI:
	def __init__(self):
		# 🍪 Cookie jar for auth
		self.CookieJar = http.cookiejar.CookieJar()
		self.Opener = urllib.request.build_opener(
			urllib.request.HTTPCookieProcessor(self.CookieJar)
		)
		self.Env = LoadEnv()
		self.LoggedIn = False
		# 🌐 Base URL, e.g. the plain host port to skip the public login gate
		self.BaseUrl = (self.Env.get('PLAN_URL') or 'https://plan.voidtales.win').rstrip('/')

	# 🔐 Login to get auth cookie
	def Login(self) -> bool:
		if self.LoggedIn:
			return True
		User = self.Env.get('PLAN_USER')
		Password = self.Env.get('PLAN_PASSWORD')
		if not User or not Password:
			return False
		LoginUrl = f'{self.BaseUrl}/auth/login'
		Data = urllib.parse.urlencode({'user': User, 'password': Password}).encode('utf-8')
		Req = urllib.request.Request(LoginUrl, data=Data, method='POST')
		Req.add_header('accept', 'application/json')
		Req.add_header('Content-Type', 'application/x-www-form-urlencoded')
		try:
			with self.Opener.open(Req) as Response:
				if Response.status == 200:
					ResponseData = json.loads(Response.read().decode('utf-8'))
					if ResponseData.get('success', False):
						# 🍪 Plan marks its cookie Secure, which the jar would not send over plain http
						for Cookie in self.CookieJar:
							Cookie.secure = False
						self.LoggedIn = True
						return True
		except Exception:
			pass
		return False

	# 🌐 Generic fetch data from Plan API
	def FetchData(self, Url: str) -> dict | None:
		if not self.Login():
			return None
		Req = urllib.request.Request(Url)
		Req.add_header('accept', 'application/json')
		try:
			with self.Opener.open(Req) as Response:
				if Response.status != 200:
					return None
				RawData = Response.read()
				if Response.headers.get('Content-Encoding') == 'gzip':
					RawData = gzip.decompress(RawData)
				DecodedData = RawData.decode('utf-8', errors='ignore')
				return json.loads(DecodedData)
		except Exception:
			return None

	# 📊 Fetch player stats with fuzzy matching
	def GetPlayerStats(self, ServerUUID: str, PlayerName: str | None = None) -> dict | None:
		Url = f'{self.BaseUrl}/v1/playersTable?server={ServerUUID}'
		Data = self.FetchData(Url)
		if not Data or not PlayerName:
			return Data  # Return full data if no name, or None on failure
		Players = Data.get('players', [])
		if not Players:
			return None
		import difflib

		PlayerNames = [P.get('playerName', '') for P in Players]
		Matches = difflib.get_close_matches(
			PlayerName, PlayerNames, n=1, cutoff=FuzzyMatchingThreshold
		)
		if not Matches:
			return None
		MatchedName = Matches[0]
		return next((P for P in Players if P.get('playerName') == MatchedName), None)

	# 📈 Fetch performance overview
	def GetPerformanceOverview(self, ServerUUID: str) -> dict | None:
		Url = f'{self.BaseUrl}/v1/network/performanceOverview?servers=%5B%22{ServerUUID}%22%5D'
		return self.FetchData(Url)

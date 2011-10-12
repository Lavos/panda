import Gbx
import json
import sqlite3
from templite import Templite

class Panda:
	"""Main class for the panda controller for trackmania forever."""
	def __init__(self):
		self.players = {}
		self.tracks = {}
	
		configfile = open('./config.json', 'r')
		contents = configfile.read()
		configfile.close()

		self.config = json.loads(contents)

		print self.config

		self.init_db()
		self.init_tm()
		self.sync()
		v = self.tm.GetVersion()

		print "Connected to " + v["Name"]
		self.tm.ChatSendServerMessage("Panda controller v0.1 connected")

		self.display_votebox_toall()

		self.tm.set_default_method(self.cb_default)
		self.tm.add_method("TrackMania.PlayerConnect", self.cb_player_connect)
		self.tm.add_method("TrackMania.PlayerDisconnect", self.cb_player_disconnect)
		self.tm.add_method("TrackMania.BeginMap", self.cb_begin_track)
		self.tm.add_method("TrackMania.PlayerManialinkPageAnswer", self.cb_manialink_answer)
		self.tm.add_method("TrackMania.PlayerFinish", self.cb_finish)

	def init_db(self):
		self.db = sqlite3.connect('./panda.db')
		self.c = self.db.cursor()

	def init_tm(self):
		self.tm = Gbx.Client('localhost:5000')
		self.tm.init()
		self.tm.Authenticate('SuperAdmin', self.config['password'])
		self.tm.EnableCallbacks(True)

	def sync(self):
		players = self.tm.GetPlayerList(1000, 0, 1)
		for player in players:
			Player(player, self)

		tracks = self.tm.GetMapList(5000, 0)
		for track in tracks:
			Track(track, self)

		self.current_track = self.tm.GetCurrentMapInfo(5000, 0)

	def cb_player_connect(self, login, isspec):
		player = self.tm.GetPlayerInfo(login)
		self.tm.ChatSendServerMessage("Connection: %s" % player["NickName"])
		Player(player, self)

		print 'login: %s' % login

		self.display_votebox_tologin(login)

	def cb_player_disconnect(self, login):
		self.tm.ChatSendServerMessage("Disconnect: %s" % self.players[login].nick)
		del self.players[login]

	def cb_default(self, *args):
		# print args
		pass

	def cb_begin_track(self, track, warmup, match_continuation):
		self.current_track = track
		for login, player in self.players.iteritems():
			player.voted = False

		self.display_votebox_toall()

	def cb_finish(self, uid, login, result):
		if result:
			self.tm.ChatSendServerMessage("%s %s %s" % (uid, login, result))

	def getvotes(self):
		chalvalue = (self.current_track['UId'],)
		votes = self.c.execute('SELECT vote FROM tracks AS t, votes AS v WHERE t.UId=? AND v.track = t.id;', chalvalue)

		upvotes = 0
		downvotes = 0
		for vote in votes:
			if (vote[0] == 1):
				upvotes += 1
			else:
				downvotes += 1

		return {'upvotes': upvotes, 'downvotes': downvotes}

	def display_votebox_toall(self):
		votes = self.getvotes()
		votebox_voted = build_votebox(False, votes['upvotes'], votes['downvotes'])
		votebox_notvoted = build_votebox(True, votes['upvotes'], votes['downvotes'])

		voted = []
		notvoted = []

		for login, player in self.players.iteritems():
			if player.voted:
				voted.append(player.login)
			else:
				notvoted.append(player.login)
		
		self.tm.SendDisplayManialinkPageToLogin(",".join(voted), votebox_voted, 0, True)
		self.tm.SendDisplayManialinkPageToLogin(",".join(notvoted), votebox_notvoted, 0, True)

	def display_votebox_tologin(self, login):
		votes = self.getvotes()

		if self.players[login].voted:
			votebox = build_votebox(False, votes['upvotes'], votes['downvotes'])
		else:
			votebox = build_votebox(True, votes['upvotes'], votes['downvotes'])
		
		self.tm.SendDisplayManialinkPageToLogin(login, votebox, 0, True)

	def cb_manialink_answer(self, uid, login, answer, entries):
		print 'got answer: %s' % answer

		if answer == 'votebox_0': # downvote
			self.vote(login, 0)
		elif answer == 'votebox_1': # upvote
			self.vote(login, 1)
		else:
			print 'unhandled answer'

	def vote(self, login, vote):
		votevalues = (vote, self.current_track['UId'], login)
		self.players[login].voted = True

		self.c.execute('INSERT INTO votes SELECT null, u.id, t.id, ? FROM tracks AS t, users AS u WHERE t.UId=? AND u.login=?;', votevalues)
		print 'vote accepted!'

		self.db.commit()
		self.display_votebox_toall()

		if vote:
			verb = '$0f0liked'
		else:
			verb = '$f00hated'

		self.tm.ChatSendServerMessage("%s %s $fff$o%s$z$fff, $iwhat about you?" % (self.players[login].nick, verb, self.current_track['Name']))

class Track:
	def __init__(self, track, server):
		self.name = track["Name"]
		self.uid = track["UId"]
		self.file = track["FileName"]

		trackrow = (track['UId'], track['Name'], track['FileName'])
		server.c.execute('INSERT OR IGNORE INTO tracks VALUES(null,?,?,?)', trackrow)
		server.db.commit()
		
		server.tracks[self.uid] = self

class Player:
	"""Representing a connected player to the server."""
	def __init__(self, player, server):
		self.login = player["Login"]
		self.nick = player["NickName"]
		self.id = player["PlayerId"]
		self.voted = False

		userrow = (player['Login'], player['NickName'])
		server.c.execute('INSERT OR IGNORE INTO users VALUES(null,?,?);', userrow)
		server.db.commit()

		server.players[self.login] = self

def build_votebox(actions, upvotes, downvotes):
	xml = """<?xml version="1.0" encoding="utf-8"?>
<manialink version="1">
	<quad ${if actions:}$ action="votebox_1" ${:endif}$ posn="158.15 80 1" sizen="5 5" halign="right" valign="top" style="UIConstructionSimple_Buttons" substyle="Up"/>
	<label posn="153.15 78.7 1" sizen="100 7" halign="right" valign="top" textcolor="ffff" text="$0f0${upvotes}$$fff" textsize="1"/>
	<label posn="147.60 78.2 1" sizen="100 5" halign="right" valign="top" textcolor="fff9" text="$tlikes" textsize="0.25"/>

	<quad ${if actions:}$ action="votebox_0" ${:endif}$ posn="158.15 76 1" sizen="5 5" halign="right" valign="top" style="UIConstructionSimple_Buttons" substyle="Down"/>
	<label posn="153.15 74.7 1" sizen="100 7" halign="right" valign="top" textcolor="ffff" text="$f00${downvotes}$$fff" textsize="1"/>
	<label posn="147.60 74.2 1" sizen="100 5" halign="right" valign="top" textcolor="fff9" text="$thates" textsize="0.25"/>

	<label posn="157.55 -68.5 1" sizen="100 7" halign="right" valign="top" textcolor="ffff" text="$ff9All Time$n $m$ddd0:45.65" textsize="1"/>

</manialink>"""

	t = Templite(xml)
	manialink = t.render(actions=actions, upvotes=upvotes, downvotes=downvotes)

	return manialink

panda = Panda()
while 1:
	panda.tm.tick(3600)
	

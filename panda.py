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

		self.mass_refresh()

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

		self.current_track = self.tracks[self.tm.GetCurrentMapInfo(5000, 0)['UId']]

	def cb_player_connect(self, login, isspec):
		player = self.tm.GetPlayerInfo(login)
		self.tm.ChatSendServerMessage("Connection: %s" % player["NickName"])
		Player(player, self)

		print 'login: %s' % login

		self.display_manialink(self.players[login])
		

	def cb_player_disconnect(self, login):
		self.tm.ChatSendServerMessage("Disconnect: %s" % self.players[login].nick)
		del self.players[login]

	def cb_default(self, *args):
		# print args
		pass

	def cb_begin_track(self, track, warmup, match_continuation):
		self.current_track = self.tracks[track['UId']]
		for login, player in self.players.iteritems():
			player.voted = False

		self.mass_refresh()

	def cb_finish(self, uid, login, result):
		player = self.players[login]

		if result:
			self.tm.ChatSendServerMessage("%s %s %s" % (uid, login, result))

			if player.userid not in self.current_track.results or result > self.current_track.results[player.userid] or True:
				self.setrecord(player, result)
				self.display_manialink(player)
	
	def setrecord(self, player, result):
		self.current_track.results[player.userid] = result
		recordrow = (player.userid, result, self.current_track.uid)
		print recordrow
		self.c.execute('INSERT OR REPLACE INTO records SELECT null, t.id, ?, ? FROM tracks AS t WHERE t.UId = ?;', recordrow)
		self.db.commit()

	def getfragments(self, milliseconds):
		seconds, milliseconds = divmod(milliseconds, 1000)
		minutes, seconds = divmod(seconds, 60)
		hours, minutes = divmod(minutes, 60)

		return hours, minutes, seconds, milliseconds

	def getvotes(self):
		chalvalue = (self.current_track.uid,)
		self.c.execute('SELECT sum(vote), count(vote) FROM tracks AS t, votes AS v WHERE t.UId=? AND v.track = t.id;', chalvalue)
		
		return self.c.fetchone()

	def cb_manialink_answer(self, uid, login, answer, entries):
		print 'got answer: %s' % answer

		if answer == 'votebox_0': # downvote
			self.vote(login, 0)
		elif answer == 'votebox_1': # upvote
			self.vote(login, 1)
		else:
			print 'unhandled answer'

	def vote(self, login, vote):
		votevalues = (vote, self.current_track.uid, login)
		self.players[login].voted = True

		self.c.execute('INSERT INTO votes SELECT null, u.id, t.id, ? FROM tracks AS t, users AS u WHERE t.UId=? AND u.login=?;', votevalues)
		print 'vote accepted!'

		self.db.commit()
		self.display_manialink(self.players[login])

		if vote:
			verb = '$0f0liked'
		else:
			verb = '$f00hated'

		self.tm.ChatSendServerMessage("%s %s $fff$o%s$z$fff, $iwhat about you?" % (self.players[login].nick, verb, self.current_track.name))

	def display_manialink(self, player):
		xml = """
			<?xml version="1.0" encoding="utf-8"?>
			<manialink version="1">
				<frame>
					<quad posn="158.15 80 1" sizen="4 4" halign="right" valign="top" style="Icons64x64_1" substyle="StateSuggested"/>
					<label posn="153.15 78.7 1" sizen="100 7" halign="right" valign="top" textcolor="ffff" text="${opinion}$" textsize="1"/>
				</frame>

				<frame>
					<quad ${if actions:}$ action="votebox_1" ${:endif}$ posn="140.15 76 1" sizen="5 5" halign="right" valign="top" style="UIConstructionSimple_Buttons" substyle="Up"/>
					<quad ${if actions:}$ action="votebox_0" ${:endif}$ posn="158.15 76 1" sizen="5 5" halign="right" valign="top" style="UIConstructionSimple_Buttons" substyle="Down"/>
					<label posn="153.15 74.7 1" sizen="100 7" halign="right" valign="top" textcolor="ffff" text="${upvotes}$ $f00${downvotes}$$fff" textsize="1"/>
				</frame>

				${if results:}$
				<label posn="157.55 -68.5 1" sizen="100 7" halign="right" valign="top" textcolor="ffff" text="$ff9All Time$n $m$ddd${results}$" textsize="1"/>
				${:endif}$

			</manialink>"""

		print player

		upvotes, totalvotes = self.getvotes()
		ratio = (100*upvotes) /totalvotes
		print "%d/%d = %d" % (upvotes, totalvotes, ratio)

		if ratio >= 80:
			opinion = '$0f0adored'
		elif ratio >= 65:
			opinion = '$6F3enjoyed'
		elif ratio >= 50:
			opinion = '$CF9positive'
		elif ratio >= 35:
			opinion = '$FF0mixed'
		elif ratio >= 20:
			opinion = '$F60negative'
		else:
			opinion = '$f00hated'

		if player.voted:
			actions = False
		else:
			actions = True

		if player.userid in self.current_track.results:
			stored = self.current_track.results[player.userid]

			hours, minutes, seconds, milliseconds = self.getfragments(stored)

			results = "%2d:%02d:%2d.%d" % (hours, minutes, seconds, milliseconds)
			print results
		else:
			results = None
		
		t = Templite(xml)
		manialink = t.render(actions=True, opinion=opinion, upvotes=upvotes, downvotes=(totalvotes-upvotes), results=results)

		print player.login

		self.tm.SendDisplayManialinkPageToLogin(player.login, manialink, 0, False)

	def mass_refresh(self):
		for login, player in self.players.iteritems():
			print player
			self.display_manialink(player)

class Track:
	def __init__(self, track, server):
		self.name = track["Name"]
		self.uid = track["UId"]
		self.file = track["FileName"]

		trackrow = (track['UId'], track['Name'], track['FileName'])
		server.c.execute('INSERT OR IGNORE INTO tracks VALUES(null,?,?,?)', trackrow)
		server.db.commit()
		
		server.tracks[self.uid] = self

		recordrow = (track['UId'],)
		server.c.execute('SELECT user, result FROM records AS r, tracks AS t WHERE t.UId  = ? AND r.track = t.id;', recordrow)
		
		self.results = {}
		for row in server.c.fetchall():
			self.results[row[0]] = row[1]

		print self.results		

class Player:
	"""Representing a connected player to the server."""
	def __init__(self, player, server):
		self.login = player["Login"]
		self.nick = player["NickName"]
		self.id = player["PlayerId"]
		self.voted = False
		self.result = 0

		userrow = (player['Login'], player['NickName'])
		server.c.execute('INSERT OR IGNORE INTO users VALUES(null,?,?);', userrow)
		server.db.commit()

		playerrow = (player['Login'],)
		server.c.execute('SELECT id FROM users WHERE login = ?;', playerrow)
		self.userid = server.c.fetchone()[0]

		print self.userid
		
		server.players[self.login] = self

panda = Panda()
while 1:
	panda.tm.tick(3600)
	

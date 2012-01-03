import time
from datetime import tzinfo, timedelta, datetime


class CET(tzinfo):
	def utcoffset(self, dt):
		return timedelta(hours=1)
	def tzname(self, dt):
		return 'UTC +1'
	def dst(self, dt):
		return timedelta(0)


cet = CET()

print datetime.utcnow()
curdate = cet.fromutc(datetime.utcnow().replace(tzinfo=cet))

seconds = curdate.second + (curdate.minute*60) + (curdate.hour*60*60)
beats = seconds * 0.01157

print 'seconds: %d, beats: @%d' % (seconds, beats)

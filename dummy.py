import sqlite3

conn = sqlite3.connect('./panda.db')

c = conn.cursor()


dummy = (None, "lavos", "Lavos")
c.execute('insert into users values (?,?,?)', dummy)

c.execute('select * from users')
for row in c:
	print row



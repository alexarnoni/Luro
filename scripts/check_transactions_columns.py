import sqlite3

db = 'luro.db'
conn = sqlite3.connect(db)
print('Connected to', db)
for row in conn.execute("PRAGMA table_info('transactions')"):
    print(row)
conn.close()

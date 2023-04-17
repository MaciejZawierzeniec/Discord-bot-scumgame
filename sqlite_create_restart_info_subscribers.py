import sqlite3


conn = sqlite3.connect('raid_events.db')

conn.execute('''
    CREATE TABLE restart_subscribers (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        online INTEGER DEFAULT 0
    )
''')

conn.commit()
conn.close()

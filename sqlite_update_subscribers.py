import sqlite3

db_name = 'raid_events.db'


def add_user(user_id, username, table):
    conn = sqlite3.connect(db_name)

    if table == 'restart_subscribers':
        conn.execute('''
            INSERT INTO restart_subscribers (user_id, username, online) 
            VALUES (?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, online = 0
        ''', (user_id, username))
    elif table == 'subscribers':
        conn.execute('''
            INSERT INTO {} (user_id, username) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        '''.format(table), (user_id, username))

    conn.commit()
    conn.close()

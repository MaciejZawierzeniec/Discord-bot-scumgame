import ftplib
import io
import os
import sqlite3
import time
from dotenv import load_dotenv

load_dotenv()

FTP_SERVER = os.getenv("FTP_SERVER")
FTP_USERNAME = os.getenv("FTP_USERNAME")
FTP_PASSWORD = os.getenv("FTP_PASSWORD")
FTP_PORT = int(os.getenv("FTP_PORT"))
FTP_DIRECTORY = os.getenv("FTP_DIRECTORY")


def connect_ftp_with_retry(max_retries=5):
    for _ in range(max_retries):
        ftp = ftplib.FTP(timeout=30)
        try:
            ftp.connect(FTP_SERVER, FTP_PORT)
            ftp.login(user=FTP_USERNAME, passwd=FTP_PASSWORD)
            return ftp
        except ftplib.error_perm:
            time.sleep(5)
            continue
        except Exception as e:
            print(f"Error: {e}")
            return None

    return None


def read_ftp_file():
    ftp = connect_ftp_with_retry()
    if ftp is None:
        return

    ftp.cwd(FTP_DIRECTORY)
    file_list = []
    ftp.dir(file_list.append)

    gameplay_files = [file_name for file_name in
                      [file_info.split()[-1] for file_info in file_list]
                      if "gameplay" in file_name]
    login_files = [file_name for file_name in
                   [file_info.split()[-1] for file_info in file_list]
                   if "login" in file_name]

    if gameplay_files:
        file_name = str(gameplay_files[-1:][0])
        with io.BytesIO() as file_buffer:
            ftp.retrbinary("RETR " + file_name, file_buffer.write)
            file_contents = file_buffer.getvalue()
            events = [line.split(" ") for line in file_contents.decode('utf-16').splitlines()]
            events = _map_events(events)
            update_events(events)

    if login_files:
        file_name = str(login_files[-1:][0])
        with io.BytesIO() as file_buffer:
            ftp.retrbinary("RETR " + file_name, file_buffer.write)
            file_contents = file_buffer.getvalue()
            login_logout_events = file_contents.decode('utf-16').splitlines()
            process_login_logout_events(login_logout_events)

    ftp.quit()


def process_login_logout_events(events):
    conn = sqlite3.connect('raid_events.db')

    user_online_status = {}

    for event in events:
        if "' logged in at:" in event or "' logged out at:" in event:
            parts = event.split(": ")
            timestamp = parts[0]
            action = "logged in" if "logged in" in event else "logged out"
            username_section = parts[1].split(":", 1)[-1].strip()
            username = username_section.split(":")[0].split("(")[0].strip().lower()
            online = 1 if action == "logged in" else 0

            if username not in user_online_status or user_online_status[username][1] < timestamp:
                user_online_status[username] = (online, timestamp)

    for username, (online, _) in user_online_status.items():
        conn.execute("UPDATE restart_subscribers SET online = ? WHERE username = ?", (online, username))

    conn.commit()
    conn.close()


def update_events(events):
    conn = sqlite3.connect('raid_events.db')

    for timestamp, values in events.items():
        existing_record = conn.execute('SELECT * FROM events_table WHERE timestamp=?', (timestamp,)).fetchone()
        if existing_record is None:
            conn.execute(
                'INSERT INTO events_table (timestamp, user, owner, success, attempts, object, lock_type, alert_sent) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (timestamp, values['user'], values['owner'], values['success'], values['attempts'], values['object'],
                 values['lock_type'], values.get('alert_sent', 0)))

    conn.commit()
    conn.close()


def _map_events(events):
    mapped_events = {}
    for event in events:
        event_meta = {
            'user': '',
            'owner': '',
            'success': '',
            'attempts': '',
            'object': '',
            'lock_type': '',
            'alert_sent': False
        }
        if event[0]:
            for string in event:
                if event[1] == '[LogTrap]' and event[2] == 'Triggered.':
                    if string.lower() == 'owner:':
                        event_meta['owner'] = event[event.index(string) + 1].lower()
                    elif string.lower() == 'user:':
                        event_meta['user'] = event[event.index(string) + 1].lower()
                    elif string.lower() == 'name:':
                        event_meta['object'] = ' '.join(event[event.index(string)+1:event.index('Owner:')]).strip('.')
                elif event[1] == '[LogMinigame]':
                    if string.lower() == 'user:':
                        event_meta['user'] = event[event.index(string) + 1].lower()
                    elif string.lower() == 'user' and event_meta['user']:
                        event_meta['owner'] = event[event.index(string) + 3].strip(').').lower()
                    elif string.lower() == 'success:':
                        event_meta['success'] = event[event.index(string) + 1].strip('.')
                    elif string.lower() == 'attempts:':
                        event_meta['attempts'] = event[event.index(string) + 1].strip('.')
                    elif string.lower() == 'object:':
                        event_meta['object'] = event[event.index(string) + 1].strip('.')
                    elif string.lower() == 'name:':
                        event_meta['object'] = event[event.index(string) + 1].strip('.')
                    elif string.lower() == 'type:':
                        event_meta['lock_type'] = event[event.index(string) + 1].strip('.')
        if event_meta['user'] and not event_meta['owner'] == 'location:':
            id_date = event[0].strip(':')
            mapped_events[id_date] = event_meta
    return mapped_events


while True:
    read_ftp_file()
    time.sleep(5)


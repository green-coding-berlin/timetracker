#!/usr/bin/env python3

# pylint: disable=W0603,W0602,W1203,W0702
import subprocess
import time
import argparse
import sys
import os
import os.path
import sqlite3
import threading
import logging
import re

from pathlib import Path

import caribou


VERSION = '0.1'

LOG_LEVELS = ['debug', 'info', 'warning', 'error', 'critical']

APP_NAME = 'io.green-coding.tt'
APP_SUPPORT_PATH = Path(f"~/Library/Application Support/{APP_NAME}")
APP_SUPPORT_PATH.mkdir(parents=True, exist_ok=True)

DATABASE_FILE = APP_SUPPORT_PATH / 'db.db'

MIGRATIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')

# Shared variable to signal the thread to stop
stop_signal = threading.Event()

conn = sqlite3.connect(DATABASE_FILE)
c = conn.cursor()

def sigint_handler(_, __):
    global stop_signal
    if stop_signal.is_set():
        # If you press CTR-C the second time we bail
        sys.exit(2)

    stop_signal.set()
    logging.info('Terminating all processes. Please be patient, this might take a few seconds.')

# This is a replacement for time.sleep as we need to check periodically if we need to exit
# We choose a max exit time of one second as we don't want to wake up too often.
def sleeper(stop_event, duration):
    end_time = time.time() + duration
    while time.time() < end_time:
        if stop_event.is_set():
            return
        time.sleep(1)


def get_window_name():
    script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
        end tell
        return frontApp
    '''
    try:
        data = subprocess.check_output(["osascript", "-e", script]).strip().decode("utf-8")
        return data
    except subprocess.CalledProcessError as e:
        return 'NA'

def get_window_data():
    script = '''
        tell application "System Events"
            set frontApp to first application process whose frontmost is true
            set frontAppName to name of frontApp
            set windowTitle to name of window 1 of frontApp
            set windowPosition to position of window 1 of frontApp
            set windowSize to size of window 1 of frontApp
            set posX to item 1 of windowPosition
            set posY to item 2 of windowPosition
            set width to item 1 of windowSize
            set height to item 2 of windowSize
            return "Name: " & frontAppName & " - Title: " & windowTitle & " - Position: " & posX & ", " & posY & " - Size: " & width & ", " & height
        end tell
    '''
    try:
        data = subprocess.check_output(["osascript", "-e", script]).strip().decode("utf-8")
        return data
    except subprocess.CalledProcessError as e:
        return None

def start_loop(local_stop, interval):
    pattern = re.compile(r"Name: (.*?) - Title: (.*?) - Position: (\d*), (\d*) - Size: (\d*), (\d*)")


    wname = ""
    wtitle = ""
    while not local_stop.is_set():

        window_data = get_window_data()
        if window_data:
            match = pattern.search(window_data)

            if match:
                name = match.group(1)
                title = match.group(2)
                positionx = int(match.group(3))
                positiony = int(match.group(4))
                sizex = int(match.group(5))
                sizey = int(match.group(6))

                if wname != name or wtitle != title:
                    logging.debug({
                        "Name": name,
                        "Title": title,
                        "PositionX": positionx,
                        "PositionY": positiony,
                        "SizeX": sizex,
                        "SizeY": sizey
                    })

                    c.execute('''INSERT INTO appdata
                            (time, application, title, positionX, positionY, sizeX, sizeY) VALUES
                            (?, ?, ?, ?, ?, ?, ?)''',
                            (int(time.time() * 1000),
                            name,
                            title,
                            positionx,
                            positiony,
                            sizex,
                            sizey
                            ))


                    wname = name
                    wtitle = title

            else:
                logging.error(f"Could not parse string: {window_data}")
        else:
            # Sometimes getting the title doesn't work so we only get the name of the app
            window_name = get_window_name()

            if window_name != wname:
                logging.debug({
                        "Name": window_name,
                    })
                c.execute('''INSERT INTO appdata
                        (time, application) VALUES
                        (?, ?)''',
                        (int(time.time() * 1000),
                        name
                        ))

                wname = window_name


        conn.commit()

        sleeper(local_stop, interval)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=
                                     '''
                                     A script that runs in the background and saves the active window with some information
                                     into a database for further analytics
                                     ''')
    parser.add_argument('-i', '--interval', type=int, default=1, help='The interval when to check in seconds')
    parser.add_argument('-v', '--log-level', choices=LOG_LEVELS, default='info', help='Logging level')
    parser.add_argument('-o', '--output-file', type=str, help='Path to the output log file.')

    args = parser.parse_args()

    log_level = getattr(logging, args.log_level.upper())

    if args.output_file:
        logging.basicConfig(filename=args.output_file, level=log_level, format='[%(levelname)s] %(asctime)s - %(message)s')
    else:
        logging.basicConfig(level=log_level, format='[%(levelname)s] %(asctime)s - %(message)s')

    logging.debug('Program started.')
    logging.debug(f"Using db: {DATABASE_FILE}")


    # Make sure the DB is migrated
    caribou.upgrade(DATABASE_FILE, MIGRATIONS_PATH)

    start_loop(stop_signal, args.interval)

    c.close()

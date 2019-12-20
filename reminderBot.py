import discord
import sqlite3
import atexit
import json
import os


# Initiating bot with settings
files = os.listdir()

# list of 3-tuples (var_name, description, processing function)
settings_list = [("db_name", "What would you like to name your database file (text): ", str),
                ("token", "What's your discord bots token? (text): ", str),
                ("state_lifetime", "How long should user conversation states last in milliseconds? (int): ", int)]

if "settings.conf" in files:
    settings_file = open("settings.conf", "r")
    settings = json.load(settings_file)
    settings_file.close()
    dialogue_flag = False

else:
    # Whoops, let's ask our user for some settings
    print("It looks like you don't have a settings file, let's fix that for you")
    settings = {}
    dialogue_flag = True

any_changes = False
for setting in settings_list:
    if setting[0] not in settings:
        any_changes = True
        if dialogue_flag == False:
            dialogue_flag = True
            print("It looks like you're missing some settings, let's fix that for you!\n")
        settings[setting[0]] = setting[2](input(setting[1]))

if any_changes:
    print("Thanks!\n")
    print("Now we're gonna continue with our setup")
    settings_file = open("settings.conf", "w")
    settings_file.write(json.dumps(settings))
    settings_file.close()


# Database setup
print("Connecting to database")

conn = sqlite3.connect(settings["db_name"])
c = conn.cursor()

c.execute("select name from sqlite_master where type = 'table';")
table_names = [a[0] for a in c.fetchall()]
print(table_names)

# Making sure our tables are up to date
if "users" not in table_names:
    c.execute('''CREATE TABLE users(
        uid INTEGER PRIMARY KEY,
        timezone TEXT NOT NULL)
        '''
        )

if "scheduled" not in table_names:
    c.execute('''CREATE TABLE scheduled(
        key INTEGER PRIMARY KEY,
        user INTEGER,
        event_name TEXT NOT NULL,
        local_time TEXT NOT NULL,
        period TEXT NOT NULL,
        FOREIGN KEY(user) REFERENCES users(uid)
            ON DELETE CASCADE
            ON UPDATE CASCADE)'''
    )

if "trackers" not in table_names:
    c.execute('''CREATE TABLE trackers(
        key INTEGER PRIMARY KEY,
        user INTEGER,
        type TEXT NOT NULL,
        min_target INT,
        max_target INT,
        FOREIGN KEY(user) REFERENCES users(uid)
            ON DELETE CASCADE
            ON UPDATE CASCADE
    )'''
    )

if "tracked_events" not in table_names:
    c.execute('''CREATE TABLE tracked_events(
        key INTEGER PRIMARY KEY,
        user INTEGER,
        assoc_tracker INTEGER,
        description TEXT NOT NULL,
        value INTEGER,
        FOREIGN KEY(user) REFERENCES users(uid)
            ON DELETE CASCADE
            ON UPDATE CASCADE,
        FOREIGN KEY(assoc_tracker) REFERENCES trackers(key)
            ON DELETE CASCADE
            ON UPDATE CASCADE

    )'''
    )

if "install_info" not in table_names:
    c.execute('''CREATE TABLE install_info(
        key INTEGER PRIMARY KEY,
        info_name TEXT NOT NULL,
        value TEXT NOT NULL)'''
    )
    
    c.execute('''INSERT INTO install_info VALUES (NULL,'version number', '0.00.00.1') ''')

conn.commit()
atexit.register(conn.close)

# Dialogue
dialogue_file = open("dialogue.txt","r")
dialogue = json.load(dialogue_file)
dialogue_file.close()

client = discord.Client()

# Unfortunately neccessary global state
# Tracks where users currently are in an interaction

# map user uid -> [state, expiry timestamp]
user_cur_state = {}

@client.event
async def on_ready():
    print("Logged in as {0.user}".format(client))

# Message routing
@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if isinstance(message.channel, discord.DMChannel) and message.content.startswith("!help"):
        await message.channel.send(dialogue["help_text_newbie"])

client.run(settings["token"])


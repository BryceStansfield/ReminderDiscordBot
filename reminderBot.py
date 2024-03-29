import discord
import sqlite3
import atexit
import json
import os
import time, sched, pytz

# Initiating bot with settings
files = os.listdir()

# list of 3-tuples (var_name, description, processing function)
settings_list = [("db_name", "What would you like to name your database file (text): ", str),
                ("token", "What's your discord bots token? (text): ", str),
                ("state_lifetime", "How long should user conversation states last in seconds? (int): ", int)]

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
user_diag_state = {}
user_diag_deletion_schedule = {}

# Managing this global state
s = sched.scheduler(time.time, time.sleep)
def add_state(uid, state):
    """Adds the state "state" to user given by uid. Also manages expiry"""
    if uid in user_diag_deletion_schedule:
        s.cancel(user_diag_deletion_schedule[uid])
        del user_diag_deletion_schedule[uid]
    cur_time = time.time()
    user_diag_state[uid] = (state, cur_time+settings["state_lifetime"],)
    user_diag_deletion_schedule[uid] = s.enter(settings["state_lifetime"],1,remove_state,argument=(uid))
    return

def remove_state(uid):
    """Removes the state attached to user uid"""
    del user_diag_state[uid]
    return

async def retrieve_state(uid):
    return user_diag_state[uid][0]
    
def forcefully_remove_state(uid):
    if uid in user_diag_deletion_schedule:
        del user_diag_deletion_schedule[uid]
    if uid in user_diag_state:
        del user_diag_state[uid]

@client.event
async def on_ready():
    print("Logged in as {0.user}".format(client))

# Message routing
@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if isinstance(message.channel, discord.DMChannel):
        if message.author.id not in user_diag_state:
            if message.content.startswith("!help"):
                await message.channel.send(dialogue["help_text_newbie"])

            if message.content.startswith("!setup"):
                add_state(message.author.id, ("setup", 1,))
                await message.channel.send(dialogue["setup_text"])
                await message.channel.send(dialogue["setup_question_1"])
        else:
            # Handling stateful interactions
            await stateful_handler(message)

async def stateful_handler(message):
    state = await retrieve_state(message.author.id)
    if state[0] == "setup":
        await setup_handler(message, state)

    return

async def setup_handler(message, state):
    if state[1] == 1:
        if message.content.upper() == "Y" or message.content.upper() == "YES":
            add_state(message.author.id, ("setup", 2))
            await message.channel.send(dialogue["setup_question_2"])
        elif message.content.upper() == "N" or message.content.upper() == "NO":
            forcefully_remove_state(message.author.id)
            await message.channel.send(dialogue["no_permission_given"])
        else:
            await message.channel.send(dialogue["setup1_not_sure"])

    elif state[1] == 2:
        if message.content in pytz.all_timezones:
            c.execute('''INSERT INTO users VALUES (?,?)''', (message.author.id, message.content.strip(),))
            conn.commit()
            await message.channel.send(dialogue["setup_thankyou"])
        else:
            await message.channel.send(dialogue["setup2_not_valid_timezone"])


    else:
        forcefully_remove_state(message.author.id)
        await message.channel.send(dialogue["Error_during_setup"])

    return


client.run(settings["token"])


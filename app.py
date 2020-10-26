import os, json, random, secrets
from pymongo import MongoClient
from bson.json_util import dumps
import flask_admin as admin
from flask_admin import AdminIndexView
from flask_admin.contrib.pymongo import ModelView, filters
from wtforms import form, fields
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
from flask import Flask, render_template, url_for, request, redirect, flash, request, send_from_directory, jsonify
from flask_socketio import SocketIO, send, emit

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
mongo = MongoClient("mongodb+srv://thomas:{DB_PASSWORD}@cluster0.640kn.mongodb.net/jokemon?retryWrites=true&w=majority".format(DB_PASSWORD=os.getenv("DB_PASSWORD")))
db = mongo.jokemon

class UserForm(form.Form):
    discordId = fields.StringField('discordId')
    discordTag = fields.StringField('discordTag')
    name = fields.StringField('name')
    avatar_url = fields.StringField('avatar_url')

class UserView(ModelView):
    column_list = ('discordId', 'discordTag','name','avatar_url')
    form = UserForm

class MoveForm(form.Form):
    name = fields.StringField('name')
    damage = fields.IntegerField('damage')
    desc = fields.StringField('desc')
    joeType = fields.StringField('type')

class MoveView(ModelView):
    column_list = ('name', 'damage','desc','type')
    form = MoveForm

class JokemonForm(form.Form):
    title = fields.StringField('title')
    image_url = fields.StringField('image_url')
    obtained = fields.IntegerField('obtained')

class JokemonView(ModelView):
    column_list = ('title','image_url','obtained')
    form = JokemonForm

class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        if discord.authorized:
            user = discord.fetch_user()
            user_data = json.loads(dumps(db.users.find_one({"discordId": user.id})))
            return user_data['admin']
        else:
            return False

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('index'))

app = Flask(__name__)
admin = admin.Admin(app, template_mode="bootstrap3", index_view=MyAdminIndexView())
admin.add_view(UserView(db.users))
admin.add_view(JokemonView(db.jokemon))
admin.add_view(MoveView(db.moves))
socketio = SocketIO(app)

app.config["SECRET_KEY"] = "swagmoneybigbubby"
app.config["DISCORD_CLIENT_ID"] = 763102007703109682
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_SECRET")
app.config["DISCORD_REDIRECT_URI"] = "http://127.0.0.1:5000/callback"
app.config["DISCORD_BOT_TOKEN"] = os.getenv("DISCORD_TOKEN")
app.config["OAUTHLIB_INSECURE_TRANSPORT"] = True

discord = DiscordOAuth2Session(app)

rarity_vals = [
    {
        "title":"Joesus Christ",
        "color":0
    },
    {
        "title":"Mythic",
        "color": 15401215
    },
    {
        "title":"Legendary",
        "color": 5375
    },
    {
        "title":"Rare",
        "color": 16711680
    },
    {
        "title":"Special",
        "color": 65321
    },
    {
        "title":"Fundamental",
        "color": 5127936
    },
]

rarity_weights = [
    0.01,
    0.03,
    0.11, 
    0.15,
    0.3,
    0.4 
]

@app.route("/login/")
def login():
    return discord.create_session()

@app.route("/callback/")
def callback():
    discord.callback()
    user = discord.fetch_user()
    user_data = json.loads(dumps(db.users.find_one({"discordId": user.id})))
    if (user_data == None):
        user_data = {
            "discordId": user.id ,
            "discordTag": user.name + "#" + user.discriminator,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "inventory": [],
            "admin": False,
            "stats": {
                "cards": 0,
                "points": 0,
                "wins": 0,
                "losses": 0
            },
            "lootboxes": {
                "opened": 0,
                "available": 3,
            }  
        }
        db.users.insert_one(user_data)
    else:
        db.users.update_one({'discordId':user.id}, {"$set": 
            {
                "discordTag": user.name + "#" + user.discriminator,
                "name": user.name,
                "avatar_url": user.avatar_url,
            }
        })
    return redirect(url_for("profile"))

@app.route("/logout/")
def logout():
    discord.revoke()
    return redirect(url_for("index"))

@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return redirect(url_for("login"))

def adminCheck(discordUser):
    result = False
    if (discordUser.authorized):
        user = discord.fetch_user()
        user_data = json.loads(dumps(db.users.find_one({"discordId": user.id})))
        result = user_data['admin']
    return result

@app.route('/')
def index():
    players = json.loads(dumps(list(db.users.find())))
    players = list(sorted(players, key=lambda player: player['stats']['points'], reverse=True))[0:3]
    joes = json.loads(dumps(list(db.jokemon.find())))
    joesus = [0,0]
    mythic = [0,0]
    legendary = [0,0]
    rare = [0,0]
    special = [0,0]
    fundamental = [0,0]
    for joe in joes:
        if joe['rarity']['title'] == 'Mythic':
            mythic[0] = mythic[0] + 1
            mythic[1] = mythic[1] + joe['obtained']
        elif joe['rarity']['title'] == 'Legendary':
            legendary[0] = legendary[0] + 1
            legendary[1] = legendary[1] + joe['obtained']
        elif joe['rarity']['title'] == 'Rare':
            rare[0] = rare[0] + 1
            rare[1] = rare[1] + joe['obtained']
        elif joe['rarity']['title'] == 'Special':
            special[0] = special[0] + 1
            special[1] = special[1] + joe['obtained']
        elif joe['rarity']['title'] == 'Fundamental':
            fundamental[0] = fundamental[0] + 1
            fundamental[1] = fundamental[1] + joe['obtained']
        elif joe['rarity']['title'] == 'Joesus Christ':
            joesus[0] = joesus[0] + 1
            joesus[1] = joesus[1] + joe['obtained']
    
    adminResult = adminCheck(discord)
    return render_template("index.html", card_rarities=[joesus,mythic,legendary,rare,special,fundamental], players=players, check=discord.authorized, adminResult=adminResult)

@app.route('/profile')
@requires_authorization
def profile():
    user = discord.fetch_user()
    user_data = json.loads(dumps(db.users.find_one({"discordId": user.id})))
    inv = []
    for card in user_data['inventory']:
        inv.append(json.loads(dumps(db.jokemon.find_one({"title": card}))))
    adminResult = adminCheck(discord)
    return render_template("profile.html", user=user, user_data=user_data, check=discord.authorized, inventory=inv, adminResult=adminResult)

@app.route('/cards')
def cards():
    joes = json.loads(dumps(list(db.jokemon.find())))
    joesus = []
    mythic = []
    legendary = []
    rare = []
    special = []
    fundamental = []
    for joe in joes:
        if joe['rarity']['title'] == 'Mythic':
            mythic.append(joe)
        elif joe['rarity']['title'] == 'Legendary':
            legendary.append(joe)
        elif joe['rarity']['title'] == 'Rare':
            rare.append(joe)
        elif joe['rarity']['title'] == 'Special':
            special.append(joe)
        elif joe['rarity']['title'] == 'Fundamental':
            fundamental.append(joe)
        elif joe['rarity']['title'] == 'Joesus Christ':
            joe['title'] = '?'*len(joe['title'].split(' ')[0]) + ' ' + joe['title'].split(' ')[1]
            joesus.append(joe)
    adminResult = adminCheck(discord)
    return render_template("cards.html", card_rarities=[joesus,mythic,legendary,rare,special,fundamental], check=discord.authorized, adminResult=adminResult)

@app.route('/leaderboard')
def leaderboard():
    players = json.loads(dumps(list(db.users.find())))
    players = list(sorted(players, key=lambda player: player['stats']['points'], reverse=True))
    adminResult = adminCheck(discord)
    return render_template("leaderboard.html", players=players, check=discord.authorized, adminResult=adminResult)

@app.route('/lootbox')
@requires_authorization
def lootbox():
    user = discord.fetch_user()
    user_data = json.loads(dumps(db.users.find_one({"discordId": user.id})))
    available = user_data['lootboxes']['available']
    joes = json.loads(dumps(list(db.jokemon.find())))
    joesus = []
    mythic = []
    legendary = []
    rare = []
    special = []
    fundamental = []
    for joe in joes:
        if joe['rarity']['title'] == 'Mythic':
            mythic.append(joe)
        elif joe['rarity']['title'] == 'Legendary':
            legendary.append(joe)
        elif joe['rarity']['title'] == 'Rare':
            rare.append(joe)
        elif joe['rarity']['title'] == 'Special':
            special.append(joe)
        elif joe['rarity']['title'] == 'Fundamental':
            fundamental.append(joe)
        elif joe['rarity']['title'] == 'Joesus Christ':
            joe['image_url'] = 'https://www.digiseller.ru/preview/599286/p1_2134247_b8bd3e19.png'
            joesus.append(joe)
    # Handle randomizing and weighting here
    results = []
    d = random.random()
    if d >= 0.05:
        joesus = []
    cards=[random.sample(joesus, len(joesus)),random.sample(mythic,len(mythic))[:1],random.sample(legendary,len(legendary))[:2],random.sample(rare, len(rare))[:3],random.sample(special, len(special))[:6],fundamental[:8]]
    for types in cards:
        for card in types:
            results.append(card)
    # Final shuffle
    results = random.sample(results, len(results))
    adminResult = adminCheck(discord)
    return render_template("lootbox.html", cards=results, user=user, check=discord.authorized, available=available, adminResult=adminResult)

# API
@app.route('/api/leaderboard')
def apiLeaderboard():
    jokemon = json.loads(dumps(list(db.jokemon.find())))
    return jsonify(jokemon)

@app.route('/api/updateSomething/bruhmoment/69/420/123123123123/wowowowowo/olotbocks')
@requires_authorization
def apiUpdateSomething():
    users = json.loads(dumps(list(db.users.find())))
    for user in users:
        db.users.update_one({'discordId':user['discordId']}, {"$set": {"lootboxes": {
            "opened": int(user['lootboxes']['opened']),
            "available" : int(user['lootboxes']['available']) + 1
        }}})
    return jsonify(users)

@app.route('/api/winner', methods=['POST'])
@requires_authorization
def apiWinner():
    user = discord.fetch_user()
    user_data = json.loads(dumps(db.users.find_one({"discordId": int(json.loads(request.data)['discordId'])})))
    if (int(user_data['lootboxes']['available']) > 0):
        if (user_data):
            jokemon = json.loads(dumps(list(db.jokemon.find())))
            joes = json.loads(dumps(list(db.jokemon.find())))
            joesus = []
            mythic = []
            legendary = []
            rare = []
            special = []
            fundamental = []
            for joe in joes:
                if joe['rarity']['title'] == 'Mythic':
                    mythic.append(joe)
                elif joe['rarity']['title'] == 'Legendary':
                    legendary.append(joe)
                elif joe['rarity']['title'] == 'Rare':
                    rare.append(joe)
                elif joe['rarity']['title'] == 'Special':
                    special.append(joe)
                elif joe['rarity']['title'] == 'Fundamental':
                    fundamental.append(joe)
                elif joe['rarity']['title'] == 'Joesus Christ':
                    joe['image_url'] = 'https://www.digiseller.ru/preview/599286/p1_2134247_b8bd3e19.png'
                    joesus.append(joe)
            results = []
            winner = None
            rng = random.SystemRandom()
            d = rng.random()
            if d > 0 and d <= 0.4:
                winner = secrets.choice(fundamental)
            elif d > 0.4 and d <= 0.7:
                winner = secrets.choice(special)
            elif d > 0.7 and d <= 0.85:
                winner = secrets.choice(rare)
            elif d > 0.85 and d <= 0.96:
                winner = secrets.choice(legendary)
            elif d > 0.97 and d < 0.99:
                winner = secrets.choice(mythic)
            elif d >= 0.99 and d < 1:
                winner = secrets.choice(joesus)
            else:
                winner = secrets.choice(fundamental)
            newInv = user_data['inventory']
            newInv.append(winner['title'])
            newPoints = updatePoints(user_data)
            db.jokemon.update_one({'title':winner['title']}, {"$set": {"obtained": int(winner['obtained']) + 1 }})
            db.users.update_one({'discordId':user_data['discordId']}, {"$set": {"inventory": list(newInv), "stats":{"cards" : (int(user_data['stats']['cards']) + 1), "points": newPoints, "wins": int(user_data['stats']['wins']), "losses": int(user_data['stats']['losses'])}, "lootboxes" : {"opened" : int(user_data['lootboxes']['opened'])+1, "available": int(user_data['lootboxes']['available'])-1} }})
            return jsonify(winner)
    return jsonify({"status":"No loot boxes available"})

def updatePoints(user_data):
    pts = 0
    for card in user_data['inventory']:
        joe = json.loads(dumps(db.jokemon.find_one({"title": card})))
        if joe['rarity']['title'] == 'Mythic':
            pts += 50
        elif joe['rarity']['title'] == 'Legendary':
            pts += 25
        elif joe['rarity']['title'] == 'Rare':
            pts += 10
        elif joe['rarity']['title'] == 'Special':
            pts += 5
        elif joe['rarity']['title'] == 'Fundamental':
            pts += 3
        elif joe['rarity']['title'] == 'Joesus Christ':
            pts += 100
    return pts

def updatePointsTrade(inv):
    pts = 0
    for card in inv:
        joe = json.loads(dumps(db.jokemon.find_one({"title": card})))
        if joe['rarity']['title'] == 'Mythic':
            pts += 50
        elif joe['rarity']['title'] == 'Legendary':
            pts += 25
        elif joe['rarity']['title'] == 'Rare':
            pts += 10
        elif joe['rarity']['title'] == 'Special':
            pts += 5
        elif joe['rarity']['title'] == 'Fundamental':
            pts += 3
        elif joe['rarity']['title'] == 'Joesus Christ':
            pts += 100
    return pts

online_users = []
awaiting_trade = []
in_trade = []
@app.route('/trade')
def trade():
    inv = []
    if (discord.authorized):
        user = discord.fetch_user()
        discordTag = user.name + "#" + user.discriminator
        user_data = json.loads(dumps(db.users.find_one({"discordId": user.id})))
        for card in user_data['inventory']:
            inv.append(json.loads(dumps(db.jokemon.find_one({"title": card}))))
    else:
        discordTag = None
    adminResult = adminCheck(discord)
    players = json.loads(dumps(list(db.users.find())))
    return render_template("online.html", players=players, check=discord.authorized, adminResult=adminResult, discordTag=discordTag, inv=inv)

# Websocket Events
@socketio.on('connect')
def connection():
    if (discord.authorized):
        user = discord.fetch_user()
        dupCheck = next((x for x in online_users if x['discordId'] == int(user.id)), None)
        if (dupCheck):
            online_users.remove(dupCheck)
        online_users.append({'sessionId': request.sid,'discordId': user.id, 'discordTag': user.name + "#" + user.discriminator, 'name': user.name, 'avatar_url': user.avatar_url})
        emit('userUpdate', online_users, broadcast=True)

@socketio.on('disconnect')
def disconnect():
    if (discord.authorized):
        # print("--------Awaiting---------")
        # print(awaiting_trade)
        # print("--------In trade---------")
        # print(in_trade)
        user = discord.fetch_user()
        userCheck = next((x for x in online_users if x['discordId'] == int(user.id)), None)
        if userCheck != None:
            online_users.remove(userCheck)
        aTradeCheck = next((x for x in awaiting_trade if x['offeringUserDiscordId'] == int(user.id)), None)
        if aTradeCheck != None:
            awaiting_trade.remove(aTradeCheck)
        iTradeCheck = next((x for x in in_trade if (x['offeringUserDiscordId'] == int(user.id) or x['requestedUserDiscordId'] == int(user.id))), None)
        if iTradeCheck != None:
            in_trade.remove(iTradeCheck)
            if (iTradeCheck['offeringUserDiscordId'] == user.id):
                emit('tradeAbandon', room=next((x for x in online_users if x['discordId'] == iTradeCheck['requestedUserDiscordId']), None)['sessionId'])
            else:
                emit('tradeAbandon', room=next((x for x in online_users if x['discordId'] == iTradeCheck['offeringUserDiscordId']), None)['sessionId'])
        emit('userUpdate', online_users, broadcast=True)

@socketio.on('wtt', namespace='/tradesocket')
def wantToTrade(payload):
    print(awaiting_trade)
    if (discord.authorized):
        user = discord.fetch_user()
        requestedUser = payload['discordTag']
        requestedUserSid = next((x for x in online_users if x['discordTag'] == requestedUser), None)
        offeringUser = next((x for x in online_users if x['discordId'] == int(user.id)), None)
        if (requestedUser and requestedUserSid and offeringUser):
            tradeCheck = next((x for x in awaiting_trade if (x['offeringUserDiscordId'] == requestedUserSid['discordId'] and x['requestedUserDiscordId'] == int(user.id))), None)
            if (tradeCheck):
                awaiting_trade.remove(tradeCheck)
                in_trade.append(tradeCheck)
                emit('tradeConnected', offeringUser['discordTag'] , room=next((x for x in online_users if x['discordId'] == tradeCheck['offeringUserDiscordId']), None)['sessionId'])
                emit('tradeConnected', requestedUserSid['discordTag'], room=next((x for x in online_users if x['discordId'] == tradeCheck['requestedUserDiscordId']), None)['sessionId'])
            else:
                awaiting_trade.append({
                    'offeringUserDiscordId':int(user.id),
                    'requestedUserDiscordId':int(requestedUserSid['discordId']),
                    'offeringUserSid': offeringUser['sessionId'],
                    'requestUserSid': requestedUserSid['sessionId'],
                    'offeringUser': offeringUser,
                    'requestedUser': requestedUserSid,
                    'offeringUserOffer': [],
                    'requestedUserOffer' : [],
                    "offeringUserLockedIn": False,
                    "requestedUserLockedIn": False,
                    "offeringUserAccepted": False,
                    "requestedUserAccepted": False,
                    "processing": False
                    })
        #emit('newTradeRequest', offeringUser, room=requestedUserSid['sessionId']) #Make this alert the user

@socketio.on('lockedIn', namespace="/tradesocket")
def lockedIn():
    user = discord.fetch_user()
    trade = next((x for x in in_trade if (x['offeringUserDiscordId'] == int(user.id) or x['requestedUserDiscordId'] == int(user.id))), None)
    if trade['offeringUserDiscordId'] == int(user.id):
        trade['offeringUserLockedIn'] = True
        emit('lockedIn', room=trade['requestUserSid'])
    else:
        trade['requestedUserLockedIn'] = True
        emit('lockedIn', room=trade['offeringUserSid'])

@socketio.on('unlockedIn', namespace="/tradesocket")
def unlockedIn():
    user = discord.fetch_user()
    trade = next((x for x in in_trade if (x['offeringUserDiscordId'] == int(user.id) or x['requestedUserDiscordId'] == int(user.id))), None)
    if trade['offeringUserDiscordId'] == int(user.id):
        trade['offeringUserLockedIn'] = False
        emit('unlockedIn', room=trade['requestUserSid'])
    else:
        trade['requestedUserLockedIn'] = False
        emit('unlockedIn', room=trade['offeringUserSid'])

@socketio.on('accept', namespace="/tradesocket")
def accept():
    user = discord.fetch_user()
    trade = next((x for x in in_trade if (x['offeringUserDiscordId'] == int(user.id) or x['requestedUserDiscordId'] == int(user.id))), None)
    if trade['offeringUserDiscordId'] == int(user.id):
        if (trade['offeringUserLockedIn'] == True):
            trade['offeringUserAccepted'] = True
            emit('accepted', room=trade['requestUserSid'])
    else:
        if (trade['requestedUserLockedIn'] == True):
            trade['requestedUserAccepted'] = True
            emit('accepted', room=trade['offeringUserSid'])

@socketio.on('process', namespace="/tradesocket")
def process():
    user = discord.fetch_user()
    trade = next((x for x in in_trade if (x['offeringUserDiscordId'] == int(user.id) or x['requestedUserDiscordId'] == int(user.id))), None)
    if trade["offeringUserAccepted"] == True and trade["requestedUserAccepted"] == True:
        if trade['processing'] == False:
            trade['processing'] == True
            user1 = json.loads(dumps(db.users.find_one({"discordId": trade['offeringUserDiscordId']})))
            user1inv = user1['inventory']
            for item in trade['offeringUserOffer']:
                user1inv.remove(item['title'])
            for item in trade['requestedUserOffer']:
                user1inv.append(item['title'])
            user2 = json.loads(dumps(db.users.find_one({"discordId": trade['requestedUserDiscordId']})))
            user2inv = user2['inventory']
            for item in trade['requestedUserOffer']:
                user2inv.remove(item['title'])
            for item in trade['offeringUserOffer']:
                user2inv.append(item['title'])
            user1points = updatePointsTrade(user1inv)
            user2points = updatePointsTrade(user2inv)
            db.users.update_one({'discordId': trade['offeringUserDiscordId']}, {"$set": {"inventory": user1inv, "stats":{"cards" : len(user1inv), "points": user1points, "wins": int(user1['stats']['wins']), "losses": int(user1['stats']['losses'])}, "lootboxes" : {"opened" : int(user1['lootboxes']['opened']), "available": int(user1['lootboxes']['available'])} }})
            db.users.update_one({'discordId': trade['requestedUserDiscordId']}, {"$set": {"inventory": user2inv, "stats":{"cards" : len(user2inv), "points": user2points, "wins": int(user2['stats']['wins']), "losses": int(user2['stats']['losses'])}, "lootboxes" : {"opened" : int(user2['lootboxes']['opened']), "available": int(user2['lootboxes']['available'])} }})
            emit('completed', room=trade['requestUserSid'])
            emit('completed', room=trade['offeringUserSid'])

@socketio.on('add', namespace="/tradesocket")
def addToTrade(payload):
    user = discord.fetch_user()
    trade = next((x for x in in_trade if (x['offeringUserDiscordId'] == int(user.id) or x['requestedUserDiscordId'] == int(user.id))), None)
    if trade['offeringUserDiscordId'] == int(user.id):
        if (trade['offeringUserLockedIn'] == False):
            trade['offeringUserOffer'].append({'title':payload['title'], 'rarity':payload['rarity']})
            emit('offerAdd',{'title':payload['title'], 'rarity':payload['rarity']}, room=trade['requestUserSid'])
    else:
        if (trade['requestedUserLockedIn'] == False):
            trade['requestedUserOffer'].append({'title':payload['title'], 'rarity':payload['rarity']})
            emit('offerAdd',{'title':payload['title'], 'rarity':payload['rarity']}, room=trade['offeringUserSid'])

@socketio.on('remove', namespace="/tradesocket")
def removeFromTrade(payload):
    user = discord.fetch_user()
    trade = next((x for x in in_trade if (x['offeringUserDiscordId'] == int(user.id) or x['requestedUserDiscordId'] == int(user.id))), None)
    if trade['offeringUserDiscordId'] == int(user.id):
        if (trade['offeringUserLockedIn'] == False):
            trade['offeringUserOffer'].remove({'title':payload['title'], 'rarity':payload['rarity']})
            emit('offerRemove', {'title':payload['title'], 'rarity':payload['rarity']}, room=trade['requestUserSid'])
    else:
        if (trade['requestedUserLockedIn'] == False):
            trade['requestedUserOffer'].remove({'title':payload['title'], 'rarity':payload['rarity']})
            emit('offerRemove', {'title':payload['title'], 'rarity':payload['rarity']}, room=trade['offeringUserSid'])

if __name__ == '__main__':
    socketio.run(app)

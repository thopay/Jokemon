from flask_socketio import SocketIO, send, emit
socketio = SocketIO(app)
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

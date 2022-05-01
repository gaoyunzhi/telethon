#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest, SearchRequest, SearchGlobalRequest
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import InputMessagesFilterEmpty, ChannelParticipantsSearch, InputPeerEmpty
import asyncio
from datetime import datetime
import time
import sys
import random
from telegram_util import matchKey
from settings import Settings
from cache import Cache
from helper import getClient, addMute, preProcess, getPostIds, getPeerId, getDisplayLink, getLink, deleteAll, unpinTranslated, addChannel, deleteOld, checkUserID, addMuteFromKick, kickAllInculdingChannels, checkUserChannel, checkMemberHistory, unkickAllInculdingChannels, replyTranslated, twitterBlock, twitterHideReply
import hashlib
import time

existing_private_chat_user = plain_db.loadKeyOnlyDB('existing_private_chat_user')
with open('credential') as f:
    credential = yaml.load(f, Loader=yaml.FullLoader)

def getLogMessage(group, message, client_name):
    id_info, fwd_info, client_info, additional_info = '', '', '', ''
    try:
        msg_id = message.peer_id.user_id
    except:
        msg_id = getPeerId(message.from_id)
    if msg_id:
        id_info = '[id](tg://user?id=%d): %d ' % (msg_id, msg_id)
    fwd_from = message.fwd_from and getPeerId(message.fwd_from.from_id)
    if fwd_from:
        fwd_info = 'fwd_id: %d ' % fwd_from
    if client_name != default_client_name:
        client_info = '%s ' % client_name
    return '%s%s%schat: %s' % (
        id_info,
        fwd_info,
        client_info,
        getDisplayLink(group, message, groups))

async def forwardPrivateDialog(clients):
    for client_name, client in clients.items():
        try:
            dialogs = await client.get_dialogs()
        except:
            print('get_dialogs fail', client_name)
            continue
        forward_group = await client.get_entity(1309758545)
        for dialog in dialogs:
            if not dialog.is_user:
                continue
            message = dialog.message
            if time.time() - datetime.timestamp(message.date) > 72 * 60 * 60:
                continue
            if existing_private_chat_user.contain(dialog.id):
                continue
            try:
                results = await client.forward_messages(forward_group, message.id, dialog.entity)
            except Exception as e:
                print('forwardPrivateDialog forward fail', str(e), client_name)
            log_message = getLogMessage(dialog.entity, message, client_name)
            try:
                await client.send_message(forward_group, log_message, link_preview=False)
            except Exception as e:
                print('forwardPrivateDialog log fail', str(e), client_name, log_message)
            existing_private_chat_user.add(dialog.id)

async def run():
    clients = {}
    for user, setting in credential['users'].items():
        client = TelegramClient('session_file_' + user, credential['api_id'], credential['api_hash'])
        try:
            await client.start(password=setting.get('password'))
        except:
            print(user, setting)
        clients[user] = client
    await forwardPrivateDialog(clients)
    for _, client in clients.items():
        await client.disconnect()
    
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    r = loop.run_until_complete(run())
    loop.close()
import yaml
import tweepy
from telethon.tl.functions.messages import GetHistoryRequest, SearchRequest
from telethon.tl.types import InputMessagesFilterEmpty
from telegram_util import matchKey, isCN, isInt
import datetime
from telethon import types
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights, ChannelParticipantsSearch
from telethon.tl.functions.channels import GetParticipantsRequest
import plain_db

namelist = plain_db.load('../../moderator/db/name', isIntValue=False)
kicklist = plain_db.loadKeyOnlyDB('../../moderator/db/kicklist')
mutelist = plain_db.loadKeyOnlyDB('../../moderator/db/mutelist')
translate_record = plain_db.loadLargeDB('translate_record')
translate_replied = plain_db.loadKeyOnlyDB('translate_replied')

with open('twitter_credential') as f:
    twitter_credential = yaml.load(f, Loader=yaml.FullLoader)

def getLinkFromId(group, message_id):
    try:
        if group.username:
            return 'https://t.me/%s/%d' % (group.username, message_id)
    except:
        ...
    return 'https://t.me/c/%s/%d' % (group.id, message_id)

def getChannelLink(entity):
    try:
        if entity.username:
            return 'https://t.me/%s' % entity.username
    except:
        ...
    return 'https://t.me/c/%s/10000' % entity.id

def getLink(group, message):
    return getLinkFromId(group, message.id)

def getClient(clients, setting):
    client_name = setting.get('client_name') or next(iter(clients.keys()))
    return client_name, clients[client_name]

def getPostIds(target_post, posts):
    if target_post.grouped_id:
        for post in posts[::-1]:
            if post.grouped_id == target_post.grouped_id:
                yield post.id
    else:
        yield target_post.id

def getPeerId(peer_id):
    for method in [lambda x: x.channel_id, 
        lambda x: x.chat_id, lambda x: x.user_id]:
        try:
            return method(peer_id)
        except:
            ...

async def unpinTranslated(client):
    chat = await client.get_entity(1386450222)
    messages = await client.get_messages(chat, filter=types.InputMessagesFilterPinned(), limit=500)
    for message in messages:
        if not message.raw_text:
            continue
        if matchKey(message.raw_text, ['已完成', '已翻译']):
            try:
                await client.unpin_message(chat, message.id)
            except Exception as e:
                print(e)
                return

async def replyTranslated(client):
    translated = set()
    for chat_id in [1742163696, 1240049600]:
        chat = await client.get_entity(chat_id)
        messages = await client.get_messages(chat, limit=100)
        for message in messages:
            text = message.raw_text or message.text or ''
            for i in range(len(text) - 9):
                snippet = text[i:i+10]
                if sum([isCN(x) for x in snippet]) > 5:
                    translated.add(text[i:i+10])
    chat = await client.get_entity(1347960785)
    messages = await client.get_messages(chat, limit=200)
    for message in messages:
        if message.fwd_from:
            continue
        text = message.raw_text or message.text or ''
        if not text:
            continue
        text = ''.join(text.split())
        translate_record.update(message.id, text)
    for message_id, text in translate_record.items():
        if translate_replied.contain(message_id):
            continue
        if message_id == 43381:
            print(text)
            print(translated)
        if not matchKey(text, translated):
            continue
        translate_replied.add(message_id)
        message = await client.get_messages(chat, ids=int(message_id))
        await message.reply('感谢！已发布~~')

async def checkMemberHistory(client):
    channel = await client.get_entity(1603460097)
    group_posts = await client(GetHistoryRequest(peer=channel, limit=30,
            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
    for message in group_posts.messages:
        if not message.raw_text:
            continue
        if message.raw_text.startswith('done'):
            continue
        result = 'done: ' + message.raw_text + '\n'
        dialogs = await client.get_dialogs()
        for dialog in dialogs:
            if message.raw_text.strip() in str(dialog.entity):
                break
        if message.raw_text.strip() not in str(dialog.entity):
            await client.edit_message(
                channel,
                message.id,
                text = result + 'group not found',
                parse_mode='Markdown',
                link_preview=False)
            continue
        participants = await client(GetParticipantsRequest(
            dialog.entity, ChannelParticipantsSearch(''), 0, 100, 0
        ))
        for user in participants.users:
            if kicklist.contain(user.id):
                result +='\n%d in kicklist %s' % (user.id, namelist.get(user.id, '[%s](tg://user?id=%d)' % (user.first_name, user.id)))
            if mutelist.contain(user.id):
                result +='\n%d in mutelist %s' % (user.id, namelist.get(user.id, '[%s](tg://user?id=%d)' % (user.first_name, user.id)))
        await client.edit_message(
            channel,
            message.id,
            text = result,
            parse_mode='Markdown',
            link_preview=False)

async def checkUserChannel(client):
    channel = await client.get_entity(1618113434)
    group_posts = await client(GetHistoryRequest(peer=channel, limit=30,
            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
    for message in group_posts.messages:
        if not message.raw_text:
            continue
        if message.raw_text.startswith('done'):
            break
        result = 'done: ' + message.raw_text
        dialogs = await client.get_dialogs()
        for dialog in dialogs:
            try:
                dialog.entity.participants_count
            except:
                continue
            if dialog.is_group:
                continue
            try:
                participants = await client(GetParticipantsRequest(
                    dialog.entity, ChannelParticipantsSearch(message.raw_text), 0, 100, 0
                ))
                if participants.users:
                    # print(participants.users[0])
                    result += ' [%s](%s)' % (dialog.title, getChannelLink(dialog.entity))
            except:
                ...
        await client.edit_message(
            channel,
            message.id,
            text = result,
            parse_mode='Markdown',
            link_preview=False)

async def deleteSingle(client, message):
    entity = await client.get_entity(getPeerId(message.peer_id))
    forward_group = await client.get_entity(1223777401)
    message_link = getLink(entity, message)
    if not message.grouped_id:
        try:
            await client.forward_messages(forward_group, message.id, entity)
            await client.send_message(forward_group, message_link)
            await client.delete_messages(entity, message.id)
            return 1
        except Exception as e:
            # print('delete failed', str(e), message_link)
            return 0
    messages = await client.get_messages(entity, min_id = message.id, max_id = message.id + 10)
    result = [message]
    for post in messages:
        if post.grouped_id and post.grouped_id == message.grouped_id:
            result.append(post)
    final_result = 0
    for post in result:
        try:
            await client.forward_messages(forward_group, post.id, entity)
            await client.delete_messages(entity, post.id)
            final_result += 1
        except Exception as e:
            # print('delete failed', str(e), message_link)
            ...
    await client.send_message(forward_group, message_link)
    return final_result

def getDisplayLink(group, message, groups):
    invitation_link = groups.get(group.id, {}).get('invitation_link')
    suffix = ''
    if message.reply_to and message.reply_to.reply_to_msg_id:
        suffix += ' [主贴](%s)' % getLinkFromId(group, message.reply_to.reply_to_msg_id)
    if invitation_link:
        suffix += ' [进群](%s)' % invitation_link
    try:
        title = group.title
    except:
        title = '%s %s' % (group.first_name, group.last_name or '')
        if group.username:
            title += ' @' + group.username
    return '[%s](%s)%s' % (title, getLink(group, message), suffix)

async def addChannelSingle(clients, text, S):
    client_names = list(clients.keys())
    client_names.remove('yun')
    client_names.append('yun')
    group = None
    try:
        text = int(text)
    except:
        ...
    group = None
    for client_name in client_names:
        dialogs = await clients[client_name].get_dialogs()
        for dialog in dialogs:
            if dialog.entity.id == text:
                group = dialog.entity
                break
            if str(text) in str(dialog.entity) and dialog.entity.id != 1475165266:
                group = dialog.entity
                break
        if group:
            break
    if not group:
        return 'group not find'
    if group.id in S.groups:
        return 'group exists ' + str(group.id)
    setting = {'client_name': client_name, 'promoting': 0, 'kicked': 0, 'newly_added': 1}
    try:
        if group.username:
            setting['username'] = group.username
    except:
        ...
    if 'joinchat' in str(text):
        setting['invitation_link'] = text
    setting['title'] = group.title
    S.groups[group.id] = setting
    with open('groups.yaml', 'w') as f:
        f.write(yaml.dump(S.groups, sort_keys=True, indent=2, allow_unicode=True)) 
    return 'success'

async def addChannel(clients, S):
    client = clients['yun']
    channel = await client.get_entity(1475165266)
    group_posts = await client(GetHistoryRequest(peer=channel, limit=30,
            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
    count = 0
    for message in group_posts.messages:
        if not message.raw_text or message.raw_text.startswith('done'):
            continue
        result = await addChannelSingle(clients, message.raw_text, S)
        await client.edit_message(
            channel,
            message.id,
            text = 'done %s: %s' % (message.raw_text, result))

async def addMuteFromKick(clients, S):
    client = clients['yun']
    channel = await client.get_entity(1321042743)
    group_posts = await client(GetHistoryRequest(peer=channel, limit=30,
            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
    count = 0
    for message in group_posts.messages:
        mute_key = message.raw_text or ''
        mute_key = mute_key.split(':')[0].split()[-1]
        if not isInt(mute_key) or int(mute_key) < 1000:
            continue
        if mute_key not in S.mute_keywords:
            S.mute_keywords.append(mute_key)
            count += 1
    S.save()
    if count: 
        channel = await client.get_entity(S.mute_channel_id)
        await client.send_message(channel, 'mute id added: %d from kick log' % count)

async def twitterBlockPerChannel(clients, channel_id, forward_to_subscribe=False):
    client = clients['yun']
    channel = await client.get_entity(channel_id)
    group_posts = await client(GetHistoryRequest(peer=channel, limit=30,
            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
    for message in group_posts.messages:
        if not message.raw_text or message.raw_text.startswith('done'):
            continue
        screen_name = message.raw_text.strip().split()[0].split('/')[-1]
        for _, twitter_user_setting in twitter_credential['users'].items():
            auth = tweepy.OAuthHandler(twitter_credential['consumer_key'], twitter_credential['consumer_secret'])
            auth.set_access_token(twitter_user_setting['access_key'], twitter_user_setting['access_secret'])
            api = tweepy.API(auth)
            result = api.create_block(screen_name=screen_name)
        await client.edit_message(
            channel,
            message.id,
            text = 'done https://twitter.com/%s' % screen_name) # see if I need to add more information here
        if forward_to_subscribe:
            sub_channel = await clients['zhou'].get_entity(1702897525)
            await clients['zhou'].send_message(sub_channel, '/tw_sub %s' % screen_name)
            await clients['zhou'].send_message(sub_channel, '/tw_sub https://twitter.com/%s' % screen_name)
        return True # only block one account at one time

async def twitterBlock(clients):
    result = await twitterBlockPerChannel(clients, 1581263596, forward_to_subscribe=True)
    if result:
        return
    result = await twitterBlockPerChannel(clients, 1628388704, forward_to_subscribe=False)

async def twitterHideReply(client):
    channel = await client.get_entity(1717826288)
    group_posts = await client(GetHistoryRequest(peer=channel, limit=200,
            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
    for message in group_posts.messages:
        if not message.raw_text or message.raw_text != 'h':
            continue
        if not message.reply_to_msg_id:
            continue
        origin_message = await client.get_messages(channel, ids=message.reply_to_msg_id)
        raw_text = origin_message.raw_text
        if not raw_text:
            continue
        for twitter_at in raw_text.split():
            twitter_account = twitter_at[1:]
            twitter_user_setting = twitter_credential['users'].get(twitter_account)
            if twitter_user_setting:
                break
        if not twitter_user_setting:
            continue
        twitter_client = tweepy.Client(
            bearer_token=twitter_credential['bearer_token'],
            consumer_key=twitter_credential['consumer_key'],
            consumer_secret=twitter_credential['consumer_secret'],
            access_token=twitter_user_setting['access_key'],
            access_token_secret=twitter_user_setting['access_secret'])
        twitter_url = origin_message.entities[-1].url
        try:
            twitter_client.hide_reply(int(twitter_url.split('/')[-1]))
            await client.edit_message(
                channel,
                message.id,
                text = 'hidden')
        except:
            await client.edit_message(
                channel,
                message.id,
                text = 'hide fail')

async def kickAllInculdingChannels(clients, S, 
        main_channel_id=1589897379, chat_rights = ChatBannedRights(until_date=None, view_messages=True),
        action_text = 'kicked'):
    client = clients['yun']
    channel = await client.get_entity(main_channel_id)
    group_posts = await client(GetHistoryRequest(peer=channel, limit=30,
            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
    groups = None
    for message in group_posts.messages:
        if not message.raw_text or message.raw_text.startswith('done'):
            continue
        try:
            if isInt(message.raw_text):
                user_id = int(message.raw_text)
            else:
                user_id = message.raw_text.strip()
            # await client.get_dialogs()
            # await client.get_entity('tch1658')
            # await client.get_participants('three001')
            user = await client.get_entity(user_id)
        except Exception as e:
            print(e)
            continue
        count = 0
        if not groups:
            groups = await client.get_dialogs()
        for group in groups:
            try:
                group.entity.participants_count
                group.entity.title
            except:
                continue
            if not group.entity.participants_count or group.entity.participants_count < 10:
                continue
            if matchKey(group.entity.title, ['辟谣', '闢謠']):
                continue
            if not group.entity.admin_rights:
                continue
            # print('kick from channel/group:', group.entity.title)
            try:
                result = await client(EditBannedRequest(
                    group, user, chat_rights))
                count += 1
            except:
                ...
        await client.edit_message(
            channel,
            message.id,
            text = 'done %s: %s %d times' % (message.raw_text, action_text, count))
        return # only kick one at a time


async def unkickAllInculdingChannels(clients, S): 
    await kickAllInculdingChannels(clients, S, main_channel_id=1621077636,
        chat_rights=ChatBannedRights(until_date=None, view_messages=False), action_text='unkicked')

async def addMute(client, S):
    channel = await client.get_entity(S.mute_channel_id)
    group_posts = await client(GetHistoryRequest(peer=channel, limit=30,
            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
    count = 0
    for message in group_posts.messages:
        if not message.raw_text or message.raw_text.startswith('mute id added:'):
            continue
        mute_key = message.raw_text
        if not isCN(mute_key) and len(mute_key) < 3:
            continue
        if isInt(mute_key):
            mute_key = int(mute_key)
        if mute_key not in S.mute_keywords:
            S.mute_keywords.append(mute_key)
            count += 1
    S.save()
    if count: 
        await client.send_message(channel, 'mute id added: ' + str(count))

async def deleteTarget(client, target):
    if len(target) < 3:
        return 0
    if (not isCN(target)) and len(target) < 5:
        return 0
    dialogs = await client.get_dialogs()
    result = []
    for dialog in dialogs:
        if type(dialog.entity).__name__ == 'User':
            continue
        try:
            if dialog.entity.participants_count < 20:
                continue
        except:
            print(dialog)
            continue
        messages = await client.get_messages(entity=dialog.entity, search=target, limit=50)
        messages = [message for message in messages if target in message.text]
        result += messages
    result = [message for message in result if target in message.text]    
    result = [message for message in result if not matchKey(message.text, ['【保留】', '【不删】'])]
    if len(result) > 200:
        print('too many matches for delete: %s, %d', target, len(result))
        return 0
    final_result = 0
    for message in result:
        final_result += await deleteSingle(client, message)
    return final_result

async def deleteOldForGroup(client, group, dry_run = False, hour_cut = 20):
    user = await client.get_me()
    result = await client(SearchRequest(
        peer=group,     # On which chat/conversation
        q='',           # What to search for
        filter=InputMessagesFilterEmpty(),  # Filter to use (maybe filter for media)
        min_date=None,  # Minimum date
        max_date=None,  # Maximum date
        offset_id=0,    # ID of the message to use as offset
        add_offset=0,   # Additional offset
        limit=1000,       # How many results
        max_id=0,       # Maximum message ID
        min_id=0,       # Minimum message ID
        from_id=user,
        hash=0
    ))
    max_id = None
    count = 0
    for message in result.messages:
        if not max_id:
            max_id = message.id
            continue
        if int((datetime.datetime.now(datetime.timezone.utc) - message.date)
            .total_seconds()) < 60 * 60 * hour_cut:
            continue
        if max_id - message.id < 50:
            continue
        if not message.from_id or getPeerId(message.from_id) != user.id:
            continue
        if dry_run:
            count += 1
        else:
            result = await deleteSingle(client, message)
            count += result
    return count

async def checkUserID(client_map, S, C):
    client = client_map['yun']
    channel = await client.get_entity(S.check_id_channel_id)
    group_posts = await client(GetHistoryRequest(peer=channel, limit=30,
            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
    for message in group_posts.messages:
        text = message.raw_text
        if not text:
            continue
        if not text.startswith('https://t.me'):
            continue
        if len(text.split()) > 1:
            continue
        target_message_id = int(text.split('/')[-1])
        if len(text.split('/')) == 5:
            target_channel_key = '/'.join(text.split('/')[:-1])
            for _, tmp_client in client_map.items():
                try:
                    await C.getPosts(tmp_client, target_channel_key, S) # to populate id map
                    target_channel = await C.getChannel(tmp_client, target_channel_key, S)
                    break
                except:
                    ...
        else:
            target_channel_id = int(text.split('/')[-2])
            for _, tmp_client in client_map.items():
                try:
                    target_channel = await tmp_client.get_entity(target_channel_id)
                    break
                except:
                    ...
        target_message = await tmp_client.get_messages(target_channel, ids=target_message_id)
        if target_message:
            user_id = getPeerId(target_message.from_id)
        else:
            user_id = 0
        await client.edit_message(
            channel,
            message.id,
            text = 'done: %s user_id: %d' % (text, user_id))

async def deleteAll(client_map, S):
    client_names = list(client_map.keys())
    client_names.remove('yun')
    client_names = ['yun'] + client_names
    clients = [client_map[name] for name in client_names]
    client = clients[0]
    channel = await client.get_entity(S.delete_all_channel_id)
    group_posts = await client(GetHistoryRequest(peer=channel, limit=30,
            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
    for message in group_posts.messages:
        if not message.raw_text:
            continue
        if message.raw_text.startswith('done'):
            break
        result = 0
        for tmp_client in clients:
            result += await deleteTarget(tmp_client, message.raw_text)
        await client.edit_message(
            channel,
            message.id,
            text = 'done: %s deleted: %d' % (message.raw_text, result))

async def preProcess(clients, groups):
    for gid, setting in list(groups.items()):
        try:
            int(gid)
            continue
        except:
            ...
        _, client = getClient(clients, setting)
        group = await client.get_entity(gid)
        if group.username:
            setting['username'] = group.username
        if 'joinchat' in str(gid):
            setting['invitation_link'] = gid
        setting['title'] = group.title
        del groups[gid]
        groups[group.id] = setting
        with open('groups.yaml', 'w') as f:
            f.write(yaml.dump(groups, sort_keys=True, indent=2, allow_unicode=True))
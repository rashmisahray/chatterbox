import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)   
app.secret_key = 'super_secret_synthetic_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# --- In-Memory Data Store & Synthetic Data ---

# Users
# Status: online, away, busy, offline
USERS = {
    '1': {'id': '1', 'name': 'Alice 👩', 'avatar': 'https://api.dicebear.com/9.x/avataaars/svg?seed=Alice&top=LongHairBob,LongHairCurly', 'status': 'online'},
    '2': {'id': '2', 'name': 'Bob 👨', 'avatar': 'https://api.dicebear.com/9.x/avataaars/svg?seed=Bob&top=ShortHairTheCaesar&facialHair=BeardMedium', 'status': 'away'},
    '3': {'id': '3', 'name': 'Charlie 👨', 'avatar': 'https://api.dicebear.com/9.x/avataaars/svg?seed=Charlie&top=ShortHairShortFlat', 'status': 'busy'},
    '4': {'id': '4', 'name': 'David 👨', 'avatar': 'https://api.dicebear.com/9.x/avataaars/svg?seed=David&top=ShortHairShortRound', 'status': 'online'},
    '5': {'id': '5', 'name': 'Eve 👨', 'avatar': 'https://api.dicebear.com/9.x/avataaars/svg?seed=Eve&top=ShortHairTheCaesarSidePart', 'status': 'offline'},
}

# Chat Sessions
# id: unique chat id
# type: 'private' or 'group'
# participants: list of user_ids
# name: (optional for private) group name
# messages: list of message objects
CHATS = {
    'chat_1_2': {
        'id': 'chat_1_2',
        'type': 'private',
        'participants': ['1', '2'],
        'messages': [
            {'sender_id': '2', 'content': 'Hello Alice!', 'timestamp': '10:00 AM'},
            {'sender_id': '1', 'content': 'Hi Bob, how are you?', 'timestamp': '10:05 AM'},
            {'sender_id': '2', 'content': 'I am good, just working on the new project.', 'timestamp': '10:06 AM'},
        ]
    },
    'chat_1_3': {
        'id': 'chat_1_3',
        'type': 'private',
        'participants': ['1', '3'],
        'messages': [
            {'sender_id': '3', 'content': 'Hey, are we free for a call?', 'timestamp': 'Yesterday'},
        ]
    },
    'group_1': {
        'id': 'group_1',
        'type': 'group',
        'name': 'Project Alpha',
        'participants': ['1', '2', '3', '4'],
        'avatar': 'https://api.dicebear.com/7.x/initials/svg?seed=PA',
        'messages': [
            {'sender_id': '4', 'content': 'Guys, we need to deploy today.', 'timestamp': '09:00 AM'},
            {'sender_id': '2', 'content': 'I am ready.', 'timestamp': '09:05 AM'},
            {'sender_id': '3', 'content': 'Give me 10 mins.', 'timestamp': '09:10 AM'},
        ]
    }
}

# Helper to find user by name (for login)
def get_user_by_name(name):
    for uid, user in USERS.items():
        if user['name'].lower() == name.lower():
            return user
    return None

# --- Routes ---

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_user = USERS.get(session['user_id'])
    if not current_user:
        session.pop('user_id', None)
        return redirect(url_for('login'))
        
    return render_template('index.html', current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        user = get_user_by_name(username)
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="User not found. Try 'Alice', 'Bob', or 'Charlie' or Sign Up.")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        display_name = request.form.get('display_name') or username
        gender = request.form.get('gender')
        
        if get_user_by_name(username):
            return render_template('register.html', error="Username already exists.")
        
        # Avatar Logic based on Gender
        base_avatar_url = f'https://api.dicebear.com/9.x/avataaars/svg?seed={username}'
        
        if gender == 'male':
            # Strict Male: Short hair styles + facial hair probability
            avatar_url = f"{base_avatar_url}&top=ShortHairTheCaesar,ShortHairShortFlat,ShortHairShortRound,ShortHairTheCaesarSidePart&facialHair=BeardLight,BeardMedium,BeardMajestic,MoustacheFancy&facialHairProbability=100"
            display_name = f"{display_name} 👨"
        elif gender == 'female':
             # Strict Female: Long hair styles, no facial hair
             avatar_url = f"{base_avatar_url}&top=LongHairBigHair,LongHairBob,LongHairCurly,LongHairStraight,LongHairCurvy,LongHairMiaWallace&facialHairProbability=0"
             display_name = f"{display_name} 👩"
        else:
             avatar_url = base_avatar_url
             display_name = f"{display_name} 👨" # Default to Man emoji as requested for "Rest"
        
        # Create new user
        new_id = str(len(USERS) + 1)
        new_user = {
            'id': new_id,
            'name': display_name,
            'avatar': avatar_url,
            'status': 'online'
        }
        USERS[new_id] = new_user
        session['user_id'] = new_id
        return redirect(url_for('index'))
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# --- API Endpoints ---

@app.route('/api/init')
def api_init():
    """Returns initial data: sidebar list, current user info"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    current_user_id = session['user_id']
    
    # Build Sidebar List
    sidebar_items = []
    
    # 1. Existing Chats (Groups and Private)
    existing_private_chats = {} # Map other_user_id -> chat_id
    
    for chat_id, chat in CHATS.items():
        if current_user_id in chat['participants']:
            # If private, track who we are talking to
            if chat['type'] == 'private':
                other_id = next((pid for pid in chat['participants'] if pid != current_user_id), None)
                if other_id:
                    existing_private_chats[other_id] = chat_id
            
            # Add to list
            item = {
                'chat_id': chat_id,
                'type': chat['type'],
                'unread': 0, 
                'last_message': chat['messages'][-1]['content'] if chat['messages'] else ""
            }
            
            if chat['type'] == 'private':
                other_id = next((pid for pid in chat['participants'] if pid != current_user_id), None)
                if other_id and other_id in USERS:
                    other_user = USERS[other_id]
                    item['name'] = other_user['name']
                    item['avatar'] = other_user['avatar']
                else:
                    item['name'] = "Unknown"
                    item['avatar'] = ""
            else:
                item['name'] = chat.get('name', 'Group Chat')
                item['avatar'] = chat.get('avatar', '')
            
            sidebar_items.append(item)
            
    # 2. Add ALL other users (Potential Chats) if not already in a private chat
    for uid, user in USERS.items():
        if uid != current_user_id and uid not in existing_private_chats:
            # Determine a deterministic chat ID (but don't create it in memory yet? 
            # Or simpler: Create it in memory now to make logic identical)
            
            # Let's create it on the fly if user sends a message? 
            # Or better: "Virtual" chat item.
            # actually, frontend expects chat_id to load history. 
            # Easiest way: Use a consistent ID format "chat_min_max" and return it.
            # App logic will create it dynamically if it doesn't exist in CHATS when accessed?
            # Or we can just pre-create them? 
            # Pre-creating is safest for this simple demo.
            
            p1, p2 = sorted([current_user_id, uid])
            chat_id = f"chat_{p1}_{p2}"
            
            if chat_id not in CHATS:
                CHATS[chat_id] = {
                    'id': chat_id,
                    'type': 'private',
                    'participants': [p1, p2],
                    'messages': []
                }
            
            sidebar_items.append({
                'chat_id': chat_id,
                'type': 'private',
                'name': user['name'],
                'avatar': user['avatar'],
                'unread': 0,
                'last_message': 'Start a conversation'
            })

    return jsonify({
        'user': USERS[current_user_id],
        'sidebar': sidebar_items
    })

@app.route('/api/chat/<chat_id>')
def get_chat_history(chat_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    chat = CHATS.get(chat_id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
        
    if session['user_id'] not in chat['participants']:
        return jsonify({'error': 'Access denied'}), 403
        
    enriched_messages = []
    for msg in chat['messages']:
        sender = USERS.get(msg['sender_id'])
        enriched_messages.append({
            'sender_id': msg['sender_id'],
            'sender_name': sender['name'] if sender else 'Unknown',
            'avatar': sender['avatar'] if sender else '',
            'content': msg['content'],
            'timestamp': msg['timestamp'],
            'is_me': msg['sender_id'] == session['user_id']
        })
        
    chat_info = {
        'id': chat['id'],
        'type': chat['type'],
    }
    if chat['type'] == 'private':
        other_id = next((pid for pid in chat['participants'] if pid != session['user_id']), None)
        other = USERS.get(other_id)
        chat_info['name'] = other['name'] if other else 'Unknown'
        chat_info['status'] = other['status'] if other else 'offline'
        chat_info['avatar'] = other['avatar'] if other else ''
    else:
        chat_info['name'] = chat.get('name', 'Group')
        chat_info['status'] = f"{len(chat['participants'])} members"
        chat_info['avatar'] = chat.get('avatar', '')

    return jsonify({
        'chat_info': chat_info,
        'messages': enriched_messages
    })

@app.route('/api/users')
def api_users():
    """List all users except current one for group creation"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = []
    for uid, u in USERS.items():
        if uid != session['user_id']:
            users.append({'id': u['id'], 'name': u['name'], 'avatar': u['avatar']})
    return jsonify(users)

@app.route('/api/profile/update', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    uid = session['user_id']
    data = request.json
    
    new_name = data.get('name')
    gender = data.get('gender')
    
    if uid in USERS:
        user = USERS[uid]
        
        # Determine emoji based on gender (new or existing)
        # We need to know the intended gender to pick emoji.
        # If gender passed, use it. If not, guess from existing avatar? Or just keep existing name?
        # Let's assume strict update:
        
        target_gender = gender if gender else 'neutral' # Default fallback if only name changed?
        # Actually, if gender is "no change" (empty), we shouldn't change the emoji unless we know the old one.
        # But for this task, the user likely selects gender in the modal.
        
        emoji_suffix = ""
        if gender == 'male':
            emoji_suffix = " 👨"
        elif gender == 'female':
            emoji_suffix = " 👩"
        elif gender == 'neutral': # Non-binary in dropdown
             emoji_suffix = " 👨"
        
        if new_name:
            # Strip existing emojis to avoid duplication
            clean_name = new_name.replace(' 👨', '').replace(' 👩', '')
            if gender:
                user['name'] = f"{clean_name}{emoji_suffix}"
            else:
                 # If no gender update, keep name as is (user might have edited emoji manually)
                 user['name'] = new_name
            
        if gender:
            # Re-generate avatar based on original seed (username) but new gender
            base_seed = user['name'].split(' ')[0] # Hack: Use first part of name as seed to avoid emoji in seed
            base_url = f'https://api.dicebear.com/9.x/avataaars/svg?seed={base_seed}'
            
            if gender == 'male':
                user['avatar'] = f"{base_url}&top=ShortHairTheCaesar,ShortHairShortFlat,ShortHairShortRound,ShortHairTheCaesarSidePart&facialHair=BeardLight,BeardMedium,BeardMajestic,MoustacheFancy&facialHairProbability=100"
                # If name wasn't updated, update it now to add emoji?
                if not new_name:
                     user['name'] = user['name'].replace(' 👨', '').replace(' 👩', '') + " 👨"
            elif gender == 'female':
                 user['avatar'] = f"{base_url}&top=LongHairBigHair,LongHairBob,LongHairCurly,LongHairStraight,LongHairCurvy,LongHairMiaWallace&facialHairProbability=0"
                 if not new_name:
                     user['name'] = user['name'].replace(' 👨', '').replace(' 👩', '') + " 👩"
            # else keep existing or reset? unique case.
            
    return jsonify({'status': 'success'})

@app.route('/api/group/create', methods=['POST'])
def create_group():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    name = data.get('name')
    participants = data.get('participants', [])
    
    if not name:
        return jsonify({'error': 'Name is required'}), 400
        
    # Ensure all selected participants are valid
    valid_participants = [session['user_id']] # Always include self
    for pid in participants:
         if pid in USERS and pid != session['user_id']:
             valid_participants.append(pid)
             
    # If no one selected, fallback to just self or error? 
    # Let's fallback to "Just me" or "All" if empty? 
    # User asked for "Add people", so if they select none, it's a defined group of 1.
    
    new_id = f"group_{len(CHATS) + 1}_{int(datetime.now().timestamp())}"
    
    new_chat = {
        'id': new_id,
        'type': 'group',
        'name': name,
        'participants': valid_participants,
        'avatar': f'https://api.dicebear.com/7.x/initials/svg?seed={name}',
        'messages': []
    }
    
    CHATS[new_id] = new_chat
    
    return jsonify({'status': 'success', 'chat_id': new_id})

# --- Socket IO Events ---

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    # print(f"User joined room: {room}")

@socketio.on('send_message')
def on_send_message(data):
    # data: { 'chat_id': '...', 'content': '...', 'sender_id': '...' }
    chat_id = data['chat_id']
    content = data['content']
    sender_id = data['sender_id']
    
    chat = CHATS.get(chat_id)
    if chat:
        timestamp = datetime.now().strftime("%I:%M %p")
        new_msg = {
            'sender_id': sender_id,
            'content': content,
            'timestamp': timestamp
        }
        chat['messages'].append(new_msg)
        
        # Prepare message for broadcast
        sender = USERS.get(sender_id)
        broadcast_msg = {
            'sender_id': sender_id,
            'sender_name': sender['name'] if sender else 'Unknown',
            'avatar': sender['avatar'] if sender else '',
            'content': content,
            'timestamp': timestamp,
            'chat_id': chat_id 
        }
        
        emit('receive_message', broadcast_msg, room=chat_id)

if __name__ == '__main__':
    socketio.run(app, debug=True)

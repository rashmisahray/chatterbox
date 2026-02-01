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
    '1': {'id': '1', 'name': 'Alice', 'avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Alice', 'status': 'online'},
    '2': {'id': '2', 'name': 'Bob', 'avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Bob', 'status': 'away'},
    '3': {'id': '3', 'name': 'Charlie', 'avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Charlie', 'status': 'busy'},
    '4': {'id': '4', 'name': 'David', 'avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=David', 'status': 'online'},
    '5': {'id': '5', 'name': 'Eve', 'avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Eve', 'status': 'offline'},
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
            return render_template('login.html', error="User not found. Try 'Alice', 'Bob', or 'Charlie'.")
    return render_template('login.html')

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
    
    for chat_id, chat in CHATS.items():
        if current_user_id in chat['participants']:
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
                    item['status'] = other_user['status']
                else:
                    item['name'] = "Unknown"
                    item['avatar'] = ""
                    item['status'] = "offline"
            else:
                item['name'] = chat.get('name', 'Group Chat')
                item['avatar'] = chat.get('avatar', '')
                item['status'] = '' 
            
            sidebar_items.append(item)

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

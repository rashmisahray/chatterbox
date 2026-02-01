var socket = io();

document.addEventListener('DOMContentLoaded', () => {
    const chatList = document.getElementById('chat-list');
    const chatArea = document.getElementById('chat-area');
    const chatWindowTemplate = document.getElementById('chat-window-template');

    let currentChatId = null;
    let currentUser = null;

    // --- Initialization ---
    fetch('/api/init')
        .then(res => res.json())
        .then(data => {
            if (data.error) return;
            currentUser = data.user; // Store current user info
            renderSidebar(data.sidebar);
        });

    // --- Socket Listeners ---
    socket.on('connect', () => {
        console.log('Connected to server via WebSocket');
    });

    socket.on('receive_message', (data) => {
        // data = { sender_id, sender_name, avatar, content, timestamp, chat_id }

        // 1. If we are currently in this chat
        if (currentChatId === data.chat_id) {
            // Check if it's my own message. If so, I already showed it optimistically.
            // In a robust app, we'd replace the "pending" message with this confirmed one.
            // For now, to avoid duplicates, we just IGNORE my own incoming message 
            // because we assume the optimistic append succeeded.
            const isMe = data.sender_id === currentUser.id;

            if (!isMe) {
                const msgObj = { ...data, is_me: false };
                appendMessage(msgObj);
            }
        }

        // 2. Update Sidebar Preview
        const sidebarItem = document.querySelector(`.chat-item[data-id="${data.chat_id}"]`);
        if (sidebarItem) {
            const lastMsgEl = sidebarItem.querySelector('.chat-last-msg');
            if (lastMsgEl) lastMsgEl.textContent = data.content;
            sidebarItem.parentElement.prepend(sidebarItem);
        }
    });

    function renderSidebar(items) {
        chatList.innerHTML = '';
        items.forEach(item => {
            const el = document.createElement('div');
            el.className = `chat-item ${currentChatId === item.chat_id ? 'active' : ''}`;
            el.dataset.id = item.chat_id;
            el.onclick = () => loadChat(item.chat_id);

            el.innerHTML = `
                <img src="${item.avatar}" class="user-avatar" alt="${item.name}">
                <div class="chat-item-content">
                    <div class="chat-item-header">
                        <span class="chat-name">${item.name}</span>
                    </div>
                    <div class="chat-last-msg">${item.last_message || 'Start a conversation'}</div>
                </div>
            `;
            chatList.appendChild(el);
        });
    }

    function loadChat(chatId) {
        currentChatId = chatId;
        socket.emit('join', { room: chatId });

        document.querySelectorAll('.chat-item').forEach(el => {
            el.classList.toggle('active', el.dataset.id === chatId);
        });

        fetch(`/api/chat/${chatId}`)
            .then(res => res.json())
            .then(data => {
                if (data.error) return;
                renderChat(data);
            });
    }

    function renderChat(data) {
        const content = chatWindowTemplate.content.cloneNode(true);

        content.getElementById('header-name').textContent = data.chat_info.name;
        content.getElementById('header-status').textContent = data.chat_info.status;
        content.getElementById('header-avatar').src = data.chat_info.avatar;

        const msgContainer = content.getElementById('messages-container');

        data.messages.forEach(msg => {
            msgContainer.appendChild(createMessageElement(msg));
        });

        // Setup Input
        const input = content.getElementById('message-input');
        const sendBtn = content.getElementById('send-btn');

        chatArea.innerHTML = '';
        chatArea.appendChild(content);

        const liveBtn = document.getElementById('send-btn');
        const liveInput = document.getElementById('message-input');

        const sendMessageHandler = () => {
            const text = liveInput.value.trim();
            if (!text) return;

            // 1. OPTIMISTIC UPDATE (Immediate Show)
            const tempMsg = {
                sender_id: currentUser.id,
                content: text,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                is_me: true
            };

            appendMessage(tempMsg);
            liveInput.value = ''; // Clear input immediately

            // 2. Emit to Server
            socket.emit('send_message', {
                chat_id: currentChatId,
                content: text,
                sender_id: currentUser.id
            });
        };

        liveBtn.onclick = sendMessageHandler;
        liveInput.onkeypress = (e) => {
            if (e.key === 'Enter') sendMessageHandler();
        };

        scrollToBottom();
    }

    // --- Profile Edit Logic ---
    const profileSection = document.querySelector('.user-profile');
    const profileModal = document.getElementById('profile-modal');
    const cancelProfile = document.getElementById('cancel-profile');
    const confirmProfile = document.getElementById('confirm-profile');

    if (profileSection && profileModal) {
        // Only make the info part clickable, not the logout
        const infoPart = profileSection.querySelector('.user-info');
        if (infoPart) {
            infoPart.style.cursor = 'pointer';
            infoPart.onclick = () => {
                document.getElementById('edit-profile-name').value = currentUser.name;
                profileModal.showModal();
            };
        }

        cancelProfile.onclick = () => profileModal.close();

        confirmProfile.onclick = () => {
            const newName = document.getElementById('edit-profile-name').value;
            const gender = document.getElementById('edit-profile-gender').value;

            fetch('/api/profile/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName, gender: gender })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'success') {
                        location.reload(); // Simple reload to reflect changes
                    }
                });
        };
    }

    // --- Create Group Logic ---
    const createGroupBtn = document.getElementById('create-group-btn');
    const groupModal = document.getElementById('group-modal');
    const cancelGroup = document.getElementById('cancel-group');
    const confirmGroup = document.getElementById('confirm-group');

    if (createGroupBtn && groupModal) {
        createGroupBtn.onclick = () => {
            // Fetch users for selection
            fetch('/api/users')
                .then(res => res.json())
                .then(users => {
                    const list = document.getElementById('user-selection-list');
                    list.innerHTML = '';
                    users.forEach(u => {
                        const div = document.createElement('div');
                        div.style.padding = '0.3rem';
                        div.innerHTML = `
                            <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                                <input type="checkbox" value="${u.id}" class="user-checkbox">
                                <img src="${u.avatar}" style="width: 20px; height: 20px; border-radius: 50%;"> 
                                ${u.name}
                            </label>
                        `;
                        list.appendChild(div);
                    });
                    groupModal.showModal();
                });
        };

        cancelGroup.onclick = () => {
            groupModal.close();
        };

        confirmGroup.onclick = () => {
            const name = document.getElementById('new-group-name').value;
            const checkboxes = document.querySelectorAll('.user-checkbox:checked');
            const participants = Array.from(checkboxes).map(cb => cb.value);

            if (name) {
                fetch('/api/group/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, participants: participants })
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'success') {
                            groupModal.close();
                            fetch('/api/init')
                                .then(res => res.json())
                                .then(initData => {
                                    renderSidebar(initData.sidebar);
                                    loadChat(data.chat_id);
                                });
                        }
                    });
            }
        };
    }

    function appendMessage(msg) {
        const container = document.getElementById('messages-container');
        if (container) {
            container.appendChild(createMessageElement(msg));
            scrollToBottom();
        }
    }

    function scrollToBottom() {
        setTimeout(() => {
            const container = document.getElementById('messages-container');
            if (container) container.scrollTop = container.scrollHeight;
        }, 10);
    }

    function createMessageElement(msg) {
        const row = document.createElement('div');
        row.className = `message-row ${msg.is_me ? 'me' : 'them'}`;

        let avatarHtml = '';
        if (!msg.is_me) {
            avatarHtml = `<img src="${msg.avatar}" class="message-avatar">`;
        }

        row.innerHTML = `
            ${avatarHtml}
            <div class="message-bubble">
                ${msg.content}
                <span class="message-time">${msg.timestamp}</span>
            </div>
        `;
        return row;
    }
});

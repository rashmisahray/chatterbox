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
    socket.on('receive_message', (data) => {
        // data = { sender_id, sender_name, avatar, content, timestamp, chat_id }

        // 1. If we are currently in this chat, append the message
        if (currentChatId === data.chat_id) {
            const isMe = data.sender_id === currentUser.id;
            const msgObj = { ...data, is_me: isMe };

            const msgContainer = document.getElementById('messages-container');
            if (msgContainer) {
                msgContainer.appendChild(createMessageElement(msgObj));
                msgContainer.scrollTop = msgContainer.scrollHeight;
            }
        }

        // 2. Update Sidebar Preview (Optional refinement)
        // Find the chat item in sidebar and update text
        const sidebarItem = document.querySelector(`.chat-item[data-id="${data.chat_id}"]`);
        if (sidebarItem) {
            const lastMsgEl = sidebarItem.querySelector('.chat-last-msg');
            if (lastMsgEl) lastMsgEl.textContent = data.content;

            // Move to top (simple move)
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
        // Leave previous room if any (optional, but good practice if tracking presence)
        // socket.emit('leave', {room: currentChatId}); 

        currentChatId = chatId;

        // Join new room
        socket.emit('join', { room: chatId });

        // Update Active State in Sidebar
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

        const input = content.getElementById('message-input');
        const sendBtn = content.getElementById('send-btn');

        const sendMessageHandler = () => {
            const text = input.value.trim();
            if (!text) return;

            // Emit via Socket instead of POST
            socket.emit('send_message', {
                chat_id: currentChatId,
                content: text,
                sender_id: currentUser.id
            });

            // We do NOT manually append here. We wait for 'receive_message' event 
            // to ensure everyone (including self) gets the same confirmation.
            // OR we append optimistically. Let's wait for socket echo for simplicity 
            // (or since we emit key info, we can just clear input).
            input.value = '';
        };

        sendBtn.onclick = sendMessageHandler;
        input.onkeypress = (e) => {
            if (e.key === 'Enter') sendMessageHandler();
        };

        chatArea.innerHTML = '';
        chatArea.appendChild(content);

        setTimeout(() => {
            const container = document.getElementById('messages-container');
            if (container) container.scrollTop = container.scrollHeight;
        }, 50);
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

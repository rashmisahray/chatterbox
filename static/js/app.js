document.addEventListener('DOMContentLoaded', () => {
    const chatList = document.getElementById('chat-list');
    const chatArea = document.getElementById('chat-area');
    const chatWindowTemplate = document.getElementById('chat-window-template');
    
    let currentChatId = null;

    // --- Initialization ---
    fetch('/api/init')
        .then(res => res.json())
        .then(data => {
            if (data.error) return; // Handle auth error simply
            renderSidebar(data.sidebar);
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
                        <!-- <span class="chat-time">Now</span> -->
                    </div>
                    <div class="chat-last-msg">${item.last_message || 'Start a conversation'}</div>
                </div>
            `;
            chatList.appendChild(el);
        });
    }

    function loadChat(chatId) {
        currentChatId = chatId;
        
        // Update Active State in Sidebar
        document.querySelectorAll('.chat-item').forEach(el => {
            el.classList.toggle('active', el.dataset.id === chatId);
        });

        // Show Loading or Skeleton? For now just fast fetch.
        fetch(`/api/chat/${chatId}`)
            .then(res => res.json())
            .then(data => {
                if (data.error) return;
                renderChat(data);
            });
    }

    function renderChat(data) {
        // Clone Template
        const content = chatWindowTemplate.content.cloneNode(true);
        
        // Header Info
        content.getElementById('header-name').textContent = data.chat_info.name;
        content.getElementById('header-status').textContent = data.chat_info.status;
        content.getElementById('header-avatar').src = data.chat_info.avatar;
        
        // Messages
        const msgContainer = content.getElementById('messages-container');
        data.messages.forEach(msg => {
            msgContainer.appendChild(createMessageElement(msg));
        });
        
        // Setup Input
        const input = content.getElementById('message-input');
        const sendBtn = content.getElementById('send-btn');
        
        const sendMessageHandler = () => {
            const text = input.value.trim();
            if (!text) return;
            
            // Optimistic UI Update (optional, but we'll wait for server for simplicity)
            // Actually, server returns the formatted msg, so standard fetch is fine.
            
            fetch(`/api/chat/${currentChatId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: text })
            })
            .then(res => res.json())
            .then(resp => {
                if (resp.status === 'success') {
                    msgContainer.appendChild(createMessageElement(resp.message));
                    msgContainer.scrollTop = msgContainer.scrollHeight;
                    input.value = '';
                }
            });
        };
        
        sendBtn.onclick = sendMessageHandler;
        input.onkeypress = (e) => {
            if (e.key === 'Enter') sendMessageHandler();
        };

        // Clear and Append
        chatArea.innerHTML = '';
        chatArea.appendChild(content);
        
        // Scroll to bottom
        setTimeout(() => {
            const container = document.getElementById('messages-container'); // Re-query from DOM
            if(container) container.scrollTop = container.scrollHeight;
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

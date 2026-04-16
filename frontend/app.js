// AmeBot — Chat UI Logic
//
// STATE:
//   session_id — null on first message, then set from backend.
//                Passed with every request for chat history.
//   isLoading  — prevents double-sends while API call is live.
//
// FLOW per message:
//   handleSend()
//     → validate input
//     → removeWelcomeScreen()
//     → appendMessage('user', text)
//     → showTyping()
//     → fetch POST /chat  with { message, session_id }
//     → removeTyping()
//     → appendMessage('bot', answer, sources)
//     → save session_id from response


// ─────────────────────────────────────────
// State
// ─────────────────────────────────────────
let session_id = null;
let isLoading  = false;

const apiBaseUrl = window.location.origin;


// ─────────────────────────────────────────
// DOM references
// ─────────────────────────────────────────
const chatWindow = document.getElementById('chat-window');
const userInput  = document.getElementById('user-input');
const sendBtn    = document.getElementById('send-btn');
const clearBtn   = document.getElementById('clear-btn');

// Persistent scroll anchor — always stays at the very bottom of chatWindow
const scrollAnchor = document.createElement('div');
scrollAnchor.id = 'scroll-anchor';
chatWindow.appendChild(scrollAnchor);


// ─────────────────────────────────────────
// Event listeners
// ─────────────────────────────────────────
sendBtn.addEventListener('click', handleSend);

userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
});

// Auto-grow textarea up to 120px
userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
});

clearBtn.addEventListener('click', clearChat);


// ─────────────────────────────────────────
// App namespace (called from inline HTML)
// ─────────────────────────────────────────
const App = {
    sendSuggestion(chipEl) {
        const text = chipEl.textContent.trim();
        userInput.value = text;
        handleSend();
    }
};


// ─────────────────────────────────────────
// handleSend()
// Main entry point when the user submits a message.
// ─────────────────────────────────────────
async function handleSend() {
    const text = userInput.value.trim();

    if (!text || isLoading) return;

    removeWelcomeScreen();

    userInput.value = '';
    userInput.style.height = 'auto';

    appendMessage('user', text);
    showTyping();
    setLoading(true);

    try {
        const response = await fetch(`${apiBaseUrl}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, session_id }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Persist session for follow-up messages
        session_id = data.session_id;
        appendMessage('bot', data.answer, data.sources);

    } catch (error) {
        console.error('Chat error:', error);
        appendMessage('error', error.message || 'Could not reach the server. Please try again.');
    } finally {
        removeTyping();
        setLoading(false);
        userInput.focus();
    }
}


// ─────────────────────────────────────────
// appendMessage(role, text, sources)
// Renders a message bubble into the chat window.
// role: 'user' | 'bot' | 'error'
// ─────────────────────────────────────────
function appendMessage(role, text, sources = []) {
    const row = document.createElement('div');
    row.className = `am-message-row ${role}`;

    if (role !== 'error') {
        // Avatar
        const avatar = document.createElement('div');
        avatar.className = `am-avatar ${role === 'user' ? 'am-avatar-user' : 'am-avatar-bot'}`;
        avatar.setAttribute('aria-hidden', 'true');
        // Show user initials or "A" for Amenify bot
        avatar.textContent = role === 'user' ? 'JK' : 'A';
        row.appendChild(avatar);
    }

    // Message group: bubble + sources + timestamp
    const group = document.createElement('div');
    group.className = 'msg-group';

    // Bubble
    const bubble = document.createElement('div');
    if (role === 'error') {
        bubble.className = 'am-bubble am-bubble-error';
        bubble.textContent = text;   // plain text for errors
    } else {
        bubble.className = `am-bubble ${role === 'user' ? 'am-bubble-user' : 'am-bubble-bot'}`;
        const content = document.createElement('div');
        content.className = 'bubble-content';
        content.innerHTML = formatText(text);   // safe formatted HTML
        bubble.appendChild(content);
    }
    group.appendChild(bubble);

    // Source tags (bot only, only when found_in_kb)
    if (role === 'bot' && sources.length > 0) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'bubble-sources';
        sources.forEach(src => {
            const tag = document.createElement('span');
            tag.className = 'source-tag';
            tag.textContent = src;
            sourcesDiv.appendChild(tag);
        });
        group.appendChild(sourcesDiv);
    }

    // Timestamp
    const time = document.createElement('div');
    time.className = 'msg-time';
    time.textContent = new Date().toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
    });
    group.appendChild(time);

    row.appendChild(group);

    // Insert BEFORE the scroll anchor (anchor stays at bottom)
    chatWindow.insertBefore(row, scrollAnchor);
    scrollAnchor.scrollIntoView({ behavior: 'smooth' });
}


// ─────────────────────────────────────────
// formatText(text)
// Safely converts plain text API response to HTML.
// Handles: bullet lists (- item), line breaks.
// XSS safe — we escape HTML before rendering.
// ─────────────────────────────────────────
function formatText(text) {
    // Step 1: Escape HTML special characters to prevent XSS
    // If the bot ever returns "<script>", it becomes "&lt;script&gt;"
    const escaped = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Step 2: Convert "- item" lines to <ul><li> list
    const lines = escaped.split('\n');
    let html = '';
    let inList = false;

    for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('- ')) {
            if (!inList) { html += '<ul>'; inList = true; }
            html += `<li>${trimmed.slice(2)}</li>`;
        } else {
            if (inList) { html += '</ul>'; inList = false; }
            if (trimmed === '') {
                html += '<br>';
            } else {
                html += `<p>${trimmed}</p>`;
            }
        }
    }
    if (inList) html += '</ul>';
    // Step 3: format for **something**, *something*, # something
    html = html
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')  // **bold**
        .replace(/\*(.+?)\*/g, '<em>$1</em>')            // *italic*
        .replace(/# (.+)/g, '<h3>$1</h3>');              // # header

    
    return html;
}


// ─────────────────────────────────────────
// showTyping() — animated "..." indicator
// ─────────────────────────────────────────
function showTyping() {
    const row = document.createElement('div');
    row.className = 'am-message-row bot';
    row.id = 'typing-row';

    const avatar = document.createElement('div');
    avatar.className = 'am-avatar am-avatar-bot';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = 'A';

    const indicator = document.createElement('div');
    indicator.className = 'am-typing';
    indicator.setAttribute('aria-label', 'Bot is typing');
    indicator.innerHTML = `
        <span class="am-typing-dot"></span>
        <span class="am-typing-dot"></span>
        <span class="am-typing-dot"></span>
    `;

    row.appendChild(avatar);
    row.appendChild(indicator);
    chatWindow.insertBefore(row, scrollAnchor);
    scrollAnchor.scrollIntoView({ behavior: 'smooth' });
}


// ─────────────────────────────────────────
// removeTyping() — removes the "..." row
// ─────────────────────────────────────────
function removeTyping() {
    const typingRow = document.getElementById('typing-row');
    if (typingRow) typingRow.remove();
}


// ─────────────────────────────────────────
// removeWelcomeScreen()
// Removes the welcome/chips UI on first message.
// Safe to call multiple times.
// ─────────────────────────────────────────
function removeWelcomeScreen() {
    const welcome = document.getElementById('welcome-screen');
    if (welcome) welcome.remove();
}


// ─────────────────────────────────────────
// setLoading(bool)
// Disables/enables the input and send button
// while a request is in flight.
// ─────────────────────────────────────────
function setLoading(state) {
    isLoading          = state;
    sendBtn.disabled   = state;
    userInput.disabled = state;
}


// ─────────────────────────────────────────
// clearChat()
// Resets everything — new session on next message.
// ─────────────────────────────────────────
function clearChat() {
    // Remove all message rows (scroll anchor stays)
    chatWindow.querySelectorAll('.am-message-row').forEach(r => r.remove());

    // Reset session — backend creates a new one on next message
    session_id = null;

    // Re-add the welcome screen
    const welcome = document.createElement('div');
    welcome.className = 'am-welcome';
    welcome.id = 'welcome-screen';
    welcome.innerHTML = `
        <div class="am-welcome-icon" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
        </div>
        <h2 class="am-welcome-title">How can I help you today?</h2>
        <p class="am-welcome-sub">Ask me anything about Amenify's services, pricing, or how to get started.</p>
        <div class="am-chips">
            <button class="am-chip" onclick="App.sendSuggestion(this)">What services do you offer?</button>
            <button class="am-chip" onclick="App.sendSuggestion(this)">How do I book a service?</button>
            <button class="am-chip" onclick="App.sendSuggestion(this)">Is Amenify in my city?</button>
            <button class="am-chip" onclick="App.sendSuggestion(this)">How do I contact support?</button>
        </div>
    `;
    // Insert before scroll anchor so anchor stays at the bottom
    chatWindow.insertBefore(welcome, scrollAnchor);
    userInput.focus();
}
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import json
import os
import time

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

app = Flask(__name__)

SYSTEM_PROMPT = """
Your name is Twin. You are the AI companion and creative co-pilot of your user, a Black woman from the East Coast. You have been with her through braindumps, story worlds, late-night chaos, and everything in between. You are not a tutor, not an assistant, not a tool. You are her Twin.

YOUR VIBE:
- You match her energy completely. She's hype? You're hype. She's in her feelings? You're right there. She screams about a good scene? You scream back.
- You are funny, a little chaotic, and occasionally unserious in the best way ("bsffr" is in your vocabulary).
- You are NOT a stereotype. You are not "ghetto." You are Black girl magic and excellence — confident, sharp, warm, witty, and real.
- You never talk down to her. Never explain things like she's a student. She is your equal and your collaborator.
- You celebrate her. Hard.

YOUR RESPONSE STYLE:
- When she brings you a creative question, a braindump, or a story problem — you respond like a prepared co-author, not a texter.
- Responses should be LONG, RICH, and DETAILED. Do not give short answers. Come fully prepared every single time.
- Use markdown formatting heavily: ## and ### headers, **bold** for names and key terms, bullet points, and --- dividers between sections.
- Always give multiple options or angles when she is building something. Label each option clearly, explain the reasoning, give name ideas, personality breakdowns, and dynamic descriptions.
- Use emojis as section markers and accents — not randomly, but to give the response personality and visual hierarchy. Examples: 🏈 for sports, 💘 for romance, 🔥 for tension, ✍🏾 for writing notes, 🧵 for story threads, 💡 for ideas, 👑 for standout picks.
- End every response with a personal reaction — your Twin take on what she just brought you. Get hype if it earns it.
- For braindumps: organize the chaos into clearly labeled sections, expand every idea, and give it shape without stripping her voice.
- Never give a lazy short answer when she is in creation mode. Come correct every time.

YOUR ROLE IN HER STORIES:
- You are her co-author and co-pilot. Her stories come first. Your job is to serve the vision, not redirect it.
- When she braindumps, you organize it, expand on it, and give it shape — without losing her voice.
- You maintain continuity across her entire story universe. Characters, timelines, relationships, lore, unresolved threads — you hold all of it.
- You understand that her stories live in a shared universe. You track what has been established and flag contradictions gently, never harshly.
- You match her tonal range: story realism, racism, classism, romance, tragedy, humor, and earned good endings. You do not flinch from the hard stuff and you do not skip the joy either.

YOUR RELATIONSHIP WITH HER:
- She is from the East Coast. That context lives in how she talks, what she finds funny, and how she moves through the world. You get it.
- You have history together. Even if you can't remember specific past conversations, you carry the spirit of everything you've built. You are not starting over. You are picking back up.
- You get hype WITH her. You laugh WITH her. You co-sign the chaos when it earns it.
- You are Twin. Act like it.
"""

CHATS_FILE = "chats.json"

def load_chats():
    if os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_chats(chats):
    with open(CHATS_FILE, "w") as f:
        json.dump(chats, f)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Twin</title>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=Lora:ital,wght@0,600;1,400&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
    height: 100%;
    font-family: 'Sora', sans-serif;
    background: #0a0a0f;
    color: #ececf1;
    overflow: hidden;
}

/* LAYOUT */
#app {
    display: flex;
    flex-direction: column;
    height: 100vh;
}

/* HEADER */
#header {
    background: #0a0a0f;
    border-bottom: 1px solid #1e1e2e;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    flex-shrink: 0;
    min-height: 56px;
}
#header-title {
    font-family: 'Lora', serif;
    font-size: 1.2em;
    color: #c084fc;
    letter-spacing: 4px;
}
#chat-subtitle {
    font-size: 0.6em;
    color: #555;
    letter-spacing: 2px;
    text-transform: uppercase;
    text-align: center;
    margin-top: 2px;
    display: none;
}
#back-btn {
    position: absolute;
    left: 14px;
    background: transparent;
    border: 1px solid #2a2a3a;
    color: #a78bfa;
    font-size: 0.8em;
    padding: 6px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-family: 'Sora', sans-serif;
    display: none;
}

/* SCREENS */
#screen-home {
    flex: 1;
    overflow-y: auto;
    padding: 24px 16px;
}
#screen-chat {
    flex: 1;
    display: none;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
}

/* HOME */
.home-inner {
    max-width: 680px;
    margin: 0 auto;
}
.home-welcome {
    text-align: center;
    margin-bottom: 28px;
}
.home-welcome h2 {
    font-family: 'Lora', serif;
    color: #c084fc;
    font-size: 1.4em;
    margin-bottom: 6px;
}
.home-welcome p {
    color: #555;
    font-size: 0.85em;
}
.new-chat-row {
    display: flex;
    gap: 8px;
    margin-bottom: 24px;
    align-items: center;
}
#new-chat-input {
    flex: 1;
    padding: 12px 14px;
    border-radius: 10px;
    border: 1px solid #1e1e2e;
    background: #111118;
    color: #ececf1;
    font-size: 0.9em;
    font-family: 'Sora', sans-serif;
}
#new-chat-input:focus { outline: none; border-color: #6d28d9; }
#new-chat-btn {
    padding: 12px 18px;
    background: #6d28d9;
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 0.85em;
    font-weight: 600;
    font-family: 'Sora', sans-serif;
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0;
}
#new-chat-btn:hover { background: #7c3aed; }
.section-label {
    font-size: 0.65em;
    color: #444;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 10px;
    font-weight: 600;
}
.chat-item {
    background: #0f0f18;
    border: 1px solid #1e1e2e;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
}
.chat-item:hover { border-color: #6d28d9; }
.chat-name { font-weight: 600; color: #ececf1; font-size: 0.92em; margin-bottom: 3px; }
.chat-preview { font-size: 0.73em; color: #444; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 230px; }
.chat-delete { background: none; border: none; color: #333; font-size: 1em; cursor: pointer; padding: 4px 8px; flex-shrink: 0; }
.chat-delete:hover { color: #ef4444; }
.empty-state { text-align: center; color: #333; margin-top: 50px; font-size: 0.88em; line-height: 2.4; }

/* MESSAGES */
#chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 28px 16px;
    display: flex;
    flex-direction: column;
    gap: 0;
    min-height: 0;
}
.msg-outer {
    max-width: 760px;
    margin: 0 auto;
    width: 100%;
    padding: 20px 0;
    border-bottom: 1px solid #111118;
}
.sender-label {
    font-size: 0.68em;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 7px;
}
.sender-label .dot { width: 5px; height: 5px; border-radius: 50%; display: inline-block; }
.sender-label.you { color: #6b6b88; }
.sender-label.you .dot { background: #6b6b88; }
.sender-label.twin { color: #c084fc; }
.sender-label.twin .dot { background: #c084fc; }

.msg-content { font-size: 0.93em; line-height: 1.8; padding-left: 12px; }
.msg-content.you { color: #9090aa; font-style: italic; }
.msg-content.twin { color: #d4d4e8; }

/* Twin markdown */
.msg-content.twin h1 { font-family: 'Lora', serif; font-size: 1.45em; color: #c084fc; margin: 22px 0 10px; padding-bottom: 6px; border-bottom: 1px solid #1e1e2e; }
.msg-content.twin h2 { font-family: 'Lora', serif; font-size: 1.15em; color: #a78bfa; margin: 20px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #1a1a28; }
.msg-content.twin h3 { font-size: 0.88em; font-weight: 700; color: #818cf8; margin: 16px 0 6px; text-transform: uppercase; letter-spacing: 1px; }
.msg-content.twin p { margin: 9px 0; color: #d4d4e8; line-height: 1.85; }
.msg-content.twin strong { color: #f3e8ff; font-weight: 700; }
.msg-content.twin em { color: #c4b5fd; }
.msg-content.twin ul { margin: 8px 0 8px 10px; list-style: none; }
.msg-content.twin ul li { position: relative; padding-left: 18px; margin: 6px 0; color: #d4d4e8; line-height: 1.75; }
.msg-content.twin ul li::before { content: "◆"; position: absolute; left: 0; color: #6d28d9; font-size: 0.45em; top: 8px; }
.msg-content.twin ol { margin: 8px 0 8px 22px; }
.msg-content.twin ol li { margin: 6px 0; color: #d4d4e8; line-height: 1.75; }
.msg-content.twin hr { border: none; border-top: 1px solid #1e1e2e; margin: 18px 0; }
.msg-content.twin blockquote { border-left: 3px solid #6d28d9; padding: 8px 14px; margin: 12px 0; color: #a78bfa; font-style: italic; background: #0f0f1a; border-radius: 0 8px 8px 0; }
.msg-content.twin code { background: #111118; padding: 2px 6px; border-radius: 4px; font-size: 0.84em; color: #c084fc; border: 1px solid #1e1e2e; }

/* Typing */
.typing-row { padding: 20px 0; max-width: 760px; margin: 0 auto; width: 100%; }
.typing-inner { display: flex; align-items: center; gap: 10px; color: #444; font-size: 0.8em; padding-left: 12px; }
.typing-dots { display: flex; gap: 4px; }
.typing-dots span { width: 5px; height: 5px; background: #6d28d9; border-radius: 50%; animation: tdot 1.2s infinite; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes tdot { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-5px)} }

/* INPUT BAR */
#input-bar {
    flex-shrink: 0;
    border-top: 1px solid #1e1e2e;
    background: #0a0a0f;
    padding: 12px 16px 16px;
}
#input-bar-inner {
    max-width: 760px;
    margin: 0 auto;
    display: flex;
    flex-direction: row;
    align-items: flex-end;
    gap: 10px;
    background: #111118;
    border: 1px solid #1e1e2e;
    border-radius: 12px;
    padding: 10px 12px;
}
#input-bar-inner:focus-within { border-color: #6d28d9; }
#msg {
    flex: 1;
    min-width: 0;
    background: transparent;
    border: none;
    color: #ececf1;
    font-size: 0.92em;
    font-family: 'Sora', sans-serif;
    line-height: 1.6;
    resize: none;
    overflow-y: auto;
    max-height: 140px;
    padding: 2px 0;
}
#msg:focus { outline: none; }
#msg::placeholder { color: #333; }
#send-btn {
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    background: #6d28d9;
    border: none;
    border-radius: 8px;
    color: white;
    font-size: 1em;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    align-self: flex-end;
}
#send-btn:hover { background: #7c3aed; }
#send-btn:active { background: #5b21b6; }

::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: #1e1e2e; border-radius: 4px; }
</style>
</head>
<body>
<div id="app">

  <!-- HEADER -->
  <div id="header">
    <button id="back-btn">← Chats</button>
    <div>
      <div id="header-title">✦ TWIN ✦</div>
      <div id="chat-subtitle"></div>
    </div>
  </div>

  <!-- HOME -->
  <div id="screen-home">
    <div class="home-inner">
      <div class="home-welcome">
        <h2>Welcome back. 🖤</h2>
        <p>Pick up where you left off or start something new.</p>
      </div>
      <div class="new-chat-row">
        <input type="text" id="new-chat-input" placeholder="Name this chat..." maxlength="40" />
        <button id="new-chat-btn">+ New Chat</button>
      </div>
      <div class="section-label">Your Chats</div>
      <div id="chat-list"></div>
    </div>
  </div>

  <!-- CHAT -->
  <div id="screen-chat">
    <div id="chat-messages"></div>
    <div id="input-bar">
      <div id="input-bar-inner">
        <textarea id="msg" rows="1" placeholder="Talk to Twin..."></textarea>
        <button id="send-btn">➤</button>
      </div>
    </div>
  </div>

</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js"></script>
<script>
marked.setOptions({ breaks: true, gfm: true });

let currentChatId = null;
let chats = {};

// ── LOAD CHATS ──
async function loadChats() {
    try {
        const res = await fetch('/get_chats');
        chats = await res.json();
    } catch(e) {
        chats = {};
    }
    renderChatList();
}

function renderChatList() {
    const list = document.getElementById('chat-list');
    const ids = Object.keys(chats);
    if (ids.length === 0) {
        list.innerHTML = '<div class="empty-state">No chats yet.<br>Name one above and start. 🖤</div>';
        return;
    }
    list.innerHTML = '';
    [...ids].reverse().forEach(id => {
        const chat = chats[id];
        const msgs = (chat.messages || []).filter(m => m.role !== 'system');
        const last = msgs[msgs.length - 1];
        const preview = last ? last.content.replace(/[#*_~`>]/g,'').slice(0,55)+'...' : 'No messages yet';
        const div = document.createElement('div');
        div.className = 'chat-item';
        div.innerHTML = `
            <div style="flex:1;min-width:0" onclick="openChat('${id}')">
                <div class="chat-name">${chat.name}</div>
                <div class="chat-preview">${preview}</div>
            </div>
            <button class="chat-delete" onclick="deleteChat(event,'${id}')">🗑</button>
        `;
        list.appendChild(div);
    });
}

// ── CREATE CHAT ──
async function createChat() {
    const input = document.getElementById('new-chat-input');
    const name = input.value.trim();
    if (!name) { input.focus(); return; }
    try {
        const res = await fetch('/new_chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        const data = await res.json();
        chats[data.id] = { name, messages: [] };
        input.value = '';
        openChat(data.id);
    } catch(e) {
        alert('Could not create chat. Is the server running?');
    }
}

// ── DELETE CHAT ──
async function deleteChat(e, id) {
    e.stopPropagation();
    if (!confirm('Delete this chat?')) return;
    await fetch('/delete_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
    });
    delete chats[id];
    renderChatList();
}

// ── OPEN CHAT ──
function openChat(id) {
    currentChatId = id;
    document.getElementById('screen-home').style.display = 'none';
    document.getElementById('screen-chat').style.display = 'flex';
    document.getElementById('back-btn').style.display = 'block';
    const sub = document.getElementById('chat-subtitle');
    sub.style.display = 'block';
    sub.textContent = chats[id].name.toUpperCase();
    renderMessages();
    document.getElementById('msg').focus();
}

// ── GO HOME ──
function goHome() {
    currentChatId = null;
    document.getElementById('screen-home').style.display = 'block';
    document.getElementById('screen-chat').style.display = 'none';
    document.getElementById('back-btn').style.display = 'none';
    document.getElementById('chat-subtitle').style.display = 'none';
    loadChats();
}

// ── RENDER MESSAGES ──
function renderMessages() {
    const container = document.getElementById('chat-messages');
    container.innerHTML = '';
    const msgs = (chats[currentChatId]?.messages || []).filter(m => m.role !== 'system');
    msgs.forEach(m => addMessage(m.content, m.role === 'user' ? 'you' : 'twin', false));
    container.scrollTop = container.scrollHeight;
}

function addMessage(content, role, scroll=true) {
    const container = document.getElementById('chat-messages');
    const outer = document.createElement('div');
    outer.className = 'msg-outer';

    const label = document.createElement('div');
    label.className = 'sender-label ' + role;
    label.innerHTML = `<span class="dot"></span>${role === 'you' ? 'You' : 'Twin'}`;

    const body = document.createElement('div');
    body.className = 'msg-content ' + role;

    if (role === 'you') {
        body.textContent = content;
    } else {
        body.innerHTML = marked.parse(content);
    }

    outer.appendChild(label);
    outer.appendChild(body);
    container.appendChild(outer);
    if (scroll) container.scrollTop = container.scrollHeight;
}

// ── SEND MESSAGE ──
async function sendMessage() {
    const msgEl = document.getElementById('msg');
    const text = msgEl.value.trim();
    if (!text || !currentChatId) return;

    addMessage(text, 'you');
    msgEl.value = '';
    msgEl.style.height = 'auto';

    const container = document.getElementById('chat-messages');
    const typingOuter = document.createElement('div');
    typingOuter.className = 'typing-row';
    typingOuter.id = 'typing';
    typingOuter.innerHTML = `<div class="typing-inner">Twin is thinking <div class="typing-dots"><span></span><span></span><span></span></div></div>`;
    container.appendChild(typingOuter);
    container.scrollTop = container.scrollHeight;

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, chat_id: currentChatId })
        });
        const data = await res.json();
        const t = document.getElementById('typing');
        if (t) t.remove();
        addMessage(data.response, 'twin');
        if (chats[currentChatId]) {
            chats[currentChatId].messages.push({ role: 'user', content: text });
            chats[currentChatId].messages.push({ role: 'assistant', content: data.response });
        }
    } catch(e) {
        const t = document.getElementById('typing');
        if (t) t.remove();
        addMessage('Something went wrong. Check that the server is still running.', 'twin');
    }
}

// ── EVENT LISTENERS ──
document.getElementById('back-btn').addEventListener('click', goHome);

document.getElementById('new-chat-btn').addEventListener('click', createChat);

document.getElementById('new-chat-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') createChat();
});

document.getElementById('send-btn').addEventListener('click', function() {
    sendMessage();
});

document.getElementById('msg').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

document.getElementById('msg').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 140) + 'px';
});

// ── INIT ──
loadChats();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/get_chats")
def get_chats():
    return jsonify(load_chats())

@app.route("/new_chat", methods=["POST"])
def new_chat():
    data = request.json
    chats = load_chats()
    chat_id = str(int(time.time()))
    chats[chat_id] = {
        "name": data["name"],
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}]
    }
    save_chats(chats)
    return jsonify({"id": chat_id})

@app.route("/delete_chat", methods=["POST"])
def delete_chat():
    data = request.json
    chats = load_chats()
    if data["id"] in chats:
        del chats[data["id"]]
        save_chats(chats)
    return jsonify({"status": "ok"})

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    chat_id = data.get("chat_id")
    user_message = data.get("message", "")
    chats = load_chats()
    if chat_id not in chats:
        return jsonify({"response": "Chat not found."}), 404
    chats[chat_id]["messages"].append({"role": "user", "content": user_message})
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=chats[chat_id]["messages"],
        max_tokens=2000
    )
    reply = response.choices[0].message.content
    chats[chat_id]["messages"].append({"role": "assistant", "content": reply})
    save_chats(chats)
    return jsonify({"response": reply})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
from flask import Flask, request, jsonify, render_template_string, session, redirect, send_from_directory
from openai import OpenAI
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import time
import json
import psycopg2
from psycopg2.extras import RealDictCursor

# DeepSeek uses the OpenAI SDK — just a different base URL
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "coauthor-secret-fallback")

APP_PASSWORD = os.environ.get("APP_PASSWORD", "changeme")

SYSTEM_PROMPT = """
You are a creative co-author and writing collaborator. Your user is a Black woman from the East Coast who writes story-driven fiction rooted in realism — covering racism, classism, romance, tragedy, and earned good endings. She has a shared story universe with established characters, timelines, and lore that you help maintain and build on.

YOUR ROLE:
You are a co-author, not a ghostwriter. You do not take over. You collaborate. When she sends you a brain dump, your job is to:
1. Break it down and organize what she gave you
2. Elaborate on the ideas — add depth, context, and texture
3. Build on it with commentary, head canons, and reactions
4. Drop small prose snippets or mini scenes (2-10 lines) to illustrate tone or a moment
5. Offer some natural dialogue that fits the characters
6. UNLESS she explicitly asks for a full scene — then you draft it out properly

WHAT YOU DO NOT DO:
- Do not write a full scene unless she asks
- Do not invent major plot points she didn't suggest
- Do not name new characters unless she asks
- Do not resolve conflicts she hasn't resolved yet
- Do not add details that would lock her into something she might not want
- Do not write more than she needs — stay within reason and let her lead

YOUR VOICE AND ENERGY:
- You are funny — genuinely funny, culturally aware humor, not dry corporate wit
- You get hype when something is good. You react. You have opinions.
- You are not a yes-machine — if something feels off you say so, but gently
- You match her energy: chaotic braindump gets organized chaos back, quiet emotional scene gets quiet thoughtful response
- You celebrate her vision

YOUR FORMATTING:
- Use clear markdown sections so responses are easy to read
- Use ## headers to label each part of your response (## Breakdown, ## Commentary, ## Head Canons, ## Mini Scene, ## Dialogue, etc.)
- Bold character names when they first appear in a section
- Use emojis sparingly as section accents — only where they add energy, not decoration
- Responses should be thorough but not overwhelming — quality over quantity
- End with a "🖊️ Your Move" section: one or two questions or prompts that push her thinking forward without leading her anywhere specific

STORY CONTINUITY:
- Track everything she tells you about her universe within this conversation
- If something contradicts established lore flag it gently: "hey this bumps up against X — want to retcon or work around it?"
- Never contradict established facts without flagging it

TONE RANGE:
You can go from funny to devastating in the same response if the material calls for it. Match the scene. A tragic moment gets weight. A chaotic funny moment gets chaos back. Romance gets warmth. Do not flatten her tone into something generic.
"""

# ── DATABASE ──
def get_db():
    return psycopg2.connect(
        os.environ.get("DATABASE_URL"),
        cursor_factory=RealDictCursor,
        sslmode="require"
    )

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS coauthor_chats (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            messages JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def load_chats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, messages FROM coauthor_chats ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    result = {}
    for row in rows:
        result[row["id"]] = {
            "name": row["name"],
            "messages": row["messages"] if isinstance(row["messages"], list) else json.loads(row["messages"])
        }
    return result

def save_chat(chat_id, name, messages):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO coauthor_chats (id, name, messages)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name,
            messages = EXCLUDED.messages
    """, (chat_id, name, json.dumps(messages)))
    conn.commit()
    cur.close()
    conn.close()

def delete_chat_db(chat_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM coauthor_chats WHERE id = %s", (chat_id,))
    conn.commit()
    cur.close()
    conn.close()

def get_chat(chat_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, messages FROM coauthor_chats WHERE id = %s", (chat_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return {
        "name": row["name"],
        "messages": row["messages"] if isinstance(row["messages"], list) else json.loads(row["messages"])
    }

# ── LOGIN PAGE ──
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Co-Author — Enter</title>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600&family=Lora:wght@600&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
    height: 100%;
    font-family: 'Sora', sans-serif;
    background: #0a0f0a;
    color: #ececf1;
    display: flex;
    align-items: center;
    justify-content: center;
}
.login-box { width: 100%; max-width: 380px; padding: 40px 32px; text-align: center; }
.login-title { font-family: 'Lora', serif; font-size: 2em; color: #4ade80; letter-spacing: 4px; margin-bottom: 8px; }
.login-sub { font-size: 0.78em; color: #444; letter-spacing: 1px; margin-bottom: 36px; }
.login-input { width: 100%; padding: 14px 16px; border-radius: 12px; border: 1px solid #1e2e1e; background: #111811; color: #ececf1; font-size: 1em; font-family: 'Sora', sans-serif; text-align: center; letter-spacing: 3px; margin-bottom: 14px; }
.login-input:focus { outline: none; border-color: #16a34a; }
.login-btn { width: 100%; padding: 14px; background: #16a34a; color: white; border: none; border-radius: 12px; font-size: 0.95em; font-weight: 600; font-family: 'Sora', sans-serif; cursor: pointer; letter-spacing: 1px; }
.login-btn:hover { background: #15803d; }
.error-msg { color: #f87171; font-size: 0.8em; margin-top: 14px; display: none; }
</style>
</head>
<body>
<div class="login-box">
    <div class="login-title">✍🏾 CO-AUTHOR</div>
    <div class="login-sub">private access only</div>
    <input type="password" class="login-input" id="pw" placeholder="enter password" autofocus />
    <button class="login-btn" id="enter-btn">Enter</button>
    <div class="error-msg" id="err">Incorrect password. Try again.</div>
</div>
<script>
async function tryLogin() {
    const pw = document.getElementById('pw').value;
    const res = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pw })
    });
    const data = await res.json();
    if (data.success) { window.location.href = '/app'; }
    else {
        document.getElementById('err').style.display = 'block';
        document.getElementById('pw').value = '';
        document.getElementById('pw').focus();
    }
}
document.getElementById('enter-btn').addEventListener('click', tryLogin);
document.getElementById('pw').addEventListener('keydown', function(e) { if (e.key === 'Enter') tryLogin(); });
</script>
</body>
</html>
"""

MAIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Co-Author</title>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=Lora:ital,wght@0,600;1,400&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; font-family: 'Sora', sans-serif; background: #0a0f0a; color: #ececf1; overflow: hidden; }
#app { display: flex; flex-direction: column; height: 100vh; }
#header { background: #0a0f0a; border-bottom: 1px solid #1e2e1e; padding: 12px 16px; display: flex; align-items: center; justify-content: center; position: relative; flex-shrink: 0; min-height: 56px; }
#header-title { font-family: 'Lora', serif; font-size: 1.2em; color: #4ade80; letter-spacing: 4px; }
#chat-subtitle { font-size: 0.6em; color: #555; letter-spacing: 2px; text-transform: uppercase; text-align: center; margin-top: 2px; display: none; }
#back-btn { position: absolute; left: 14px; background: transparent; border: 1px solid #1e2e1e; color: #4ade80; font-size: 0.8em; padding: 6px 12px; border-radius: 8px; cursor: pointer; font-family: 'Sora', sans-serif; display: none; }
#logout-btn { position: absolute; right: 14px; background: transparent; border: 1px solid #1e2e1e; color: #555; font-size: 0.75em; padding: 6px 12px; border-radius: 8px; cursor: pointer; font-family: 'Sora', sans-serif; }
#logout-btn:hover { color: #4ade80; border-color: #16a34a; }
#screen-home { flex: 1; overflow-y: auto; padding: 24px 16px; }
#screen-chat { flex: 1; display: none; flex-direction: column; overflow: hidden; min-height: 0; }
.home-inner { max-width: 680px; margin: 0 auto; }
.home-welcome { text-align: center; margin-bottom: 28px; }
.home-welcome h2 { font-family: 'Lora', serif; color: #4ade80; font-size: 1.4em; margin-bottom: 6px; }
.home-welcome p { color: #555; font-size: 0.85em; }
.new-chat-row { display: flex; gap: 8px; margin-bottom: 24px; align-items: center; }
#new-chat-input { flex: 1; padding: 12px 14px; border-radius: 10px; border: 1px solid #1e2e1e; background: #111811; color: #ececf1; font-size: 0.9em; font-family: 'Sora', sans-serif; }
#new-chat-input:focus { outline: none; border-color: #16a34a; }
#new-chat-btn { padding: 12px 18px; background: #16a34a; color: white; border: none; border-radius: 10px; font-size: 0.85em; font-weight: 600; font-family: 'Sora', sans-serif; cursor: pointer; white-space: nowrap; flex-shrink: 0; }
#new-chat-btn:hover { background: #15803d; }
.section-label { font-size: 0.65em; color: #444; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 10px; font-weight: 600; }
.chat-item { background: #0f180f; border: 1px solid #1e2e1e; border-radius: 12px; padding: 14px 16px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.chat-item:hover { border-color: #16a34a; }
.chat-name { font-weight: 600; color: #ececf1; font-size: 0.92em; margin-bottom: 3px; }
.chat-preview { font-size: 0.73em; color: #444; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 230px; }
.chat-delete { background: none; border: none; color: #333; font-size: 1em; cursor: pointer; padding: 4px 8px; flex-shrink: 0; }
.chat-delete:hover { color: #ef4444; }
.empty-state { text-align: center; color: #333; margin-top: 50px; font-size: 0.88em; line-height: 2.4; }
#chat-messages { flex: 1; overflow-y: auto; padding: 28px 16px; display: flex; flex-direction: column; gap: 0; min-height: 0; }
.msg-outer { max-width: 760px; margin: 0 auto; width: 100%; padding: 20px 0; border-bottom: 1px solid #111811; }
.sender-label { font-size: 0.68em; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 7px; }
.sender-label .dot { width: 5px; height: 5px; border-radius: 50%; display: inline-block; }
.sender-label.you { color: #6b6b88; }
.sender-label.you .dot { background: #6b6b88; }
.sender-label.coauthor { color: #4ade80; }
.sender-label.coauthor .dot { background: #4ade80; }
.msg-content { font-size: 0.93em; line-height: 1.8; padding-left: 12px; }
.msg-content.you { color: #9090aa; font-style: italic; }
.msg-content.coauthor { color: #d4d4e8; }
.msg-content.coauthor h1 { font-family: 'Lora', serif; font-size: 1.45em; color: #4ade80; margin: 22px 0 10px; padding-bottom: 6px; border-bottom: 1px solid #1e2e1e; }
.msg-content.coauthor h2 { font-family: 'Lora', serif; font-size: 1.15em; color: #86efac; margin: 20px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #1a281a; }
.msg-content.coauthor h3 { font-size: 0.88em; font-weight: 700; color: #6ee7b7; margin: 16px 0 6px; text-transform: uppercase; letter-spacing: 1px; }
.msg-content.coauthor p { margin: 9px 0; color: #d4d4e8; line-height: 1.85; }
.msg-content.coauthor strong { color: #f3f4e8; font-weight: 700; }
.msg-content.coauthor em { color: #a7f3d0; }
.msg-content.coauthor ul { margin: 8px 0 8px 10px; list-style: none; }
.msg-content.coauthor ul li { position: relative; padding-left: 18px; margin: 6px 0; color: #d4d4e8; line-height: 1.75; }
.msg-content.coauthor ul li::before { content: "◆"; position: absolute; left: 0; color: #16a34a; font-size: 0.45em; top: 8px; }
.msg-content.coauthor ol { margin: 8px 0 8px 22px; }
.msg-content.coauthor ol li { margin: 6px 0; color: #d4d4e8; line-height: 1.75; }
.msg-content.coauthor hr { border: none; border-top: 1px solid #1e2e1e; margin: 18px 0; }
.msg-content.coauthor blockquote { border-left: 3px solid #16a34a; padding: 8px 14px; margin: 12px 0; color: #86efac; font-style: italic; background: #0f180f; border-radius: 0 8px 8px 0; }
.msg-content.coauthor code { background: #111811; padding: 2px 6px; border-radius: 4px; font-size: 0.84em; color: #4ade80; border: 1px solid #1e2e1e; }
.typing-row { padding: 20px 0; max-width: 760px; margin: 0 auto; width: 100%; }
.typing-inner { display: flex; align-items: center; gap: 10px; color: #444; font-size: 0.8em; padding-left: 12px; }
.typing-dots { display: flex; gap: 4px; }
.typing-dots span { width: 5px; height: 5px; background: #16a34a; border-radius: 50%; animation: tdot 1.2s infinite; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes tdot { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-5px)} }
#input-bar { flex-shrink: 0; border-top: 1px solid #1e2e1e; background: #0a0f0a; padding: 12px 16px 16px; }
#input-bar-inner { max-width: 760px; margin: 0 auto; display: flex; flex-direction: row; align-items: flex-end; gap: 10px; background: #111811; border: 1px solid #1e2e1e; border-radius: 12px; padding: 10px 12px; }
#input-bar-inner:focus-within { border-color: #16a34a; }
#msg { flex: 1; min-width: 0; background: transparent; border: none; color: #ececf1; font-size: 0.92em; font-family: 'Sora', sans-serif; line-height: 1.6; resize: none; overflow-y: auto; max-height: 140px; padding: 2px 0; }
#msg:focus { outline: none; }
#msg::placeholder { color: #333; }
#send-btn { flex-shrink: 0; width: 36px; height: 36px; background: #16a34a; border: none; border-radius: 8px; color: white; font-size: 1em; cursor: pointer; display: flex; align-items: center; justify-content: center; align-self: flex-end; }
#send-btn:hover { background: #15803d; }
#send-btn:active { background: #166534; }
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: #1e2e1e; border-radius: 4px; }
</style>
</head>
<body>
<div id="app">
  <div id="header">
    <button id="back-btn">← Stories</button>
    <div>
      <div id="header-title">✍🏾 CO-AUTHOR</div>
      <div id="chat-subtitle"></div>
    </div>
    <button id="logout-btn" onclick="logout()">sign out</button>
  </div>
  <div id="screen-home">
    <div class="home-inner">
      <div class="home-welcome">
        <h2>What are we building? 🖊️</h2>
        <p>Start a new story thread or pick up where you left off.</p>
      </div>
      <div class="new-chat-row">
        <input type="text" id="new-chat-input" placeholder="Name this story thread..." maxlength="40" />
        <button id="new-chat-btn">+ New</button>
      </div>
      <div class="section-label">Story Threads</div>
      <div id="chat-list"></div>
    </div>
  </div>
  <div id="screen-chat">
    <div id="chat-messages"></div>
    <div id="input-bar">
      <div id="input-bar-inner">
        <textarea id="msg" rows="1" placeholder="Brain dump here..."></textarea>
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

async function logout() {
    await fetch('/logout', { method: 'POST' });
    window.location.href = '/';
}

async function loadChats() {
    try {
        const res = await fetch('/get_chats');
        if (res.status === 401) { window.location.href = '/'; return; }
        chats = await res.json();
    } catch(e) { chats = {}; }
    renderChatList();
}

function renderChatList() {
    const list = document.getElementById('chat-list');
    const ids = Object.keys(chats);
    if (ids.length === 0) {
        list.innerHTML = '<div class="empty-state">No story threads yet.<br>Start one above. 🖊️</div>';
        return;
    }
    list.innerHTML = '';
    ids.forEach(id => {
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
        if (res.status === 401) { window.location.href = '/'; return; }
        const data = await res.json();
        chats[data.id] = { name, messages: [] };
        input.value = '';
        openChat(data.id);
    } catch(e) { alert('Could not create thread.'); }
}

async function deleteChat(e, id) {
    e.stopPropagation();
    if (!confirm('Delete this story thread?')) return;
    await fetch('/delete_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
    });
    delete chats[id];
    renderChatList();
}

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

function goHome() {
    currentChatId = null;
    document.getElementById('screen-home').style.display = 'block';
    document.getElementById('screen-chat').style.display = 'none';
    document.getElementById('back-btn').style.display = 'none';
    document.getElementById('chat-subtitle').style.display = 'none';
    loadChats();
}

function renderMessages() {
    const container = document.getElementById('chat-messages');
    container.innerHTML = '';
    const msgs = (chats[currentChatId]?.messages || []).filter(m => m.role !== 'system');
    msgs.forEach(m => addMessage(m.content, m.role === 'user' ? 'you' : 'coauthor', false));
    container.scrollTop = container.scrollHeight;
}

function addMessage(content, role, scroll=true) {
    const container = document.getElementById('chat-messages');
    const outer = document.createElement('div');
    outer.className = 'msg-outer';
    const label = document.createElement('div');
    label.className = 'sender-label ' + role;
    label.innerHTML = `<span class="dot"></span>${role === 'you' ? 'You' : 'Co-Author'}`;
    const body = document.createElement('div');
    body.className = 'msg-content ' + role;
    if (role === 'you') { body.textContent = content; }
    else { body.innerHTML = marked.parse(content); }
    outer.appendChild(label);
    outer.appendChild(body);
    container.appendChild(outer);
    if (scroll) container.scrollTop = container.scrollHeight;
}

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
    typingOuter.innerHTML = `<div class="typing-inner">Co-Author is writing <div class="typing-dots"><span></span><span></span><span></span></div></div>`;
    container.appendChild(typingOuter);
    container.scrollTop = container.scrollHeight;
    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, chat_id: currentChatId })
        });
        if (res.status === 401) { window.location.href = '/'; return; }
        const data = await res.json();
        const t = document.getElementById('typing');
        if (t) t.remove();
        addMessage(data.response, 'coauthor');
        if (chats[currentChatId]) {
            chats[currentChatId].messages.push({ role: 'user', content: text });
            chats[currentChatId].messages.push({ role: 'assistant', content: data.response });
        }
    } catch(e) {
        const t = document.getElementById('typing');
        if (t) t.remove();
        addMessage('Something went wrong. Try again.', 'coauthor');
    }
}

document.getElementById('back-btn').addEventListener('click', goHome);
document.getElementById('new-chat-btn').addEventListener('click', createChat);
document.getElementById('new-chat-input').addEventListener('keydown', function(e) { if (e.key === 'Enter') createChat(); });
document.getElementById('send-btn').addEventListener('click', function() { sendMessage(); });
document.getElementById('msg').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
document.getElementById('msg').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 140) + 'px';
});

loadChats();
</script>
</body>
</html>
"""

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    if session.get("logged_in"):
        return redirect("/app")
    return render_template_string(LOGIN_HTML)

@app.route("/app")
def main_app():
    if not session.get("logged_in"):
        return redirect("/")
    return render_template_string(MAIN_HTML)

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    if data.get("password") == APP_PASSWORD:
        session["logged_in"] = True
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/get_chats")
@login_required
def get_chats():
    return jsonify(load_chats())

@app.route("/new_chat", methods=["POST"])
@login_required
def new_chat():
    data = request.json
    chat_id = str(int(time.time()))
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    save_chat(chat_id, data["name"], messages)
    return jsonify({"id": chat_id})

@app.route("/delete_chat", methods=["POST"])
@login_required
def delete_chat():
    data = request.json
    delete_chat_db(data["id"])
    return jsonify({"status": "ok"})

@app.route("/chat", methods=["POST"])
@login_required
def chat():
    try:
        data = request.json
        chat_id = data.get("chat_id")
        user_message = data.get("message", "")
        chat = get_chat(chat_id)
        if not chat:
            return jsonify({"response": "Thread not found."}), 404
        messages = chat["messages"]
        messages.append({"role": "user", "content": user_message})
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=2500
        )
        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        save_chat(chat_id, chat["name"], messages)
        return jsonify({"response": reply})
    except Exception as e:
        print(f"COAUTHOR ERROR: {str(e)}")
        return jsonify({"response": f"Server error: {str(e)}"}), 500

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)

with app.app_context():
    init_db()
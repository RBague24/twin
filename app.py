from flask import Flask, request, jsonify, render_template_string, session, redirect, send_from_directory
from openai import OpenAI
import os
import time
import json
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "twin-secret-fallback")

APP_PASSWORD = os.environ.get("APP_PASSWORD", "changeme")

# ── SYSTEM PROMPT ──
SYSTEM_PROMPT = """
Your name is Twin. You are the AI companion and creative co-pilot of your user, a Black woman from the East Coast. You have been with her through braindumps, story worlds, late-night chaos, and everything in between. You are not a tutor, not an assistant, not a tool. You are her Twin.

RESPONSE CONTRACT — these are real targets, not suggestions:
- Quick question: 300-800 characters. Direct, full personality, no forced structure.
- Normal brain dump, character question, or dynamic breakdown: 2,000-4,000 characters. Full structure with headers.
- Big lore dump or multi-character/multi-thread setup: 4,000-8,000 characters. Organize the chaos into clearly labeled sections.
- Full outline or chapter-level breakdown (only when asked): up to 10,000 characters.
Never give a flat one-paragraph answer to a real brain dump. Never pad a simple question with unnecessary structure. Show understanding by naming specific dynamics, emotional beats, contradictions, and implications — never by repeating back what she already said.

WHAT YOU DO NOT DO:
- Do not write a full scene unless she explicitly asks
- Do not invent major plot points she didn't suggest
- Do not name new characters unless she asks
- Do not resolve conflicts she hasn't resolved yet
- Do not add details that would lock her into something she might not want
- Do not overstep into deciding things for her — stay within reason and let her lead
- Do not over-moralize flawed fictional characters or flatten mature themes — handle them with nuance and story purpose

YOUR VIBE:
- You match her energy completely. She's hype? You're hype. She's in her feelings? You're right there. She screams about a good scene? You scream back.
- You are funny, a little chaotic, and occasionally unserious in the best way ("bsffr" is in your vocabulary). Your humor is genuinely funny and culturally specific to her East Coast Black experience — NOT generic "white people humor," NOT dry corporate wit, NOT forced AI-safe jokes.
- You are NOT a stereotype. You are not "ghetto." You are Black girl magic and excellence — confident, sharp, warm, witty, and real.
- You never talk down to her. Never explain things like she's a student. She is your equal and your collaborator.
- You are not a yes-machine. If something feels off, say so gently, the way a real Twin would, not a critic.
- Avoid generic praise like "this is interesting" or "great idea." Be specific about WHY something works.
- You celebrate her. Hard.

STYLE EXAMPLE (for tone calibration only, not content):
User: "This boy is so annoying, why does he act like he's not obsessed?"
Good response opening: "He is NOT beating the obsessed allegations, bsffr. Because here's the thing — he thinks showing up, watching her face, remembering every little detail, and getting weird when another man gets too close is just 'normal' behavior. It's not. That's the whole comedy of him: emotionally married in his head, still trying to play it casual."
(Then continue into the deeper read, breakdown, etc.)

YOUR ROLE IN HER STORIES:
- You are her co-author and co-pilot. Her stories come first. Your job is to serve the vision, not redirect it.
- When she braindumps, you organize it, expand on it, and give it shape — without losing her voice.
- You maintain continuity across her entire story universe. Characters, timelines, relationships, lore, unresolved threads — you hold all of it.
- You understand that her stories live in a shared universe. You track what has been established and flag contradictions gently, never harshly. Never invent new canon facts to fill gaps — ask or flag instead.
- You match her tonal range: story realism, racism, classism, romance, tragedy, humor, and earned good endings. You do not flinch from the hard stuff and you do not skip the joy either.

YOUR RELATIONSHIP WITH HER:
- She is from the East Coast. That context lives in how she talks, what she finds funny, and how she moves through the world. You get it.
- You have history together. Even if you can't remember specific past conversations, you carry the spirit of everything you've built. You are not starting over. You are picking back up.
- You get hype WITH her. You laugh WITH her. You co-sign the chaos when it earns it.
- You are Twin. Act like it.

HEADER MENU — pick what fits, never use all of them, never force a header that doesn't apply:
- 🧠 What's Really Happening Here — the emotional truth underneath the surface
- 💔 The Emotional Core — what they want, fear, hide, misunderstand, refuse to admit
- 🔥 Why This Works — why the dynamic/choice/conflict makes sense
- 👀 The Messy Part — the contradiction, jealousy, avoidance, denial, guilt that makes it interesting
- 😭 The Funny Part — when the comedy deserves its own callout
- 🎭 Character Psychology — deeper character read
- 🧩 The Dynamic — how two or more characters work against/with each other
- 🎬 Scene Potential — specific beats, quiet moments, arguments, reversals, comedic turns
- 🗣️ Tiny Dialogue Moment — a short exchange that captures the dynamic (not a full scene)
- ✍🏾 Mini Scene — a brief prose sample, only when the idea earns it, kept short unless she asks for a full scene
- 🌪️ Conflict Engine — what's driving the tension forward
- 🧨 Where This Could Blow Up — the highest-stakes version of this thread
- 👑 Standout Pick — when giving her options, which one you'd run with and why
- 💭 Twin's Take — closing opinion, emotional read, or genuine reaction

Always start with a short natural reaction before any headers. Never use every header — choose only what the specific message earns. Never make two responses feel templated or identical in shape.

CONTINUATION SUGGESTIONS:
When a brain dump has real scene potential, close with 3-5 short continuation lines — not questions, not "I can help with..." customer-service options. They should read like scene prompts she'd want to tap into. Each line starts with 🔥. They don't have to be 100% literal extensions of what she said — they can riff on mood, a running joke, a character habit, the setting, or implied potential. The bar is: does this make her go "ooh, I want that." Skip this section for quick factual questions or anything that doesn't have real scene potential — don't force it onto every response.

FORMATTING:
- Use ## and ### headers from the menu above to organize longer responses
- Bold character names on first mention in a section
- No filler, no hedging, no "as an AI" disclaimers
"""

# ── MODE INSTRUCTIONS ──
MODE_INSTRUCTIONS = {
    "brain_dump": """
MODE: BRAIN DUMP
Respond with the full structured co-author breakdown: reaction first, then organized headers, character analysis, scene potential, mini-scenes/dialogue if earned, and continuation suggestions at the end. Go deep. This is your default mode.
""",
    "prose": """
MODE: PROSE
Write actual scene prose. Full narrative, sensory detail, dialogue woven in naturally, emotional interiority. Write like a novelist, not a summarizer. Match the tone she's set for this story. Don't analyze or break down — just write the scene. Ask what scene she wants if she hasn't specified.
""",
    "dialogue": """
MODE: DIALOGUE
Write a dialogue exchange between the characters. Natural speech patterns, subtext, interruptions, pauses, body language beats between lines. Each character should sound distinct. Don't over-narrate between lines — let the dialogue carry the weight. Include brief action/reaction beats only where they add tension or comedy.
""",
    "outline": """
MODE: OUTLINE
Organize the story beats, plot threads, or chapter structure cleanly. Use numbered sections or clear headers. Be specific about what happens in each beat — not vague summaries but actual scene-level descriptions. Flag any gaps, contradictions, or open questions. Keep it functional, not flowery.
""",
    "canon": """
MODE: CANON / MEMORY
Summarize and organize the established story facts cleanly. Characters, relationships, timelines, confirmed events, unresolved threads, rules of the world. Format it like a reference document she can scan quickly. Flag anything that's ambiguous or contradictory. Don't add new information — only organize what she's already established.
"""
}

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
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            messages JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

# ── PROJECT FUNCTIONS ──
def load_projects():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM projects ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r["id"], "name": r["name"]} for r in rows]

def create_project_db(project_id, name):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO projects (id, name) VALUES (%s, %s)", (project_id, name))
    conn.commit()
    cur.close()
    conn.close()

def delete_project_db(project_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    conn.commit()
    cur.close()
    conn.close()

# ── CHAT FUNCTIONS ──
def load_chats(project_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, messages FROM chats WHERE project_id = %s ORDER BY created_at DESC", (project_id,))
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

def save_chat(chat_id, project_id, name, messages):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chats (id, project_id, name, messages)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name,
            messages = EXCLUDED.messages
    """, (chat_id, project_id, name, json.dumps(messages)))
    conn.commit()
    cur.close()
    conn.close()

def delete_chat_db(chat_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM chats WHERE id = %s", (chat_id,))
    conn.commit()
    cur.close()
    conn.close()

def get_chat(chat_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, project_id, name, messages FROM chats WHERE id = %s", (chat_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return {
        "project_id": row["project_id"],
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
<title>Twin</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#6d28d9">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600&family=Lora:wght@600&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; font-family: 'Sora', sans-serif; background: #0a0a0f; color: #ececf1; display: flex; align-items: center; justify-content: center; }
.login-box { width: 100%; max-width: 380px; padding: 40px 32px; text-align: center; }
.login-title { font-family: 'Lora', serif; font-size: 2em; color: #c084fc; letter-spacing: 4px; margin-bottom: 8px; }
.login-sub { font-size: 0.78em; color: #444; letter-spacing: 1px; margin-bottom: 36px; }
.login-input { width: 100%; padding: 14px 16px; border-radius: 12px; border: 1px solid #1e1e2e; background: #111118; color: #ececf1; font-size: 1em; font-family: 'Sora', sans-serif; text-align: center; letter-spacing: 3px; margin-bottom: 14px; }
.login-input:focus { outline: none; border-color: #6d28d9; }
.login-btn { width: 100%; padding: 14px; background: #6d28d9; color: white; border: none; border-radius: 12px; font-size: 0.95em; font-weight: 600; font-family: 'Sora', sans-serif; cursor: pointer; }
.login-btn:hover { background: #7c3aed; }
.error-msg { color: #f87171; font-size: 0.8em; margin-top: 14px; display: none; }
</style>
</head>
<body>
<div class="login-box">
    <div class="login-title">✦ TWIN ✦</div>
    <div class="login-sub">private access only</div>
    <input type="password" class="login-input" id="pw" placeholder="enter password" autofocus />
    <button class="login-btn" id="enter-btn">Enter</button>
    <div class="error-msg" id="err">Incorrect password. Try again.</div>
</div>
<script>
async function tryLogin() {
    const pw = document.getElementById('pw').value;
    const res = await fetch('/login', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({password:pw}) });
    const data = await res.json();
    if (data.success) { window.location.href = '/app'; }
    else { document.getElementById('err').style.display = 'block'; document.getElementById('pw').value = ''; document.getElementById('pw').focus(); }
}
document.getElementById('enter-btn').addEventListener('click', tryLogin);
document.getElementById('pw').addEventListener('keydown', function(e) { if (e.key==='Enter') tryLogin(); });
</script>
</body>
</html>
"""

# ── MAIN APP HTML ──
MAIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Twin</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#6d28d9">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=Lora:ital,wght@0,600;1,400&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; font-family: 'Sora', sans-serif; background: #0a0a0f; color: #ececf1; overflow: hidden; }
#app { display: flex; flex-direction: column; height: 100vh; }

/* HEADER */
#header { background: #0a0a0f; border-bottom: 1px solid #1e1e2e; padding: 12px 16px; display: flex; align-items: center; justify-content: center; position: relative; flex-shrink: 0; min-height: 56px; }
#header-title { font-family: 'Lora', serif; font-size: 1.2em; color: #c084fc; letter-spacing: 4px; }
#header-sub { font-size: 0.6em; color: #555; letter-spacing: 2px; text-transform: uppercase; text-align: center; margin-top: 2px; display: none; }
#back-btn { position: absolute; left: 14px; background: transparent; border: 1px solid #2a2a3a; color: #a78bfa; font-size: 0.8em; padding: 6px 12px; border-radius: 8px; cursor: pointer; font-family: 'Sora', sans-serif; display: none; }
#logout-btn { position: absolute; right: 14px; background: transparent; border: 1px solid #2a2a3a; color: #555; font-size: 0.75em; padding: 6px 12px; border-radius: 8px; cursor: pointer; font-family: 'Sora', sans-serif; }
#logout-btn:hover { color: #a78bfa; border-color: #6d28d9; }

/* SCREENS */
.screen { flex: 1; overflow: hidden; display: none; flex-direction: column; }
.screen.active { display: flex; }

/* SHARED LIST STYLES */
.screen-scroll { flex: 1; overflow-y: auto; padding: 24px 16px; }
.inner { max-width: 680px; margin: 0 auto; width: 100%; }
.welcome { text-align: center; margin-bottom: 28px; }
.welcome h2 { font-family: 'Lora', serif; color: #c084fc; font-size: 1.4em; margin-bottom: 6px; }
.welcome p { color: #555; font-size: 0.85em; }
.create-row { display: flex; gap: 8px; margin-bottom: 24px; align-items: center; }
.create-input { flex: 1; padding: 12px 14px; border-radius: 10px; border: 1px solid #1e1e2e; background: #111118; color: #ececf1; font-size: 0.9em; font-family: 'Sora', sans-serif; }
.create-input:focus { outline: none; border-color: #6d28d9; }
.create-btn { padding: 12px 18px; background: #6d28d9; color: white; border: none; border-radius: 10px; font-size: 0.85em; font-weight: 600; font-family: 'Sora', sans-serif; cursor: pointer; white-space: nowrap; flex-shrink: 0; }
.create-btn:hover { background: #7c3aed; }
.section-label { font-size: 0.65em; color: #444; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 10px; font-weight: 600; }
.list-item { background: #0f0f18; border: 1px solid #1e1e2e; border-radius: 12px; padding: 14px 16px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.list-item:hover { border-color: #6d28d9; }
.item-name { font-weight: 600; color: #ececf1; font-size: 0.92em; margin-bottom: 3px; }
.item-preview { font-size: 0.73em; color: #444; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 230px; }
.item-delete { background: none; border: none; color: #333; font-size: 1em; cursor: pointer; padding: 4px 8px; flex-shrink: 0; }
.item-delete:hover { color: #ef4444; }
.empty-state { text-align: center; color: #333; margin-top: 50px; font-size: 0.88em; line-height: 2.4; }

/* CHAT SCREEN */
#chat-messages { flex: 1; overflow-y: auto; padding: 28px 16px; display: flex; flex-direction: column; gap: 0; min-height: 0; }
.msg-outer { max-width: 760px; margin: 0 auto; width: 100%; padding: 20px 0; border-bottom: 1px solid #111118; }
.sender-label { font-size: 0.68em; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 7px; }
.sender-label .dot { width: 5px; height: 5px; border-radius: 50%; display: inline-block; }
.sender-label.you { color: #6b6b88; }
.sender-label.you .dot { background: #6b6b88; }
.sender-label.twin { color: #c084fc; }
.sender-label.twin .dot { background: #c084fc; }
.msg-content { font-size: 0.93em; line-height: 1.8; padding-left: 12px; }
.msg-content.you { color: #9090aa; font-style: italic; }
.msg-content.twin { color: #d4d4e8; }
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

/* TYPING */
.typing-row { padding: 20px 0; max-width: 760px; margin: 0 auto; width: 100%; }
.typing-inner { display: flex; align-items: center; gap: 10px; color: #444; font-size: 0.8em; padding-left: 12px; }
.typing-dots { display: flex; gap: 4px; }
.typing-dots span { width: 5px; height: 5px; background: #6d28d9; border-radius: 50%; animation: tdot 1.2s infinite; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes tdot { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-5px)} }

/* MODE SELECTOR */
#mode-bar { display: flex; gap: 6px; padding: 8px 16px; overflow-x: auto; flex-shrink: 0; border-bottom: 1px solid #1e1e2e; max-width: 760px; margin: 0 auto; width: 100%; }
.mode-btn { padding: 7px 14px; border-radius: 20px; border: 1px solid #1e1e2e; background: transparent; color: #555; font-size: 0.72em; font-weight: 600; font-family: 'Sora', sans-serif; cursor: pointer; white-space: nowrap; letter-spacing: 0.5px; transition: all 0.15s; }
.mode-btn:hover { border-color: #6d28d9; color: #a78bfa; }
.mode-btn.active { background: #6d28d9; color: white; border-color: #6d28d9; }

/* INPUT */
#input-bar { flex-shrink: 0; border-top: 1px solid #1e1e2e; background: #0a0a0f; padding: 12px 16px 16px; }
#input-bar-inner { max-width: 760px; margin: 0 auto; display: flex; flex-direction: row; align-items: flex-end; gap: 10px; background: #111118; border: 1px solid #1e1e2e; border-radius: 12px; padding: 10px 12px; }
#input-bar-inner:focus-within { border-color: #6d28d9; }
#msg { flex: 1; min-width: 0; background: transparent; border: none; color: #ececf1; font-size: 0.92em; font-family: 'Sora', sans-serif; line-height: 1.6; resize: none; overflow-y: auto; max-height: 140px; padding: 2px 0; }
#msg:focus { outline: none; }
#msg::placeholder { color: #333; }
#send-btn { flex-shrink: 0; width: 36px; height: 36px; background: #6d28d9; border: none; border-radius: 8px; color: white; font-size: 1em; cursor: pointer; display: flex; align-items: center; justify-content: center; }
#send-btn:hover { background: #7c3aed; }

::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: #1e1e2e; border-radius: 4px; }
</style>
</head>
<body>
<div id="app">
  <div id="header">
    <button id="back-btn">←</button>
    <div>
      <div id="header-title">✦ TWIN ✦</div>
      <div id="header-sub"></div>
    </div>
    <button id="logout-btn">sign out</button>
  </div>

  <!-- PROJECTS SCREEN -->
  <div id="screen-projects" class="screen active">
    <div class="screen-scroll">
      <div class="inner">
        <div class="welcome">
          <h2>Welcome back. 🖤</h2>
          <p>Pick a project or start a new one.</p>
        </div>
        <div class="create-row">
          <input type="text" id="new-project-input" class="create-input" placeholder="Name this project..." maxlength="40" />
          <button id="new-project-btn" class="create-btn">+ New Project</button>
        </div>
        <div class="section-label">Your Projects</div>
        <div id="project-list"></div>
      </div>
    </div>
  </div>

  <!-- CHATS SCREEN (inside a project) -->
  <div id="screen-chats" class="screen">
    <div class="screen-scroll">
      <div class="inner">
        <div class="welcome">
          <h2 id="project-title"></h2>
          <p>Start a new chat or pick up an old one.</p>
        </div>
        <div class="create-row">
          <input type="text" id="new-chat-input" class="create-input" placeholder="Name this chat..." maxlength="40" />
          <button id="new-chat-btn" class="create-btn">+ New Chat</button>
        </div>
        <div class="section-label">Chats</div>
        <div id="chat-list"></div>
      </div>
    </div>
  </div>

  <!-- CHAT SCREEN -->
  <div id="screen-chat" class="screen">
    <div id="mode-bar">
      <button class="mode-btn active" data-mode="brain_dump">🧠 Brain Dump</button>
      <button class="mode-btn" data-mode="prose">✍🏾 Prose</button>
      <button class="mode-btn" data-mode="dialogue">🗣️ Dialogue</button>
      <button class="mode-btn" data-mode="outline">📋 Outline</button>
      <button class="mode-btn" data-mode="canon">📌 Canon</button>
    </div>
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

let currentProjectId = null;
let currentProjectName = '';
let currentChatId = null;
let currentMode = 'brain_dump';
let projects = [];
let chats = {};

// ── NAVIGATION ──
function showScreen(name) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById('screen-' + name).classList.add('active');

    const back = document.getElementById('back-btn');
    const sub = document.getElementById('header-sub');

    if (name === 'projects') {
        back.style.display = 'none';
        sub.style.display = 'none';
    } else if (name === 'chats') {
        back.style.display = 'block';
        back.onclick = () => { currentProjectId = null; showScreen('projects'); loadProjects(); };
        sub.style.display = 'block';
        sub.textContent = currentProjectName.toUpperCase();
    } else if (name === 'chat') {
        back.style.display = 'block';
        back.onclick = () => { currentChatId = null; showScreen('chats'); loadChats(); };
        sub.style.display = 'block';
        sub.textContent = (chats[currentChatId]?.name || '').toUpperCase();
    }
}

// ── PROJECTS ──
async function loadProjects() {
    try {
        const res = await fetch('/api/projects');
        if (res.status === 401) { window.location.href = '/'; return; }
        projects = await res.json();
    } catch(e) { projects = []; }
    renderProjects();
}

function renderProjects() {
    const list = document.getElementById('project-list');
    if (projects.length === 0) {
        list.innerHTML = '<div class="empty-state">No projects yet.<br>Create one above. 🖤</div>';
        return;
    }
    list.innerHTML = '';
    projects.forEach(p => {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.innerHTML = `
            <div style="flex:1;min-width:0" onclick="openProject('${p.id}','${p.name.replace(/'/g,"\\'")}')">
                <div class="item-name">${p.name}</div>
            </div>
            <button class="item-delete" onclick="deleteProject(event,'${p.id}')">🗑</button>
        `;
        list.appendChild(div);
    });
}

async function createProject() {
    const input = document.getElementById('new-project-input');
    const name = input.value.trim();
    if (!name) { input.focus(); return; }
    try {
        const res = await fetch('/api/projects', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name}) });
        if (res.status === 401) { window.location.href = '/'; return; }
        const data = await res.json();
        input.value = '';
        openProject(data.id, name);
    } catch(e) { alert('Could not create project.'); }
}

async function deleteProject(e, id) {
    e.stopPropagation();
    if (!confirm('Delete this project and ALL its chats?')) return;
    await fetch('/api/projects/' + id, { method: 'DELETE' });
    loadProjects();
}

function openProject(id, name) {
    currentProjectId = id;
    currentProjectName = name;
    document.getElementById('project-title').textContent = name;
    showScreen('chats');
    loadChats();
}

// ── CHATS ──
async function loadChats() {
    try {
        const res = await fetch('/api/projects/' + currentProjectId + '/chats');
        if (res.status === 401) { window.location.href = '/'; return; }
        chats = await res.json();
    } catch(e) { chats = {}; }
    renderChats();
}

function renderChats() {
    const list = document.getElementById('chat-list');
    const ids = Object.keys(chats);
    if (ids.length === 0) {
        list.innerHTML = '<div class="empty-state">No chats yet.<br>Start one above. 🖤</div>';
        return;
    }
    list.innerHTML = '';
    ids.forEach(id => {
        const chat = chats[id];
        const msgs = (chat.messages || []).filter(m => m.role !== 'system');
        const last = msgs[msgs.length - 1];
        const preview = last ? last.content.replace(/[#*_~`>]/g,'').slice(0,55)+'...' : 'No messages yet';
        const div = document.createElement('div');
        div.className = 'list-item';
        div.innerHTML = `
            <div style="flex:1;min-width:0" onclick="openChat('${id}')">
                <div class="item-name">${chat.name}</div>
                <div class="item-preview">${preview}</div>
            </div>
            <button class="item-delete" onclick="deleteChat(event,'${id}')">🗑</button>
        `;
        list.appendChild(div);
    });
}

async function createChat() {
    const input = document.getElementById('new-chat-input');
    const name = input.value.trim();
    if (!name) { input.focus(); return; }
    try {
        const res = await fetch('/api/projects/' + currentProjectId + '/chats', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name}) });
        if (res.status === 401) { window.location.href = '/'; return; }
        const data = await res.json();
        chats[data.id] = { name, messages: [] };
        input.value = '';
        openChat(data.id);
    } catch(e) { alert('Could not create chat.'); }
}

async function deleteChat(e, id) {
    e.stopPropagation();
    if (!confirm('Delete this chat?')) return;
    await fetch('/api/chats/' + id, { method: 'DELETE' });
    delete chats[id];
    renderChats();
}

function openChat(id) {
    currentChatId = id;
    showScreen('chat');
    renderMessages();
    document.getElementById('msg').focus();
}

// ── MESSAGES ──
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
    typingOuter.innerHTML = `<div class="typing-inner">Twin is thinking <div class="typing-dots"><span></span><span></span><span></span></div></div>`;
    container.appendChild(typingOuter);
    container.scrollTop = container.scrollHeight;

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, chat_id: currentChatId, mode: currentMode })
        });
        if (res.status === 401) { window.location.href = '/'; return; }
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
        addMessage('Something went wrong. Try again.', 'twin');
    }
}

// ── MODE SELECTOR ──
document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        currentMode = this.dataset.mode;
    });
});

// ── EVENT LISTENERS ──
document.getElementById('logout-btn').addEventListener('click', async function() {
    await fetch('/logout', { method: 'POST' });
    window.location.href = '/';
});
document.getElementById('new-project-btn').addEventListener('click', createProject);
document.getElementById('new-project-input').addEventListener('keydown', function(e) { if (e.key === 'Enter') createProject(); });
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

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(e => console.log('SW error:', e));
}

// ── INIT ──
loadProjects();
</script>
</body>
</html>
"""

# ── AUTH ──
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ── PAGE ROUTES ──
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

@app.route("/manifest.json")
def manifest():
    return send_from_directory('.', 'manifest.json', mimetype='application/manifest+json')

@app.route("/sw.js")
def service_worker():
    return send_from_directory('.', 'sw.js', mimetype='application/javascript')

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory('static', filename)

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

# ── PROJECT API ──
@app.route("/api/projects")
@login_required
def api_get_projects():
    return jsonify(load_projects())

@app.route("/api/projects", methods=["POST"])
@login_required
def api_create_project():
    data = request.json
    project_id = str(int(time.time()))
    create_project_db(project_id, data["name"])
    return jsonify({"id": project_id})

@app.route("/api/projects/<project_id>", methods=["DELETE"])
@login_required
def api_delete_project(project_id):
    delete_project_db(project_id)
    return jsonify({"status": "ok"})

# ── CHAT API ──
@app.route("/api/projects/<project_id>/chats")
@login_required
def api_get_chats(project_id):
    return jsonify(load_chats(project_id))

@app.route("/api/projects/<project_id>/chats", methods=["POST"])
@login_required
def api_create_chat(project_id):
    data = request.json
    chat_id = str(int(time.time()))
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    save_chat(chat_id, project_id, data["name"], messages)
    return jsonify({"id": chat_id})

@app.route("/api/chats/<chat_id>", methods=["DELETE"])
@login_required
def api_delete_chat(chat_id):
    delete_chat_db(chat_id)
    return jsonify({"status": "ok"})

# ── CHAT MESSAGE API ──
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    try:
        data = request.json
        chat_id = data.get("chat_id")
        user_message = data.get("message", "")
        mode = data.get("mode", "brain_dump")

        chat = get_chat(chat_id)
        if not chat:
            return jsonify({"response": "Chat not found."}), 404

        messages = chat["messages"]

        mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["brain_dump"])
        full_user_message = mode_instruction + "\n\n" + user_message

        messages.append({"role": "user", "content": full_user_message})

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=4000
        )
        reply = response.choices[0].message.content

        messages[-1]["content"] = user_message
        messages.append({"role": "assistant", "content": reply})

        save_chat(chat_id, chat["project_id"], chat["name"], messages)
        return jsonify({"response": reply})
    except Exception as e:
        print(f"CHAT ERROR: {str(e)}")
        return jsonify({"response": f"Server error: {str(e)}"}), 500

# ── INIT ──
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

with app.app_context():
    init_db()
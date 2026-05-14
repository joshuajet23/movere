"""Local web chat interface for Movere."""

from flask import Flask, request, jsonify

from . import config
from .chat import process
from . import logger

PORT = 7842

app = Flask(__name__)
_cfg: dict = {}

_CHAT_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Talk to Movere</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: Georgia, serif;
      background: #f9f7f4;
      color: #1a1a1a;
      height: 100dvh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: #1a1a1a;
      color: #f9f7f4;
      padding: 18px 28px;
      display: flex;
      align-items: baseline;
      gap: 16px;
      flex-shrink: 0;
    }
    header h1 { font-size: 18px; letter-spacing: 0.1em; text-transform: uppercase; }
    header span { font-size: 13px; opacity: 0.5; font-style: italic; flex: 1; }
    header a {
      font-size: 12px;
      color: #f9f7f4;
      opacity: 0.55;
      text-decoration: none;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      border-bottom: 1px solid rgba(249,247,244,0.3);
      padding-bottom: 1px;
    }
    header a:hover { opacity: 1; }
    #log {
      flex: 1;
      overflow-y: auto;
      padding: 28px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .bubble {
      max-width: 72%;
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 15px;
      line-height: 1.6;
    }
    .bubble.user {
      align-self: flex-end;
      background: #1a1a1a;
      color: #f9f7f4;
      border-bottom-right-radius: 3px;
    }
    .bubble.assistant {
      align-self: flex-start;
      background: #fff;
      border: 1px solid #e8e4de;
      border-bottom-left-radius: 3px;
    }
    .bubble.thinking {
      align-self: flex-start;
      background: #f0ece4;
      color: #aaa;
      font-style: italic;
      font-size: 14px;
    }
    #form {
      display: flex;
      gap: 10px;
      padding: 16px 28px 24px;
      background: #f9f7f4;
      border-top: 1px solid #e8e4de;
      flex-shrink: 0;
    }
    #input {
      flex: 1;
      padding: 12px 16px;
      font-family: Georgia, serif;
      font-size: 15px;
      border: 1px solid #ddd;
      border-radius: 8px;
      background: #fff;
      outline: none;
      resize: none;
      height: 48px;
    }
    #input:focus { border-color: #1a1a1a; }
    button {
      padding: 0 22px;
      background: #1a1a1a;
      color: #f9f7f4;
      border: none;
      border-radius: 8px;
      font-family: Georgia, serif;
      font-size: 14px;
      cursor: pointer;
      letter-spacing: 0.04em;
    }
    button:disabled { opacity: 0.4; cursor: default; }
    #clear-btn {
      background: none;
      color: rgba(249,247,244,0.45);
      font-size: 11px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 0;
      border-radius: 0;
      cursor: pointer;
    }
    #clear-btn:hover { color: #f9f7f4; }
  </style>
</head>
<body>
  <header>
    <h1>Movere</h1>
    <span>your personal project OS</span>
    <button id="clear-btn">Clear</button>
    <a href="/history">History &rarr;</a>
  </header>
  <div id="log"></div>
  <form id="form">
    <textarea id="input" placeholder="e.g. change my Rhodes essay goal to 1 hour a day" rows="1"></textarea>
    <button type="submit" id="btn">Send</button>
  </form>
  <script>
    const STORAGE_KEY = 'movere_history';
    const log = document.getElementById('log');
    const input = document.getElementById('input');
    const btn = document.getElementById('btn');

    // history sent to the API (role/content pairs)
    let history = [];

    function addBubble(role, text, save = true) {
      const div = document.createElement('div');
      div.className = 'bubble ' + role;
      div.textContent = text;
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
      return div;
    }

    function saveToStorage() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    }

    function loadFromStorage() {
      try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        if (saved.length) {
          history = saved;
          for (const turn of history) {
            addBubble(turn.role, turn.content, false);
          }
          return;
        }
      } catch {}
      addBubble('assistant', "Hey — what\\'s on your mind? You can log progress, update a goal, add a project, or just tell me what you did today.", false);
    }

    document.getElementById('clear-btn').addEventListener('click', () => {
      history = [];
      localStorage.removeItem(STORAGE_KEY);
      log.innerHTML = '';
      addBubble('assistant', "Fresh start. What\\'s on your mind?", false);
    });

    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });

    document.getElementById('form').addEventListener('submit', e => {
      e.preventDefault();
      send();
    });

    async function send() {
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      btn.disabled = true;

      addBubble('user', text, false);
      const thinking = addBubble('thinking', 'Thinking…', false);

      try {
        const res = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, history }),
        });
        const data = await res.json();
        thinking.remove();
        addBubble('assistant', data.reply, false);
        history.push({ role: 'user', content: text });
        history.push({ role: 'assistant', content: data.reply });
        saveToStorage();
      } catch {
        thinking.remove();
        addBubble('assistant', 'Something went wrong — check the Movere server logs.', false);
      }

      btn.disabled = false;
      input.focus();
    }

    loadFromStorage();
  </script>
</body>
</html>"""

_HISTORY_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Movere — History</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Georgia, serif; background: #f9f7f4; color: #1a1a1a; }
    header {
      background: #1a1a1a;
      color: #f9f7f4;
      padding: 18px 28px;
      display: flex;
      align-items: baseline;
      gap: 16px;
    }
    header h1 { font-size: 18px; letter-spacing: 0.1em; text-transform: uppercase; }
    header span { font-size: 13px; opacity: 0.5; font-style: italic; flex: 1; }
    header a {
      font-size: 12px;
      color: #f9f7f4;
      opacity: 0.55;
      text-decoration: none;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      border-bottom: 1px solid rgba(249,247,244,0.3);
      padding-bottom: 1px;
    }
    header a:hover { opacity: 1; }
    .container { max-width: 680px; margin: 36px auto; padding: 0 24px 60px; }
    .day { margin-bottom: 32px; }
    .day-header {
      display: flex;
      align-items: baseline;
      gap: 10px;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid #e8e4de;
    }
    .day-name { font-size: 15px; font-weight: bold; }
    .day-date { font-size: 12px; color: #aaa; }
    .entry {
      display: flex;
      align-items: baseline;
      gap: 10px;
      padding: 7px 0;
      font-size: 14px;
      line-height: 1.5;
      border-bottom: 1px solid #f0ece4;
    }
    .entry:last-child { border-bottom: none; }
    .entry-project {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      color: #888;
      min-width: 100px;
      flex-shrink: 0;
      padding-top: 2px;
    }
    .entry-note {
      flex: 1;
      color: #1a1a1a;
      cursor: text;
      border-radius: 3px;
      padding: 1px 3px;
    }
    .entry-note:focus {
      outline: none;
      background: #fff;
      box-shadow: 0 0 0 2px #1a1a1a22;
    }
    .entry-actions { display: flex; gap: 8px; flex-shrink: 0; opacity: 0; transition: opacity 0.15s; }
    .entry:hover .entry-actions { opacity: 1; }
    .btn-action {
      background: none;
      border: none;
      cursor: pointer;
      font-size: 13px;
      padding: 2px 6px;
      border-radius: 3px;
      color: #aaa;
    }
    .btn-action:hover { color: #1a1a1a; background: #eee; }
    .btn-delete:hover { color: #c0392b; background: #fdecea; }
    .empty { font-size: 13px; color: #ccc; font-style: italic; }
    .entry.deleting { opacity: 0.3; pointer-events: none; transition: opacity 0.2s; }
  </style>
</head>
<body>
  <header>
    <h1>Movere</h1>
    <span>history</span>
    <a href="/">&larr; Chat</a>
  </header>
  <div class="container">
    {% for day in history %}
    <div class="day" data-date="{{ day.date }}">
      <div class="day-header">
        <span class="day-name">{{ day.day }}</span>
        <span class="day-date">{{ day.date }}</span>
      </div>
      {% if day.entries %}
        {% for entry in day.entries %}
        <div class="entry" data-idx="{{ loop.index0 }}">
          <span class="entry-project">{{ (entry.project or 'general') | replace('-', ' ') }}</span>
          <span class="entry-note" contenteditable="true" spellcheck="false">{{ entry.note }}</span>
          <div class="entry-actions">
            <button class="btn-action btn-save" title="Save edit" style="display:none;">Save</button>
            <button class="btn-action btn-delete" title="Delete">&#x2715;</button>
          </div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty">Nothing logged</div>
      {% endif %}
    </div>
    {% endfor %}
  </div>
  <script>
    document.querySelectorAll('.entry-note').forEach(el => {
      const entry = el.closest('.entry');
      const saveBtn = entry.querySelector('.btn-save');
      const original = el.textContent;

      el.addEventListener('input', () => {
        saveBtn.style.display = el.textContent !== original ? '' : 'none';
      });

      el.addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); saveBtn.click(); }
        if (e.key === 'Escape') { el.textContent = original; saveBtn.style.display = 'none'; el.blur(); }
      });

      saveBtn.addEventListener('click', async () => {
        const date = entry.closest('.day').dataset.date;
        const idx = parseInt(entry.dataset.idx);
        const note = el.textContent.trim();
        const res = await fetch('/history/entry', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ date, idx, note }),
        });
        if (res.ok) { saveBtn.style.display = 'none'; }
      });
    });

    document.querySelectorAll('.btn-delete').forEach(btn => {
      btn.addEventListener('click', async () => {
        const entry = btn.closest('.entry');
        const date = entry.closest('.day').dataset.date;
        const idx = parseInt(entry.dataset.idx);
        entry.classList.add('deleting');
        const res = await fetch('/history/entry', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ date, idx }),
        });
        if (res.ok) {
          entry.remove();
        } else {
          entry.classList.remove('deleting');
        }
      });
    });
  </script>
</body>
</html>"""


@app.get("/")
def index():
    return _CHAT_PAGE, 200, {"Content-Type": "text/html"}


@app.get("/history")
def history():
    from jinja2 import Environment
    days = logger.week_history(days=14)
    env = Environment()
    html = env.from_string(_HISTORY_PAGE).render(history=days)
    return html, 200, {"Content-Type": "text/html"}


@app.route("/history/entry", methods=["DELETE", "PATCH"])
def history_entry():
    from datetime import date as _date
    body = request.get_json(force=True)
    try:
        d = _date.fromisoformat(body["date"])
        idx = int(body["idx"])
    except (KeyError, ValueError):
        return jsonify({"error": "invalid request"}), 400

    if request.method == "DELETE":
        ok = logger.delete_entry(d, idx)
        return jsonify({"ok": ok}), (200 if ok else 404)

    note = (body.get("note") or "").strip()
    if not note:
        return jsonify({"error": "note required"}), 400
    ok = logger.update_entry(d, idx, note)
    return jsonify({"ok": ok}), (200 if ok else 404)


@app.post("/chat")
def chat():
    body = request.get_json(force=True)
    message = (body.get("message") or "").strip()
    hist = body.get("history") or []
    if not message:
        return jsonify({"reply": ""}), 400
    reply = process(message, _cfg, history=hist)
    return jsonify({"reply": reply})


def run(port: int = PORT) -> None:
    global _cfg
    _cfg = config.load()
    app.run(host="127.0.0.1", port=port, debug=False)

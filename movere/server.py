"""Local web chat interface for Movere."""

from flask import Flask, request, jsonify

from . import config
from .chat import process

PORT = 7842

app = Flask(__name__)
_cfg: dict = {}

_PAGE = """<!DOCTYPE html>
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
      gap: 12px;
      flex-shrink: 0;
    }
    header h1 { font-size: 18px; letter-spacing: 0.1em; text-transform: uppercase; }
    header span { font-size: 13px; opacity: 0.5; font-style: italic; }
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
  </style>
</head>
<body>
  <header>
    <h1>Movere</h1>
    <span>your personal project OS</span>
  </header>
  <div id="log">
    <div class="bubble assistant">Hey — what's on your mind? You can log progress, update a goal, add a project, or just tell me what you did today.</div>
  </div>
  <form id="form">
    <textarea id="input" placeholder="e.g. change my Rhodes essay goal to 1 hour a day" rows="1"></textarea>
    <button type="submit" id="btn">Send</button>
  </form>
  <script>
    const log = document.getElementById('log');
    const input = document.getElementById('input');
    const btn = document.getElementById('btn');
    const history = [];

    function addBubble(role, text) {
      const div = document.createElement('div');
      div.className = 'bubble ' + role;
      div.textContent = text;
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
      return div;
    }

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

      addBubble('user', text);
      const thinking = addBubble('thinking', 'Thinking…');

      try {
        const res = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, history }),
        });
        const data = await res.json();
        thinking.remove();
        addBubble('assistant', data.reply);
        history.push({ role: 'user', content: text });
        history.push({ role: 'assistant', content: data.reply });
      } catch {
        thinking.remove();
        addBubble('assistant', 'Something went wrong — check the Movere server logs.');
      }

      btn.disabled = false;
      input.focus();
    }
  </script>
</body>
</html>"""


@app.get("/")
def index():
    return _PAGE, 200, {"Content-Type": "text/html"}


@app.post("/chat")
def chat():
    body = request.get_json(force=True)
    message = (body.get("message") or "").strip()
    history = body.get("history") or []
    if not message:
        return jsonify({"reply": ""}), 400
    reply = process(message, _cfg, history=history)
    return jsonify({"reply": reply})


def run(port: int = PORT) -> None:
    global _cfg
    _cfg = config.load()
    app.run(host="127.0.0.1", port=port, debug=False)

"""
obs_overlay/server.py
"""

import collections
import json
import logging
import time

from aiohttp import web

logger = logging.getLogger("obs_overlay")

_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  html, body {
    width: 100%;
    height: 100%;
    background: transparent;
    overflow: hidden;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
  }

  body {
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 8px 6px;
    gap: 4px;
  }

  /* ── Vote box ── */
  #vote-box {
    display: none;
    background: rgba(0,0,0,0.78);
    border: 1px solid rgba(255,215,0,0.5);
    border-radius: 7px;
    padding: 7px 11px;
  }
  #vote-box.visible { display: block; }
  #vote-title { color: #ffd700; font-weight: 700; font-size: 12px; margin-bottom: 3px; }
  .vote-row { display: flex; justify-content: space-between; font-size: 11px; margin: 2px 0; }
  .vote-row .opt { color: #ffe082; font-family: monospace; }
  .vote-row .cnt { color: #80ff80; font-weight: 600; }
  #vote-timer { color: #ff8a65; font-size: 10px; margin-top: 3px; text-align: right; }

  /* ── Active command bar ── */
  #cmd-bar {
    display: none;
    background: rgba(0,0,0,0.72);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 5px;
    padding: 4px 10px;
    font-size: 12px;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  #cmd-bar.visible { display: block; }
  #cmd-bar .who { color: #80cfff; font-weight: 600; }
  #cmd-bar .what { color: #ffe082; font-family: monospace; }

  /* ── Chat ── */
  #chat {
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow: hidden;
    max-height: 100%;
  }

  .msg {
    font-size: 12px;
    line-height: 1.35;
    word-break: break-word;
    padding: 2px 6px;
    border-radius: 3px;
    background: rgba(0,0,0,0.5);
    transition: opacity 0.5s ease;
  }
  .msg.fade-out { opacity: 0; }

  @keyframes pop {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; }
  }
  .msg { animation: pop 0.15s ease; }

  .author { font-weight: 700; margin-right: 3px; }
  .author.owner  { color: #ffd700; }
  .author.mod    { color: #00e5ff; }
  .author.member { color: #b9f6ca; }
  .author.viewer { color: #ccc; }
  .text { color: #f0f0f0; }
  .msg.bot .text { color: #80ff80; font-style: italic; }
</style>
</head>
<body>
<div id="chat"></div>
<div id="cmd-bar">
  <span class="who" id="cmd-who"></span><span style="color:#888"> → </span><span class="what" id="cmd-what"></span>
</div>
<div id="vote-box">
  <div id="vote-title">🗳️ COMMUNITY VOTE</div>
  <div id="vote-opts"></div>
  <div id="vote-timer"></div>
</div>

<script>
const EXPIRE_MS = 8000;
const MAX = 20;
let lastTs = 0;

async function poll() {
  try {
    const r = await fetch('/state?since=' + lastTs);
    if (!r.ok) return;
    const s = await r.json();
    lastTs = s.ts;

    const chat = document.getElementById('chat');

    for (const m of s.new_messages) {
      const div = document.createElement('div');
      div.className = m.bot ? 'msg bot' : 'msg';
      if (m.bot) {
        div.innerHTML = '<span class="text">🤖 ' + esc(m.text) + '</span>';
      } else {
        div.innerHTML =
          '<span class="author ' + (m.badge||'viewer') + '">' + esc(m.author) + ':</span>' +
          '<span class="text">' + esc(m.text) + '</span>';
      }
      chat.appendChild(div);

      // Auto-remove after 8s with fade
      setTimeout(() => {
        div.classList.add('fade-out');
        setTimeout(() => { if (div.parentNode) div.parentNode.removeChild(div); }, 500);
      }, EXPIRE_MS);

      // Hard cap
      while (chat.children.length > MAX) chat.removeChild(chat.firstChild);
    }

    // Active command
    const cmdBar = document.getElementById('cmd-bar');
    if (s.active_cmd) {
      document.getElementById('cmd-who').textContent = s.active_cmd.user;
      document.getElementById('cmd-what').textContent =
        '!' + s.active_cmd.name + (s.active_cmd.args ? ' ' + s.active_cmd.args : '');
      cmdBar.classList.add('visible');
    } else {
      cmdBar.classList.remove('visible');
    }

    // Vote
    const voteBox = document.getElementById('vote-box');
    if (s.vote) {
      const opts = document.getElementById('vote-opts');
      opts.innerHTML = '';
      for (const [k, v] of Object.entries(s.vote.options)) {
        opts.innerHTML += '<div class="vote-row"><span class="opt">!' + esc(k) +
          '</span><span class="cnt">' + v + ' votes</span></div>';
      }
      document.getElementById('vote-timer').textContent =
        '⏱ ' + Math.ceil(s.vote.time_remaining) + 's remaining';
      voteBox.classList.add('visible');
    } else {
      voteBox.classList.remove('visible');
    }
  } catch(e) {}
}

function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

setInterval(poll, 500);
poll();
</script>
</body>
</html>"""


class OverlayServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 7373, screenshot_dir: str = "data/screenshots"):
        self.host = host
        self.port = port
        self._runner: web.AppRunner | None = None
        self._chat: collections.deque = collections.deque(maxlen=80)
        self._active_cmd: dict | None = None
        self._vote: dict | None = None
        self._ts: float = time.time()

    def add_bot_message(self, text: str):
        self._chat.append({"bot": True, "text": text[:300], "t": time.time()})
        self._bump()

    def add_chat_message(self, author: str, text: str, badge: str = ""):
        self._chat.append({"bot": False, "author": author, "text": text[:300], "badge": badge, "t": time.time()})
        self._bump()

    def set_active_command(self, user: str, name: str, args: str = ""):
        self._active_cmd = {"user": user, "name": name, "args": args}
        self._bump()

    def clear_active_command(self):
        if self._active_cmd is not None:
            self._active_cmd = None
            self._bump()

    def set_vote_status(self, options: dict, time_remaining: float):
        self._vote = {"options": dict(options), "time_remaining": time_remaining}
        self._bump()

    def clear_vote(self):
        if self._vote is not None:
            self._vote = None
            self._bump()

    async def start(self):
        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/state", self._handle_state)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.host, self.port).start()
        logger.info(f"OBS overlay → http://{self.host}:{self.port}")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
            self._runner = None

    def _bump(self):
        self._ts = time.time()

    async def _handle_index(self, _: web.Request) -> web.Response:
        return web.Response(text=_INDEX_HTML, content_type="text/html")

    async def _handle_state(self, request: web.Request) -> web.Response:
        try:
            since = float(request.rel_url.query.get("since", 0))
        except ValueError:
            since = 0.0
        return web.Response(
            text=json.dumps({
                "ts": self._ts,
                "new_messages": [m for m in self._chat if m["t"] > since],
                "active_cmd": self._active_cmd,
                "vote": self._vote,
            }),
            content_type="application/json",
            headers={"Cache-Control": "no-store"},
        )
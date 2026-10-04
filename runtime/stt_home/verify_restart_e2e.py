from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
PORT = 18787

def get_json(url):
    with urlopen(url, timeout=3) as r:
        return json.loads(r.read().decode("utf-8"))

def post_json(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    with urlopen(Request(url, data=data, headers={"Content-Type":"application/json"}, method="POST"), timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))

def start(db):
    env = os.environ.copy()
    env["PARADISE_HOME_DATA"] = str(db)
    env["PARADISE_HOME_PORT"] = str(PORT)
    env["PARADISE_HOME_HOST"] = "127.0.0.1"
    return subprocess.Popen([sys.executable, str(HERE / "server.py")], cwd=str(HERE), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_ready():
    for _ in range(60):
        try:
            return get_json(f"http://127.0.0.1:{PORT}/api/health")
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("server did not become ready")

with tempfile.TemporaryDirectory() as td:
    db = Path(td) / "restart-e2e.sqlite3"
    p = start(db)
    try:
        h1 = wait_ready()
        s = post_json(f"http://127.0.0.1:{PORT}/api/session", {})
        sid = s["session_id"]
        first = post_json(f"http://127.0.0.1:{PORT}/api/chat", {
            "session_id": sid, "message": "PARADISE lÃ  nhÃ  cá»§a STT."
        })
        p.terminate(); p.wait(timeout=3)
        p = start(db)
        h2 = wait_ready()
        restored = get_json(f"http://127.0.0.1:{PORT}/api/session/{sid}")
        second = post_json(f"http://127.0.0.1:{PORT}/api/chat", {
            "session_id": sid, "message": "STT Ä‘Ã£ thá»©c dáº­y trong nhÃ  chÆ°a?"
        })
        state = get_json(f"http://127.0.0.1:{PORT}/api/state")
        assert h1["home"] == "PARADISE" and h2["home"] == "PARADISE"
        assert h2["status"] == "READY"
        assert restored["messages"][0]["content"] == "PARADISE lÃ  nhÃ  cá»§a STT."
        assert first["evidence_id"] and second["evidence_id"]
        assert state["identity"]["home"] == "PARADISE"
        assert state["evidence_count"] >= 3
        print("RESTART_E2E=PASS")
        print(f"SESSION={sid}")
        print(f"EVIDENCE_COUNT={state['evidence_count']}")
    finally:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()

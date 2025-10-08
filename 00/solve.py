import requests
import sys
#172.24.0.2
ipsocket = sys.argv[1]
url = f"http://{ipsocket}/get-flag"
params = {"seriously": "true"}
data = {"please": "pretty please"}
response = requests.post(url, params=params,data=data)
print(response.text)
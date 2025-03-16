import requests

corpid = "ww2965fcb1f3435d23"
corpsecret = "UIugLUofqZsSp7jkDVQgce1XSascxVpfSOVJPX5gLOs"
url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corpid}&corpsecret={corpsecret}"

response = requests.get(url)
data = response.json()

if data.get("errcode") == 0:
    access_token = data["access_token"]
    print("Access Token:", access_token)
else:
    print("Error:", data)
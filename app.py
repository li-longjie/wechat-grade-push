import json
import time
import logging
import requests
from datetime import datetime
from threading import Lock
import os
import hashlib
from cryptography.fernet import Fernet
from flask import Flask, request, Response
import grade_fetcher
from xml.etree import ElementTree
from datetime import datetime
import pytz  # PythonAnywhere 已经安装了这个包
from apscheduler.schedulers.background import BackgroundScheduler



    
app = Flask(__name__)

class WeChatTest:
    def __init__(self, appid, appsecret):
        self.appid = appid
        self.appsecret = appsecret
        self.token = "wechatgrade"
        self.access_token = None
        self.token_expires = 0
        self.token_lock = Lock()
        self.key = self.load_or_create_key()
        self.fernet = Fernet(self.key)
        self.user_bindings = self.load_user_bindings()

    def check_signature(self, signature, timestamp, nonce):
        temp_list = [self.token, timestamp, nonce]
        temp_list.sort()
        temp_str = ''.join(temp_list)
        hash_sha1 = hashlib.sha1(temp_str.encode('utf-8'))
        return hash_sha1.hexdigest() == signature

    def load_or_create_key(self):
        key_file = 'key.dat'
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            return key

    def load_user_bindings(self):
        file_path = 'user_bindings.json'
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    bindings = json.load(f)
                for data in bindings.values():
                    if 'encrypted_password' in data:
                        data['password'] = self.fernet.decrypt(data['encrypted_password'].encode()).decode()
                        del data['encrypted_password']
                return bindings
        except Exception as e:
            logging.error(f"加载用户绑定失败: {e}")
        return {}

    def save_user_bindings(self):
        file_path = 'user_bindings.json'
        try:
            bindings = self.user_bindings.copy()
            for data in bindings.values():
                if 'password' in data:
                    data['encrypted_password'] = self.fernet.encrypt(data['password'].encode()).decode()
                    del data['password']
            with open(file_path, 'w') as f:
                json.dump(bindings, f)
        except Exception as e:
            logging.error(f"保存用户绑定失败: {e}")

    def get_access_token(self):
        with self.token_lock:
            now = time.time()
            if self.access_token and now < self.token_expires:
                return self.access_token
            url = "https://api.weixin.qq.com/cgi-bin/token"
            params = {"grant_type": "client_credential", "appid": self.appid, "secret": self.appsecret}
            try:
                response = requests.get(url, params=params)
                result = response.json()
                if "access_token" in result:
                    self.access_token = result["access_token"]
                    self.token_expires = now + result["expires_in"] - 300
                    return self.access_token
            except Exception as e:
                logging.error(f"获取access_token异常: {e}")
                return None

    def handle_message(self, msg):
        openid = msg.get('FromUserName')
        to_user = msg.get('ToUserName')
        content = msg.get('Content', '').strip()

        if content.startswith('绑定'):
            return self.handle_bind(openid, content)
        elif content == '查询':
            return self.handle_query(openid)
        else:
            return self.create_text_response(openid, self.get_help_message())

    def handle_bind(self, openid, content):
        try:
            parts = content.split()
            if len(parts) != 3:
                raise ValueError("格式错误")
            _, student_id, password = parts
            self.user_bindings[openid] = {"student_id": student_id, "password": password, "last_grades": {}}
            self.save_user_bindings()
            return self.create_text_response(openid, f"绑定成功！学号: {student_id}")
        except Exception as e:
            return self.create_text_response(openid, f"绑定失败！请使用格式：绑定 学号 密码，错误: {e}")

    def handle_query(self, openid):
        if openid not in self.user_bindings:
            return self.create_text_response(openid, "您还未绑定学号和密码，请先绑定！")
        data = self.user_bindings[openid]
        try:
            grades = grade_fetcher.get_grades(data["student_id"], data["password"])
            grade_str = "\n".join(f"{course}: {grade}" for course, grade in grades)
            return self.create_text_response(openid, f"查询成功！\n{grade_str}")
        except Exception as e:
            return self.create_text_response(openid, f"查询失败: {e}")

    def get_help_message(self):
        return """欢迎使用成绩查询系统！
可用命令：
1. 绑定 学号 密码 - 绑定您的学号和密码
2. 查询 - 查询最新成绩"""


    def create_text_response(self, to_user, content):
        # 获取当前 UTC 时间并转换为北京时间
        utc_now = datetime.now(pytz.UTC)
        beijing_time = utc_now.astimezone(pytz.timezone('Asia/Shanghai'))
        return {
            "ToUserName": to_user,
            "FromUserName": self.appid,
            "CreateTime": int(beijing_time.timestamp()),
            "MsgType": "text",
            "Content": content
        }



    def send_template_message(self, openid, template_id, data):
        access_token = self.get_access_token()
        if access_token:
            url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}"
            payload = {"touser": openid, "template_id": template_id, "data": data}
            try:
                response = requests.post(url, json=payload)
                return response.json().get("errcode") == 0
            except Exception as e:
                logging.error(f"发送模板消息异常: {e}")
        return False

    def notify_grade(self, openid, grades):
        for course, grade in grades:
            template_data = {
                "first": {"value": "您有新的成绩出来啦！", "color": "#173177"},
                "keyword1": {"value": course, "color": "#173177"},
                "keyword2": {"value": str(grade), "color": "#173177"},
                "keyword3": {"value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "color": "#173177"},
                "remark": {"value": "点击查看详情", "color": "#173177"}
            }
            self.send_template_message(openid, "SN1yTrpcxmJvvzcCLTYhtMa4lgBf8_rZAm8o8r3lslM", template_data)

    def automatic_push_grades(self):
        for openid, data in self.user_bindings.items():
            try:
                current_grades = grade_fetcher.get_grades(data["student_id"], data["password"])
                current_grades_dict = dict(current_grades)
                last_grades = data.get("last_grades", {})
                if current_grades_dict != last_grades:
                    new_grades = [(course, grade) for course, grade in current_grades if course not in last_grades or last_grades[course] != grade]
                    if new_grades:
                        self.notify_grade(openid, new_grades)
                    data["last_grades"] = current_grades_dict
            except Exception as e:
                logging.error(f"自动推送 {openid} 成绩失败: {e}")
        self.save_user_bindings()

wechat = WeChatTest(appid="wxdbef19045c608d50", appsecret="ac6b733fae9aa679989dc4c45ba7ebe0")

def parse_xml(xml_string):
    root = ElementTree.fromstring(xml_string)
    result = {}
    for child in root:
        if child.text:
            text = child.text.strip()
            if text.startswith('<![CDATA[') and text.endswith(']]>'):
                text = text[9:-3]
            result[child.tag] = text
    return result

@app.route('/', methods=['GET', 'POST'])
def handle_wechat():
    if request.method == 'GET':
        signature = request.args.get('signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')
        if wechat.check_signature(signature, timestamp, nonce):
            return echostr
        return "Invalid signature", 403

    elif request.method == 'POST':
        xml_data = request.data.decode('utf-8')
        logging.info(f"Received POST data: {xml_data}")
        msg = parse_xml(xml_data)
        logging.info(f"Parsed message: {msg}")
        result = wechat.handle_message(msg)
        logging.info(f"Message handling result: {result}")
        response = f"""<xml>
            <ToUserName><![CDATA[{result['ToUserName']}]]></ToUserName>
            <FromUserName><![CDATA[{result['FromUserName']}]]></FromUserName>
            <CreateTime>{result['CreateTime']}</CreateTime>
            <MsgType><![CDATA[{result['MsgType']}]]></MsgType>
            <Content><![CDATA[{result['Content']}]]></Content>
        </xml>"""
        logging.info(f"Response XML: {response}")
        return Response(response, mimetype='application/xml')

# 添加定时任务
scheduler = BackgroundScheduler()

@scheduler.scheduled_job('interval', minutes=30)  # 每30分钟检查一次
def check_grades():
    wechat.automatic_push_grades()

scheduler.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
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
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
import threading
from WXBizMsgCrypt import WXBizMsgCrypt
import xml.etree.ElementTree as ET
import base64
from gunicorn.app.base import BaseApplication

# 配置常量
TOKEN = "wechatgrade"    #需和微信url配置界面相同
ENCODING_AES_KEY = "jWmYm7qr5nMoAUwZRjGtBxmz3KA1tkAj3ykkR6q2B2C"   #需和微信url配置界面相同
CORP_ID = "ww2965fcb1f3435d23"

# 全局变量
app = Flask(__name__)
scheduler = None
wechat = None
wxcpt = None
processed_messages = set()
message_lock = threading.Lock()

# 配置日志
# 移除所有现有的处理器
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 创建处理器
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler('/var/log/grade-push.log')

# 设置格式化器
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# 配置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 检查是否已经有相同的处理器
handlers_to_add = []
existing_handler_types = {type(h) for h in root_logger.handlers}

if logging.StreamHandler not in existing_handler_types:
    handlers_to_add.append(console_handler)
if logging.FileHandler not in existing_handler_types:
    handlers_to_add.append(file_handler)

# 添加处理器
for handler in handlers_to_add:
    root_logger.addHandler(handler)

logger = logging.getLogger(__name__)

# 设置其他模块的日志级别
logging.getLogger('grade_fetcher').setLevel(logging.INFO)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)

# 添加启动日志
logger.info("成绩查询系统启动成功！")

class EnterpriseWeChat:
    def __init__(self, corpid, corpsecret, agentid):
        self.corpid = corpid
        self.corpsecret = corpsecret
        self.agentid = agentid
        self.access_token = None
        self.token_expires = 0
        self.token_lock = Lock()
        self.user_bindings = self.load_user_bindings()
        # 初始化加密解密实例
        self.crypto = WXBizMsgCrypt(TOKEN, ENCODING_AES_KEY, self.corpid)

    def get_access_token(self):
        """获取企业微信访问令牌"""
        with self.token_lock:
            now = time.time()
            if self.access_token and now < self.token_expires:
                return self.access_token
            
            url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            params = {
                "corpid": self.corpid,
                "corpsecret": self.corpsecret
            }
            
            try:
                response = requests.get(url, params=params)
                result = response.json()
                if result.get("errcode") == 0:
                    self.access_token = result["access_token"]
                    self.token_expires = now + result["expires_in"] - 300
                    return self.access_token
            except Exception as e:
                logging.error(f"获取access_token异常: {e}")
            return None

    def send_message(self, userid, content):
        """发送企业微信消息"""
        access_token = self.get_access_token()
        if not access_token:
            return False

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
        data = {
            "touser": userid,
            "msgtype": "text",
            "agentid": self.agentid,
            "text": {
                "content": content
            }
        }

        try:
            response = requests.post(url, json=data)
            result = response.json()
            if result.get("errcode") == 0:
                logging.info("企业微信消息发送成功")
                return True
            else:
                logging.error(f"发送企业微信消息失败：{result}")
                return False
        except Exception as e:
            logging.error(f"发送企业微信消息异常：{e}")
            return False

    def async_query_grades(self, userid):
        """异步查询成绩并推送结果"""
        try:
            logging.info(f"开始异步查询成绩: {userid}")
            grades = grade_fetcher.get_grades(
                self.user_bindings[userid]['student_id'],
                self.user_bindings[userid]['password']
            )
            
            if grades:
                # 分离排名信息和成绩信息
                student_info = None
                if grades and grades[0][0] == "排名信息":
                    rank_info = json.loads(grades[0][1])
                    student_info = {
                        "name": rank_info["name"],
                        "major": rank_info["major"],
                        "rank": rank_info["rank"],
                        "avg_score": rank_info["avg_score"]
                    }
                    grades = grades[1:]

                # 构建成绩列表
                grade_items = []
                for course, score in grades:
                    try:
                        score_float = float(score)
                        emoji = "🏆" if score_float >= 90 else "✨" if score_float >= 80 else "👍"
                        grade_items.append(f"• {course}：{score} {emoji}")
                    except ValueError:
                        grade_items.append(f"• {course}：{score}")

                # 构建卡片消息
                picurl = f"https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421f1e2559434357a467b1ac7a09641367b918300a4219f/authserver/default/static/common/images/PC_BG_0.png?t={int(time.time())}"
                card_message = {
                    "touser": userid,
                    "msgtype": "news",
                    "agentid": self.agentid,
                    "news": {
                        "articles": [
                            {
                                "title": "📊 成绩查询结果",
                                "description": (
                                    f"👤 {student_info['name']} | {student_info['major']}\n"
                                    f"📈 排名：{student_info['rank']} | 均分：{student_info['avg_score']}\n\n"
                                    "📋 成绩列表\n" +
                                    "\n".join(grade_items)
                                ),
                                "url": "https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421e9fd529b2b287c1e72069db9d6502720d35c6c/gsapp/sys/wdcjapp/*default/index.do",
                                "picurl": picurl
                            }
                        ]
                    }
                }

                # 发送卡片消息
                access_token = self.get_access_token()
                if access_token:
                    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
                    try:
                        response = requests.post(url, json=card_message)
                        result = response.json()
                        if result.get("errcode") != 0:
                            logger.error(f"发送企业微信卡片消息失败：{result}")
                            # 如果卡片消息发送失败，回退到普通文本消息
                            self.send_fallback_message(userid, grade_items, student_info)
                        else:
                            logger.info("企业微信卡片消息发送成功")
                    except Exception as e:
                        logger.error(f"发送企业微信卡片消息异常：{e}")
                        self.send_fallback_message(userid, grade_items, student_info)
                else:
                    self.send_message(userid, "❌ 暂无成绩信息\n\n如需再次查询请回复：查询")
            
        except Exception as e:
            logging.error(f"异步查询成绩失败: {e}")
            error_msg = f"查询失败：{str(e)}\n\n请稍后重试"
            self.send_message(userid, error_msg)

    def load_user_bindings(self):
        """加载用户绑定信息"""
        file_path = 'user_bindings.json'
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"加载用户绑定失败: {e}")
        return {}

    def save_user_bindings(self):
        """保存用户绑定信息"""
        file_path = 'user_bindings.json'
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.user_bindings, f, ensure_ascii=False)
        except Exception as e:
            logging.error(f"保存用户绑定失败: {e}")

    def handle_message(self, msg):
        """处理用户消息"""
        try:
            openid = msg.get('FromUserName')
            to_user = msg.get('ToUserName')
            content = msg.get('Content', '').strip()
            
            logger.info(f"Processing message from {openid}: {content}")
            
            if content.startswith('绑定'):
                response = self.handle_bind(openid, content)
            elif content == '查询':
                response = self.handle_query(openid)
            else:
                response = self.get_help_message()
            
            # 确保 response 是 UTF-8 编码的正常字符串
            if isinstance(response, str):
                response = response.encode('utf-8').decode('utf-8')
            logger.info(f"Generated response: {repr(response)}")
            
            return {
                "ToUserName": openid,
                "FromUserName": to_user,
                "CreateTime": int(time.time()),
                "MsgType": "text",
                "Content": response
            }
        except Exception as e:
            logger.error(f"处理消息异常：{e}")
            return {
                "ToUserName": openid,
                "FromUserName": to_user,
                "CreateTime": int(time.time()),
                "MsgType": "text",
                "Content": "系统处理消息时出现错误，请稍后重试".encode('utf-8').decode('utf-8')
            }

    def handle_bind(self, userid, content):
        """处理绑定命令"""
        try:
            # 解析学号和密码
            parts = content.split()
            if len(parts) != 3:
                return self.get_help_message()
            
            _, student_id, password = parts
            
            # 使用一个标记来确保只发送一次验证消息
            verification_sent = False
            
            try:
                # 先发送验证消息
                if not verification_sent:
                    self.send_message(userid, "正在验证账号，请稍候...")
                    verification_sent = True
                
                # 验证账号密码
                success, message = grade_fetcher.verify_credentials(student_id, password)
                
                if success:
                    # 验证成功，保存绑定信息
                    self.user_bindings[userid] = {
                        'student_id': student_id,
                        'password': password,
                        'last_grades': {}
                    }
                    self.save_user_bindings()
                    return "✅ 绑定成功！\n您可以使用【查询】命令查看成绩，系统也会在有新成绩时自动通知您。"
                else:
                    return f"❌ 绑定失败！\n{message}"
            except Exception as e:
                logger.error(f"验证过程异常: {e}")
                return "❌ 绑定失败！\n系统异常，请稍后重试。"
            
        except Exception as e:
            logger.error(f"绑定处理异常: {e}")
            return "❌ 绑定失败！\n系统异常，请稍后重试。"

    def handle_query(self, openid):
        if openid not in self.user_bindings:
            return '您还没有绑定账号，请先使用"绑定 学号 密码"命令绑定账号。'
        else:
            threading.Thread(target=self.async_query_grades, args=(openid,)).start()
            return "正在查询成绩，请稍候..."

    def get_help_message(self):
        return (
            "👋 欢迎使用成绩查询系统！\n\n"
            "📝 可用命令和功能：\n"
            "1️⃣ 绑定 学号 密码 - 绑定您的学号和密码\n"
            "2️⃣ 查询 - 先手动查询最新成绩\n"
            "3️⃣ 自动推送 - 无需输入，有新成绩发布时自动推送\n\n"
            "🔔 温馨提示：请先使用【绑定】命令绑定您的账号"
        )

    def notify_grade(self, userid, grades):
        """通知新成绩"""
        if grades:
            # 分离排名信息和成绩信息
            student_info = None
            if grades and grades[0][0] == "排名信息":
                rank_data = json.loads(grades[0][1])
                student_info = {
                    "name": rank_data.get("XM", ""),
                    "major": rank_data.get("ZYDM_DISPLAY", "").split(" ")[1],
                    "avg_score": rank_data.get("JQPJF", ""),
                    "rank": rank_data.get("ZYPMZYZRS", "")  # 保持原始格式 "20/31人"
                }
                grades = grades[1:]

            # 构建成绩列表
            grade_items = []
            for course, score in grades:
                try:
                    score_float = float(score)
                    emoji = "🏆" if score_float >= 90 else "✨" if score_float >= 80 else "👍"
                    grade_items.append(f"• {course}：{score} {emoji}")
                except ValueError:
                    grade_items.append(f"• {course}：{score}")

            # 构建卡片消息
            picurl = f"https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421f1e2559434357a467b1ac7a09641367b918300a4219f/authserver/default/static/common/images/PC_BG_0.png?t={int(time.time())}"
            card_message = {
                "touser": userid,
                "msgtype": "news",
                "agentid": self.agentid,
                "news": {
                    "articles": [
                        {
                            "title": "🎉 新成绩通知",
                            "description": (
                                f"👤 {student_info['name']} | {student_info['major']}\n"
                                f"📈 排名：{student_info['rank']} | 均分：{student_info['avg_score']}\n"
                                "━━━━━━━━━━━━━━\n"
                                "📋 最新成绩\n" +
                                "\n".join(grade_items) +
                                "\n\n点击查看完整成绩单"
                            ),
                            "url": "https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421e9fd529b2b287c1e72069db9d6502720d35c6c/gsapp/sys/wdcjapp/*default/index.do",
                            "picurl": picurl
                        }
                    ]
                }
            }

            # 发送卡片消息
            access_token = self.get_access_token()
            if access_token:
                url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
                try:
                    response = requests.post(url, json=card_message)
                    result = response.json()
                    if result.get("errcode") == 0:
                        logger.info("企业微信图文消息发送成功")
                        return True
                    else:
                        logger.error(f"发送企业微信图文消息失败：{result}")
                        self.send_fallback_message(userid, grade_items, student_info)
                except Exception as e:
                    logger.error(f"发送企业微信图文消息异常：{e}")
                    self.send_fallback_message(userid, grade_items, student_info)
            return False

    def send_fallback_message(self, userid, grade_items, student_info):
        """发送备用文本消息"""
        message = (
            "📊 成绩查询结果\n\n"
            f"📈 当前排名：{student_info['rank'] if student_info else '暂无排名'}\n\n"
            "📋 成绩列表\n" +
            "\n".join(grade_items) +
            "\n\n回复【查询】查看完整成绩单"
        )
        self.send_message(userid, message)

    def automatic_push_grades(self):
        """自动检查并推送新成绩"""
        # 创建用户绑定信息的副本进行遍历
        user_bindings_copy = dict(self.user_bindings)
        
        for openid, data in user_bindings_copy.items():
            try:
                # 检查用户是否仍在关注
                if not self.check_user_follow(openid):
                    logger.info(f"用户已取消关注，移除绑定信息 (openid: {openid})")
                    del self.user_bindings[openid]
                    self.save_user_bindings()
                    continue
                
                current_grades = grade_fetcher.get_grades(
                    data['student_id'],
                    data['password']
                )
                
                # 检查是否成功获取到成绩
                if not current_grades:
                    logger.info(f"未获取到成绩数据 (openid: {openid})")
                    continue
                
                # 检查成绩列表是否为空或无效
                if not isinstance(current_grades, list) or len(current_grades) == 0:
                    logger.info(f"成绩列表为空或无效 (openid: {openid})")
                    continue

                # 分离排名信息和成绩信息
                student_info = {
                    "name": "同学",
                    "major": "研究生",
                    "avg_score": "暂无",
                    "rank": "暂无"
                }
                
                try:
                    if current_grades[0][0] == "排名信息":
                        try:
                            rank_data = json.loads(current_grades[0][1])
                            student_info = {
                                "name": rank_data.get("XM", "同学"),
                                "major": rank_data.get("ZYDM_DISPLAY", "").split(" ")[1] if rank_data.get("ZYDM_DISPLAY") else "研究生",
                                "avg_score": rank_data.get("JQPJF", "暂无"),
                                "rank": rank_data.get("ZYPMZYZRS", "暂无")
                            }
                            current_grades = current_grades[1:]
                        except (json.JSONDecodeError, IndexError, KeyError) as e:
                            logger.error(f"解析排名数据失败 (openid: {openid}): {e}")
                except IndexError:
                    logger.error(f"成绩列表格式无效 (openid: {openid})")
                    continue
                
                # 检查剩余成绩列表是否为空
                if not current_grades:
                    logger.info(f"成绩列表为空 (openid: {openid})")
                    continue
                
                try:
                    current_grades_dict = dict(current_grades)
                except (TypeError, ValueError) as e:
                    logger.error(f"转换成绩列表失败 (openid: {openid}): {e}")
                    continue
                    
                last_grades = data.get('last_grades', {})
                
                new_grades = []
                # 检查成绩是否有变化
                has_new_grades = False
                for course, grade in current_grades:
                    if course not in last_grades or last_grades[course] != grade:
                        has_new_grades = True
                        new_grades.append((course, grade))
                
                if has_new_grades:
                    # 构建成绩列表
                    grade_items = []
                    for course, score in new_grades:
                        try:
                            score_float = float(score)
                            emoji = "🏆" if score_float >= 90 else "✨" if score_float >= 80 else "👍"
                            grade_items.append(f"• {course}：{score} {emoji}")
                        except ValueError:
                            grade_items.append(f"• {course}：{score}")

                    # 构建图文消息
                    picurl = f"https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421f1e2559434357a467b1ac7a09641367b918300a4219f/authserver/default/static/common/images/PC_BG_0.png?t={int(time.time())}"
                    card_message = {
                        "touser": openid,
                        "msgtype": "news",
                        "agentid": self.agentid,
                        "news": {
                            "articles": [
                                {
                                    "title": "🎉 新成绩通知",
                                    "description": (
                                        f"👤 {student_info['name']} | {student_info['major']}\n"
                                        f"📈 排名：{student_info['rank']} | 均分：{student_info['avg_score']}\n"
                                        "━━━━━━━━━━━━━━\n"
                                        "📋 最新成绩\n" +
                                        "\n".join(grade_items) +
                                        "\n\n点击查看完整成绩单"
                                    ),
                                    "url": "https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421e9fd529b2b287c1e72069db9d6502720d35c6c/gsapp/sys/wdcjapp/*default/index.do",
                                    "picurl": picurl
                                }
                            ]
                        }
                    }

                    # 发送消息
                    access_token = self.get_access_token()
                    if access_token:
                        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
                        try:
                            response = requests.post(url, json=card_message)
                            result = response.json()
                            if result.get("errcode") == 0:
                                logger.info(f"企业微信图文消息发送成功 (openid: {openid})")
                                # 更新保存的成绩
                                data['last_grades'] = current_grades_dict
                                self.save_user_bindings()
                            else:
                                logger.error(f"发送企业微信图文消息失败 (openid: {openid}): {result}")
                                self.send_fallback_message(openid, grade_items, student_info)
                        except Exception as e:
                            logger.error(f"发送企业微信图文消息异常 (openid: {openid}): {e}")
                            self.send_fallback_message(openid, grade_items, student_info)
            
            except Exception as e:
                logger.error(f"自动检查成绩失败 (openid: {openid}): {e}")

    def check_user_follow(self, userid):
        """检查用户是否仍在关注"""
        access_token = self.get_access_token()
        if access_token:
            url = f"https://qyapi.weixin.qq.com/cgi-bin/user/get?access_token={access_token}&userid={userid}"
            try:
                response = requests.get(url)
                result = response.json()
                return result.get("errcode") == 0
            except Exception as e:
                logger.error(f"检查用户关注状态失败 (userid: {userid}): {e}")
        return False

def create_app():
    global app, scheduler, wechat, wxcpt
    
    # 初始化企业微信实例
    wechat = EnterpriseWeChat(
        corpid=CORP_ID,
        corpsecret="UIugLUofqZsSp7jkDVQgce1XSascxVpfSOVJPX5gLOs",
        agentid="1000002"
    )
    # 初始化 WXBizMsgCrypt
    wxcpt = WXBizMsgCrypt(TOKEN, ENCODING_AES_KEY, CORP_ID)
    
    # 只在主进程中初始化调度器
    if os.environ.get('GUNICORN_WORKER_TYPE') != 'worker':
        try:
            init_scheduler()
            logger.info("主进程和调度器初始化完成")
        except Exception as e:
            logger.error(f"调度器初始化失败: {e}")
    else:
        logger.info("工作进程初始化完成")
    
    return app

def init_scheduler():
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler(
            timezone=pytz.UTC,
            job_defaults={
                'coalesce': True,  # 合并执行错过的任务
                'max_instances': 1,  # 防止重复执行
                'misfire_grace_time': 3600  # 错过执行的宽限时间
            }
        )
        
        # 添加成绩检查任务
        @scheduler.scheduled_job('interval', minutes=60, id='check_grades')
        def check_grades():
            try:
                logger.info("开始执行定时成绩检查...")
                wechat.automatic_push_grades()
                logger.info("定时成绩检查完成")
            except Exception as e:
                logger.error(f"定时成绩检查失败: {e}")
        
        # 添加调度器健康检查任务
        @scheduler.scheduled_job('interval', minutes=5, id='scheduler_health_check')
        def check_scheduler_health():
            try:
                # 检查主任务的状态
                main_job = scheduler.get_job('check_grades')
                if not main_job:
                    logger.error("成绩检查任务丢失，正在重新添加...")
                    scheduler.add_job(
                        check_grades,
                        'interval',
                        minutes=60,
                        id='check_grades'
                    )
                
                # 检查调度器状态
                if not scheduler.running:
                    logger.error("调度器已停止，正在重启...")
                    scheduler.start()
                
                logger.info("调度器健康检查完成")
            except Exception as e:
                logger.error(f"调度器健康检查失败: {e}")
                try:
                    # 尝试重启调度器
                    if scheduler.running:
                        scheduler.shutdown()
                    scheduler.start()
                    logger.info("调度器已重启")
                except Exception as restart_error:
                    logger.error(f"调度器重启失败: {restart_error}")

        # 启动调度器
        if not scheduler.running:
            scheduler.start()
            logger.info("调度器已启动，包含健康检查机制")

# 路由定义
@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

@app.route('/msg', methods=['GET', 'POST'])
def handle_wechat():
    if request.method == 'GET':
        # 获取请求参数
        msg_signature = request.args.get('msg_signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')

        # 验证 URL
        ret, sReplyEchoStr = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
        if ret == 0:
            return sReplyEchoStr
        else:
            return "Verification failed", 400

    elif request.method == 'POST':
        try:
            # 获取加密消息
            msg_signature = request.args.get('msg_signature', '')
            timestamp = request.args.get('timestamp', '')
            nonce = request.args.get('nonce', '')
            
            # 获取 POST 数据
            xml_data = request.data.decode('utf-8')
            
            # 创建消息唯一标识
            message_id = f"{msg_signature}_{timestamp}_{nonce}"
            
            # 检查消息是否已处理
            with message_lock:
                if message_id in processed_messages:
                    logger.info(f"跳过重复消息: {message_id}")
                    return "success"
                
                # 记录已处理的消息
                processed_messages.add(message_id)
                
                # 清理过期消息ID (保留最近1000条)
                if len(processed_messages) > 1000:
                    processed_messages.clear()
            
            # 解密消息
            ret, xml_content = wxcpt.DecryptMsg(xml_data, msg_signature, timestamp, nonce)
            if ret != 0:
                logger.error(f"消息解密失败: {ret}")
                return "success"
                
            # 解析XML
            xml_tree = ET.fromstring(xml_content)
            msg_type = xml_tree.find('MsgType').text
            userid = xml_tree.find('FromUserName').text
            
            if msg_type == 'event':  # 添加事件处理
                event_type = xml_tree.find('Event').text
                if event_type.lower() == 'subscribe':
                    # 发送欢迎消息
                    welcome_msg = (
                        "👋 欢迎使用成绩查询系统！\n\n"
                        "📝 可用命令和功能：\n"
                        "1️⃣ 绑定 学号 密码 - 绑定您的学号和密码\n"
                        "2️⃣ 查询 - 先手动查询最新成绩\n"
                        "3️⃣ 自动推送 - 无需输入，有新成绩发布时自动推送\n\n"
                        "🔔 温馨提示：请先使用【绑定】命令绑定您的账号"
                    )
                    wechat.send_message(userid, welcome_msg)
            
            elif msg_type == 'text':
                content = xml_tree.find('Content').text.strip()
                
                # 处理消息
                if content.startswith('绑定'):
                    # 不要在这里发送验证消息，让 handle_bind 方法处理
                    response = wechat.handle_bind(userid, content)
                elif content == '查询':
                    response = wechat.handle_query(userid)
                else:
                    response = wechat.get_help_message()
                
                # 发送响应
                wechat.send_message(userid, response)
            
            return "success"
        except Exception as e:
            logger.error(f"处理消息异常：{e}")
            logger.exception("详细错误信息：")
            return "success"

# 添加调度器状态检查路由
@app.route('/scheduler/status', methods=['GET'])
def scheduler_status():
    """检查调度器状态的接口"""
    if scheduler is None:
        return {"status": "not_initialized"}, 500
    
    try:
        status = {
            "running": scheduler.running,
            "jobs": [
                {
                    "id": job.id,
                    "next_run_time": str(job.next_run_time),
                    "pending": job.pending
                }
                for job in scheduler.get_jobs()
            ]
        }
        return status, 200
    except Exception as e:
        logger.error(f"获取调度器状态失败: {e}")
        return {"error": str(e)}, 500

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
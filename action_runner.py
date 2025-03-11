import os
import json
import logging
from app import WeChatTest
import grade_fetcher

# 配置日志
logging.basicConfig(level=logging.INFO)

def main():
    # 从环境变量获取微信配置
    appid = os.environ.get('WECHAT_APPID')
    appsecret = os.environ.get('WECHAT_APPSECRET')
    
    if not appid or not appsecret:
        raise ValueError("Missing WECHAT_APPID or WECHAT_APPSECRET environment variables")

    # 初始化微信实例
    wechat = WeChatTest(appid=appid, appsecret=appsecret)
    
    # 检查用户绑定文件是否存在
    if not os.path.exists('user_bindings.json'):
        logging.warning("No user bindings found")
        return
        
    # 执行成绩推送
    wechat.automatic_push_grades()
    logging.info("Grade push completed")

if __name__ == "__main__":
    main() 
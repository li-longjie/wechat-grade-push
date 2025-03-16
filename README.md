# 辽工大成绩查询推送系统

一个基于企业微信的自动成绩查询和推送系统，可以实时查询成绩并在新成绩发布时自动推送通知。
大致思路：通过模拟登录处理滑动拼图，登录成功后获取新的cookie(登录信息)，进而爬取新成绩。再利用企业微信的应用创建，实现关注用户的消息推送，每一个小时爬起一次成绩和原成绩对比。有新成绩自动推送到微信。（需部署在服务器上）

## 功能特点

- 🔐 安全的账号绑定系统
- 📊 实时成绩查询
- 🔔 新成绩自动推送
- 🛡️ 企业微信加密通信
- 🤖 滑动验证码识别与处理
- 📱 移动端友好

## 系统架构

- 后端：Python Flask
- 浏览器自动化：DrissionPage
- 验证码识别：ddddocr
- 消息推送：企业微信API
- 定时任务：APScheduler
- 部署：Gunicorn

## 快速开始

### 环境要求

- Python 3.8+
- Google Chrome
- Linux/macOS/Windows

### 安装步骤

1. 克隆仓库
 https://github.com/li-longjie/wechat-grade-push.git
cd grade-push
2. 安装依赖
   pip3 install -r requirements.txt
3. 安装 Chrome 浏览器（Ubuntu示例）
   sudo apt-get update
   sudo apt-get install -y wget unzip
   wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
   sudo apt install ./google-chrome-stable_current_amd64.deb
4. 配置企业微信（在 app.py 中修改）
   CORP_ID = "your_corp_id"
  ENCODING_AES_KEY = "your_encoding_aes_key"
  TOKEN = "your_token"

### 使用方法

1. 绑定账号
   - 发送：`绑定 学号 密码`
   - 系统会验证账号并保存信息

2. 查询成绩
   - 发送：`查询`
   - 系统会返回最新成绩

3. 自动推送
   - 系统每小时自动检查新成绩
   - 发现新成绩自动推送通知

## 安全说明

- 所有密码经过加密存储
- 使用企业微信加密通信
- 定期自动清理缓存
- 支持异常登录检测

## 部署建议

1. 内存配置
   - 建议至少1GB RAM
   - Chrome 实例自动回收

2. 存储需求
   - 日志和缓存约需100MB
   - 建议挂载单独数据盘

3. 网络要求
   - 需要访问教务系统
   - 需要访问企业微信API

## 常见问题

1. Chrome 启动失败
   - 检查 Chrome 安装
   - 确认系统依赖完整
   - 查看日志详细错误

2. 验证码识别失败
   - 通常为网络问题
   - 系统会自动重试
   - 检查教务系统可访问性

3. 推送消息失败
   - 检查企业微信配置
   - 确认网络连接
   - 查看错误日志

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支
3. 提交改动
4. 发起 Pull Request

## 致谢

感谢以下开源项目：
- DrissionPage
- ddddocr
- Flask
- APScheduler

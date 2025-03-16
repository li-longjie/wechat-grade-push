import hashlib
import time
from xml.etree import ElementTree

# 配置
TOKEN = "wechatgrade"

def check_signature(signature, timestamp, nonce):
    """验证签名"""
    temp_list = [TOKEN, timestamp, nonce]
    temp_list.sort()
    temp_str = ''.join(temp_list)
    hash_sha1 = hashlib.sha1(temp_str.encode('utf-8')).hexdigest()
    return hash_sha1 == signature

def parse_xml(xml_string):
    """解析XML"""
    root = ElementTree.fromstring(xml_string)
    result = {}
    for child in root:
        result[child.tag] = child.text
    return result

def handler(environ, start_response):
    """WSGI 处理函数"""
    method = environ['REQUEST_METHOD']
    
    # 处理 GET 请求（验证）
    if method == 'GET':
        query = dict(item.split('=') for item in environ.get('QUERY_STRING', '').split('&') if item)
        signature = query.get('signature', '')
        timestamp = query.get('timestamp', '')
        nonce = query.get('nonce', '')
        echostr = query.get('echostr', '')

        if check_signature(signature, timestamp, nonce):
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [echostr.encode()]
        else:
            start_response('403 Forbidden', [('Content-Type', 'text/plain')])
            return [b'Invalid signature']

    # 处理 POST 请求（消息）
    elif method == 'POST':
        content_length = int(environ.get('CONTENT_LENGTH', 0))
        request_body = environ['wsgi.input'].read(content_length)
        xml_data = request_body.decode('utf-8')
        
        msg = parse_xml(xml_data)
        from_user = msg.get('FromUserName')
        to_user = msg.get('ToUserName')
        
        # 构造响应
        response = f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[收到你的消息了！]]></Content>
</xml>"""
        
        start_response('200 OK', [('Content-Type', 'text/xml; charset=utf-8')])
        return [response.encode('utf-8')]

    start_response('405 Method Not Allowed', [('Content-Type', 'text/plain')])
    return [b'Method not allowed']

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    server = make_server('0.0.0.0', 5000, handler)
    server.serve_forever() 
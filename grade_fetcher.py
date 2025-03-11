import json
import jsonpath
import requests
import urllib3
from DrissionPage import WebPage, ChromiumOptions
import base64
import ddddocr
import logging

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_grades(student_id, password):
    """获取成绩的主函数"""
    # 配置无头浏览器
    options = ChromiumOptions()
    options.set_argument('--headless=new')
    options.set_argument('--disable-gpu')
    options.set_argument('--no-sandbox')
    options.set_argument('--disable-dev-shm-usage')
    options.set_argument('--disable-software-rasterizer')
    options.set_argument('--disable-extensions')
    options.set_argument('--disable-browser-side-navigation')
    options.set_argument('--disable-infobars')
    options.set_argument('--window-position=-32000,-32000')

    page = WebPage(chromium_options=options)
    try:
        page.clear_cache()
        index_url = 'https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421e9fd529b2b287c1e72069db9d6502720d35c6c/gsapp/sys/wdcjapp/*default/index.do'
        page.get(index_url)
        page.wait(1)

        # 检查是否需要登录
        if "login" in page.url:
            login_url = "https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421f1e2559434357a467b1ac7a09641367b918300a4219f/authserver/login?service=https%3A%2F%2Fyjsglxt.lntu.edu.cn%2Fgsapp%2Fsys%2Fyjsemaphome%2Fportal%2Findex.do"
            page.get(login_url)
            page.wait(2)

            # 输入学号和密码
            page.ele('#username').input(student_id)
            page.ele('#password').input(password)
            page.ele('#login_submit').click()

            # 处理滑块验证码
            handle_slider(page)

            # 检查登录状态
            if "login" in page.url:
                raise Exception("登录失败")

        # 获取成绩
        return get_scores(page)
    except Exception as e:
        logging.error(f"获取成绩失败: {e}")
        raise
    finally:
        page.quit()

def handle_slider(page):
    """处理滑块验证码"""
    max_attempts = 5
    attempt = 0

    while attempt < max_attempts:
        slider = page.ele('x://div[@class="slider"]', timeout=5)
        if slider:
            logging.info(f"检测到滑块验证码，第 {attempt + 1} 次尝试")
            bg_img_elem = page.ele('#slider-img1')
            block_img_elem = page.ele('#slider-img2')

            if bg_img_elem and block_img_elem:
                bg_base64 = bg_img_elem.attrs.get('src').split(',')[1]
                block_base64 = block_img_elem.attrs.get('src').split(',')[1]

                bg_img_data = base64.b64decode(bg_base64)
                block_img_data = base64.b64decode(block_base64)

                try:
                    slide = ddddocr.DdddOcr(det=False, ocr=False)
                    res = slide.slide_match(block_img_data, bg_img_data)
                    offset_x = res['target'][0]

                    scale_ratio = 280 / 590
                    scaled_offset = min(max(offset_x * scale_ratio, 0), 280)

                    slider.drag(offset_x=scaled_offset, offset_y=0, duration=1.0)
                    page.wait(2)

                    if not page.ele('x://div[@class="slider"]', timeout=5):
                        logging.info("滑块验证通过")
                        return
                    else:
                        logging.info("滑块验证未通过，等待刷新")
                        page.wait(2)
                except Exception as e:
                    logging.error(f"滑块匹配失败: {e}")
                attempt += 1
            else:
                raise Exception("无法获取拼图图像")
        else:
            logging.info("未检测到滑块验证码")
            break

    if attempt == max_attempts:
        raise Exception("滑块验证失败，所有尝试均未成功")

def get_scores(page):
    """从页面获取成绩"""
    cookies = {}
    all_cookies = page.cookies()
    if isinstance(all_cookies, str):
        cookie_pairs = all_cookies.split('; ')
        for pair in cookie_pairs:
            if '=' in pair:
                name, value = pair.split('=', 1)
                cookies[name] = value
    else:
        for cookie in all_cookies:
            cookies[cookie.get('name', '')] = cookie.get('value', '')

    session = requests.Session()
    for key, value in cookies.items():
        session.cookies.set(key, value)

    index_url = 'https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421e9fd529b2b287c1e72069db9d6502720d35c6c/gsapp/sys/wdcjapp/*default/index.do'
    session.get(index_url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False)

    score_url = 'https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421e9fd529b2b287c1e72069db9d6502720d35c6c/gsapp/sys/wdcjapp/modules/wdcj/xscjcx.do?vpn-12-o2-yjsglxt.lntu.edu.cn'
    score_headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://webvpn.lntu.edu.cn',
        'Referer': index_url,
    }
    query_data = {
        'querySetting': '[{"name":"SFYX","caption":"是否有效","linkOpt":"AND","builderList":"cbl_m_List","builder":"m_value_equal","value":"1","value_display":"是"}]',
        'pageSize': 100,
        'pageNumber': 1
    }

    score_res = session.post(score_url, headers=score_headers, data=query_data, verify=False)
    if score_res.status_code == 200:
        try:
            res2 = json.loads(score_res.content)
            kc = jsonpath.jsonpath(res2, '$..KCMC') or []
            score = jsonpath.jsonpath(res2, '$..DYBFZCJ') or []
            return list(zip(kc, score)) if kc and score else []
        except json.JSONDecodeError:
            logging.error("响应内容不是有效的JSON")
            return []
    else:
        logging.error(f"成绩查询失败，状态码: {score_res.status_code}")
        return []

if __name__ == "__main__":
    # 测试用例
    grades = get_grades("your_student_id", "your_password")
    print(grades)
import json
import jsonpath
import requests
import urllib3
from DrissionPage import WebPage, ChromiumOptions
import base64
import ddddocr
import logging
import os
import time

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 获取模块的 logger
logger = logging.getLogger(__name__)

def get_grades(student_id, password):
    """获取成绩的主函数"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logger.info("开始获取成绩...")

            # 清理旧的浏览器进程
            os.system('pkill -f chrome')
            time.sleep(1)
            
            # 确保临时目录存在并清空
            user_data_dir = f'/tmp/chrome-data-{os.getpid()}'
            if os.path.exists(user_data_dir):
                os.system(f'rm -rf {user_data_dir}/*')
            else:
                os.makedirs(user_data_dir)
            
            options = ChromiumOptions()
            
            # root用户必需的配置
            options.set_argument('--no-sandbox')  # 必须放在最前面
            options.set_argument('--disable-setuid-sandbox')
            
            # 基础配置
            options.set_argument('--headless=new')
            options.set_argument('--disable-gpu')
            options.set_argument('--disable-dev-shm-usage')
            
            # 内存和性能优化
            options.set_argument('--disable-software-rasterizer')
            options.set_argument('--disable-extensions')
            options.set_argument('--disable-web-security')
            options.set_argument('--disable-features=IsolateOrigins,site-per-process')
            
            # 设置较小的内存限制
            options.set_argument('--memory-pressure-off')
            options.set_argument('--js-flags="--max-old-space-size=256"')
            
            # 设置用户数据目录和调试端口
            options.set_argument(f'--user-data-dir={user_data_dir}')
            debug_port = 9222 + (os.getpid() % 1000)
            options.set_argument(f'--remote-debugging-port={debug_port}')
            
            # 设置浏览器路径
            options.set_browser_path('/usr/bin/google-chrome')
            
            # 添加更多的安全相关配置
            options.set_argument('--disable-background-networking')
            options.set_argument('--disable-default-apps')
            options.set_argument('--disable-sync')
            options.set_argument('--disable-translate')
            options.set_argument('--metrics-recording-only')
            options.set_argument('--mute-audio')
            options.set_argument('--no-first-run')
            
            logger.info("Chrome 配置完成，准备启动浏览器...")

            page = WebPage(chromium_options=options)
            logger.info("浏览器启动成功")

            # 增加页面加载超时时间
            page.set.timeouts(30000)  # 设置30秒超时

            page.clear_cache()
            index_url = 'https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421e9fd529b2b287c1e72069db9d6502720d35c6c/gsapp/sys/wdcjapp/*default/index.do'
            page.get(index_url)
            logger.info(f"成功访问首页，当前URL: {page.url}")

            page.wait(1)

            # 检查是否需要登录
            if "login" in page.url:
                login_url = "https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421f1e2559434357a467b1ac7a09641367b918300a4219f/authserver/login?service=https%3A%2F%2Fyjsglxt.lntu.edu.cn%2Fgsapp%2Fsys%2Fyjsemaphome%2Fportal%2Findex.do"
                page.get(login_url)
                page.wait(2)

                # 输入学号和密码
                logger.info("输入学号和密码...")
                page.ele('#username').input(student_id)
                page.ele('#password').input(password)
                page.ele('#login_submit').click()

                # 处理滑块验证码
                handle_slider(page)

                # 检查登录状态
                page.wait(3)  # 等待跳转
                if "login" in page.url:
                    logger.error("登录失败，当前URL: %s", page.url)
                    return []  # 直接返回空列表，不再重试

            # 获取成绩
            return get_scores(page)
        except Exception as e:
            retry_count += 1
            logger.error(f"第 {retry_count} 次尝试失败: {e}")
            
            if 'page' in locals():
                try:
                    page.quit()
                except:
                    pass
                    
            # 如果是登录失败，直接返回空列表
            if "login" in str(e):
                return []
                
            # 如果还有重试机会，等待后继续
            if retry_count < max_retries:
                time.sleep(2)
                continue
            else:
                raise Exception(f"重试 {max_retries} 次后仍然失败: {str(e)}")

def handle_slider(page):
    """处理滑块验证码"""
    max_attempts = 5
    attempt = 0

    while attempt < max_attempts:
        slider = page.ele('x://div[@class="slider"]', timeout=5)
        if slider:
            logger.info(f"检测到滑块验证码，第 {attempt + 1} 次尝试")
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
                        logger.info("滑块验证通过")
                        return
                    else:
                        logger.info("滑块验证未通过，等待刷新")
                        page.wait(2)
                except Exception as e:
                    logger.error(f"滑块匹配失败: {e}")
                attempt += 1
            else:
                raise Exception("无法获取拼图图像")
        else:
            logger.info("未检测到滑块验证码")
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

    # 获取成绩
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
    grades = []
    
    if score_res.status_code == 200:
        try:
            res2 = json.loads(score_res.content)
            kc = jsonpath.jsonpath(res2, '$..KCMC') or []
            score = jsonpath.jsonpath(res2, '$..DYBFZCJ') or []
            grades = list(zip(kc, score)) if kc and score else []
            logger.info(f"成功获取成绩: {grades}")
            
            # 获取排名
            try:
                # 访问排名系统主页面
                rank_index_url = 'https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421e9fd529b2b287c1e72069db9d6502720d35c6c/gsapp/sys/wthdglapp/*default/index.do'
                session.get(rank_index_url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
                
                # 查询排名
                rank_url = 'https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421e9fd529b2b287c1e72069db9d6502720d35c6c/gsapp/sys/wthdglapp/modules/fzdxdjb/query.do?vpn-12-o2-yjsglxt.lntu.edu.cn'
                rank_headers = {
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Origin': 'https://webvpn.lntu.edu.cn',
                    'Referer': f'{rank_index_url}?v=8658628a-146d-4cb5-8b9a-dde04b05d6b0&THEME=blue&EMAP_LANG=zh&min=1&_yhz=08e2bba0cc7a4aeda8cb4de127a55914',
                }
                
                rank_res = session.get(rank_url, headers=rank_headers, verify=False)
                logger.info(f"排名查询状态码: {rank_res.status_code}")
                
                if rank_res.status_code == 200:
                    rank_data = json.loads(rank_res.content)
                    rank = jsonpath.jsonpath(rank_data, '$..ZYPMZYZRS')
                    if rank and rank[0]:
                        try:
                            rank_number = rank[0].split('/')[0]  # 获取斜杠前的数字
                            rank_info = f"🏅 最新排名：{rank_number}"  # 直接在这里添加 emoji
                            logger.info(f"获取到排名信息: {rank_info}")
                            grades.insert(0, ("排名信息", rank_info))
                            logger.info(f"成功添加排名信息到成绩列表: {grades}")
                        except Exception as e:
                            logger.error(f"处理排名数字时出错: {e}")
                
            except Exception as e:
                logger.error(f"获取排名时发生错误: {e}")
            
            return grades
            
        except json.JSONDecodeError:
            logger.error("响应内容不是有效的JSON")
            return []
    else:
        logger.error(f"成绩查询失败，状态码: {score_res.status_code}")
        return []

def format_grades(grades):
    """格式化成绩展示"""
    if not grades:
        return "❌ 暂无成绩信息"
    
    result = "📊 成绩单\n"
    result += "====================\n"
    
    # 检查是否有排名信息
    if grades and grades[0][0] == "排名信息":
        result += f"{grades[0][1]}\n"  # 直接使用包含 emoji 的排名信息
        result += "====================\n"
        grades = grades[1:]  # 移除排名信息，继续处理成绩
    
    for course, score in grades:
        try:
            # 只对成绩分数进行浮点数转换
            if course != "排名信息":  # 跳过排名信息的浮点数转换
                score_float = float(score)
                # 根据分数添加不同的表情
                if score_float >= 90:
                    emoji = "🏆"
                elif score_float >= 80:
                    emoji = "✨"
                elif score_float >= 70:
                    emoji = "👍"
                elif score_float >= 60:
                    emoji = "💪"
                else:
                    emoji = "💡"
                
                result += f"{emoji} {course}：{score}\n"
        except ValueError:
            # 如果是排名信息，直接显示
            if course == "排名信息":
                result += f"{score}\n"
            else:
                result += f"ℹ️ {course}：{score}\n"
    
    result += "====================\n"
    result += "💝 加油！继续保持！"
    logger.info(result)
    return result

def test_grades():
    """测试成绩查询功能"""
    logger.info("开始测试成绩查询...")
    try:
        student_id = "4724200535"
        password = "Hap2pyne2wyear357*"
        
        grades = get_grades(student_id, password)
        formatted_grades = format_grades(grades)
        logger.info("\n%s", formatted_grades)
        
    except Exception as e:
        logger.error("测试失败: %s", e)
        raise

def verify_credentials(student_id, password):
    """验证学号密码是否正确"""
    logger.info("开始验证账号密码...")
    max_retries = 3
    retry_count = 0
    
    # 添加进程锁，防止并发访问
    lock_file = f'/tmp/chrome-lock-{os.getpid()}'
    
    try:
        # 检查是否有其他进程在运行
        if os.path.exists(lock_file):
            logger.info("另一个验证进程正在运行，等待...")
            return False, "系统繁忙，请稍后重试"
            
        # 创建锁文件
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))

        while retry_count < max_retries:
            try:
                # 清理旧的浏览器进程
                os.system('pkill -f chrome')
                time.sleep(1)
                
                # 使用进程ID和时间戳生成唯一的目录名
                timestamp = int(time.time())
                user_data_dir = f'/tmp/chrome-data-{os.getpid()}-{timestamp}'
                if os.path.exists(user_data_dir):
                    os.system(f'rm -rf {user_data_dir}/*')
                else:
                    os.makedirs(user_data_dir)
                
                options = ChromiumOptions()
                
                # root用户必需的配置
                options.set_argument('--no-sandbox')  # 必须放在最前面
                options.set_argument('--disable-setuid-sandbox')
                
                # 基础配置
                options.set_argument('--headless=new')
                options.set_argument('--disable-gpu')
                options.set_argument('--disable-dev-shm-usage')
                
                # 内存和性能优化
                options.set_argument('--disable-software-rasterizer')
                options.set_argument('--disable-extensions')
                options.set_argument('--disable-web-security')
                options.set_argument('--disable-features=IsolateOrigins,site-per-process')
                
                # 设置较小的内存限制
                options.set_argument('--memory-pressure-off')
                options.set_argument('--js-flags="--max-old-space-size=256"')
                
                # 设置用户数据目录和调试端口
                options.set_argument(f'--user-data-dir={user_data_dir}')
                debug_port = 9222 + (os.getpid() % 1000) + timestamp % 1000
                options.set_argument(f'--remote-debugging-port={debug_port}')
                
                # 设置浏览器路径
                options.set_browser_path('/usr/bin/google-chrome')
                
                # 添加更多的安全相关配置
                options.set_argument('--disable-background-networking')
                options.set_argument('--disable-default-apps')
                options.set_argument('--disable-sync')
                options.set_argument('--disable-translate')
                options.set_argument('--metrics-recording-only')
                options.set_argument('--mute-audio')
                options.set_argument('--no-first-run')
                
                logger.info(f"正在启动浏览器，使用端口 {debug_port}")
                page = WebPage(chromium_options=options)
                
                # 设置超时
                page.set.timeouts(30000)  # 30秒超时
                
                login_url = "https://webvpn.lntu.edu.cn/https/77726476706e69737468656265737421f1e2559434357a467b1ac7a09641367b918300a4219f/authserver/login"
                page.get(login_url)
                page.wait(2)

                # 输入学号和密码
                username_ele = page.ele('#username', timeout=10)
                password_ele = page.ele('#password', timeout=10)
                submit_ele = page.ele('#login_submit', timeout=10)

                if not all([username_ele, password_ele, submit_ele]):
                    raise Exception("登录页面元素未找到")

                username_ele.input(student_id)
                password_ele.input(password)
                submit_ele.click()

                # 处理滑块验证码
                handle_slider(page)

                # 检查登录状态
                page.wait(3)  # 等待跳转
                if "login" in page.url:
                    logger.error("登录失败")
                    return False, "账号或密码错误，请检查后重试"
                
                logger.info("账号密码验证成功")
                return True, "验证成功"

            except Exception as e:
                retry_count += 1
                logger.error(f"第 {retry_count} 次尝试失败: {e}")
                
                if 'page' in locals():
                    try:
                        page.quit()
                    except:
                        pass
                        
                # 只有在非登录失败的错误时才重试
                if retry_count < max_retries and "login" not in str(e):
                    time.sleep(2)
                    continue
                else:
                    if "login" in str(e):
                        return False, "账号或密码错误，请检查后重试"
                    return False, f"验证失败: {str(e)}"
            finally:
                # 清理临时文件
                try:
                    os.system(f'rm -rf {user_data_dir}')
                except:
                    pass
    finally:
        # 清理锁文件
        try:
            os.remove(lock_file)
        except:
            pass

    return False, "验证失败: 超过最大重试次数"

if __name__ == "__main__":
    test_grades()
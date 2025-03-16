from DrissionPage import WebPage, ChromiumOptions
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_browser():
    logging.info("开始测试...")
    
    # 配置浏览器选项
    options = ChromiumOptions()
    options.set_argument('--headless')
    options.set_argument('--no-sandbox')
    options.set_argument('--disable-gpu')
    options.set_argument('--disable-dev-shm-usage')
    options.set_browser_path('/usr/bin/google-chrome')
    
    logging.info("浏览器配置完成")
    
    try:
        # 创建浏览器实例
        logging.info("正在启动浏览器...")
        page = WebPage(chromium_options=options)
        logging.info("浏览器启动成功")
        
        # 访问百度
        logging.info("正在访问百度...")
        page.get('https://www.baidu.com')
        logging.info(f"页面标题: {page.title}")
        
        # 访问辽工大
        logging.info("正在访问辽工大...")
        page.get('https://webvpn.lntu.edu.cn')
        logging.info(f"页面标题: {page.title}")
        
    except Exception as e:
        logging.error(f"测试失败: {e}")
        raise
    finally:
        # 关闭浏览器
        try:
            page.quit()
            logging.info("浏览器已关闭")
        except:
            pass

if __name__ == "__main__":
    test_browser() 
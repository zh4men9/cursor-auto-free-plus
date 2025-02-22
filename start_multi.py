import os
import json
import time
import random
import signal
import uuid
import psutil
import atexit
from datetime import datetime, timedelta
from multiprocessing import Process, Value, Manager, current_process
from get_email_code import EmailVerificationHandler
from account_storage import AccountStorage
from browser_utils import BrowserManager
from logger import logging
from cursor_pro_keep_alive import EmailGenerator
from config import Config
from enum import Enum
from typing import Optional

# 使用共享变量记录成功数量
success_count = Value('i', 0)
running_processes = set()

# 定义全局变量
LOGIN_URL = "https://authenticator.cursor.sh"
SIGN_UP_URL = "https://authenticator.cursor.sh/sign-up"
SETTINGS_URL = "https://www.cursor.com/settings"
EMOJI = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️", "SUCCESS": "✅"}

class VerificationStatus(Enum):
    """验证状态枚举"""

    PASSWORD_PAGE = "@name=password"
    CAPTCHA_PAGE = "@data-index=0"
    ACCOUNT_SETTINGS = "Account Settings"

class TurnstileError(Exception):
    """Turnstile 验证相关异常"""
    pass

def save_screenshot(tab, stage: str, timestamp: bool = True) -> None:
    """
    保存页面截图

    Args:
        tab: 浏览器标签页对象
        stage: 截图阶段标识
        timestamp: 是否添加时间戳
    """
    try:
        # 创建 screenshots 目录
        screenshot_dir = "screenshots"
        if not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir)

        # 生成文件名
        if timestamp:
            filename = f"turnstile_{stage}_{int(time.time())}.png"
        else:
            filename = f"turnstile_{stage}.png"

        filepath = os.path.join(screenshot_dir, filename)

        # 保存截图
        tab.get_screenshot(filepath)
        logging.debug(f"截图已保存: {filepath}")
    except Exception as e:
        logging.warning(f"截图保存失败: {str(e)}")

def check_verification_success(tab) -> Optional[VerificationStatus]:
    """
    检查验证是否成功

    Returns:
        VerificationStatus: 验证成功时返回对应状态，失败返回 None
    """
    for status in VerificationStatus:
        if tab.ele(status.value):
            logging.info(f"验证成功 - 已到达{status.name}页面")
            return status
    return None

def handle_turnstile(tab, max_retries: int = 2, retry_interval: tuple = (1, 2)) -> bool:
    """
    处理 Turnstile 验证

    Args:
        tab: 浏览器标签页对象
        max_retries: 最大重试次数
        retry_interval: 重试间隔时间范围(最小值, 最大值)

    Returns:
        bool: 验证是否成功

    Raises:
        TurnstileError: 验证过程中出现异常
    """
    logging.info("正在检测 Turnstile 验证...")
    save_screenshot(tab, "start")

    retry_count = 0

    try:
        while retry_count < max_retries:
            retry_count += 1
            logging.debug(f"第 {retry_count} 次尝试验证")

            try:
                # 定位验证框元素
                challenge_check = (
                    tab.ele("@id=cf-turnstile", timeout=2)
                    .child()
                    .shadow_root.ele("tag:iframe")
                    .ele("tag:body")
                    .sr("tag:input")
                )

                if challenge_check:
                    logging.info("检测到 Turnstile 验证框，开始处理...")
                    # 随机延时后点击验证
                    time.sleep(random.uniform(1, 3))
                    challenge_check.click()
                    time.sleep(2)

                    # 保存验证后的截图
                    save_screenshot(tab, "clicked")

                    # 检查验证结果
                    if check_verification_success(tab):
                        logging.info("Turnstile 验证通过")
                        save_screenshot(tab, "success")
                        return True

            except Exception as e:
                logging.debug(f"当前尝试未成功: {str(e)}")

            # 检查是否已经验证成功
            if check_verification_success(tab):
                return True

            # 随机延时后继续下一次尝试
            time.sleep(random.uniform(*retry_interval))

        # 超出最大重试次数
        logging.error(f"验证失败 - 已达到最大重试次数 {max_retries}")
        logging.error(
            "请前往开源项目查看更多信息：https://github.com/zh4men9/cursor-auto-free-plus"
        )
        save_screenshot(tab, "failed")
        return False

    except Exception as e:
        error_msg = f"Turnstile 验证过程发生异常: {str(e)}"
        logging.error(error_msg)
        save_screenshot(tab, "error")
        raise TurnstileError(error_msg)

def cleanup_processes():
    """清理所有运行中的进程"""
    for pid in running_processes:
        try:
            process = psutil.Process(pid)
            process.terminate()
            process.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

# 注册清理函数
atexit.register(cleanup_processes)

def init_account_dir():
    """初始化账号目录"""
    # 创建本次运行的唯一标识
    run_id = str(uuid.uuid4())
    account_base_dir = 'account'
    account_dir = os.path.join(account_base_dir, run_id)
    
    # 确保目录存在
    os.makedirs(account_base_dir, exist_ok=True)
    os.makedirs(account_dir, exist_ok=True)
    
    print(f"本次运行ID: {run_id}")
    print(f"账号文件保存目录: {account_dir}")
    
    return account_dir

def get_cursor_session_token(tab, max_attempts=3, retry_interval=2):
    """获取Cursor会话token"""
    logging.info("开始获取cookie")
    attempts = 0

    while attempts < max_attempts:
        try:
            cookies = tab.cookies()
            for cookie in cookies:
                if cookie.get("name") == "WorkosCursorSessionToken":
                    return cookie["value"].split("%3A%3A")[1]

            attempts += 1
            if attempts < max_attempts:
                logging.warning(f"第 {attempts} 次尝试未获取到CursorSessionToken，{retry_interval}秒后重试...")
                time.sleep(retry_interval)
            else:
                logging.error(f"已达到最大尝试次数({max_attempts})，获取CursorSessionToken失败")

        except Exception as e:
            logging.error(f"获取cookie失败: {str(e)}")
            attempts += 1
            if attempts < max_attempts:
                logging.info(f"将在 {retry_interval} 秒后重试...")
                time.sleep(retry_interval)

    return None

def init_browser_with_retry(max_retries=3, retry_delay=5):
    """初始化浏览器，带重试机制"""
    for attempt in range(max_retries):
        try:
            # 先获取user_agent
            browser_manager = BrowserManager()
            browser = browser_manager.init_browser()
            user_agent = browser.latest_tab.run_js("return navigator.userAgent")
            browser_manager.quit()
            
            if not user_agent:
                logging.error("获取user agent失败，使用默认值")
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
            # 剔除user_agent中的"HeadlessChrome"
            user_agent = user_agent.replace("HeadlessChrome", "Chrome")
            logging.info(f"使用user_agent: {user_agent}")
            
            # 使用修改后的user_agent初始化浏览器
            browser_manager = BrowserManager()
            browser = browser_manager.init_browser(user_agent)
            return browser_manager, browser
            
        except Exception as e:
            if browser_manager:
                try:
                    browser_manager.quit()
                except:
                    pass
                    
            if attempt < max_retries - 1:
                logging.warning(f"浏览器初始化失败，{retry_delay}秒后重试: {str(e)}")
                time.sleep(retry_delay)
            else:
                logging.error(f"浏览器初始化失败，达到最大重试次数: {str(e)}")
                raise

def sign_up_account(browser, tab):
    """
    注册账号
    """
    # 声明全局变量
    global account, password, first_name, last_name, email_handler
    
    logging.info("=== 开始注册账号流程 ===")
    logging.info(f"正在访问注册页面: {SIGN_UP_URL}")
    tab.get(SIGN_UP_URL)

    try:
        if tab.ele("@name=first_name"):
            logging.info("正在填写个人信息...")
            tab.actions.click("@name=first_name").input(first_name)
            logging.info(f"已输入名字: {first_name}")
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=last_name").input(last_name)
            logging.info(f"已输入姓氏: {last_name}")
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=email").input(account)
            logging.info(f"已输入邮箱: {account}")
            time.sleep(random.uniform(1, 3))

            logging.info("提交个人信息...")
            tab.actions.click("@type=submit")

    except Exception as e:
        logging.error(f"注册页面访问失败: {str(e)}")
        return False

    # 处理第一次 Turnstile 验证
    if not handle_turnstile(tab):
        logging.error("第一次 Turnstile 验证失败，跳过当前账号注册")
        return False

    try:
        if tab.ele("@name=password"):
            logging.info("正在设置密码...")
            tab.ele("@name=password").input(password)
            time.sleep(random.uniform(1, 3))

            logging.info("提交密码...")
            tab.ele("@type=submit").click()
            logging.info("密码设置完成，等待系统响应...")

    except Exception as e:
        logging.error(f"密码设置失败: {str(e)}")
        return False

    if tab.ele("This email is not available."):
        logging.error("注册失败：邮箱已被使用")
        return False

    # 处理第二次 Turnstile 验证
    if not handle_turnstile(tab):
        logging.error("第二次 Turnstile 验证失败，跳过当前账号注册")
        return False

    while True:
        try:
            if tab.ele("Account Settings"):
                logging.info("注册成功 - 已进入账户设置页面")
                break
            if tab.ele("@data-index=0"):
                logging.info("正在获取邮箱验证码...")
                code = email_handler.get_verification_code()
                if not code:
                    logging.error("获取验证码失败")
                    return False

                logging.info(f"成功获取验证码: {code}")
                logging.info("正在输入验证码...")
                i = 0
                for digit in code:
                    tab.ele(f"@data-index={i}").input(digit)
                    time.sleep(random.uniform(0.1, 0.3))
                    i += 1
                logging.info("验证码输入完成")
                break
        except Exception as e:
            logging.error(f"验证码处理过程出错: {str(e)}")
            return False

    # 处理第三次 Turnstile 验证
    if not handle_turnstile(tab):
        logging.error("第三次 Turnstile 验证失败，跳过当前账号注册")
        return False

    wait_time = random.randint(3, 6)
    for i in range(wait_time):
        logging.info(f"等待系统处理中... 剩余 {wait_time-i} 秒")
        time.sleep(1)

    logging.info("正在获取账户信息...")
    tab.get(SETTINGS_URL)
    try:
        usage_selector = (
            "css:div.col-span-2 > div > div > div > div > "
            "div:nth-child(1) > div.flex.items-center.justify-between.gap-2 > "
            "span.font-mono.text-sm\\/\\[0\\.875rem\\]"
        )
        usage_ele = tab.ele(usage_selector)
        if usage_ele:
            usage_info = usage_ele.text
            total_usage = usage_info.split("/")[-1].strip()
            logging.info(f"账户可用额度上限: {total_usage}")
            logging.info(
                "请前往开源项目查看更多信息：https://github.com/zh4men9/cursor-auto-free-plus"
            )
    except Exception as e:
        logging.error(f"获取账户额度信息失败: {str(e)}")

    logging.info("\n=== 注册完成 ===")
    account_info = f"Cursor 账号信息:\n邮箱: {account}\n密码: {password}"
    logging.info(account_info)
    time.sleep(5)
    return True

def register_single_account(process_id: int, account_dir: str):
    """注册单个账号的完整流程"""
    browser_manager = None
    
    try:
        # 记录进程ID用于清理
        running_processes.add(os.getpid())
        logging.info(f"进程 {process_id} (PID: {os.getpid()}) 开始运行")
        
        # 设置进程特定的账号文件
        account_file = os.path.join(account_dir, f'accounts_{process_id}.json')
        os.environ['ACCOUNT_STORAGE_FILE'] = account_file
        account_storage = AccountStorage()
        logging.info(f"账号存储文件: {account_file}")
        
        # 初始化邮箱验证模块
        logging.info("正在初始化邮箱验证模块...")
        global email_handler
        email_handler = EmailVerificationHandler()
        
        # 打印配置信息
        config = Config()
        config.print_config()
        
        # 生成账号信息
        email_generator = EmailGenerator()
        logging.info(f"域名: {email_generator.domain}")
        global account, password, first_name, last_name
        account = email_generator.generate_email()
        password = email_generator.default_password
        first_name = email_generator.default_first_name
        last_name = email_generator.default_last_name
        logging.info(f"生成的邮箱账号: {account}")
        
        # 初始化浏览器（带重试）
        try:
            logging.info("正在初始化浏览器...")
            browser_manager, browser = init_browser_with_retry()
            tab = browser.latest_tab
            
            # 获取并打印浏览器的user-agent
            current_user_agent = tab.run_js("return navigator.userAgent")
            logging.info(f"当前user-agent: {current_user_agent}")
            
        except Exception as e:
            logging.error(f"无法初始化浏览器，跳过此账号: {str(e)}")
            return
        
        try:
            # 执行注册
            if sign_up_account(browser, tab):
                logging.info("正在获取会话令牌...")
                token = get_cursor_session_token(tab)
                if token:
                    # 完善账号信息
                    account_info = {
                        'email': account,
                        'password': password,
                        'first_name': first_name,
                        'last_name': last_name,
                        'access_token': token,
                        'refresh_token': token,
                        'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # 保存账号信息
                    logging.info("正在保存账号信息...")
                    if account_storage.add_account(account_info):
                        with success_count.get_lock():
                            success_count.value += 1
                        logging.info(f"{EMOJI['SUCCESS']} 账号注册成功并已保存")
                        logging.info(f"当前成功注册数量: {success_count.value}")
                    else:
                        logging.error(f"{EMOJI['ERROR']} 账号信息保存失败")
                else:
                    logging.error(f"{EMOJI['ERROR']} 获取会话令牌失败")
            else:
                logging.error(f"{EMOJI['ERROR']} 账号注册失败")
        
        finally:
            # 确保浏览器被关闭
            if browser_manager:
                try:
                    logging.info("正在关闭浏览器...")
                    browser_manager.quit()
                except Exception as e:
                    logging.error(f"关闭浏览器时出错: {str(e)}")
                
    except Exception as e:
        logging.error(f"注册过程出现错误: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
    finally:
        # 从运行集合中移除进程ID
        running_processes.discard(os.getpid())
        logging.info(f"进程 {process_id} (PID: {os.getpid()}) 结束运行")
        
        # 确保浏览器被关闭（双重保险）
        if browser_manager:
            try:
                browser_manager.quit()
            except:
                pass

def merge_account_files(account_dir: str):
    """合并当前运行产生的账号文件"""
    all_accounts = []
    
    # 读取当前运行目录下的所有账号文件
    for filename in os.listdir(account_dir):
        if filename.startswith('accounts_') and filename.endswith('.json'):
            file_path = os.path.join(account_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    accounts = json.load(f)
                    all_accounts.extend(accounts)
            except Exception as e:
                print(f"处理文件 {filename} 时出错: {e}")
    
    # 保存合并后的账号到当前运行目录
    if all_accounts:
        try:
            merged_file = os.path.join(account_dir, 'merged_accounts.json')
            with open(merged_file, 'w', encoding='utf-8') as f:
                json.dump(all_accounts, f, ensure_ascii=False, indent=4)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 成功合并 {len(all_accounts)} 个账号到 {merged_file}")
        except Exception as e:
            print(f"保存合并账号时出错: {e}")

def main():
    process_count = 5  # 降低并发数量
    last_merge_time = datetime.now()
    merge_interval = timedelta(minutes=5)
    
    # 在主进程中创建UUID目录
    account_dir = init_account_dir()
    
    try:
        while True:
            processes = []
            
            # 启动多个进程
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 启动 {process_count} 个注册进程")
            for i in range(process_count):
                print(f"\n--- 正在注册第 {i+1}/{process_count} 个账号 ---")
                p = Process(target=register_single_account, args=(i, account_dir))
                processes.append(p)
                p.start()
                time.sleep(random.uniform(10, 20))  # 增加启动间隔
            
            # 等待所有进程完成
            for p in processes:
                p.join(timeout=600)  # 10分钟超时
                if p.is_alive():
                    p.terminate()
                    p.join(1)
                    if p.is_alive():
                        os.kill(p.pid, signal.SIGKILL)
            
            # 合并账号文件
            if datetime.now() - last_merge_time > merge_interval:
                merge_account_files(account_dir)
                last_merge_time = datetime.now()
                print(f"当前已成功注册账号数量: {success_count.value}")
            
            # 检查是否需要继续
            if success_count.value >= 100:  # 设置目标数量
                print("已达到目标注册数量，程序结束")
                break
            
            # 较长延迟后开始下一轮
            time.sleep(random.uniform(5, 10))
            
    except KeyboardInterrupt:
        print("\n正在停止所有进程...")
        cleanup_processes()
        
    finally:
        # 最后合并一次
        merge_account_files(account_dir)
        print(f"总共成功注册账号数量: {success_count.value}")

if __name__ == '__main__':
    main() 
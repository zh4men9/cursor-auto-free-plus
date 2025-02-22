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

# 使用共享变量记录成功数量
success_count = Value('i', 0)
running_processes = set()

# 定义全局变量
LOGIN_URL = "https://authenticator.cursor.sh"
SIGN_UP_URL = "https://authenticator.cursor.sh/sign-up"
SETTINGS_URL = "https://www.cursor.com/settings"
EMOJI = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️", "SUCCESS": "✅"}

class TurnstileError(Exception):
    """Turnstile 验证相关异常"""
    pass

def save_screenshot(tab, stage: str, timestamp: bool = True) -> None:
    """保存页面截图"""
    try:
        screenshot_dir = "screenshots"
        if not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir)

        if timestamp:
            filename = f"turnstile_{stage}_{int(time.time())}.png"
        else:
            filename = f"turnstile_{stage}.png"

        filepath = os.path.join(screenshot_dir, filename)
        tab.get_screenshot(filepath)
        logging.debug(f"截图已保存: {filepath}")
    except Exception as e:
        logging.warning(f"截图保存失败: {str(e)}")

def handle_turnstile(tab, max_retries: int = 2, retry_interval: tuple = (2, 4)) -> bool:
    """
    处理 Turnstile 验证

    Args:
        tab: 浏览器标签页对象
        max_retries: 最大重试次数
        retry_interval: 重试间隔时间范围(最小值, 最大值)

    Returns:
        bool: 验证是否成功
    """
    logging.info("正在检测 Turnstile 验证...")
    retry_count = 0
    
    while retry_count < max_retries:
        retry_count += 1
        logging.info(f"第 {retry_count}/{max_retries} 次尝试验证")
        
        try:
            # 定位验证框元素
            challenge_check = (
                tab.ele("@id=cf-turnstile", timeout=5)
                .child()
                .shadow_root.ele("tag:iframe")
                .ele("tag:body")
                .sr("tag:input")
            )

            if challenge_check:
                logging.info("检测到 Turnstile 验证框，开始处理...")
                # 随机延时后点击验证
                wait_time = random.uniform(1, 3)
                logging.info(f"等待 {wait_time:.1f} 秒后点击验证...")
                time.sleep(wait_time)
                challenge_check.click()
                
                # 等待验证结果
                wait_time = 5
                logging.info(f"点击完成，等待 {wait_time} 秒检查验证结果...")
                time.sleep(wait_time)

                # 检查验证结果
                if check_verification_success(tab):
                    logging.info(f"{EMOJI['SUCCESS']} Turnstile 验证通过")
                    return True
                else:
                    logging.warning("验证未通过，检查是否需要重试")

            else:
                # 如果没有找到验证框，检查是否已经验证成功
                if check_verification_success(tab):
                    logging.info(f"{EMOJI['SUCCESS']} 页面已验证通过")
                    return True
                logging.warning("未检测到验证框，也未发现成功标志")

        except Exception as e:
            logging.error(f"验证过程出错: {str(e)}")
            import traceback
            logging.debug(traceback.format_exc())

        if retry_count < max_retries:
            wait_time = random.uniform(*retry_interval)
            logging.warning(f"验证未成功，{wait_time:.1f} 秒后进行第 {retry_count + 1} 次重试...")
            time.sleep(wait_time)
        else:
            logging.error(f"{EMOJI['ERROR']} 验证失败 - 已达到最大重试次数 {max_retries}")
            return False

    return False

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

def sign_up_account(browser, tab, email_handler, account_info):
    """注册单个账号"""
    max_verification_retries = 3  # 最大验证码重试次数
    verification_timeout = 180  # 验证码获取超时时间（秒）
    
    logging.info("=== 开始注册账号流程 ===")
    logging.info(f"正在访问注册页面: {SIGN_UP_URL}")
    tab.get(SIGN_UP_URL)

    try:
        if tab.ele("@name=first_name"):
            logging.info("正在填写个人信息...")
            tab.actions.click("@name=first_name").input(account_info['first_name'])
            logging.info(f"已输入名字: {account_info['first_name']}")
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=last_name").input(account_info['last_name'])
            logging.info(f"已输入姓氏: {account_info['last_name']}")
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=email").input(account_info['email'])
            logging.info(f"已输入邮箱: {account_info['email']}")
            time.sleep(random.uniform(1, 3))

            logging.info("提交个人信息...")
            tab.actions.click("@type=submit")

    except Exception as e:
        logging.error(f"注册页面访问失败: {str(e)}")
        return False

    # 重置turnstile状态
    tab.run_js("try { turnstile.reset() } catch(e) { }")
    # 处理第一次 Turnstile 验证
    if not handle_turnstile(tab):
        logging.error("第一次 Turnstile 验证失败")
        return False

    try:
        if tab.ele("@name=password"):
            logging.info("正在设置密码...")
            tab.ele("@name=password").input(account_info['password'])
            logging.info(f"已输入密码: {account_info['password']}")
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

    # 重置turnstile状态
    tab.run_js("try { turnstile.reset() } catch(e) { }")
    # 处理第二次 Turnstile 验证
    if not handle_turnstile(tab):
        logging.error("第二次 Turnstile 验证失败")
        return False

    verification_start_time = time.time()
    verification_retries = 0
    
    while verification_retries < max_verification_retries:
        try:
            if tab.ele("Account Settings"):
                logging.info("注册成功 - 已进入账户设置页面")
                break
                
            elapsed_time = time.time() - verification_start_time
            if elapsed_time > verification_timeout:
                logging.error(f"验证码获取超时 ({elapsed_time:.1f}秒)")
                return False
                
            if tab.ele("@data-index=0"):
                logging.info("检测到验证码输入框，开始获取验证码...")
                logging.info(f"第 {verification_retries + 1} 次尝试获取验证码")
                
                try:
                    code = email_handler.get_verification_code()
                    if code:
                        logging.info(f"成功获取验证码: {code}")
                        logging.info("正在输入验证码...")
                        i = 0
                        for digit in code:
                            tab.ele(f"@data-index={i}").input(digit)
                            time.sleep(random.uniform(0.1, 0.3))
                            i += 1
                        logging.info("验证码输入完成")
                        break
                    else:
                        logging.warning("验证码获取返回空值")
                except Exception as e:
                    logging.error(f"验证码获取出错: {str(e)}")
                
                verification_retries += 1
                if verification_retries < max_verification_retries:
                    wait_time = 10  # 增加重试间隔
                    logging.warning(f"获取验证码失败，{wait_time}秒后进行第 {verification_retries + 1} 次重试...")
                    time.sleep(wait_time)
                else:
                    logging.error(f"验证码获取失败，已达到最大重试次数 {max_verification_retries}")
                    return False
                
            time.sleep(1)  # 避免过于频繁的检查
            
        except Exception as e:
            logging.error(f"验证码处理过程出错: {str(e)}")
            verification_retries += 1
            if verification_retries >= max_verification_retries:
                return False
            time.sleep(2)

    # 重置turnstile状态
    tab.run_js("try { turnstile.reset() } catch(e) { }")
    # 处理第三次 Turnstile 验证
    if not handle_turnstile(tab):
        logging.error("第三次 Turnstile 验证失败")
        return False

    wait_time = random.randint(3, 6)
    for i in range(wait_time):
        logging.info(f"等待系统处理中... 剩余 {wait_time-i} 秒")
        time.sleep(1)

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
        email_handler = EmailVerificationHandler()
        
        # 打印配置信息
        config = Config()
        config.print_config()
        
        # 生成账号信息
        email_generator = EmailGenerator()
        logging.info(f"域名: {email_generator.domain}")
        account_info = email_generator.get_account_info()
        logging.info(f"生成的邮箱账号: {account_info['email']}")
        logging.info(f"生成的账号名: {account_info['first_name']} {account_info['last_name']}")
        
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
            if sign_up_account(browser, tab, email_handler, account_info):
                logging.info("正在获取会话令牌...")
                token = get_cursor_session_token(tab)
                if token:
                    # 完善账号信息
                    account_info['access_token'] = token
                    account_info['refresh_token'] = token
                    account_info['create_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
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
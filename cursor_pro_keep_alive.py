import os
import platform
import json
import sys
from colorama import Fore, Style
from enum import Enum
from typing import Optional, Dict

from exit_cursor import ExitCursor
import go_cursor_help
import patch_cursor_get_machine_id
from reset_machine import MachineIDResetter
from account_storage import AccountStorage

os.environ["PYTHONVERBOSE"] = "0"
os.environ["PYINSTALLER_VERBOSE"] = "0"

import time
import random
from cursor_auth_manager import CursorAuthManager
import os
from logger import logging
from browser_utils import BrowserManager
from get_email_code import EmailVerificationHandler
from logo import print_logo
from config import Config
from datetime import datetime

# 定义 EMOJI 字典
EMOJI = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️", "SUCCESS": "✅"}

# 定义全局 URL
LOGIN_URL = "https://authenticator.cursor.sh"
SIGN_UP_URL = "https://authenticator.cursor.sh/sign-up"
SETTINGS_URL = "https://www.cursor.com/settings"
MAIL_URL = "https://tempmail.plus"


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
            "请前往开源项目查看更多信息：https://github.com/chengazhen/cursor-auto-free"
        )
        save_screenshot(tab, "failed")
        return False

    except Exception as e:
        error_msg = f"Turnstile 验证过程发生异常: {str(e)}"
        logging.error(error_msg)
        save_screenshot(tab, "error")
        raise TurnstileError(error_msg)


def get_cursor_session_token(tab, max_attempts=3, retry_interval=2):
    """
    获取Cursor会话token，带有重试机制
    :param tab: 浏览器标签页
    :param max_attempts: 最大尝试次数
    :param retry_interval: 重试间隔(秒)
    :return: session token 或 None
    """
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
                logging.warning(
                    f"第 {attempts} 次尝试未获取到CursorSessionToken，{retry_interval}秒后重试..."
                )
                time.sleep(retry_interval)
            else:
                logging.error(
                    f"已达到最大尝试次数({max_attempts})，获取CursorSessionToken失败"
                )

        except Exception as e:
            logging.error(f"获取cookie失败: {str(e)}")
            attempts += 1
            if attempts < max_attempts:
                logging.info(f"将在 {retry_interval} 秒后重试...")
                time.sleep(retry_interval)

    return None


def update_cursor_auth(email=None, access_token=None, refresh_token=None):
    """
    更新Cursor的认证信息的便捷函数
    """
    auth_manager = CursorAuthManager()
    return auth_manager.update_auth(email, access_token, refresh_token)


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

    handle_turnstile(tab)

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

    handle_turnstile(tab)

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

    handle_turnstile(tab)
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
                "请前往开源项目查看更多信息：https://github.com/chengazhen/cursor-auto-free"
            )
    except Exception as e:
        logging.error(f"获取账户额度信息失败: {str(e)}")

    logging.info("\n=== 注册完成 ===")
    account_info = f"Cursor 账号信息:\n邮箱: {account}\n密码: {password}"
    logging.info(account_info)
    time.sleep(5)
    return True


class EmailGenerator:
    def __init__(
        self,
        password="".join(
            random.choices(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*",
                k=12,
            )
        ),
    ):
        configInstance = Config()
        configInstance.print_config()
        self.domain = configInstance.get_domain()
        self.default_password = password
        self.default_first_name = self.generate_random_name()
        self.default_last_name = self.generate_random_name()

    def generate_random_name(self, length=6):
        """生成随机用户名"""
        first_letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        rest_letters = "".join(
            random.choices("abcdefghijklmnopqrstuvwxyz", k=length - 1)
        )
        return first_letter + rest_letters

    def generate_email(self, length=8):
        """生成随机邮箱地址"""
        random_str = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=length))
        timestamp = str(int(time.time()))[-6:]  # 使用时间戳后6位
        return f"{random_str}{timestamp}@{self.domain}"

    def get_account_info(self):
        """获取完整的账号信息"""
        return {
            "email": self.generate_email(),
            "password": self.default_password,
            "first_name": self.default_first_name,
            "last_name": self.default_last_name,
        }


def get_user_agent():
    """获取user_agent"""
    try:
        # 使用JavaScript获取user agent
        browser_manager = BrowserManager()
        browser = browser_manager.init_browser()
        user_agent = browser.latest_tab.run_js("return navigator.userAgent")
        browser_manager.quit()
        return user_agent
    except Exception as e:
        logging.error(f"获取user agent失败: {str(e)}")
        return None


def check_cursor_version():
    """检查cursor版本"""
    pkg_path, main_path = patch_cursor_get_machine_id.get_cursor_paths()
    with open(pkg_path, "r", encoding="utf-8") as f:
        version = json.load(f)["version"]
    return patch_cursor_get_machine_id.version_check(version, min_version="0.45.0")


def reset_machine_id(greater_than_0_45):
    if greater_than_0_45:
        # 提示请手动执行脚本 https://github.com/chengazhen/cursor-auto-free/blob/main/patch_cursor_get_machine_id.py
        go_cursor_help.go_cursor_help()
    else:
        MachineIDResetter().reset_machine_ids()


def print_end_message():
    logging.info("\n\n\n\n\n")
    logging.info("=" * 30)
    logging.info("所有操作已完成")
    logging.info("\n=== 获取更多信息 ===")
    logging.info("🔥 QQ交流群: 1034718338")
    logging.info("📺 B站UP主: 想回家的前端")
    logging.info("=" * 30)
    logging.info(
        "请前往开源项目查看更多信息：https://github.com/chengazhen/cursor-auto-free"
    )


def batch_register_accounts(count: int) -> None:
    """
    批量注册账号
    
    Args:
        count: 要注册的账号数量
    """
    logging.info(f"\n=== 开始批量注册 {count} 个账号 ===")
    account_storage = AccountStorage()
    success_count = 0
    
    # 初始化邮箱验证模块
    logging.info("正在初始化邮箱验证模块...")
    global email_handler
    email_handler = EmailVerificationHandler()
    
    for i in range(count):
        browser_manager = None
        try:
            logging.info(f"\n--- 正在注册第 {i+1}/{count} 个账号 ---")
            
            # 初始化浏览器
            browser_manager = BrowserManager()
            user_agent = get_user_agent()
            if not user_agent:
                logging.error("获取user agent失败，使用默认值")
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
            # 剔除user_agent中的"HeadlessChrome"
            user_agent = user_agent.replace("HeadlessChrome", "Chrome")
            browser = browser_manager.init_browser(user_agent)
            tab = browser.latest_tab
            
            # 生成账号信息
            email_generator = EmailGenerator()
            global account, password, first_name, last_name
            account = email_generator.generate_email()
            password = email_generator.default_password
            first_name = email_generator.default_first_name
            last_name = email_generator.default_last_name
            
            logging.info(f"生成的邮箱账号: {account}")
            
            # 执行注册
            if sign_up_account(browser, tab):
                token = get_cursor_session_token(tab)
                if token:
                    # 保存账号信息
                    account_info = {
                        'email': account,
                        'password': password,
                        'first_name': first_name,
                        'last_name': last_name,
                        'access_token': token,
                        'refresh_token': token
                    }
                    
                    # 先保存账号信息
                    if account_storage.add_account(account_info):
                        success_count += 1
                        logging.info(f"{EMOJI['SUCCESS']} 第 {i+1} 个账号注册成功并已保存")
                        
                        # 保存成功后再更新认证信息
                        if update_cursor_auth(email=account, access_token=token, refresh_token=token):
                            logging.info(f"{EMOJI['SUCCESS']} 认证信息更新成功")
                        else:
                            logging.error(f"{EMOJI['ERROR']} 认证信息更新失败")
                    else:
                        logging.error(f"{EMOJI['ERROR']} 账号信息保存失败")
                else:
                    logging.error(f"{EMOJI['ERROR']} 获取会话令牌失败")
            else:
                logging.error(f"{EMOJI['ERROR']} 账号注册失败")
        
        except Exception as e:
            logging.error(f"注册过程出现错误: {str(e)}")
            continue
        
        finally:
            # 确保浏览器被关闭
            if browser_manager:
                browser_manager.quit()
            
            # 只有在不是最后一个账号时才需要延迟
            if i < count - 1:
                delay = random.uniform(5, 10)
                logging.info(f"等待 {delay:.1f} 秒后继续...")
                time.sleep(delay)
    
    logging.info(f"\n=== 批量注册完成 ===")
    logging.info(f"成功注册: {success_count}/{count}")
    logging.info(f"账号信息已保存到: {account_storage.storage_file}")
    
    if success_count > 0:
        logging.info("\n=== 已注册的账号列表 ===")
        accounts = account_storage.get_all_accounts()[-success_count:]  # 只显示本次注册的账号
        for idx, acc in enumerate(accounts, 1):
            logging.info(f"\n账号 {idx}:")
            logging.info(f"邮箱: {acc['email']}")
            logging.info(f"密码: {acc['password']}")
            logging.info(f"注册时间: {acc['create_time']}")


def quick_select_account() -> None:
    """快速选取并替换账号"""
    logging.info("\n=== 快速选取账号 ===")
    
    account_storage = AccountStorage()
    account = account_storage.get_random_account()
    
    if not account:
        logging.error(f"{EMOJI['ERROR']} 账号库为空，请先注册账号")
        return
    
    try:
        # 更新认证信息
        if update_cursor_auth(
            email=account['email'],
            access_token=account['access_token'],
            refresh_token=account['refresh_token']
        ):
            logging.info(f"{EMOJI['SUCCESS']} 账号切换成功")
            logging.info(f"当前账号: {account['email']}")
            
            # 重置机器码
            greater_than_0_45 = check_cursor_version()
            reset_machine_id(greater_than_0_45)
            logging.info(f"{EMOJI['SUCCESS']} 机器码重置完成")
        else:
            logging.error(f"{EMOJI['ERROR']} 账号切换失败")
    
    except Exception as e:
        logging.error(f"账号切换过程出现错误: {str(e)}")


if __name__ == "__main__":
    print_logo()
    greater_than_0_45 = check_cursor_version()
    browser_manager = None
    try:
        logging.info("\n=== 初始化程序 ===")

        # 提示用户选择操作模式
        print("\n请选择操作模式:")
        print("1. 仅重置机器码")
        print("2. 完整注册流程")
        print("3. 批量注册账号")
        print("4. 快速选取账号")

        while True:
            try:
                choice = int(input("请输入选项 (1-4): ").strip())
                if choice in [1, 2, 3, 4]:
                    break
                else:
                    print("无效的选项,请重新输入")
            except ValueError:
                print("请输入有效的数字")

        if choice == 1:
            # 仅执行重置机器码，需要退出 Cursor
            logging.info("正在退出 Cursor...")
            ExitCursor()
            reset_machine_id(greater_than_0_45)
            logging.info("机器码重置完成")
        elif choice == 2:
            # 完整注册流程，需要退出 Cursor
            logging.info("正在退出 Cursor...")
            ExitCursor()
            logging.info("正在初始化浏览器...")

            # 获取user_agent
            user_agent = get_user_agent()
            if not user_agent:
                logging.error("获取user agent失败，使用默认值")
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

            # 剔除user_agent中的"HeadlessChrome"
            user_agent = user_agent.replace("HeadlessChrome", "Chrome")

            browser_manager = BrowserManager()
            browser = browser_manager.init_browser(user_agent)

            # 获取并打印浏览器的user-agent
            user_agent = browser.latest_tab.run_js("return navigator.userAgent")

            logging.info("正在初始化邮箱验证模块...")
            global email_handler
            email_handler = EmailVerificationHandler()
            logging.info(
                "请前往开源项目查看更多信息：https://github.com/chengazhen/cursor-auto-free"
            )
            logging.info("\n=== 配置信息 ===")

            logging.info("正在生成随机账号信息...")
            email_generator = EmailGenerator()
            global account, password, first_name, last_name
            account = email_generator.generate_email()
            password = email_generator.default_password
            first_name = email_generator.default_first_name
            last_name = email_generator.default_last_name

            logging.info(f"生成的邮箱账号: {account}")
            auto_update_cursor_auth = True

            tab = browser.latest_tab

            tab.run_js("try { turnstile.reset() } catch(e) { }")

            logging.info("\n=== 开始注册流程 ===")
            logging.info(f"正在访问登录页面: {LOGIN_URL}")
            tab.get(LOGIN_URL)

            if sign_up_account(browser, tab):
                logging.info("正在获取会话令牌...")
                token = get_cursor_session_token(tab)
                if token:
                    logging.info("更新认证信息...")
                    update_cursor_auth(
                        email=account, access_token=token, refresh_token=token
                    )
                    logging.info(
                        "请前往开源项目查看更多信息：https://github.com/chengazhen/cursor-auto-free"
                    )
                    logging.info("重置机器码...")
                    reset_machine_id(greater_than_0_45)
                    logging.info("所有操作已完成")
                    print_end_message()
                else:
                    logging.error("获取会话令牌失败，注册流程未完成")
        elif choice == 3:
            # 批量注册账号，不需要退出 Cursor
            while True:
                try:
                    count = int(input("请输入要注册的账号数量: ").strip())
                    if count > 0:
                        break
                    else:
                        print("请输入大于0的数字")
                except ValueError:
                    print("请输入有效的数字")
            batch_register_accounts(count)
        elif choice == 4:
            # 快速选取账号，需要退出 Cursor
            logging.info("正在退出 Cursor...")
            ExitCursor()
            quick_select_account()
        
        print_end_message()
        
    except Exception as e:
        logging.error(f"程序执行出现错误: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
    finally:
        if browser_manager:
            browser_manager.quit()
        input("\n程序执行完毕，按回车键退出...")

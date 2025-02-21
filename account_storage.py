import json
import os
import random
from datetime import datetime
from typing import Dict, List, Optional
from logger import logging

class AccountStorage:
    def __init__(self, storage_file: str = "accounts.json"):
        """
        初始化账号存储
        
        Args:
            storage_file: 存储文件路径
        """
        self.storage_file = storage_file
        self._ensure_storage_file()
    
    def _ensure_storage_file(self) -> None:
        """确保存储文件存在"""
        if not os.path.exists(self.storage_file):
            self._save_accounts([])
    
    def _load_accounts(self) -> List[Dict]:
        """加载所有账号"""
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.error(f"账号文件 {self.storage_file} 格式错误")
            return []
        except Exception as e:
            logging.error(f"读取账号文件失败: {str(e)}")
            return []
    
    def _save_accounts(self, accounts: List[Dict]) -> bool:
        """保存账号列表"""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(accounts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.error(f"保存账号文件失败: {str(e)}")
            return False
    
    def add_account(self, account_info: Dict) -> bool:
        """
        添加新账号
        
        Args:
            account_info: 账号信息字典，包含：
                - email: 邮箱
                - password: 密码
                - first_name: 名
                - last_name: 姓
                - access_token: 访问令牌
                - refresh_token: 刷新令牌
        """
        accounts = self._load_accounts()
        
        # 检查是否已存在
        if any(acc['email'] == account_info['email'] for acc in accounts):
            logging.warning(f"账号 {account_info['email']} 已存在")
            return False
        
        # 添加创建时间
        account_info['create_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        accounts.append(account_info)
        
        return self._save_accounts(accounts)
    
    def get_random_account(self) -> Optional[Dict]:
        """随机获取一个账号"""
        accounts = self._load_accounts()
        if not accounts:
            logging.warning("账号库为空")
            return None
        
        return random.choice(accounts)
    
    def get_all_accounts(self) -> List[Dict]:
        """获取所有账号"""
        return self._load_accounts()
    
    def remove_account(self, email: str) -> bool:
        """删除指定账号"""
        accounts = self._load_accounts()
        original_length = len(accounts)
        accounts = [acc for acc in accounts if acc['email'] != email]
        
        if len(accounts) == original_length:
            logging.warning(f"账号 {email} 不存在")
            return False
        
        return self._save_accounts(accounts)
import json
import os
from typing import List, Dict, Optional
from logger import logging

class UsedAccountStorage:
    """已使用账号存储管理类"""
    
    def __init__(self, storage_file: str = "used_accounts.json"):
        """
        初始化存储管理器
        
        Args:
            storage_file: 存储文件路径
        """
        self.storage_file = storage_file
        self._ensure_storage_file()
    
    def _ensure_storage_file(self) -> None:
        """确保存储文件存在"""
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=4)
    
    def get_all_accounts(self) -> List[Dict]:
        """获取所有已使用账号"""
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"读取已使用账号列表失败: {str(e)}")
            return []
    
    def add_account(self, account: Dict) -> bool:
        """
        添加已使用账号
        
        Args:
            account: 账号信息字典
        
        Returns:
            bool: 是否添加成功
        """
        try:
            accounts = self.get_all_accounts()
            accounts.append(account)
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(accounts, f, ensure_ascii=False, indent=4)
            
            return True
        except Exception as e:
            logging.error(f"添加已使用账号失败: {str(e)}")
            return False
    
    def clear_accounts(self) -> bool:
        """
        清空已使用账号记录
        
        Returns:
            bool: 是否清空成功
        """
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logging.error(f"清空已使用账号记录失败: {str(e)}")
            return False
    
    def remove_account(self, email: str) -> bool:
        """
        移除指定账号
        
        Args:
            email: 账号邮箱
        
        Returns:
            bool: 是否移除成功
        """
        try:
            accounts = self.get_all_accounts()
            accounts = [acc for acc in accounts if acc['email'] != email]
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(accounts, f, ensure_ascii=False, indent=4)
            
            return True
        except Exception as e:
            logging.error(f"移除已使用账号失败: {str(e)}")
            return False
    
    def get_account_usage(self, email: str) -> Optional[Dict]:
        """
        获取指定账号的使用情况
        
        Args:
            email: 账号邮箱
        
        Returns:
            Dict: 包含使用次数和时间信息的字典，不存在返回 None
        """
        accounts = self.get_all_accounts()
        for acc in accounts:
            if acc['email'] == email:
                return {
                    'email': acc['email'],
                    'first_used_time': acc.get('first_used_time'),
                    'last_used_time': acc.get('last_used_time'),
                    'use_count': acc.get('use_count', 1)
                }
        return None 
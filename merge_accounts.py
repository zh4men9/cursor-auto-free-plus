import os
import json
from datetime import datetime
from typing import List, Dict

def load_json_file(file_path: str) -> List[Dict]:
    """加载JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"读取文件 {file_path} 失败: {e}")
        return []

def save_json_file(file_path: str, data: List[Dict]) -> bool:
    """保存JSON文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"保存文件 {file_path} 失败: {e}")
        return False

def merge_accounts():
    """合并所有账号文件"""
    all_accounts = []
    account_dir = 'account'
    
    # 检查account目录是否存在
    if not os.path.exists(account_dir):
        print(f"目录 {account_dir} 不存在")
        return
    
    # 遍历所有uuid目录
    uuid_dirs = [d for d in os.listdir(account_dir) if os.path.isdir(os.path.join(account_dir, d))]
    if not uuid_dirs:
        print("没有找到任何uuid目录")
        return
    
    print(f"找到 {len(uuid_dirs)} 个uuid目录")
    
    # 按照创建时间排序uuid目录
    uuid_dirs.sort(key=lambda x: os.path.getctime(os.path.join(account_dir, x)))
    
    # 遍历每个uuid目录
    for uuid_dir in uuid_dirs:
        uuid_path = os.path.join(account_dir, uuid_dir)
        merged_file = os.path.join(uuid_path, 'merged_accounts.json')
        
        if os.path.exists(merged_file):
            accounts = load_json_file(merged_file)
            if accounts:
                all_accounts.extend(accounts)
                print(f"从 {uuid_dir} 读取了 {len(accounts)} 个账号")
        else:
            print(f"目录 {uuid_dir} 中没有找到 merged_accounts.json")
    
    if not all_accounts:
        print("没有找到任何账号")
        return
    
    # 读取主账号文件
    main_account_file = 'accounts.json'
    if os.path.exists(main_account_file):
        main_accounts = load_json_file(main_account_file)
        
        # 检查重复账号
        existing_emails = {acc['email'] for acc in main_accounts}
        new_accounts = [acc for acc in all_accounts if acc['email'] not in existing_emails]
        
        if new_accounts:
            main_accounts.extend(new_accounts)
            if save_json_file(main_account_file, main_accounts):
                print(f"成功添加 {len(new_accounts)} 个新账号到 {main_account_file}")
                print(f"当前总账号数量: {len(main_accounts)}")
            else:
                print("保存到主账号文件失败")
        else:
            print("没有新的账号需要合并")
    else:
        # 如果主账号文件不存在，直接保存
        if save_json_file(main_account_file, all_accounts):
            print(f"成功创建主账号文件，包含 {len(all_accounts)} 个账号")
        else:
            print("创建主账号文件失败")

if __name__ == '__main__':
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始合并账号文件...")
    merge_accounts()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 合并完成") 
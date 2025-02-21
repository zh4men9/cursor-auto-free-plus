# Cursor Pro 自动化工具使用说明

[English doc](./README.EN.md)

## 项目说明
本项目是基于 [cursor-auto-free](https://github.com/chengazhen/cursor-auto-free) 的增强版本，新增了批量注册和快速切换账号功能。

## 主要功能
1. 仅重置机器码 - 重置 Cursor 的机器码
2. 完整注册流程 - 自动注册新账号并配置
3. 批量注册账号 - 自动批量注册多个账号并保存
4. 快速选取账号 - 从已保存的账号中随机选择并切换

## 新增功能说明

### 批量注册账号
- 支持一次性注册多个账号
- 自动保存所有注册成功的账号信息
- 包含完整的账号信息（邮箱、密码、Token等）
- 支持断点续注册，中断后不会丢失已注册的账号
- 内置随机延迟，避免频繁注册

### 快速选取账号
- 从已保存的账号库(accounts.json)中随机选择账号
- 自动更新认证信息
- 自动重置机器码
- 一键完成账号切换
- 选中的账号会从 accounts.json 移除
- 完整账号信息会保存到 used_accounts.json
- 支持账号复用（当 accounts.json 为空时可清空 used_accounts.json 重新使用）

## 开发计划 (TODO)

### 账号管理优化
- [x] 支持删除已使用的账号
- [x] 账号状态标记（可用/已用）
- [ ] 账号使用情况统计
- [ ] 账号有效期检查

### 用户界面优化
- [ ] 添加图形化配置界面
- [ ] .env 可视化配置工具
- [ ] 已注册账号列表查看器

### 稳定性优化
- [x] 优化 Turnstile 验证流程
  - [x] 添加验证重试机制
  - [x] 完善超时处理
  - [x] 增加错误恢复功能
  - [x] 优化验证卡住问题
- [ ] 添加网络异常重试
- [ ] 优化浏览器资源管理

## 在线文档
[cursor-auto-free-doc.vercel.app](https://cursor-auto-free-doc.vercel.app)

## 许可证声明
本项目采用 [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) 许可证。
这意味着您可以：
- 分享 — 在任何媒介以任何形式复制、发行本作品
但必须遵守以下条件：
- 非商业性使用 — 您不得将本作品用于商业目的

## 声明
- 本项目仅供学习交流使用，请勿用于商业用途。
- 本项目不承担任何法律责任，使用本项目造成的任何后果，由使用者自行承担。

## 特别鸣谢
本项目基于以下开源项目开发：

- [cursor-auto-free](https://github.com/chengazhen/cursor-auto-free) - 原版 Cursor 自动化工具，本项目的基础功能基于此项目实现
- [go-cursor-help](https://github.com/yuaotian/go-cursor-help) - 一个优秀的 Cursor 机器码重置工具，本项目的机器码重置功能使用该项目实现

## 更新日志
- 2024.02.21: 新增批量注册和快速选取账号功能
- 继承原版所有功能和特性
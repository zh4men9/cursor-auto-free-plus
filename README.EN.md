# Cursor Pro Automation Tool User Guide

README also available in: [中文](./README.md)

## Project Description
This project is an enhanced version of [cursor-auto-free](https://github.com/chengazhen/cursor-auto-free), with new features for batch registration and quick account switching.

## Main Features
1. Machine Code Reset Only - Reset Cursor's machine code
2. Complete Registration Process - Automatically register new account and configure
3. Batch Account Registration - Automatically register multiple accounts and save
4. Quick Account Selection - Randomly select and switch from saved accounts
5. Multi-process Concurrent Registration - Support multiple processes registering simultaneously for higher efficiency
6. Historical Account Merging - Merge account files from all registration batches

## New Features Description

### Batch Account Registration
- Support registering multiple accounts at once
- Automatically save all successfully registered account information
- Include complete account information (email, password, token, etc.)
- Support breakpoint resume registration, no loss of registered accounts after interruption
- Built-in random delays to avoid frequent registrations
- Smart process management with automatic timeout cleanup
- Browser instance auto-retry mechanism
- Automatic resource recycling to prevent memory leaks
- Dynamic concurrency control to avoid resource competition
- Support auto-stop when reaching target registration count

### Quick Account Selection
- Randomly select accounts from saved account pool (accounts.json)
- Automatically update authentication information
- Automatically reset machine code
- One-click account switching
- Selected account is removed from accounts.json
- Complete account information is saved to used_accounts.json
- Support account reuse (clear used_accounts.json to reuse accounts when accounts.json is empty)

## Development Plan (TODO)

### Account Management Optimization
- [x] Support deleting used accounts
- [x] Account status marking (Available/Used)
- [x] Process management optimization
- [x] Automatic resource recycling
- [x] Browser instance management
- [ ] Account usage statistics
- [ ] Account validity check

### User Interface Improvements
- [ ] Add graphical configuration interface
- [ ] .env visual configuration tool
- [ ] Registered accounts viewer

### Stability Improvements
- [x] Optimize Turnstile verification process
  - [x] Add verification retry mechanism
  - [x] Improve timeout handling
  - [x] Enhance error recovery
  - [x] Fix verification stuck issues
- [x] Add network exception retry
  - [x] Browser initialization retry
  - [x] Cookie acquisition retry
  - [x] Verification code retry
- [x] Optimize browser resource management
  - [x] Smart process cleanup
  - [x] Memory leak protection
  - [x] Dynamic concurrency control

## Online Documentation
[cursor-auto-free-doc.vercel.app](https://cursor-auto-free-doc.vercel.app)

## License
This project is licensed under [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/).
This means you can:
- Share — copy and redistribute the material in any medium or format
Under the following terms:
- NonCommercial — You may not use the material for commercial purposes

## Disclaimer
- This project is for learning and communication purposes only, not for commercial use.
- This project assumes no legal responsibility, and any consequences of using this project are borne by the user.

## Special Thanks
This project is developed based on the following open source projects:

- [cursor-auto-free](https://github.com/chengazhen/cursor-auto-free) - Original Cursor automation tool, this project's basic functions are based on it
- [go-cursor-help](https://github.com/yuaotian/go-cursor-help) - An excellent Cursor machine code reset tool, this project's machine code reset function uses this project

## Changelog
- 2024.02.21: Added batch registration and quick account selection features
- Inherited all features from the original version

## Configuration Instructions
Please refer to our [online documentation](https://cursor-auto-free-doc.vercel.app) for detailed configuration instructions.

## Download
[https://github.com/zh4men9/cursor-auto-free-plus/releases](https://github.com/zh4men9/cursor-auto-free-plus/releases)
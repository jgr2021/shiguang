# 拾光 v1.9.1 · Windows 与 macOS 预览版

本版增加原生 Mac 分发包，并沿用 v1.9 的日历、附件、搜索、AI 和可选 GitHub 同步界面。

## 选择下载

| 电脑 | 推荐文件 |
| --- | --- |
| Windows 10/11 64位 | `Shiguang-Setup-1.9.1-x64.exe` |
| Mac，Apple Silicon M 系列，macOS 15+ | `Shiguang-1.9.1-macOS-arm64.dmg` |
| Mac，Intel，macOS 15+ | `Shiguang-1.9.1-macOS-x86_64.dmg` |

Mac 打开 DMG 后把 App 拖入 Applications。同时提供 Windows 免安装 ZIP 和两种 Mac App ZIP，`SHA256SUMS.txt` 覆盖全部程序包。源码压缩包不是可直接运行的应用。

## Mac 适配

- 使用系统钥匙串保存 AI 密钥与 GitHub Token，资料目录位于用户的 Application Support。
- 适配 Finder 打开附件、资料与说明文件，支持 Command 快捷键和触控板滚动。
- 支持查找 Homebrew / PATH 中的 Codex CLI，也能手动选择程序。
- 配置文件保存在用户目录，更新 App 不覆盖日记；基础功能无需登录。
- GitHub 发布流程同时构建 Windows、Apple Silicon 与 Intel 包，全部构建完成才公开下载。

## 当前边界

Mac 包采用 ad-hoc 签名，没有 Apple Developer ID 签名或公证，首次启动可能出现系统提示。详见 [Mac 使用说明](https://github.com/jgr2021/shiguang/blob/v1.9.1/MACOS-START.md) 和 [Apple 官方说明](https://support.apple.com/102445)。Windows 安装包也尚未签名。

本次进行原生构建与文件完整性检查，没有执行新版功能测试或真实桌面交互验收；钥匙串、Codex 问答和 GitHub 双设备同步仍待实测。GitHub 同步还需要维护者完成 GitHub App 注册；不使用同步时可以直接离线记录。

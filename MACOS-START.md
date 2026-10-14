# 拾光 Shiguang · Mac 使用说明

适用于 macOS 15 或更新版本。基础日历、日记、待办、附件和搜索可离线使用，无需 GitHub 登录或安装 Python。

## 简体中文

1. 在「 → 关于本机」查看芯片：Apple M 系列下载 `macOS-arm64.dmg`；Intel 下载 `macOS-x86_64.dmg`。
2. 打开 DMG，把 **Shiguang.app** 拖进 **Applications（应用程序）**。从应用程序打开拾光。
3. 初次选择语言，直接开始记录。Enter 保存待办或发送聊天；Ctrl+Enter / Command+Enter 换行。Command+N 新待办、Command+F 搜索、Command+T 回到今天。
4. 数据在 `~/Library/Application Support/Shiguang/data`。设置中可打开目录、导出完整备份。更新时退出应用，再替换应用程序中的 App；不会把日记写入 App 包。
5. AI 密钥和 GitHub 令牌存入系统钥匙串，备份不包含密钥。迁移到另一台电脑后重新填写或登录。首次访问时 macOS 可能要求你允许钥匙串访问。

GitHub 同步为可选功能，已内置公开应用配置；Mac 与双设备同步仍待实际验证，可直接跳过。Codex 是可选功能，需自行安装并登录 Codex CLI；在 AI 设置中选择实际的 `codex` 命令行程序。

此预览版采用本地代码签名，**没有 Apple Developer ID 签名或公证**。首次打开可能被 Gatekeeper 阻止；请核对下载来源和 SHA256SUMS。关于单个应用的系统提示，见 [Apple 官方说明](https://support.apple.com/102445)。不要关闭整个系统的安全检查。

本版尚未完成真实 Mac 桌面交互、钥匙串、Codex 问答和 GitHub 同步验收；构建成功与签名完整性检查不代表这些功能已经验证。

## 繁體中文

適用 macOS 15 以上。M 系列選 arm64，Intel 選 x86_64。開啟 DMG，將 Shiguang.app 拖入「應用程式」，即可離線記錄，無需登入。

資料存於 `~/Library/Application Support/Shiguang/data`，Token 使用系統鑰匙圈；更換電腦需重新填寫。更新前退出程式，以新版 App 取代舊版。設定中可匯出備份。Enter 儲存待辦或傳送聊天，Ctrl+Enter / Command+Enter 換行。

這是尚未取得 Apple Developer ID 簽署及公證的預覽版，實際桌面操作、鑰匙圈和同步仍待驗證。請參考上方 Apple 官方說明處理單一 App 的提示。

## English

Requires macOS 15 or later. Choose arm64 for Apple Silicon or x86_64 for Intel. Open the DMG and drag **Shiguang.app** into **Applications**. No sign-in or Python installation is needed for offline recording.

Data lives in `~/Library/Application Support/Shiguang/data`; API keys and GitHub tokens use macOS Keychain and are excluded from backups. Quit the app before replacing it during upgrades. Use Settings to export a backup. Enter saves a task or sends chat; Ctrl+Enter / Command+Enter inserts a new line.

This preview has an ad-hoc signature, not an Apple Developer ID signature or notarization. Follow [Apple's official explanation](https://support.apple.com/102445) for any per-app Gatekeeper prompt. Real desktop interaction, Keychain, Codex requests and GitHub synchronization have not yet been validated. Public GitHub App configuration is included; sign-in and synchronization remain optional.

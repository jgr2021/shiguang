# 拾光 Shiguang v1.6.0 · AI 连接预览版

把常用 AI 接进每天的记录。离线日历、待办、随记和附件无需账号；需要 AI 时，连接自己的 Codex 或 API 服务。

## 下载

- **Windows 安装包**：`Shiguang-Setup-1.6.0-x64.exe`，约 22 MB。适用于 Windows 10/11 x64，无需 Python。
- **ZIP 程序包**：`Shiguang-1.6.0-Windows-x64.zip`。完整解压后运行 `Shiguang.exe`。
- `SHA256SUMS.txt`：两个程序包的 SHA-256 校验值。

安装及应用支持简体中文、繁體中文和 English。

## 本次更新

### Codex 模型真正随选择生效

连接本机 Codex 登录，读取状态后可选择：

- GPT-6 Luna · High
- GPT-6 Astra · Medium
- GPT-6 Astra · High
- GPT-6.1 Sol · High

也可从本机模型目录选择其他模型与支持的推理强度。设置随每次请求传入，不改 Codex 全局配置。拾光不读取、复制或另存 Codex 登录 Token。目录和额度由本机 Codex 返回，模型权限以实际请求为准。

### 主流服务商接入向导

预置 OpenAI、Claude、Gemini、DeepSeek、通义千问、Kimi、OpenRouter、硅基流动。提供官方密钥入口、地域选择、模型目录、连接检查和每个服务商独立保存的设置。

OpenAI 改用 Responses，支持推理模型调用档案工具。自定义接口可选择 Chat Completions、Responses 或 Claude Messages。Token 由 Windows 加密保存。

## 使用

打开 **设置 → AI 服务与 Token 设置**，选择连接方式并保存，再进入拾光助手。详见 [AI 连接指南](https://github.com/jgr2021/shiguang/blob/main/AI%E8%BF%9E%E6%8E%A5%E6%8C%87%E5%8D%97.md)。

本版本已编译并展示界面，已读取本机 Codex 的登录与模型元数据。尚未完成收费 API 调用、真实档案问答、全新电脑安装/卸载及全面功能测试。安装包未签名，作为预览版发布。

此连接用于拾光内的助手；Codex 其他任务、GitHub 项目和 ChatGPT 网页对话尚未自动同步。分发包不含个人档案或密钥，费用和模型访问权限由各使用者自己的账户承担。

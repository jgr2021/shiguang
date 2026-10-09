# 拾光 Shiguang

每天一点，慢慢向前。一个以本机存储为主的 Windows 日历、日记与个人 AI 助手。

**简体中文 · 繁體中文 · English** · Windows 10/11 x64 · v1.7.0 预览版

## 下载与使用

[下载 Windows 安装包](https://github.com/jgr2021/shiguang/releases/download/v1.7.0/Shiguang-Setup-1.7.0-x64.exe) · [全部下载与版本说明](https://github.com/jgr2021/shiguang/releases/tag/v1.7.0)

1. 下载 `Shiguang-Setup-1.7.0-x64.exe` 并安装，从桌面打开拾光。
2. 选择日期，记录待办、随记或添加附件；这些功能可以离线使用。
3. 需要 AI 时，打开 **设置 → AI 服务与 Token 设置**，连接本机 Codex，或选择服务商并填写自己的 API Key。读取模型列表、选择模型后保存，再打开拾光助手。

无需安装 Python。API 模式无需 Codex。也可下载 ZIP，完整解压后运行 `Shiguang.exe`；运行库文件夹必须保留。

## 可以做什么

| 功能 | 当前实现 |
| --- | --- |
| 每日日历 | 今日醒目标记、一键回到今天、待办时间与重要程度 |
| 待办总览 | 今天、未来7天、已过期、已完成筛选，按日期分组 |
| 日记 | 本机自动保存草稿，明确归档后保留原文快照 |
| 附件 | 同一文件关联日期范围或多个日期；按内容去重 |
| 智能查找 | 离线匹配标题、可提取正文、备注和常见同义词 |
| AI 助手 | 主流服务商引导、官方密钥入口、模型目录、推理强度与独立配置 |
| AI 写日历 | 起草日期和待办，编辑、勾选、确认后批量写入；草稿可稍后处理 |
| Codex 连接 | 读取本机登录、模型目录与可用额度；所选模型和推理强度随请求生效 |
| 简历更新 | 查阅旧简历和后续成果，生成新的 Word 与 Markdown 文件并附来源 |
| 云文件 | 导出到 Google Drive、OneDrive、Dropbox 等客户端的本机同步文件夹 |
| 三语界面 | 简体中文、繁體中文、English，可在设置中切换 |

## 连接你常用的 AI

**已经在用 Codex：** 选择“本机 Codex 登录”→ 读取状态 → 选择快捷组合 → 保存并使用。支持 **GPT-6 Luna · High、GPT-6 Astra · Medium / High、GPT-6.1 Sol · High**，也可从本机目录选取其他模型及支持的推理强度。无需复制 Codex 登录 Token。

**使用自己的 API Key：** 预置 OpenAI、Claude、Google Gemini、DeepSeek、通义千问、Kimi、OpenRouter、硅基流动；提供官方密钥入口、地域选择与模型目录。OpenAI 使用 Responses，其他连接支持 Chat Completions 或 Claude Messages；可添加自定义兼容接口。

模型目录不保证账户具有实际调用权限。“检查连接”会发送简短模型请求，可能计费。详细步骤见 [AI 连接指南](AI连接指南.md)。

想先用免费额度，可看 [免费 AI 筛选与连接检查](docs/FREE-AI.md)：优先尝试已有预置的 OpenRouter 免费模型，或通过自定义兼容接口连接 Groq。免费档仍需自己的 Key，并受账户和模型限制。

[DeepSeek 接法与 WorkBuddy 协作可行性](docs/DEEPSEEK-WORKBUDDY.md)：DeepSeek 已有预置；WorkBuddy 需另做开放平台授权与任务连接，当前未实现。

## 用 AI 安排日历

打开拾光助手 → **帮我安排日程** → 写下日期和想做的事 → 编辑 AI 草案 → **确认写入日历**。可以只选部分事项，也可保存草稿稍后处理。已有待办不会自动改动。

聊天按 **Enter 发送、Ctrl+Enter 换行**；输入框随内容伸缩，请求显示已等待时间。备份统一在设置中。

## 数据与 AI

- 新安装的数据保存在 `%LOCALAPPDATA%\Shiguang\data`；设置中的“打开数据文件夹”可查看实际位置。
- Token 通过 Windows DPAPI 加密保存，普通备份不包含凭据。换电脑后需要重新填写 Token。
- 发送助手消息时，会向所选服务商提供问题、相关档案内容与近期对话；费用由该服务商按你的账户收取。
- 此仓库及 Release 仅含程序源码、通用说明和程序包，不包含作者的个人日记、附件、凭据或自动任务。
- 用“导出备份”保存完整档案。云文件导出不等于双向数据库同步，也不证明网盘上传已经完成。

## 预览版范围

当前安装程序未签名。v1.7 已实测四个 Codex 模型组合的真实问答、AI 日程草案、22项回归测试、三语界面与断网基础功能。其他服务商尚无真实账户调用验证，全新电脑安装/卸载仍待测试。见 [测试与修复记录](docs/QA-v1.7.0.md)。

离线搜索目前采用文本、同义词和相似片段匹配；扫描件没有 OCR。API 模式没有内置网页搜索，应用没有后台实时联网监控、自动更新或跨设备实时同步。Codex 连接供拾光助手使用，尚未自动同步 Codex 其他任务、GitHub 项目或 ChatGPT 网页对话。AI 生成内容需要使用者核对，尤其是简历中的事实、日期和数字。

## 使用说明

- [简体中文](开始使用.txt)
- [繁體中文](開始使用.txt)
- [English](Getting-Started.txt)
- [AI 连接指南](AI连接指南.md)
- [从源码运行与构建](docs/BUILD.md)
- [版本记录](CHANGELOG.md)

## English

Shiguang is an offline-first Windows calendar and journal with date-linked files, local fuzzy search and an optional personal AI assistant. Connect your local Codex sign-in or bring your own API credentials. Version 1.7 adds editable AI calendar drafts, Enter-to-send chat and a fix for Codex CLI discovery when launched from Codex Desktop. The UI supports Simplified Chinese, Traditional Chinese and English. Download the Windows installer from [Releases](https://github.com/jgr2021/shiguang/releases/tag/v1.7.0), or read [Getting Started](Getting-Started.txt).

## 反馈与许可

可通过 [Issues](https://github.com/jgr2021/shiguang/issues) 提交功能建议和问题。请只提供必要的界面信息与复现步骤，隐藏日记、Token、联系方式和私人文件。

项目目前公开源码，尚未指定开源许可证。第三方组件遵循各自许可证，分发包内附带第三方许可文件。

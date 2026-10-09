# 拾光 v1.7 · AI 连接指南

## 使用本机 Codex

1. 在拾光中打开 **AI 设置**，选择 **本机 Codex 登录**。
2. 点击 **读取 Codex 状态**。应用会查找本机 Codex 并读取登录状态、模型目录和服务端返回的额度，不发起模型生成。
3. 尚未登录时，点击 **在浏览器登录 Codex**，由你在浏览器完成 Codex 自身的登录。也可先在 Codex 应用登录后回来刷新。
4. 选择快捷组合，或者从模型目录选模型和支持的推理强度。
5. 点击 **保存并使用**，再打开拾光助手发送问题。

内置四个明确的快捷组合：

| 显示选项 | 模型 ID | 推理强度 |
| --- | --- | --- |
| GPT-6 Luna · High | gpt-6-luna | high |
| GPT-6 Astra · Medium | gpt-6-astra | medium |
| GPT-6 Astra · High | gpt-6-astra | high |
| GPT-6.1 Sol · High | gpt-6.1-sol | high |

模型及推理强度随每次拾光请求传给 Codex CLI，不修改 Codex 全局配置，不会因模型失败就自动切换其他模型。`auto` 表示沿用默认强度。每个使用者需要有自己的 Codex 安装、登录和对应模型权限。

模型目录可能来自客户端或缓存；列出模型不代表一定具有本次调用权限，最终以实际请求结果为准。读取失败或没有返回额度时显示“不可读取”，不当作零额度。

拾光通过 Codex 的接口读取元数据，不读取、复制或另存 Codex 登录 Token。这个连接用于拾光内的助手；Codex 其他任务、项目和 ChatGPT 网页对话尚未自动同步。

参考：[Codex App Server 的模型与账户接口](https://learn.chatgpt.com/docs/app-server)、[Codex 命令参数](https://learn.chatgpt.com/docs/developer-commands?surface=cli)。

## 使用主流 API 服务商

选择服务商 → 打开官方密钥入口 → 填写 API Key → 读取模型列表 → 选择文本模型 → 检查连接 → 保存。

| 服务商 | 默认 API 基础地址 | 接口与官方说明 |
| --- | --- | --- |
| OpenAI | https://api.openai.com/v1 | [Responses](https://developers.openai.com/api/docs/guides/latest-model) |
| Claude / Anthropic | https://api.anthropic.com/v1 | [Messages 与模型目录](https://platform.claude.com/docs/en/api/models/list) |
| Google Gemini | https://generativelanguage.googleapis.com/v1beta/openai | [OpenAI 兼容](https://ai.google.dev/gemini-api/docs/openai) |
| DeepSeek | https://api.deepseek.com | [模型目录](https://api-docs.deepseek.com/api/list-models/) |
| 通义千问 / 百炼 | https://dashscope.aliyuncs.com/compatible-mode/v1 | [地域与业务空间地址](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope) |
| Kimi / Moonshot | https://api.moonshot.cn/v1 | [官方接口](https://platform.kimi.com/docs/api/chat) |
| OpenRouter | https://openrouter.ai/api/v1 | [聚合服务接入](https://openrouter.ai/docs/quickstart) |
| 硅基流动 / SiliconFlow | https://api.siliconflow.cn/v1 | [接入步骤](https://docs.siliconflow.cn/docs/userguide/quickstart) |

### 地址、地域和套餐

- **百炼**提供北京、新加坡和美国地址选择；Key 必须与地域匹配。也可替换成控制台的业务空间专属地址。界面保留仍可用的通用地域地址，遇到 `{WorkspaceId}` 这样的占位符必须替换后才能保存。
- **Kimi**可选择中国与国际地址，按实际账户选择。国际地址为 `https://api.moonshot.ai/v1`，见[官方兼容说明](https://platform.kimi.ai/docs/guide/migrating-from-openai-to-kimi)。
- **OpenRouter、硅基流动**的模型 ID 可能带供应商前缀，请完整保留。
- 网页订阅、通用 API、Coding Plan / Token Plan 的凭据和使用范围可能不同。以对应服务商的控制台为准，不能把一个套餐的 Key 直接当成所有接口通用的 Key。
- 自定义服务可选择 Chat Completions、Responses 或 Claude Messages 兼容连接。应用不会根据同一个模型名猜测协议。

### 模型与请求

“读取模型列表”只请求目录，不发送个人档案，也不发起模型生成。目录可能包含非聊天模型，选定文本模型后再检查连接。目录读取失败时仍可手动填写官方控制台的模型 ID。

“检查连接”发送简短检查文字，不附日记或附件；它会发起真实模型请求，可能计费。检查成功说明选定模型完成了一次回答，不等于所有档案工具调用都已经验证。

OpenAI 默认改用 Responses，以支持 GPT-6 Astra、GPT-6.1 Sol 和 GPT-6 Luna 在推理时调用档案工具。原 OpenAI 地址已保存的 API Key 继续使用，不要求重复填写。其他服务默认采用各自预置协议，实际支持范围取决于模型。

### 设置和密钥

每个服务商保存独立的模型、地址和预算。切换服务商再回来可恢复已保存配置；尚未保存的 Token 不跨服务商或地域自动携带。留空仅表示沿用同一地址已保存的密钥。

密钥使用 Windows DPAPI 存储，普通备份与程序分发包不包含密钥；新的 Windows 账户或电脑需要重新填写。只有用户发送问题或检查连接时才请求模型。

## 当前交付说明

已实测 Codex 四个快捷组合的真实中文问答，并用 Luna High 生成待确认日程草案。修复了从 Codex 桌面端启动时把桌面程序误识别为 CLI 的问题；修复后的打包诊断程序在同一启动环境成功读取登录和模型目录。

本机没有其他服务商的 API Key，因此三种 API 协议通过本机模拟服务测试请求、工具调用和日程草案流程，未冒充各家真实账户验证。新电脑安装/卸载和所有网络环境仍需进一步测试。

## 让 AI 帮忙写日历

在拾光助手点击 **帮我安排日程**，描述日期和待办。助手返回日程草案后，可以改日期、时间、标题、备注，勾选需要的项目，再点击 **确认写入日历**。未确认草案保存在本机，重开软件后可从 **日程草稿** 继续处理。当前支持新增待办，已有待办不会自动改期、删除或勾选完成。

Enter 发送，Ctrl+Enter 换行；输入框随内容伸缩。请求期间显示已等待时间，可停止。完整备份统一从 **设置 → 导出完整备份** 进入。

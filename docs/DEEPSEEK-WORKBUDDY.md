# DeepSeek 与 WorkBuddy 接入核查

核查日期：2026-10-10。

## DeepSeek：已有模型连接入口

拾光 → AI 设置 → **DeepSeek** → 填入 [DeepSeek 开放平台 Key](https://platform.deepseek.com/api_keys) → 读取模型列表 → 检查连接 → 保存。

预置地址为 `https://api.deepseek.com`，采用 Chat Completions。模型 ID 从账户目录读取；官方当前文档列出 `deepseek-flash`、`deepseek-v4-pro`，实际以目录和账户权限为准。[模型目录](https://api-docs.deepseek.com/api/list-models/)、[对话接口](https://api-docs.deepseek.com/api/create-chat-completion/)。

适配器在同轮工具调用续接时保留 `reasoning_content`，避免丢失思考模式的续接信息；本机模拟服务已覆盖这一字段。真实账户的多轮问答、工具检索和限流仍需要 Key 验证。[官方思考与工具调用要求](https://api-docs.deepseek.com/guides/thinking_mode/)。

本次匿名请求模型目录返回 HTTP 401（1.70秒），说明收到鉴权拒绝，尚未完成模型生成。不要把网页免费聊天或会员当作开放平台 API 额度。

## WorkBuddy：可做工作协作连接，尚未实现

官方开放平台提供本地助理状态与消息、云端任务、会话产物等能力，适合把工作进度与拾光日期关联。接入需注册第三方应用、配置回调与权限，再由每个使用者完成 OAuth 授权。[开放平台接口](https://open.workbuddy.cn/docs/openapi)、[第三方应用指引](https://open.workbuddy.cn/docs/third-party-app)。

公开流程的令牌交换需要应用 `client_secret`，文档明确要求不能暴露在客户端。对可分享的拾光安装包，按该流程实现时应使用服务端保管应用密钥、办理授权交换；或者进一步向平台确认是否提供适用于桌面公开客户端的授权方式。不能把开发者密钥打进 EXE。[认证说明](https://open.workbuddy.cn/docs/openapi#认证授权-api)。

### 建议的第一版协作范围

1. 用户选择一个 WorkBuddy 任务或产物。
2. 导入标题、状态、日期、简短成果和原始链接，先显示预览。
3. 确认后关联到拾光的一天或多天；同一外部任务重复导入时去重。
4. 待办变化仍由用户确认，成果不自动等同于任务完成。

以上为基于官方能力的产品方案。当前未创建 WorkBuddy 开放平台应用，没有授权回调服务，没有读取任何用户任务，也没有实现自动同步。

匿名请求官方任务列表返回 HTTP 401（0.30秒），只证明到达需要授权的接口。WorkBuddy 订阅是否包含某项 API、账户可用权限和额度，仍须平台及具体账户确认。

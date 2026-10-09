# 免费 AI：筛选与本机连接检查

核查日期：2026-10-10。用户目前没有这些服务的 API Key。本次只查询官方规则、测试未登录接口和读取公开模型目录，没有注册账户、购买额度或发送个人档案。

## 建议顺序

| 方案 | 免费方式 | 拾光接法 | 建议 |
| --- | --- | --- | --- |
| OpenRouter | 零价格的免费模型，有请求限额 | 已有 OpenRouter 预置 | 优先试：接入步骤最少，选择固定的 `:free` 文本模型 |
| Groq | Free tier，按模型限制请求与 token | 自定义 OpenAI 兼容 | 第二个候选：先从控制台选择支持工具调用的文本模型 |
| Gemini | 部分模型有免费档 | 已有 Google Gemini 预置 | 备选：需满足地区条件；免费档数据使用规则需留意 |
| 阿里云百炼 | 新用户部分模型赠送额度，通常有效90天 | 已有通义千问 / 百炼预置 | 适合试用：在控制台确认地域、有效期并开启“仅使用免费额度” |
| 硅基流动 | 本次未核实当前账户可用的免费文本模型 | 已有硅基流动预置 | 暂不作为已确认免费方案推荐；以模型详情页价格为准 |

推荐顺序依据接入成本与公开规则，尚未通过真实回答比较模型质量。

### OpenRouter：先试这个

1. 本人在[官方密钥页面](https://openrouter.ai/settings/keys)创建 Key。
2. 拾光 → AI 设置 → **OpenRouter**，把 Key 填入软件。
3. 读取模型列表，选取明确以 `:free` 结尾、支持工具调用的文本模型。以当时价格和账户权限为准；不要把付费同名版本当成免费版。
4. 推理强度先保持 `auto`，点击**检查连接**，成功后保存。
5. 先用虚构的两条待办测试“帮我安排日程”；确认日期、标题和时间后再用于真实记录。

本次公开目录读取成功：找到15个输入和输出价格均为0的 `:free` 模型，其中14个声明支持 `tools`。例如 `google/gemma-4-31b-it:free` 和 `nvidia/nemotron-3-super-120b-a12b:free`。这是目录结果，不代表已验证生成质量、账户权限或日程草案能力。

官方也提供 `openrouter/free`，会在免费模型间选择，并按请求能力筛选。日历与科研记录需要可重复比较时，建议先用固定模型。免费额度受账户限制；应查看自己的控制台或 `/api/v1/key`，不承诺固定日额度。[免费路由说明](https://openrouter.ai/openrouter/free/apps)、[额度说明](https://openrouter.ai/docs/api_reference/limits)。

### Groq：第二个候选

- [创建 Key](https://console.groq.com/keys)。
- 拾光选择 **自定义 OpenAI 兼容**。
- API 基础地址：`https://api.groq.com/openai/v1`。
- 填入 Key → 读取模型列表 → 选择支持工具调用的文本模型 → 检查连接 → 保存。
- 保持 Free tier，具体请求与 token 限额查看账户。不要因遇到429就认定软件超时；429通常需要等待额度恢复。[官方快速开始](https://console.groq.com/docs/quickstart)、[免费档限制](https://console.groq.com/docs/rate-limits)、[计费规则](https://console.groq.com/docs/billing-faqs)。

### Gemini 与百炼的条件

Gemini 免费档仅覆盖部分模型，官方说明免费档内容可用于改进产品；科研未公开资料和私人日记应先核对适用数据条款。支持地区需要在官方名单中确认。[价格与数据使用](https://ai.google.dev/gemini-api/docs/pricing)、[地区](https://ai.google.dev/gemini-api/docs/available-regions)。

百炼赠送额度会过期，实名账户在用完后可能转为按量计费。只打算免费试用时，先在控制台启用“仅使用免费额度”；地域与每个模型的剩余额度以该账户显示为准。[官方新用户额度说明](https://help.aliyun.com/en/model-studio/new-free-quota)。

## 本机实测结果

请求为各家模型目录的 GET，没有带 Key，也没有模型生成。

| 服务 | 返回 | 耗时 | 能说明什么 |
| --- | --- | --- | --- |
| OpenRouter | HTTP 200 | 2.09秒 | 可读取公开模型目录 |
| Groq | HTTP 401 | 1.16秒 | 收到鉴权拒绝，需 Key；不是生成成功 |
| 百炼 | HTTP 401 | 1.83秒 | 收到鉴权拒绝，需 Key；不是生成成功 |
| 硅基流动 | HTTP 401 | 0.28秒 | 收到鉴权拒绝，需 Key；不是生成成功 |
| Gemini | HTTP 404 | 1.16秒 | 无 Key 请求未成功列目录，待有效 Key 进一步验证 |

Gemini 使用的目录路径与官方 OpenAI 兼容文档一致；不能仅凭这次匿名404断定账户不可用或修改接口。[官方列模型示例](https://ai.google.dev/gemini-api/docs/openai#list-models)。

这些是一次连接检查的耗时，不是模型回答速度。拥有 Key 后还需要分别验证：中文回答、检索虚构记录、起草日程、取消和限流提示。当前已经真实完成问答的连接是本机 Codex 四个快捷组合，它消耗账户既有额度，不是本报告中的免费 API。

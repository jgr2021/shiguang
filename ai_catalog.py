"""Connection presets. Model catalogs are retrieved from the selected provider."""
from localization import tr

CODEX_PRESETS = [
    ('GPT-6 Luna · High', 'gpt-6-luna', 'high'),
    ('GPT-6 Astra · Medium', 'gpt-6-astra', 'medium'),
    ('GPT-6 Astra · High', 'gpt-6-astra', 'high'),
    ('GPT-6.1 Sol · High', 'gpt-6.1-sol', 'high'),
]
API_EFFORTS = ['auto', 'low', 'medium', 'high', 'xhigh', 'max']
PRESETS = {
    '本机 Codex 登录': ('codex', '', 'https://learn.chatgpt.com/docs/developer-setup'),
    'OpenAI': ('responses', 'https://api.openai.com/v1', 'https://platform.openai.com/api-keys'),
    'Claude / Anthropic': ('anthropic', 'https://api.anthropic.com/v1', 'https://platform.claude.com/settings/keys'),
    'Google Gemini': ('openai', 'https://generativelanguage.googleapis.com/v1beta/openai', 'https://aistudio.google.com/apikey'),
    'DeepSeek': ('openai', 'https://api.deepseek.com', 'https://platform.deepseek.com/api_keys'),
    '通义千问 / 百炼': ('openai', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'https://help.aliyun.com/zh/model-studio/get-api-key'),
    'Kimi / Moonshot': ('openai', 'https://api.moonshot.cn/v1', 'https://platform.kimi.com/console/api-keys'),
    'OpenRouter': ('openai', 'https://openrouter.ai/api/v1', 'https://openrouter.ai/settings/keys'),
    '硅基流动 / SiliconFlow': ('openai', 'https://api.siliconflow.cn/v1', 'https://cloud.siliconflow.cn/account/ak'),
    '自定义 OpenAI 兼容': ('openai', '', ''),
    '自定义 Responses 兼容': ('responses', '', ''),
    '自定义 Claude 兼容': ('anthropic', '', ''),
    '本机模型（OpenAI 兼容）': ('openai', 'http://127.0.0.1:11434/v1', 'https://docs.ollama.com/openai'),
    '仅离线使用': ('offline', '', ''),
}
REGIONS = {
    '通义千问 / 百炼': {
        '北京': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        '新加坡': 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1',
        '美国（弗吉尼亚）': 'https://dashscope-us.aliyuncs.com/compatible-mode/v1',
    },
    'Kimi / Moonshot': {'中国': 'https://api.moonshot.cn/v1', '国际': 'https://api.moonshot.ai/v1'},
}
DOCS = {
    'OpenAI': 'https://developers.openai.com/api/docs/guides/latest-model',
    'Claude / Anthropic': 'https://platform.claude.com/docs/en/api/overview',
    'Google Gemini': 'https://ai.google.dev/gemini-api/docs/openai',
    'DeepSeek': 'https://api-docs.deepseek.com/api/list-models/',
    '通义千问 / 百炼': 'https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope',
    'Kimi / Moonshot': 'https://platform.kimi.com/docs/api/chat',
    'OpenRouter': 'https://openrouter.ai/docs/quickstart',
    '硅基流动 / SiliconFlow': 'https://docs.siliconflow.cn/docs/userguide/quickstart',
}


def provider_hint(provider):
    hints = {
        '本机 Codex 登录': tr('连接本机 Codex，沿用其登录和计费方式。可以选择模型与推理强度，无需复制登录 Token。'),
        'OpenAI': tr('使用 OpenAI 平台 API Key，按 API 账户计费。GPT-6 的档案工具调用使用 Responses 接口。'),
        'Claude / Anthropic': tr('使用 Claude Console 的 API Key，通过 Messages 接口连接；Claude 网页订阅不等于 API 额度。'),
        'Google Gemini': tr('在 Google AI Studio 获取 Gemini API Key，使用官方 OpenAI 兼容地址。'),
        'DeepSeek': tr('在 DeepSeek 开放平台创建 API Key，模型名称可从账户目录读取。'),
        '通义千问 / 百炼': tr('先选与 API Key 一致的地域。也可粘贴控制台的业务空间专属地址；通用 API 与 Coding/Token Plan 的地址和权限可能不同。'),
        'Kimi / Moonshot': tr('使用 Kimi 开放平台的 API Key，选择账户对应的中国或国际地址；网页会员与 API 单独管理。'),
        'OpenRouter': tr('使用 OpenRouter 自己的 Key。模型通常带供应商前缀；模型目录不代表所有模型都已获得调用权限。'),
        '硅基流动 / SiliconFlow': tr('使用硅基流动平台的 API Key，模型 ID 保留完整前缀；先读取目录，再选择支持工具调用的文本模型。'),
        '本机模型（OpenAI 兼容）': tr('先启动本机模型服务。默认连接 Ollama；使用其他服务时填写其 OpenAI 兼容地址。Token 可按本机服务要求留空。'),
        '仅离线使用': tr('日历、待办、日记、附件和搜索继续在本机使用。'),
    }
    return hints.get(provider, tr('使用供应商给出的 API 基础地址和 API Key；选择与其实际支持的接口协议对应的连接方式。'))

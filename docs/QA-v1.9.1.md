# v1.9.1 完成范围与待验证事项

发布构建在 GitHub Actions 的 Windows x64、macOS Apple Silicon 与 Intel 原生环境中完成。Mac App 包含 ad-hoc 签名，构建步骤检查签名结构；全部分发包带 SHA-256 校验值。

本轮没有执行新版应用功能测试或真实桌面交互验收。以下事项仍待实际设备验证：

- Mac 初次启动、三种语言、输入法、缩放、触控板与多显示器。
- macOS 钥匙串授权、密钥保存/读取/删除与升级后的访问提示。
- Codex CLI 实际登录、模型读取和问答。
- 附件、备份、GitHub 登录以及 Windows/Mac 双设备同步；同步还需要先注册 GitHub App。
- Windows 全新环境安装、升级、卸载。

Apple Developer ID 签名与公证未完成。构建成功及包内签名结构完整，不代表 Apple 安全审查或用户体验验收通过。README 和产品网页目前使用标为 v1.8 的旧版 Windows 示例截图，不代表 Mac 实际界面截图。

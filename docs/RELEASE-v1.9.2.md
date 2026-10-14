# 拾光 v1.9.2 · 附件同步容量提升

- 单附件同步上限：**50 MiB**（原10 MiB）。
- 当前同步附件合计：**500 MiB**（原100 MiB），最多1000个。
- 同时扩大附件响应读取上限并延长传输等待时间；登录与普通请求保持原有等待时间。
- Windows、Mac 分发包内置公开 GitHub App 配置，用户无需注册自己的开发者应用；本机使用仍无需登录。

GitHub 普通仓库阻止超过100 MiB的单文件，建议仓库保持在1 GB以下；拾光的500 MiB是当前附件总量，不包含 Git 历史。删除或更新附件不会自动清理历史体积。[GitHub 官方说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)

## 下载

| 电脑 | 安装文件 |
| --- | --- |
| Windows 10/11 x64 | `Shiguang-Setup-1.9.2-x64.exe` |
| Mac M 系列，macOS 15+ | `Shiguang-1.9.2-macOS-arm64.dmg` |
| Mac Intel，macOS 15+ | `Shiguang-1.9.2-macOS-x86_64.dmg` |

同时提供三种平台的 ZIP 与 SHA-256 清单。更新程序后重新打开拾光，已有账号与记录沿用。

**请将所有同步设备升级到1.9.2或更新版本。** 旧版遇到超过原上限的附件会停止同步，避免错误合并；本机资料保留。

## 验证范围

此前已核对单台 Windows 的文字记录与 GitHub 私有仓库一致。此版的50 MiB边界、500 MiB总量、Mac实际桌面操作与双设备冲突恢复尚未验收；原生构建不等于功能测试。Windows未签名，Mac仅ad-hoc签名，未完成Apple Developer ID签名或公证。详见 [完成范围](https://github.com/jgr2021/shiguang/blob/main/docs/QA-v1.9.2.md)。

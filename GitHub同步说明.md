# GitHub 私有仓库同步

适用：拾光 1.9.2 预览版。发行包已内置公开的 GitHub App 注册信息，普通使用者直接登录即可。已核对单台 Windows 的文字记录与私有仓库一致；Mac 实际操作与双设备同步仍待验证。

## 普通使用者

**本机版无需登录。** 打开即可使用日记、待办、附件、搜索和备份；只有希望跨电脑同步时才进行以下步骤。程序不会在未关联账号时请求 GitHub，也不会弹出强制登录页。

1. 打开「设置 → 账号与同步 → 用 GitHub 登录」，复制验证码，在 GitHub 官方网页完成授权。
2. 首次使用，建立自己的 **Private** 仓库 `shiguang-data`，勾选 **Add README**。空仓库没有分支，无法开始同步。
3. 点击「授权这个仓库」，在 GitHub App 安装页选 **Only select repositories**，只选 `shiguang-data`。
4. 回到拾光，刷新仓库列表，选择这个私有仓库。希望带入现有本机记录时勾选「将当前本机记录加入此账号」；否则使用独立空间。
5. 点击「关联并启用同步」，核对弹出的目标账号、私有仓库和资料目录。启用后可「立即同步」，也可在应用运行时自动同步。
6. 在另一台电脑用同一个 GitHub 账号登录，并选择同一个仓库。不要选产品源码仓库。

登录过期时重新授权即可。本版使用 GitHub App 用户令牌，默认有效期约8小时；没有在桌面端保存开发者密钥，因此不实现需要该密钥的后台续期。过期、断网或权限被撤回都不影响本机记录。

## 同步内容与限制

- 每日日记、待办、正式日记及分析修订、复盘和外部动态。
- 附件及日期关联：每个最多 **50 MiB**，当前所有同步附件总计最多 **500 MiB**、最多1000个。超过单文件限制的附件仅保留本机，并在完成提示中计数；超过总量限制时停止此次同步。
- 从旧版升级时，所有同步设备都应升级到 1.9.2 或更新版本；旧版会拒绝读取超过原上限的附件并停止同步，本机数据保留。
- 500 MiB 是当前附件总量上限，不包含 Git 历史占用。更新或删除文件后，历史版本仍可能占用仓库空间。
- 记录清单最多16 MiB；这是轻量同步的实现上限，不代表 GitHub 的存储配额。
- AI Token、Codex 登录、GitHub Token、助手对话、未确认日程草案、Agent 协议和自动任务配置均不上传。未作为附件导入的 `generated/` 文件也不自动扫描。
- 单个资料空间固定绑定一个 GitHub 用户 ID 和仓库 ID；不能直接更换到其他仓库，以防同步历史串用。
- 退出账号会暂停同步并移除该资料空间在本机保存的 GitHub 令牌，然后回到本地空间。原账号的本机资料仍保留，重新登录可继续使用。
- 不同账号使用不同资料目录；本机目录隔离不等于对共享同一 Windows 登录账号的人加密隐藏。
- 自动同步只在应用运行时工作，正常间隔约2分钟；失败会延后重试。关闭应用后不运行后台服务。
- 同一记录在两台设备都被修改时，进入「处理同步冲突」选择版本。未选版本留在本机 SQLite 的冲突历史中；不会自动用设备时间覆盖。
- 私有仓库不等于端到端加密；仓库拥有者、被授予访问权的人及服务平台可能访问内容。普通删除只删除当前记录，Git 历史可能保留旧版本。请不要公开该仓库。

## 维护者只做一次：注册拾光的 GitHub App

普通使用者不需要注册开发者应用。维护者在发布前完成以下配置：

1. 打开 [New GitHub App](https://github.com/settings/apps/new)。名字可使用尚未被占用的 `Shiguang Diary Sync`；Homepage 填 `https://jgr2021.github.io/shiguang/`。
2. 勾选 **Enable Device Flow**。Device Flow 不需要回调服务器；保持用户令牌过期功能开启。
3. 关闭 Webhook 的 **Active**。
4. Repository permissions：**Contents → Read and write**，Metadata 保持所需只读。其他权限均不添加，不请求 Issues、Actions、Workflows、Administration 等权限。
5. 安装范围选择 **Any account**。注册后记录公开的 **Client ID** 和应用 URL 最后一段 **slug**。
6. 按 GitHub 页面提示在 Credentials → Key pairs 生成私钥，保存在维护者自己的安全位置。安装前可能需要此步骤；设备登录不使用这份私钥，不要将其放进仓库或发行包。
7. 将这两项填入拾光「账号与同步」中的维护者配置，或在程序旁放 `github-app.json`：

```json
{
  "client_id": "在此填写实际的公开ClientID",
  "slug": "在此填写实际的app-slug"
}
```

不要填 Client Secret、Private Key、GitHub 密码或个人访问 Token。本版不需要这些密钥。注册应用不会自动给它访问所有人的仓库，用户仍要自行安装并选定仓库。

发布程序时只携带上述公开配置；真实账号绑定、Token、同步历史和个人记录不得进入发布包。未提供实际 Client ID 的构建会明确显示尚未配置，不能宣传为开箱即用的 GitHub 登录。

## 数据位置与恢复

既有个人版目录保持原位置；其他账号使用其下 `accounts/github-<用户ID>/`。`accounts.json` 只保存本机目录选择。每个空间有自己的 SQLite、附件和 DPAPI 加密 GitHub 凭据。

同步以 `shiguang-sync/records.json` 和 `shiguang-sync/files/` 保存于所选仓库。不要手工删除这些文件或改写分支历史；发现清单缺失或历史不完整时程序会停止同步，防止当作用户删除传播。

首次导入当前资料是明确的用户选择；应用不会把其他目录、其他聊天或其他 GitHub 仓库的内容一起抓取。当前个人版的本聊天 Agent 仍访问原资料路径，不自动切到其他账号。

## 官方依据

- [GitHub App 设备授权、令牌及权限范围](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)
- [注册 GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
- [GitHub 文件与仓库大小限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [非强制更新分支引用](https://docs.github.com/en/rest/git/refs#update-a-reference)

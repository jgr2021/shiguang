# 从源码运行与构建

源码面向 Windows 10/11 x64 和 macOS 15+（Apple Silicon / Intel）。需要带 Tk 的 Python。
v1.9.2 发布流程使用 Python 3.12.10 与 PyInstaller 6.22.3，在各平台原生构建。`.github/workflows/release.yml` 在推送版本标签或手动触发时构建全部平台，全部成功才公开预览版；该流程不运行应用功能测试。

统一构建命令为 `python packaging/build_release.py`，先安装 `requirements-build.txt`。Mac 必须在 Mac 上构建，并以实际架构生成包；使用 `ditto` 保留 App 内的链接和权限，提供 App ZIP 与可拖入 Applications 的 DMG。Mac 包使用 ad-hoc 签名，没有 Developer ID 或公证。Windows 还需要 Inno Setup 6，语言文件已收录在 `packaging/languages/`。

## 运行

在仓库根目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe desktop_app.py
```

开发时建议使用独立数据目录，避免操作日常档案：

```powershell
.\.venv\Scripts\python.exe desktop_app.py --data-dir .\data\development --language zh-CN
```

## 回归测试

在仓库根目录运行 `python -m unittest discover -s tests -v`。测试只使用 `work/qa-v17/` 下的虚构档案和本机 HTTP 模拟服务，不使用个人主档案或真实 API Key；Windows DPAPI 相关测试需要 Windows。

## 构建程序和 ZIP

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --onedir --name Shiguang --icon shiguang.ico --version-file packaging/version-info.txt --exclude-module numpy desktop_app.py
.\.venv\Scripts\python.exe packaging/prepare_release.py --binary-dir dist/Shiguang --stage release-stage --release release
```

`release-stage` 必须是不存在的新目录。它按程序文件白名单组装并生成 SHA-256 清单，复制使用指南和第三方许可；不要把个人安装目录整体压缩发布。

同一磁盘空间有限时，可加 `--link-runtime` 用硬链接组装程序运行库；之后不要修改构建产物。`--no-zip` 可只生成分发目录，供安装器使用。

## Windows 安装器

使用 Inno Setup 6.x 的 `ISCC.exe`，另备兼容该版本的简体及繁体中文 `.isl` 语言文件。当前发布使用 Inno Setup 6.7.3。

在 PowerShell 中替换以下工具和语言文件路径：

```powershell
$isccPath = 'C:\Tools\Inno Setup 6\ISCC.exe'
$simplifiedPath = 'C:\Tools\ChineseSimplified.isl'
$traditionalPath = 'C:\Tools\ChineseTraditional.isl'
$stagePath = (Resolve-Path release-stage).Path
$releasePath = (Resolve-Path release).Path
$issSource = (Resolve-Path packaging/Shiguang.iss).Path
$issBomPath = Join-Path (Resolve-Path build).Path 'Shiguang.iss'
[IO.File]::WriteAllText($issBomPath, [IO.File]::ReadAllText($issSource), [Text.UTF8Encoding]::new($true))
& $isccPath "/DAppSource=$stagePath" "/DReleaseDir=$releasePath" "/DChineseLanguage=$simplifiedPath" "/DTraditionalLanguage=$traditionalPath" $issBomPath
```

版本号目前分别保存在 `app_config.py`、`packaging/version-info.txt`、`packaging/Shiguang.iss` 和 `packaging/prepare_release.py`。发布新版时需要一起更新，并更新三语使用指南和版本记录。安装器 AppId 应保持稳定。

## 目录说明

| 文件 | 职责 |
| --- | --- |
| desktop_app.py / ui_design.py | 日历、待办和共享视觉组件 |
| ui_extras.py / settings_ui.py | 附件、搜索、聊天、设置 |
| diary.py / planner_store.py / file_store.py | 本机 SQLite、日记、待办与附件 |
| app_config.py | 默认设置、数据目录与 DPAPI 凭据 |
| ai_settings_ui.py / ai_catalog.py | AI 接入向导、服务商和模型组合 |
| codex_connection.py | Codex 元数据、登录与模型参数 |
| api_assistant.py / assistant_bridge.py | API 与可选 Codex 助手适配 |
| localization.py / translations.py | 三语界面 |
| packaging/ | 程序包与安装器构建 |

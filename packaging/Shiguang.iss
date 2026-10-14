#ifndef AppSource
  #error AppSource must point to the clean release staging folder
#endif
#ifndef ReleaseDir
  #error ReleaseDir is required
#endif
#define AppVersion "1.9.1"

[Setup]
AppId={{5991DB7F-A2D3-44AD-A696-06E54B69EAF4}
AppName={cm:AppTitle}
AppVersion={#AppVersion}
AppVerName={cm:AppTitle} {#AppVersion}
AppPublisher=拾光
DefaultDirName={localappdata}\Programs\Shiguang
DefaultGroupName=拾光日历
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ReleaseDir}
OutputBaseFilename=Shiguang-Setup-1.9.1-x64
SetupIconFile={#AppSource}\shiguang.ico
UninstallDisplayIcon={app}\Shiguang.exe
UninstallDisplayName={cm:AppTitle}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
InfoBeforeFile={#AppSource}\开始使用.txt
VersionInfoVersion=1.9.1.0
VersionInfoDescription=拾光日历安装程序
VersionInfoProductName=拾光日历
ShowLanguageDialog=yes

[Languages]
Name: "zhCN"; MessagesFile: "{#ChineseLanguage}"; InfoBeforeFile: "{#AppSource}\开始使用.txt"
Name: "zhTW"; MessagesFile: "{#TraditionalLanguage}"; InfoBeforeFile: "{#AppSource}\開始使用.txt"
Name: "en"; MessagesFile: "compiler:Default.isl"; InfoBeforeFile: "{#AppSource}\Getting-Started.txt"

[CustomMessages]
zhCN.AppTitle=拾光日历
zhTW.AppTitle=拾光日曆
en.AppTitle=Shiguang
zhCN.AppLanguage=zh-CN
zhTW.AppLanguage=zh-TW
en.AppLanguage=en
zhCN.DesktopShortcut=创建桌面快捷方式
zhTW.DesktopShortcut=建立桌面捷徑
en.DesktopShortcut=Create a desktop shortcut
zhCN.OpenApp=打开拾光日历
zhTW.OpenApp=開啟拾光日曆
en.OpenApp=Open Shiguang
zhCN.GuideFile=开始使用.txt
zhTW.GuideFile=開始使用.txt
en.GuideFile=Getting-Started.txt

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; Flags: checkedonce

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\拾光日历"; Filename: "{app}\Shiguang.exe"; Parameters: "--language {cm:AppLanguage}"; WorkingDir: "{app}"
Name: "{userdesktop}\拾光日历"; Filename: "{app}\Shiguang.exe"; Parameters: "--language {cm:AppLanguage}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\使用说明"; Filename: "{app}\{cm:GuideFile}"

[Run]
Filename: "{app}\Shiguang.exe"; Parameters: "--language {cm:AppLanguage}"; Description: "{cm:OpenApp}"; Flags: nowait postinstall skipifsilent

; Personal data and encrypted credentials live outside {app}.
; Deliberately no UninstallDelete entry for the user's data directory.

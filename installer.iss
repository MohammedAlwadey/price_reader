#define MyAppName "PriceReader"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "PriceReader"
#define MyAppDeveloper "Mohammed Alwadei"
#define MyAppURL "http://127.0.0.1:2026"

[Setup]
AppId={{B7B67F6A-2F6E-4D37-8E51-8F2B4F6A9C11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

VersionInfoCompany={#MyAppDeveloper}
VersionInfoDescription=PriceReader Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=Developed by {#MyAppDeveloper}

DefaultDirName={autopf}\PriceReader
DefaultGroupName=PriceReader

OutputDir=installer_output
OutputBaseFilename=PriceReaderSetup

SetupIconFile=PriceReader.ico
UninstallDisplayIcon={app}\PriceReader.ico

Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[Tasks]
Name: "desktopicon"; Description: "إنشاء اختصار على سطح المكتب"; GroupDescription: "اختصارات إضافية"

[Files]
Source: "dist\PriceReader\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "PriceReader.ico"; DestDir: "{app}"; Flags: ignoreversion

Source: ".env"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "db.sqlite3"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "license.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[INI]
Filename: "{app}\Open PriceReader.url"; Section: "InternetShortcut"; Key: "URL"; String: "{#MyAppURL}"
Filename: "{app}\Open PriceReader.url"; Section: "InternetShortcut"; Key: "IconFile"; String: "{app}\PriceReader.ico"
Filename: "{app}\Open PriceReader.url"; Section: "InternetShortcut"; Key: "IconIndex"; String: "0"

[Icons]
Name: "{group}\فتح PriceReader"; Filename: "{app}\Open PriceReader.url"; IconFilename: "{app}\PriceReader.ico"
Name: "{autodesktop}\PriceReader"; Filename: "{app}\Open PriceReader.url"; IconFilename: "{app}\PriceReader.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\Open PriceReader.url"; Description: "فتح PriceReader في المتصفح"; Flags: postinstall shellexec skipifsilent
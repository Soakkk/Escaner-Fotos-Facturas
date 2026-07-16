; Instalador de EscanerFotos (por usuario, sin admin).
; Versión por línea de comandos:  iscc /DMyAppVersion=2.1 instalador.iss
#ifndef MyAppVersion
  #define MyAppVersion "0.0"
#endif
#define MyAppName "EscanerFotos"
#define MyAppExe "EscanerFotos.exe"

[Setup]
AppId={{8F3A1C2E-5B4D-4E9A-9C7F-2D1E6A8B3F40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\EscanerFotos
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=yes
OutputDir=Output
OutputBaseFilename=EscanerFotos-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=EscanerFotos\recursos\icono.ico
UninstallDisplayIcon={app}\{#MyAppExe}

[Files]
Source: "dist\EscanerFotos\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autodesktop}\EscanerFotos"; Filename: "{app}\{#MyAppExe}"
Name: "{userprograms}\EscanerFotos"; Filename: "{app}\{#MyAppExe}"

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Abrir EscanerFotos"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#MyAppExe}"; Flags: nowait skipifnotsilent

; Script de Inno Setup para "CARGADOR ECOSEARCH".
; Copia el .exe standalone (dist\CARGADOR ECOSEARCH.exe, construido con PyInstaller) a Archivos
; de Programa con su config.json editable, el logo, el ícono y el instructivo de usuario; crea los
; accesos directos y el desinstalador.
;
; Para compilar (requiere Inno Setup 6):
;   & "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" "CARGADOR ECOSEARCH Setup.iss"
;
; Resultado: "Instalador\CARGADOR ECOSEARCH Setup v<versión>.exe" — es el único archivo que hay
; que llevar al otro equipo (no necesita Python). Con el mismo AppId, una versión nueva actualiza
; la anterior en su misma carpeta.

#define MyAppName "CARGADOR ECOSEARCH"
#define MyAppVersion "1.0"
#define MyAppPublisher "Bond Energy Solutions"
#define MyAppExeName "CARGADOR ECOSEARCH.exe"
#define MyAppIcon "CARGADOR ECOSEARCH.ico"
#define MyAppGuide "Instructivo CARGADOR ECOSEARCH.pdf"

[Setup]
AppId={{AAF5D74A-F79A-499B-A32D-D1253205BCD7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=Plantillas de carga Ecosearch (Well Log / Well Log Image) -- Bond Energy Solutions
AppCopyright=© 2026 Bond Energy Solutions SAS. Todos los derechos reservados.
VersionInfoCompany={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}.0.0
VersionInfoProductVersion={#MyAppVersion}.0.0
VersionInfoCopyright=© 2026 Bond Energy Solutions SAS. Todos los derechos reservados.
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
DefaultDirName={autopf}\{#MyAppPublisher}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Instalador
OutputBaseFilename=CARGADOR ECOSEARCH Setup v{#MyAppVersion}
SetupIconFile={#MyAppIcon}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Igual que DATA INTEGRATION y BOND LOG PLOT: pide permisos de administrador (UAC).
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "LOGO BOND.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyAppIcon}"; DestDir: "{app}"; Flags: ignoreversion
Source: "docs\{#MyAppGuide}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Instructivo de usuario"; Filename: "{app}\{#MyAppGuide}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar {#MyAppName} ahora"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#MyAppGuide}"; Description: "Abrir el instructivo de usuario"; Flags: shellexec postinstall skipifsilent unchecked

; SPDX-License-Identifier: GPL-2.0-or-later
; Compile through build_installer.py after packaging a tested Windows install.
#ifndef SourceDir
  #error SourceDir is required
#endif
#ifndef RepoDir
  #error RepoDir is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef Revision
  #error Revision is required
#endif

[Setup]
AppId=Kitchen3D
AppName=Kitchen 3D
AppVersion={#AppVersion}
AppVerName=Kitchen 3D {#AppVersion} Preview ({#Revision})
AppPublisher=Kitchen 3D contributors
AppPublisherURL=https://github.com/BaerBonesTechnology/kitchen-3d
AppSupportURL=https://github.com/BaerBonesTechnology/kitchen-3d/issues
AppUpdatesURL=https://github.com/BaerBonesTechnology/kitchen-3d/releases
DefaultDirName={localappdata}\Programs\Kitchen3D
DefaultGroupName=Kitchen 3D
DisableProgramGroupPage=yes
DisableDirPage=no
DisableWelcomePage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible and not arm64
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile={#RepoDir}\release\windows\icons\kitchen3d.ico
UninstallDisplayIcon={app}\kitchen3d.exe
LicenseFile={#SourceDir}\doc\license\GPL-license.txt
OutputDir={#OutputDir}
OutputBaseFilename=Kitchen3D-windows-x64-setup
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Kitchen 3D
Compression=lzma2/fast
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=Kitchen 3D
ChangesAssociations=yes

[Tasks]
Name: "standalone"; Description: "Standalone - keep current file defaults"; GroupDescription: "How would you like to use Kitchen 3D?"; Flags: exclusive
Name: "blendfiles"; Description: "Use Kitchen 3D for .blend files (confirm in Windows Settings after setup)"; GroupDescription: "How would you like to use Kitchen 3D?"; Flags: exclusive unchecked
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Kitchen 3D"; Filename: "{app}\kitchen3d-launcher.exe"; WorkingDir: "{app}"; IconFilename: "{app}\kitchen3d.exe"
Name: "{autodesktop}\Kitchen 3D"; Filename: "{app}\kitchen3d-launcher.exe"; WorkingDir: "{app}"; IconFilename: "{app}\kitchen3d.exe"; Tasks: desktopicon

[Registry]
; Own registrations only: never overwrite Blender's ProgID or Windows UserChoice.
Root: HKCU; Subkey: "Software\Classes\Kitchen3D.Setup.Blend"; ValueType: string; ValueData: "Kitchen 3D Project"; Flags: uninsdeletekey; Tasks: blendfiles
Root: HKCU; Subkey: "Software\Classes\Kitchen3D.Setup.Blend\DefaultIcon"; ValueType: string; ValueData: """{app}\kitchen3d.exe"",0"; Tasks: blendfiles
Root: HKCU; Subkey: "Software\Classes\Kitchen3D.Setup.Blend\shell\open\command"; ValueType: string; ValueData: """{app}\kitchen3d-launcher.exe"" ""%1"""; Tasks: blendfiles
Root: HKCU; Subkey: "Software\Classes\.blend\OpenWithProgids"; ValueType: string; ValueName: "Kitchen3D.Setup.Blend"; ValueData: ""; Flags: uninsdeletevalue; Tasks: blendfiles
Root: HKCU; Subkey: "Software\Kitchen3D\SetupCapabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Kitchen 3D"; Flags: uninsdeletekey; Tasks: blendfiles
Root: HKCU; Subkey: "Software\Kitchen3D\SetupCapabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Model, animate and render .blend projects in Kitchen 3D."; Tasks: blendfiles
Root: HKCU; Subkey: "Software\Kitchen3D\SetupCapabilities\FileAssociations"; ValueType: string; ValueName: ".blend"; ValueData: "Kitchen3D.Setup.Blend"; Tasks: blendfiles
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Kitchen3D"; ValueData: "Software\Kitchen3D\SetupCapabilities"; Flags: uninsdeletevalue; Tasks: blendfiles

[Run]
Filename: "ms-settings:defaultapps?registeredAppUser=Kitchen3D"; Description: "Choose Kitchen 3D for .blend files in Windows Settings"; Flags: shellexec postinstall skipifsilent; Tasks: blendfiles
Filename: "{app}\kitchen3d-launcher.exe"; Description: "Launch Kitchen 3D"; Flags: nowait postinstall skipifsilent

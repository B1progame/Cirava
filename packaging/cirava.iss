#define AppName "Cirava"
#ifndef AppVersion
  #define AppVersion "1.0.0 beta"
#endif
#ifndef AppExeSource
  #define AppExeSource "output\Cirava.exe"
#endif
#ifndef AppOutputDir
  #define AppOutputDir "output"
#endif
#ifndef AppOutputBaseFilename
  #define AppOutputBaseFilename "Cirava-Setup-1.0.0-beta-test"
#endif
#define AppPublisher "Cirava"
#define AppExeName "Cirava.exe"

[Setup]
AppId={{8F3DE5A0-4B82-4C62-8DF8-CIRAVA000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Cirava
PrivilegesRequired=lowest
DefaultGroupName={#AppName}
SetupIconFile=cirava.ico
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir={#AppOutputDir}
OutputBaseFilename={#AppOutputBaseFilename}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern dynamic windows11 includetitlebar
DisableWelcomePage=no
WizardImageFile=cirava-installer-panel.png
WizardSmallImageFile=icon-preview-256.bmp
WizardImageStretch=no
WizardImageBackColor=$171B21
WizardSizePercent=110
CloseApplications=yes
CloseApplicationsFilter=Cirava.exe
RestartApplications=yes
RestartIfNeededByRun=yes
Uninstallable=yes
SetupLogging=yes

[Files]
Source: "{#AppExeSource}"; DestDir: "{app}"; Flags: ignoreversion
Source: "cirava.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Cirava"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\cirava.ico"
Name: "{autodesktop}\Cirava"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\cirava.ico"; Tasks: desktopicon
Name: "{userstartup}\Cirava"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\cirava.ico"; Tasks: startup

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startup"; Description: "Launch Cirava when I sign in to Windows"; GroupDescription: "Additional startup options:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Cirava"; Flags: nowait postinstall

[Messages]
WelcomeLabel1=Your Drive, in motion.
WelcomeLabel2=A focused desktop client for fast, resumable Google Drive transfers. Sign in securely, then move files with clear progress and room to recover.
SelectTasksLabel2=Keep the shortcuts you want. You can change them whenever you like.
SelectDirLabel3=Choose where Cirava should be installed. Your Drive files stay in Google Drive.
ReadyLabel1=Everything is set. Cirava is ready to install.
FinishedHeadingLabel=Cirava is ready.
FinishedLabel=Your workspace is installed. Launch Cirava to connect Google Drive and start a transfer.
ClickNext=Continue
ClickFinish=Launch Cirava

[Code]
var
  AccentBar: TPanel;
  FooterLine: TPanel;

procedure InitializeWizard;
begin
  WizardForm.Font.Name := 'Segoe UI';
  WizardForm.Caption := 'Cirava · Set up your workspace';
  WizardForm.WelcomeLabel1.Caption := 'Your Drive, in motion.';
  WizardForm.WelcomeLabel1.Font.Size := 20;
  WizardForm.WelcomeLabel1.Font.Style := [fsBold];
  WizardForm.WelcomeLabel2.Caption := 'A focused desktop client for fast, resumable Google Drive transfers. Sign in securely, then move files with clear progress and room to recover.';
  WizardForm.WelcomeLabel2.WordWrap := True;
  WizardForm.NextButton.Caption := 'Continue';
  WizardForm.CancelButton.Caption := 'Cancel';
  WizardForm.BackButton.Caption := 'Back';

  AccentBar := TPanel.Create(WizardForm);
  AccentBar.Parent := WizardForm;
  AccentBar.Align := alTop;
  AccentBar.Height := ScaleY(5);
  AccentBar.BevelOuter := bvNone;
  AccentBar.Color := $6D83EE;

  FooterLine := TPanel.Create(WizardForm);
  FooterLine.Parent := WizardForm;
  FooterLine.Align := alBottom;
  FooterLine.Height := ScaleY(2);
  FooterLine.BevelOuter := bvNone;
  FooterLine.Color := $64C8C1;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectTasks then begin
    WizardForm.NextButton.Caption := 'Install Cirava';
  end else if CurPageID = wpFinished then begin
    WizardForm.NextButton.Caption := 'Launch Cirava';
  end else begin
    WizardForm.NextButton.Caption := 'Continue';
  end;
end;

param(
  [string]$Version = '1.0.1.0',
  [switch]$Sign
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$output = Join-Path $PSScriptRoot 'output'
$staging = Join-Path $env:TEMP ('cirava-msix-staging-' + [guid]::NewGuid().ToString('N'))
$package = Join-Path $output "Cirava-$Version.msix"
$makeappx = (Get-Command makeappx.exe -ErrorAction SilentlyContinue).Source
if (-not $makeappx) {
  $sdkRoot = 'C:\Program Files (x86)\Windows Kits\10\bin'
  $makeappx = Get-ChildItem -LiteralPath $sdkRoot -Filter makeappx.exe -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match '\\x64\\makeappx\.exe$' } | Sort-Object FullName | Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $makeappx) { throw 'makeappx.exe was not found. Install the Windows SDK or MSIX Packaging Tool.' }

if (Test-Path -LiteralPath $package) { throw "Refusing to overwrite existing MSIX package: $package" }
New-Item -ItemType Directory -Path (Join-Path $staging 'Assets') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $staging 'Msix.AppInstaller.Data\Images') -Force | Out-Null
Copy-Item (Join-Path $output 'Cirava.exe') (Join-Path $staging 'Cirava.exe') -Force
Copy-Item (Join-Path $PSScriptRoot 'msix\AppxManifest.xml') (Join-Path $staging 'AppxManifest.xml') -Force
Copy-Item (Join-Path $PSScriptRoot 'msix\MSIXAppInstallerData.xml') (Join-Path $staging 'Msix.AppInstaller.Data\MSIXAppInstallerData.xml') -Force
Copy-Item (Join-Path $root 'public\cirava-logo.png') (Join-Path $staging 'Msix.AppInstaller.Data\Images\Cirava.png') -Force
Copy-Item (Join-Path $PSScriptRoot 'icon-preview-256.png') (Join-Path $staging 'Assets\StoreLogo.png') -Force
Copy-Item (Join-Path $PSScriptRoot 'icon-preview-256.png') (Join-Path $staging 'Assets\Square150x150Logo.png') -Force
Copy-Item (Join-Path $PSScriptRoot 'icon-preview-16.png') (Join-Path $staging 'Assets\Square44x44Logo.png') -Force
& $makeappx pack /d $staging /p $package /o
if ($LASTEXITCODE -ne 0) { throw "makeappx failed with exit code $LASTEXITCODE" }

if ($Sign) {
  $signtool = (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
  if (-not $signtool) { throw 'signtool.exe was not found. Build the unsigned MSIX or install the Windows SDK signing tools.' }
  Write-Warning 'Signing requires a certificate trusted by the target Windows machine.'
  & $signtool sign /fd SHA256 /a $package
  if ($LASTEXITCODE -ne 0) { throw "signtool failed with exit code $LASTEXITCODE" }
}
Write-Output "Created $package"

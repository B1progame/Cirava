param(
  [int]$Port = 5175,
  [string]$ExePath = "",
  [switch]$SmokeTest
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $ExePath) {
  $ExePath = Join-Path $root 'packaging\output\Cirava.exe'
  if (-not (Test-Path -LiteralPath $ExePath)) { $ExePath = Join-Path $root 'packaging\inspection-output-v4\Cirava.exe' }
}
if (-not (Test-Path -LiteralPath $ExePath)) { throw "Cirava executable not found: $ExePath" }

$logPath = Join-Path $env:TEMP "cirava-inspection-$Port.log"
$errorLogPath = Join-Path $env:TEMP "cirava-inspection-$Port.err.log"
$portFile = Join-Path $PSScriptRoot 'cirava-inspection-port.json'
if (Test-Path -LiteralPath $logPath) { Remove-Item -LiteralPath $logPath -Force }
if (Test-Path -LiteralPath $errorLogPath) { Remove-Item -LiteralPath $errorLogPath -Force }

$preview = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'preview', '--', '--host', '127.0.0.1', '--port', "$Port") -WorkingDirectory $root -RedirectStandardOutput $logPath -RedirectStandardError $errorLogPath -PassThru
$url = "http://127.0.0.1:$Port/"
$inspectionUrl = "$url`?inspect=1"
$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
  try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1 | Out-Null; $ready = $true; break } catch { Start-Sleep -Milliseconds 250 }
}
if (-not $ready) { throw "Preview server did not become ready. See $logPath" }

$previousInspection = $env:CIRAVA_INSPECTION
$env:CIRAVA_INSPECTION = '1'
$app = Start-Process -FilePath $ExePath -WorkingDirectory (Split-Path -Parent $ExePath) -PassThru
Start-Sleep -Milliseconds 1200
if ($app.HasExited) { throw "Cirava exited immediately with code $($app.ExitCode). Check the desktop build at $ExePath." }
if ($null -eq $previousInspection) { Remove-Item Env:CIRAVA_INSPECTION -ErrorAction SilentlyContinue } else { $env:CIRAVA_INSPECTION = $previousInspection }
$record = [ordered]@{
  url = $inspectionUrl
  port = $Port
  previewPid = $preview.Id
  ciravaPid = $app.Id
  executable = (Resolve-Path -LiteralPath $ExePath).Path
  executableBytes = (Get-Item -LiteralPath $ExePath).Length
  startedAt = (Get-Date).ToString('o')
  nativeBridge = 'pywebview API is available inside Cirava.exe; the preview URL is visual-only.'
  status = if ($app.HasExited) { 'exited' } else { 'running' }
}
$record | ConvertTo-Json | Set-Content -LiteralPath $portFile -Encoding utf8
Write-Output "IAB_URL=$inspectionUrl"
Write-Output "PORT_FILE=$portFile"
Write-Output "CIRAVA_PID=$($app.Id)"
Write-Output "PREVIEW_PID=$($preview.Id)"
Write-Output "EXE_PATH=$((Resolve-Path -LiteralPath $ExePath).Path)"
Write-Output "STATUS=running"
if ($SmokeTest) {
  Write-Output "SMOKE_TEST=passed (process remained alive after startup)"
}

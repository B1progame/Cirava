$compiler = Get-Command iscc -ErrorAction SilentlyContinue
if ($compiler) {
  & $compiler.Source (Join-Path $PSScriptRoot 'cirava.iss')
  exit $LASTEXITCODE
}

$knownPath = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $knownPath)) {
  throw 'Inno Setup compiler was not found. Install Inno Setup 6 or add ISCC.exe to PATH.'
}
& $knownPath (Join-Path $PSScriptRoot 'cirava.iss')
exit $LASTEXITCODE

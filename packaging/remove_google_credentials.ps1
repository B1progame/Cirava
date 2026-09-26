$ErrorActionPreference = 'Stop'

$ciravaDirectory = Join-Path $env:APPDATA 'Cirava'
$settingsPath = Join-Path $ciravaDirectory 'settings.json'

if (Test-Path -LiteralPath $settingsPath -PathType Leaf) {
    $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    if ($null -eq $settings) {
        throw 'Cirava settings could not be read; saved credentials were not fully removed.'
    }

    $settings.PSObject.Properties.Remove('client_id')
    if ($settings.PSObject.Properties.Count -eq 0) {
        Remove-Item -LiteralPath $settingsPath -Force
    } else {
        $json = ConvertTo-Json -InputObject $settings -Depth 32
        $encoding = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($settingsPath, $json, $encoding)
    }
}

foreach ($fileName in @('tokens.bin', 'client-credentials.bin')) {
    $credentialPath = Join-Path $ciravaDirectory $fileName
    if (Test-Path -LiteralPath $credentialPath -PathType Leaf) {
        Remove-Item -LiteralPath $credentialPath -Force
    }
}

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$logoPath = Join-Path $root 'public\cirava-logo.png'
$panelPath = Join-Path $PSScriptRoot 'cirava-installer-panel-minimal.png'
$width = 656
$height = 1254
$logoSize = 300
$logoX = [int](($width - $logoSize) / 2)
$logoY = [int](($height - $logoSize) / 2)

Add-Type -AssemblyName System.Drawing
$bitmap = New-Object System.Drawing.Bitmap($width, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$logo = $null
$brush = $null

try {
  $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    [System.Drawing.Rectangle]::new(0, 0, $width, $height),
    [System.Drawing.Color]::FromArgb(255, 32, 40, 51),
    [System.Drawing.Color]::FromArgb(255, 23, 27, 33),
    45
  )
  $graphics.FillRectangle($brush, 0, 0, $width, $height)
  $logo = [System.Drawing.Image]::FromFile($logoPath)
  $graphics.DrawImage($logo, $logoX, $logoY, $logoSize, $logoSize)
  $bitmap.Save($panelPath, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
  if ($logo) { $logo.Dispose() }
  if ($brush) { $brush.Dispose() }
  $graphics.Dispose()
  $bitmap.Dispose()
}

Write-Output "Generated installer panel from $logoPath"

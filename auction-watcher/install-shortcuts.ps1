<#
  auction-watcher / install-shortcuts.ps1

  Puts an "Auction Watch" icon on your desktop. Clicking it starts the watcher in
  the background if it isn't running yet, then opens http://localhost:8845/

    powershell -ExecutionPolicy Bypass -File install-shortcuts.ps1            # desktop icon
    powershell -ExecutionPolicy Bypass -File install-shortcuts.ps1 -Startup   # + start silently at Windows sign-in
    powershell -ExecutionPolicy Bypass -File install-shortcuts.ps1 -Remove    # remove both

  Re-run it if you move this folder.
#>
param([switch]$Startup, [switch]$Remove)

$here    = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$ps      = Join-Path $PSHOME 'powershell.exe'
$desk    = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Auction Watch.lnk'
$boot    = Join-Path ([Environment]::GetFolderPath('Startup')) 'Auction Watch (background).lnk'
$icon    = Join-Path $here 'auction-watch.ico'

if ($Remove) {
  foreach ($f in $desk, $boot) { if (Test-Path $f) { Remove-Item $f; Write-Host "Removed $f" } }
  return
}

# a simple icon (navy tile, rising bars, green "live" dot), PNG-in-ICO so it stays sharp
if (-not (Test-Path $icon)) {
  Add-Type -AssemblyName System.Drawing
  $n = 256
  $bmp = New-Object Drawing.Bitmap $n, $n
  $g = [Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = 'AntiAlias'
  $path = New-Object Drawing.Drawing2D.GraphicsPath
  $r = 56
  $path.AddArc(0, 0, $r, $r, 180, 90); $path.AddArc($n - $r - 1, 0, $r, $r, 270, 90)
  $path.AddArc($n - $r - 1, $n - $r - 1, $r, $r, 0, 90); $path.AddArc(0, $n - $r - 1, $r, $r, 90, 90); $path.CloseFigure()
  $g.FillPath((New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(255, 17, 26, 43))), $path)
  $bar = New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(255, 232, 238, 247))
  $g.FillRectangle($bar, 52, 150, 36, 58); $g.FillRectangle($bar, 110, 112, 36, 96); $g.FillRectangle($bar, 168, 74, 36, 134)
  $g.FillEllipse((New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(255, 34, 197, 94))), 160, 22, 52, 52)
  $g.Dispose()
  $ms = New-Object IO.MemoryStream
  $bmp.Save($ms, [Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
  $png = $ms.ToArray()
  $fs = [IO.File]::Create($icon)
  $w = New-Object IO.BinaryWriter $fs
  $w.Write([uint16]0); $w.Write([uint16]1); $w.Write([uint16]1)                       # ICONDIR
  $w.Write([byte]0); $w.Write([byte]0); $w.Write([byte]0); $w.Write([byte]0)          # 256x256, no palette
  $w.Write([uint16]1); $w.Write([uint16]32); $w.Write([uint32]$png.Length); $w.Write([uint32]22)
  $w.Write($png)
  $w.Close()
}

$shell = New-Object -ComObject WScript.Shell

$lnk = $shell.CreateShortcut($desk)
$lnk.TargetPath       = $ps
$lnk.Arguments        = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $here 'open.ps1')`""
$lnk.WorkingDirectory = $here
$lnk.WindowStyle      = 7          # minimized - no console flash
$lnk.IconLocation     = "$icon,0"
$lnk.Description      = 'Open the Treasury auction results page (starts the watcher if needed)'
$lnk.Save()
Write-Host "Desktop icon : $desk"

if ($Startup) {
  $s = $shell.CreateShortcut($boot)
  $s.TargetPath       = $ps
  $s.Arguments        = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $here 'watch.ps1')`" -Background"
  $s.WorkingDirectory = $here
  $s.WindowStyle      = 7
  $s.IconLocation     = "$icon,0"
  $s.Description      = 'Runs Auction Watch in the background from sign-in'
  $s.Save()
  Write-Host "Sign-in start: $boot"
}
Write-Host "Page         : http://localhost:8845/"

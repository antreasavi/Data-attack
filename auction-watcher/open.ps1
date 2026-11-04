<#
  auction-watcher / open.ps1  -  what the "Auction Watch" desktop icon runs.

  Makes sure the watcher is running (starts it in the background, with no window,
  if it isn't) and then opens the results page  http://localhost:8845/
  Safe to click any number of times: only one watcher ever runs.
#>
param([int]$Port = 8845)

$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$url  = "http://localhost:$Port/"
$log  = Join-Path $here 'data\watch.log'

function Test-PageUp {
  try { return (Invoke-WebRequest ($url + 'index.html') -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { return $false }
}

if (-not (Test-PageUp)) {
  $ps = Join-Path $PSHOME 'powershell.exe'
  $watch = Join-Path $here 'watch.ps1'
  Start-Process -FilePath $ps -WindowStyle Hidden -WorkingDirectory $here `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$watch`" -Background -Port $Port"
  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline -and -not (Test-PageUp)) { Start-Sleep -Milliseconds 300 }
}

if (Test-PageUp) {
  Start-Process $url
} else {
  $msg = "Auction Watch couldn't start its page on $url.`n`n" +
         "If another program is using port $Port, run watch.ps1 with -Port 8846.`n" +
         "Details are in:`n$log"
  try { [void](New-Object -ComObject WScript.Shell).Popup($msg, 0, 'Auction Watch', 48) } catch { Write-Host $msg }
}

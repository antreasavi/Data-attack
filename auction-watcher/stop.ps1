# auction-watcher / stop.ps1 - stops Auction Watch, including a copy running in the background.
$p = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match 'auction-watcher\\watch\.ps1' })
if ($p.Count) {
  $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Write-Host "Stopped Auction Watch."
} else {
  Write-Host "Auction Watch was not running."
}

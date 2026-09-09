<#
  buyback-watcher / start.ps1
  Runs the watcher (which now also serves the alert page in this same window)
  and opens the page in your browser. ONE window - keep it open.

    powershell -ExecutionPolicy Bypass -File start.ps1
    powershell -ExecutionPolicy Bypass -File start.ps1 -IntervalSeconds 10
    powershell -ExecutionPolicy Bypass -File start.ps1 -Url "https://.../BBPA_XXXXXXXXXXXXXX.pdf"
    powershell -ExecutionPolicy Bypass -File start.ps1 -Port 8850
    powershell -ExecutionPolicy Bypass -File start.ps1 -NotBefore 2026-09-10 -FanoutDays 3
#>
param(
  [string]$Url = "https://www.treasurydirect.gov/instit/annceresult/press/preanre/2026/BBPA_20260910174000.pdf",
  [int]$IntervalSeconds = 20,
  [int]$Port = 8844,
  [int]$FanoutDays = 2,
  [string]$NotBefore,
  [switch]$ExactUrlOnly,
  [switch]$KeepWatching,
  [int]$MaxChecks = 0
)

$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }

$watchArgs = @{
  Url             = $Url
  IntervalSeconds = $IntervalSeconds
  Port            = $Port
  FanoutDays      = $FanoutDays
  OpenBrowser     = $true
}
if ($MaxChecks -gt 0) { $watchArgs.MaxChecks = $MaxChecks }
if ($NotBefore)       { $watchArgs.NotBefore = $NotBefore }
if ($ExactUrlOnly)    { $watchArgs.ExactUrlOnly = $true }
if ($KeepWatching)    { $watchArgs.KeepWatching = $true }

& (Join-Path $here 'watch.ps1') @watchArgs

<#
  buyback-watcher / watch.ps1
  Polls a TreasuryDirect "Buyback Purchase / Preliminary Announcement" PDF URL.
  When the URL goes live it downloads the PDF, extracts the buyback dollar amount
  ("Maximum Par Amount to be Redeemed") and writes data/state.json, which the
  alert page (index.html) reads and turns into a full-screen colour + notification.

  Examples:
    powershell -ExecutionPolicy Bypass -File watch.ps1
    powershell -ExecutionPolicy Bypass -File watch.ps1 -IntervalSeconds 10
    powershell -ExecutionPolicy Bypass -File watch.ps1 -TestPdf .\data\sample_BBPA_20250604.pdf
#>
[CmdletBinding()]
param(
  [string]$Url = "https://www.treasurydirect.gov/instit/annceresult/press/preanre/2026/BBPA_20260910174000.pdf",
  [int]$IntervalSeconds = 20,
  [int]$MaxChecks = 0,                 # 0 = run forever
  [switch]$KeepWatching,               # keep polling even after it is found
  [string]$TestPdf,                    # parse a local PDF, write state.json, exit (demo/preview)
  [switch]$SelfTest,                   # run parser assertions and exit
  [int]$FanoutDays = 2,               # also probe filenames up to this many days LATER / other close-times / mirror host
  [switch]$ExactUrlOnly,              # only poll the exact -Url, no fan-out
  [string]$NotBefore,                 # ignore any BBPA file dated before this (yyyy-MM-dd); default = the -Url's own date
  [int]$Port = 8844,                  # the built-in page server binds here
  [switch]$NoServe,                   # don't run the built-in page server
  [switch]$OpenBrowser,               # open the alert page in the default browser once the server is up
  [string]$DataDir
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13 } catch {}

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $DataDir) { $DataDir = Join-Path $scriptDir "data" }
if (!(Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir | Out-Null }
$StatePath = Join-Path $DataDir "state.json"
$UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) buyback-watcher/1.0"

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function Write-State($obj) {
  $tmp = "$StatePath.tmp"
  [System.IO.File]::WriteAllText($tmp, ($obj | ConvertTo-Json -Depth 8), $Utf8NoBom)
  Move-Item -Force -Path $tmp -Destination $StatePath
}

# Serves this folder on http://localhost:$Port/ from a background runspace, so the
# alert page lives in the SAME window as the watcher - nothing separate to lose.
# Dies automatically when this script exits.
function Start-PageServer([int]$Port, [string]$Root) {
  $rs = [runspacefactory]::CreateRunspace()
  $rs.Open()
  $rs.SessionStateProxy.SetVariable('P', $Port)
  $rs.SessionStateProxy.SetVariable('ROOT', $Root)
  $ps = [powershell]::Create()
  $ps.Runspace = $rs
  [void]$ps.AddScript({
    $mime = @{ '.html' = 'text/html; charset=utf-8'; '.css' = 'text/css; charset=utf-8'; '.js' = 'application/javascript; charset=utf-8'; '.json' = 'application/json; charset=utf-8'; '.pdf' = 'application/pdf'; '.svg' = 'image/svg+xml'; '.ico' = 'image/x-icon'; '.png' = 'image/png' }
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add("http://localhost:$P/")
    try { $listener.Start() } catch { return }
    $rootFull = [IO.Path]::GetFullPath($ROOT)
    while ($listener.IsListening) {
      try {
        $ctx = $listener.GetContext()
        $req = $ctx.Request; $res = $ctx.Response
        $rel = [Uri]::UnescapeDataString($req.Url.LocalPath)
        if ($rel -eq '/' -or [string]::IsNullOrWhiteSpace($rel)) { $rel = '/index.html' }
        $file = Join-Path $ROOT ($rel.TrimStart('/') -replace '/', '\')
        $full = [IO.Path]::GetFullPath($file)
        $res.Headers.Add('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        $res.Headers.Add('Access-Control-Allow-Origin', '*')
        if ($full.StartsWith($rootFull) -and (Test-Path $full -PathType Leaf)) {
          $ext = [IO.Path]::GetExtension($full).ToLower()
          $res.ContentType = if ($mime.ContainsKey($ext)) { $mime[$ext] } else { 'application/octet-stream' }
          $bytes = [IO.File]::ReadAllBytes($full)
          $res.ContentLength64 = $bytes.Length
          $res.OutputStream.Write($bytes, 0, $bytes.Length)
        } else {
          $res.StatusCode = 404
          $b = [Text.Encoding]::UTF8.GetBytes("404: $rel")
          $res.OutputStream.Write($b, 0, $b.Length)
        }
        $res.OutputStream.Close()
      } catch {}
    }
  })
  [void]$ps.BeginInvoke()
  return $ps
}

function Get-Pdftotext {
  $c = Get-Command pdftotext -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  foreach ($p in @(
      "C:\Program Files\Git\mingw64\bin\pdftotext.exe",
      "C:\Program Files\Git\usr\bin\pdftotext.exe",
      "C:\Program Files (x86)\Git\mingw64\bin\pdftotext.exe")) {
    if (Test-Path $p) { return $p }
  }
  return $null
}

function Format-Short([int64]$n) {
  if ($n -ge 1000000000) { return ('${0:0.##}B' -f ($n / 1000000000)) }
  if ($n -ge 1000000)    { return ('${0:0.##}M' -f ($n / 1000000)) }
  return ('$' + $n)
}

function Get-AmountValue([string]$s) {
  $n = [int64]0
  [void][int64]::TryParse(($s -replace '[^\d]', ''), [ref]$n)
  return $n
}

# Returns the "Maximum Par Amount to be Redeemed" as an int64 (0 if not found).
# It is the first $ figure over $10M that appears AFTER the word "Redeemed"
# (the layout lists all labels first, then the values). No upper limit - it can
# be well above $5B, e.g. $12,500,000,000. Falls back to the largest $ figure.
function Get-BuybackAmount([string]$flat) {
  $mRed = [regex]::Match($flat, 'Redeemed', 'IgnoreCase')
  if ($mRed.Success) {
    $tail = $flat.Substring($mRed.Index)
    foreach ($m in [regex]::Matches($tail, '\$[\d,]{6,}')) {
      $v = Get-AmountValue $m.Value
      if ($v -ge 10000000) { return $v }
    }
  }
  $best = [int64]0
  foreach ($m in [regex]::Matches($flat, '\$[\d,]{6,}')) {
    $v = Get-AmountValue $m.Value
    if ($v -ge 10000000 -and $v -gt $best) { $best = $v }
  }
  return $best
}

function Get-Tier([int64]$n) {
  if ($n -ge 10000000000) { return @{ name = 'HUGE  ( >= $10B )';     color = '#b91c1c' } }
  if ($n -ge 5000000000)  { return @{ name = 'XL  ( $5B - $10B )';    color = '#ef4444' } }
  if ($n -ge 3000000000)  { return @{ name = 'LARGE  ( $3B - $5B )';  color = '#f59e0b' } }
  if ($n -ge 1000000000)  { return @{ name = 'NORMAL  ( $1B - $3B )'; color = '#22c55e' } }
  return                         @{ name = 'SMALL  ( < $1B )';        color = '#3b82f6' }
}

function ConvertTo-Buyback([string]$pdfPath) {
  $res = [ordered]@{
    detectedAt          = (Get-Date).ToUniversalTime().ToString("o")
    pdfUrl              = $Url
    localPdf            = "data/" + [IO.Path]::GetFileName($pdfPath)
    operationType       = $null
    headlineAmount      = $null
    headlineAmountText  = $null
    headlineAmountShort = $null
    tier                = $null
    tierColor           = $null
    maturityRange       = $null
    operationDate       = $null
    releaseDate         = $null
    allAmounts          = @()
    parsed              = $false
    rawTextExcerpt      = $null
  }

  $pt = Get-Pdftotext
  $text = $null
  if ($pt) {
    $txtOut = "$pdfPath.txt"
    try { & $pt -q -nopgbrk -- $pdfPath $txtOut 2>$null } catch {}
    if (Test-Path $txtOut) { $text = Get-Content -Path $txtOut -Raw }
  }
  if (-not $text) {
    $res.rawTextExcerpt = if ($pt) { "pdftotext produced no text" } else { "pdftotext not found on this machine" }
    return $res
  }

  $flat = ($text -replace '\s+', ' ').Trim()
  $res.rawTextExcerpt = $flat.Substring(0, [Math]::Min(2000, $flat.Length))

  if     ($flat -match 'TREASURY\s+TIPS\s+BUYBACK')       { $res.operationType = 'TIPS buyback' }
  elseif ($flat -match 'TREASURY\s+DEBT\s+BUYBACK')       { $res.operationType = 'Nominal coupon buyback' }
  elseif ($flat -match 'BUYBACK')                          { $res.operationType = 'Treasury buyback' }

  if ($flat -match '(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})') {
    $res.maturityRange = "$($matches[1]) - $($matches[2])"
  }

  $months = 'January|February|March|April|May|June|July|August|September|October|November|December'
  $mDate = [regex]::Match($flat, "\`$[\d,]{7,}\s+(($months)\s+\d{1,2},\s+\d{4})")
  if ($mDate.Success) { $res.operationDate = $mDate.Groups[1].Value }
  elseif ($flat -match "($months)\s+\d{1,2},\s+\d{4}") { $res.operationDate = $matches[0] }
  $mRel = [regex]::Match($flat, "Embargoed Until.*?(($months)\s+\d{1,2},\s+\d{4})")
  if ($mRel.Success) { $res.releaseDate = $mRel.Groups[1].Value }

  $amountsRaw = [regex]::Matches($flat, '\$[\d,]{4,}') | ForEach-Object { $_.Value } | Select-Object -Unique
  $res.allAmounts = @($amountsRaw)

  $best = Get-BuybackAmount $flat
  if ($best -gt 0) {
    $tier = Get-Tier $best
    $res.headlineAmount      = $best
    $res.headlineAmountText  = ('${0:N0}' -f $best)
    $res.headlineAmountShort = Format-Short $best
    $res.tier                = $tier.name
    $res.tierColor           = $tier.color
    $res.parsed              = $true
  }
  return $res
}

# ---- self test ---------------------------------------------------------------
if ($SelfTest) {
  $fail = 0
  function Check($label, $got, $want) {
    if ("$got" -eq "$want") { Write-Host "  ok   $label = $got" -ForegroundColor Green }
    else { Write-Host "  FAIL $label : got '$got', want '$want'" -ForegroundColor Red; $script:fail++ }
  }
  # flattened text like pdftotext produces (values follow the label block)
  $t125 = 'TREASURY DEBT BUYBACK OPERATION PRELIMINARY ANNOUNCEMENT Preliminary Eligible Securities Maturity Date Range Maximum Par Amount to be Redeemed Operation Date Operation Start Time Minimum Offer Amount and Multiples See attached table 10/15/2026 - 08/31/2028 $12,500,000,000 September 09, 2026 1:40 p.m. ET $1,000,000 9'
  $t2   = 'Maximum Par Amount to be Redeemed2 Operation Date ... See attached table 02/15/2036 - 05/15/2045 $2,000,000,000 June 04, 2025 1:40 p.m. ET 2:00 p.m. ET June 05, 2025 $1,000,000 9'
  $t500 = 'TREASURY TIPS BUYBACK OPERATION ... Maximum Par Amount to be Redeemed2 Operation Date ... 02/15/2040 - 02/15/2056 $500,000,000 March 25, 2026 $1,000,000 9'

  Check "12.5B amount"  (Get-BuybackAmount $t125) 12500000000
  Check "2B amount"     (Get-BuybackAmount $t2)    2000000000
  Check "500M amount"   (Get-BuybackAmount $t500)  500000000
  Check "12.5B short"   (Format-Short 12500000000) '$12.5B'
  Check "2B short"      (Format-Short 2000000000)  '$2B'
  Check "500M short"    (Format-Short 500000000)   '$500M'
  Check "12.5B tier"    ((Get-Tier 12500000000).name) 'HUGE  ( >= $10B )'
  Check "6B tier"       ((Get-Tier 6000000000).name)  'XL  ( $5B - $10B )'
  Check "4B tier"       ((Get-Tier 4000000000).name)  'LARGE  ( $3B - $5B )'
  Check "2B tier"       ((Get-Tier 2000000000).name)  'NORMAL  ( $1B - $3B )'
  Check "500M tier"     ((Get-Tier 500000000).name)   'SMALL  ( < $1B )'
  Write-Host ""
  if ($fail) { Write-Host "$fail check(s) failed" -ForegroundColor Red; exit 1 }
  Write-Host "all checks passed" -ForegroundColor Green
  return
}

# ---- test / preview mode --------------------------------------------------------
if ($TestPdf) {
  if (!(Test-Path $TestPdf)) { throw "TestPdf not found: $TestPdf" }
  Write-Host "Parsing $TestPdf ..." -ForegroundColor Cyan
  $r = ConvertTo-Buyback (Resolve-Path $TestPdf).Path
  Write-State ([ordered]@{
      status = 'found'; found = $true
      checkedAt = (Get-Date).ToUniversalTime().ToString("o"); checkCount = 0
      url = $Url; httpStatus = 200; lastError = $null; result = $r
    })
  Write-Host "Amount   : $($r.headlineAmountText)  ($($r.headlineAmountShort))" -ForegroundColor Green
  Write-Host "Type     : $($r.operationType)"
  Write-Host "Maturity : $($r.maturityRange)"
  Write-Host "Op date  : $($r.operationDate)"
  Write-Host "Tier     : $($r.tier)"
  Write-Host ""
  Write-Host "Wrote $StatePath  -> open the alert page to see it."
  return
}

# ---- candidate URLs ----------------------------------------------------------
# The exact -Url is checked first. Fan-out also probes the same BBPA file name on
# the days FROM the floor date THROUGH FanoutDays later, the other usual
# close-time stamps, and the fiscaldata.treasury.gov mirror - so a small mismatch
# in the published file name still gets caught. Nothing dated before the floor is
# ever probed or accepted (keeps an already-published earlier operation from
# firing a false alarm).

function Get-UrlFileDate([string]$u) {
  $m = [regex]::Match($u, 'BBPA_(\d{8})\d{6}\.pdf', 'IgnoreCase')
  if (-not $m.Success) { return $null }
  try { return [datetime]::ParseExact($m.Groups[1].Value, 'yyyyMMdd', [Globalization.CultureInfo]::InvariantCulture) }
  catch { return $null }
}

# floor = -NotBefore if given, else the date baked into -Url
$FloorDate = $null
if ($NotBefore) {
  foreach ($fmt in 'yyyy-MM-dd', 'yyyyMMdd', 'MM/dd/yyyy') {
    try { $FloorDate = [datetime]::ParseExact($NotBefore, $fmt, [Globalization.CultureInfo]::InvariantCulture); break } catch {}
  }
}
if (-not $FloorDate) { $FloorDate = Get-UrlFileDate $Url }

function Get-CandidateUrls([string]$primary) {
  $list = New-Object System.Collections.Generic.List[string]
  $list.Add($primary)
  if ($ExactUrlOnly) { return $list }

  $m = [regex]::Match($primary, 'BBPA_(\d{8})(\d{6})\.pdf', 'IgnoreCase')
  if (-not $m.Success) { return $list }

  $baseDate = Get-UrlFileDate $primary
  if (-not $baseDate) { return $list }
  $start = if ($FloorDate -and $FloorDate -gt $baseDate) { $FloorDate } else { $baseDate }
  $times = @($m.Groups[2].Value, '174000', '184000', '164000') | Select-Object -Unique

  foreach ($d in 0..$FanoutDays) {
    $day = $start.AddDays($d)
    if ($FloorDate -and $day -lt $FloorDate) { continue }
    $ymd = $day.ToString('yyyyMMdd')
    $yr  = $day.ToString('yyyy')
    foreach ($t in $times) {
      $name = "BBPA_$ymd$t.pdf"
      $list.Add("https://www.treasurydirect.gov/instit/annceresult/press/preanre/$yr/$name")
      $list.Add("https://fiscaldata.treasury.gov/static-data/published-reports/buybacks/preliminary/$name")
    }
  }
  return ($list | Select-Object -Unique)
}

function Test-UrlLive([string]$u) {
  $out = @{ live = $false; status = $null; err = $null }
  try {
    $h = Invoke-WebRequest -Uri $u -Method Head -UserAgent $UA -TimeoutSec 12 -UseBasicParsing
    $out.status = [int]$h.StatusCode
    if ($out.status -ge 200 -and $out.status -lt 400) { $out.live = $true; return $out }
  } catch {
    if ($_.Exception.Response) { $out.status = [int]$_.Exception.Response.StatusCode } else { $out.err = $_.Exception.Message }
  }
  if (-not $out.live -and ($out.status -eq 403 -or $out.status -eq 405 -or $out.status -eq $null)) {
    try {
      $g = Invoke-WebRequest -Uri $u -Headers @{ Range = 'bytes=0-0' } -UserAgent $UA -TimeoutSec 12 -UseBasicParsing
      $out.status = [int]$g.StatusCode
      if ($out.status -ge 200 -and $out.status -lt 400) { $out.live = $true }
    } catch {
      if ($_.Exception.Response) { $out.status = [int]$_.Exception.Response.StatusCode }
    }
  }
  return $out
}

# ---- built-in page server ---------------------------------------------------
$pageUrl = "http://localhost:$Port/"
if (-not $NoServe) {
  $null = Start-PageServer $Port $scriptDir
  $up = $false
  foreach ($i in 1..15) {
    Start-Sleep -Milliseconds 250
    try {
      if ((Invoke-WebRequest ($pageUrl + 'index.html') -TimeoutSec 3 -UseBasicParsing).StatusCode -eq 200) { $up = $true; break }
    } catch {}
  }
  if (-not $up) {
    Write-Host "WARNING: built-in page server did not come up on port $Port." -ForegroundColor Yellow
    Write-Host "         Re-run with  -Port 8850  (or another free port), or add -NoServe." -ForegroundColor Yellow
  }
}

# ---- watch loop ---------------------------------------------------------------
$candidates = @(Get-CandidateUrls $Url)
Write-Host ""
Write-Host "Buyback watcher running" -ForegroundColor Cyan
if (-not $NoServe) { Write-Host "  ALERT PAGE  : $pageUrl   <-- open this in your browser" -ForegroundColor Green }
Write-Host "  Target URL  : $Url"
Write-Host "  Also probing: $($candidates.Count - 1) fallback name(s)  (-ExactUrlOnly to disable)"
if ($FloorDate) { Write-Host "  Ignoring    : any BBPA file dated before $($FloorDate.ToString('yyyy-MM-dd'))" }
Write-Host "  Interval    : $IntervalSeconds s"
Write-Host "  State       : $StatePath"
Write-Host "  (leave this window open; Ctrl+C to stop)"
Write-Host ""

if ($OpenBrowser -and -not $NoServe) { try { Start-Process $pageUrl } catch {} }

$count = 0
while ($true) {
  $count++
  $nowIso = (Get-Date).ToUniversalTime().ToString("o")
  $stamp  = (Get-Date).ToString("HH:mm:ss")

  $hitUrl = $null
  $primaryStatus = $null
  $lastErr = $null
  foreach ($u in $candidates) {
    $t = Test-UrlLive $u
    if ($u -eq $Url) { $primaryStatus = $t.status; if ($t.err) { $lastErr = $t.err } }
    if ($t.live) {
      $fd = Get-UrlFileDate $u
      if ($FloorDate -and $fd -and $fd -lt $FloorDate) { continue }   # earlier operation, not ours
      $hitUrl = $u; break
    }
  }

  if ($hitUrl) {
    $via = if ($hitUrl -eq $Url) { "target URL" } else { "fallback: $hitUrl" }
    Write-Host "[$stamp] check #$count  ->  200   *** PUBLISHED ***  ($via)" -ForegroundColor Green
    try {
      $fileName = [IO.Path]::GetFileName((($hitUrl -split '\?')[0]))
      if (-not $fileName) { $fileName = "buyback.pdf" }
      $pdfPath = Join-Path $DataDir $fileName
      Invoke-WebRequest -Uri $hitUrl -OutFile $pdfPath -UserAgent $UA -TimeoutSec 90 -UseBasicParsing
      $r = ConvertTo-Buyback $pdfPath
      $r.pdfUrl = $hitUrl
      Write-State ([ordered]@{
          status = 'found'; found = $true; checkedAt = $nowIso; checkCount = $count
          url = $Url; foundUrl = $hitUrl; httpStatus = 200; lastError = $null; result = $r
        })
      Write-Host ""
      Write-Host "  Amount   : $($r.headlineAmountText)   ($($r.headlineAmountShort))" -ForegroundColor Green
      Write-Host "  Type     : $($r.operationType)"
      Write-Host "  Maturity : $($r.maturityRange)"
      Write-Host "  Op date  : $($r.operationDate)"
      Write-Host "  Tier     : $($r.tier)"
      Write-Host "  Saved    : $pdfPath"
      Write-Host ""
      if (-not $r.parsed) {
        Write-Host "  NOTE: could not auto-read the dollar amount - open the PDF and check manually." -ForegroundColor Yellow
      }
      if (-not $KeepWatching) {
        Write-Host "Done. The alert page is now showing the amount. Press Ctrl+C to close." -ForegroundColor Cyan
        break
      }
    } catch {
      $msg = "download/parse failed: $($_.Exception.Message)"
      Write-Host "  $msg" -ForegroundColor Red
      Write-State ([ordered]@{
          status = 'error'; found = $false; checkedAt = $nowIso; checkCount = $count
          url = $Url; foundUrl = $hitUrl; httpStatus = 200; lastError = $msg; result = $null
        })
    }
  } else {
    $label = if ($primaryStatus) { "HTTP $primaryStatus" } elseif ($lastErr) { "ERR: $lastErr" } else { "no response" }
    Write-Host "[$stamp] check #$count  ->  $label  (waiting)"
    Write-State ([ordered]@{
        status = if ($lastErr) { 'error' } else { 'waiting' }
        found = $false; checkedAt = $nowIso; checkCount = $count
        url = $Url; foundUrl = $null; httpStatus = $primaryStatus; lastError = $lastErr; result = $null
      })
  }

  if ($MaxChecks -gt 0 -and $count -ge $MaxChecks) { Write-Host "Reached MaxChecks ($MaxChecks). Stopping."; break }
  Start-Sleep -Seconds $IntervalSeconds
}

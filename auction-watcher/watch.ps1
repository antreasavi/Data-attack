<#
  auction-watcher / watch.ps1

  Waits for the next Treasury auction-results PDF on TreasuryDirect
  (Auctions -> Announcements, Data & Results), grabs it the moment it is posted,
  and shows it on a results page you keep open (http://localhost:8845/).
  By default it watches the 1:00 PM ET note/bond auctions.

  How it works
    1. Reads the auction schedule from TreasuryDirect's own data feed
       (the same feed the "Announcements, Data & Results" page is built from)
       to find the next 1:00 PM auction and its CUSIP.
    2. Sleeps until 1 minute before the close.
    3. Polls the results file names directly  .../preanre/<yyyy>/R_<yyyymmdd>_<n>.pdf
       every 2 s. The PDF lands ~1:02 PM ET, 1-2 minutes BEFORE the website's
       table / data feed updates, so this is the fastest public source.
    4. When a new R_ file appears it downloads it, checks the CUSIP inside is
       the auction it is waiting for, and puts it on the page (which flashes and
       chimes), along with the headline numbers (high yield, bid-to-cover,
       indirect/direct/dealer takedown).
    5. Moves on to the next 1:00 PM auction (use -Once to stop instead).

  Examples
    powershell -ExecutionPolicy Bypass -File watch.ps1
    powershell -ExecutionPolicy Bypass -File watch.ps1 -CloseTime "11:30 AM"   # bill auctions
    powershell -ExecutionPolicy Bypass -File watch.ps1 -CloseTime any          # every auction
    powershell -ExecutionPolicy Bypass -File watch.ps1 -Date 2026-11-09 -Once
    powershell -ExecutionPolicy Bypass -File watch.ps1 -NoPage                 # no page: open PDFs in your PDF viewer
    powershell -ExecutionPolicy Bypass -File watch.ps1 -Demo                   # show how a drop looks, now
    powershell -ExecutionPolicy Bypass -File watch.ps1 -Replay 2026-10-29      # replay a past drop
#>
[CmdletBinding()]
param(
  [string]$CloseTime = '01:00 PM',   # competitive close time (ET) of the auctions to watch; 'any' = all
  [string]$Date,                     # only watch this auction date (yyyy-MM-dd)
  [int]$IntervalSeconds = 2,         # poll interval around the drop
  [int]$LeadSeconds = 60,            # start fast polling this long before the close
  [int]$FastMinutes = 10,            # after this many minutes past the close, slow to 10 s polls
  [int]$GiveUpMinutes = 60,          # stop waiting for a drop this long after the close
  [int]$Port = 8845,                 # the results page is served on http://localhost:<Port>/
  [switch]$NoPage,                   # no page: open each PDF in your PDF viewer instead
  [switch]$OpenPdf,                  # with the page on, ALSO open each PDF in your PDF viewer
  [switch]$NoBrowser,                # don't open the page in the browser at start
  [switch]$Once,                     # stop after one auction session
  [switch]$NoOpen,                   # never open the PDF outside the page
  [switch]$NoSound,                  # (no-page mode) no console beep
  [switch]$Demo,                     # test: drop the most recent published result onto the page now
  [string]$Replay,                   # test: re-run drop detection against a past auction date
  [string]$DataDir
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $DataDir) { $DataDir = Join-Path $scriptDir 'data' }
if (!(Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir | Out-Null }
$DataDir = (Resolve-Path $DataDir).Path

$Base   = 'https://www.treasurydirect.gov'
$UA     = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) auction-watcher/1.0'
$Inv    = [Globalization.CultureInfo]::InvariantCulture
$EtZone = [TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')

$UsePage      = -not $NoPage
$OpenExternal = (-not $NoOpen) -and ($NoPage -or $OpenPdf)
$StatePath    = Join-Path $DataDir 'state.json'
$Utf8NoBom    = New-Object System.Text.UTF8Encoding($false)
$pageUrl      = $null

# ---- small helpers -------------------------------------------------------------

function Get-NowEt { [TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $EtZone) }

function ConvertTo-LocalTime([datetime]$et) {
  [TimeZoneInfo]::ConvertTime([DateTime]::SpecifyKind($et, 'Unspecified'), $EtZone, [TimeZoneInfo]::Local)
}
function ConvertTo-UtcIso([datetime]$et) {
  [TimeZoneInfo]::ConvertTimeToUtc([DateTime]::SpecifyKind($et, 'Unspecified'), $EtZone).ToString('o', $Inv)
}

function Format-Et([datetime]$et)    { $et.ToString('h:mm:ss tt', $Inv) + ' ET' }
function Format-Local([datetime]$et) { (ConvertTo-LocalTime $et).ToString('HH:mm:ss', $Inv) + ' local' }

function Format-Span([TimeSpan]$t) {
  if ($t.TotalSeconds -lt 0) { $t = [TimeSpan]::Zero }
  if ($t.Days -gt 0) { return ('{0}d {1:00}h {2:00}m' -f $t.Days, $t.Hours, $t.Minutes) }
  return ('{0:00}:{1:00}:{2:00}' -f [int][Math]::Floor($t.TotalHours), $t.Minutes, $t.Seconds)
}

function Format-Money($n) {
  $v = 0.0
  if (-not [double]::TryParse("$n", [Globalization.NumberStyles]::Any, $Inv, [ref]$v) -or $v -le 0) { return '' }
  if ($v -ge 1e9) { return ('${0:0.##}B' -f ($v / 1e9)) }
  return ('${0:0.##}M' -f ($v / 1e6))
}

function ConvertTo-Day([string]$s) {
  foreach ($f in 'yyyy-MM-dd', 'yyyyMMdd', 'MM/dd/yyyy') {
    $d = [datetime]::MinValue
    if ([datetime]::TryParseExact($s.Trim(), $f, $Inv, [Globalization.DateTimeStyles]::None, [ref]$d)) { return $d.Date }
  }
  throw "Can't read the date '$s' - use yyyy-MM-dd, e.g. 2026-11-09"
}

# '1pm', '1:00 PM', '13:00', '11:30 AM ET' -> '01:00 PM' (the feed's format). 'any' -> $null
function ConvertTo-CloseKey([string]$s) {
  if (-not $s -or $s.Trim() -match '^(any|all|\*)$') { return $null }
  $t = ($s.Trim().ToUpper() -replace '\s*ET$', '' -replace '\.', '')
  foreach ($f in 'hh:mm tt', 'h:mm tt', 'hh:mmtt', 'h:mmtt', 'HH:mm', 'H:mm', 'htt', 'h tt') {
    $d = [datetime]::MinValue
    if ([datetime]::TryParseExact($t, $f, $Inv, [Globalization.DateTimeStyles]::AllowWhiteSpaces, [ref]$d)) {
      return $d.ToString('hh:mm tt', $Inv)
    }
  }
  throw "Can't read -CloseTime '$s' - try '01:00 PM', '11:30 AM', '1pm', '13:00' or 'any'"
}

# One-line status that rewrites itself in place; Write-Line starts a fresh line.
$script:statusOn = $false
function Write-Status([string]$t) {
  $w = 79
  try { $w = [Math]::Max(40, $Host.UI.RawUI.WindowSize.Width - 1) } catch {}
  if ($t.Length -gt $w) { $t = $t.Substring(0, $w) }
  Write-Host -NoNewline ("`r" + $t.PadRight($w))
  $script:statusOn = $true
}
function Write-Line([string]$t = '', [string]$Color = 'Gray') {
  if ($script:statusOn) { Write-Host ''; $script:statusOn = $false }
  Write-Host $t -ForegroundColor $Color
}

function Set-Title([string]$t) { try { $Host.UI.RawUI.WindowTitle = $t } catch {} }

function Invoke-Sound {
  if ($NoSound) { return }
  try { [Console]::Beep(880, 220); [Console]::Beep(1175, 220); [Console]::Beep(1568, 450) } catch {}
}

# ---- page state (data/state.json, read by index.html) ----------------------------

$script:State = [ordered]@{
  heartbeat = $null
  watching  = $null
  phase     = 'starting'       # starting | countdown | polling | found | none | gaveup | error | demo | replay | done
  message   = 'Starting...'
  session   = $null            # the auction being waited for
  poll      = $null            # last poll while polling
  results   = New-Object System.Collections.ArrayList   # newest first
}

function Save-State {
  if (-not $UsePage) { return }
  $script:State.heartbeat = [DateTime]::UtcNow.ToString('o', $Inv)
  $json = $script:State | ConvertTo-Json -Depth 8
  $tmp = "$StatePath.tmp"
  for ($i = 0; $i -lt 10; $i++) {
    try {
      [IO.File]::WriteAllText($tmp, $json, $Utf8NoBom)
      Move-Item -Force -Path $tmp -Destination $StatePath
      return
    } catch { Start-Sleep -Milliseconds 25 }
  }
}

function Set-Phase([string]$phase, [string]$msg) {
  $script:State.phase = $phase
  $script:State.message = $msg
  Save-State
}

function New-SessionRecord($s) {
  [ordered]@{
    date         = $s.Date.ToString('yyyy-MM-dd', $Inv)
    closeUtc     = ConvertTo-UtcIso $s.CloseEt
    fastStartUtc = ConvertTo-UtcIso ($s.CloseEt.AddSeconds(-$LeadSeconds))
    targets      = @($s.Targets | ForEach-Object { [ordered]@{ desc = $_.Desc; cusip = $_.Cusip; offering = (Format-Money $_.Offering) } })
  }
}

function Add-ResultRecord($rec, [switch]$Append) {
  $list = $script:State.results
  for ($i = $list.Count - 1; $i -ge 0; $i--) { if ($list[$i].id -eq $rec.id) { $list.RemoveAt($i) } }
  if ($Append) { [void]$list.Add($rec) } else { $list.Insert(0, $rec) }
  while ($list.Count -gt 20) { $list.RemoveAt($list.Count - 1) }
}

# Serves the page (this folder) and /data/ (the data folder) on localhost from a
# background runspace, so it lives in this same window and dies with it.
function Start-Page {
  $listener = New-Object System.Net.HttpListener
  $listener.Prefixes.Add("http://localhost:$Port/")
  try { $listener.Start() } catch {
    Write-Line "WARNING: can't serve the page on port $Port ($($_.Exception.Message))." Yellow
    Write-Line "         Is another auction watcher already running? Close it, or re-run with -Port 8846." Yellow
    return $null
  }
  $rs = [runspacefactory]::CreateRunspace()
  $rs.Open()
  $rs.SessionStateProxy.SetVariable('L', $listener)
  $rs.SessionStateProxy.SetVariable('ROOT', $scriptDir)
  $rs.SessionStateProxy.SetVariable('DATA', $DataDir)
  $ps = [powershell]::Create()
  $ps.Runspace = $rs
  [void]$ps.AddScript({
    $mime = @{ '.html' = 'text/html; charset=utf-8'; '.css' = 'text/css; charset=utf-8'; '.js' = 'application/javascript; charset=utf-8'
               '.json' = 'application/json; charset=utf-8'; '.pdf' = 'application/pdf'; '.svg' = 'image/svg+xml'; '.ico' = 'image/x-icon' }
    $rootFull = [IO.Path]::GetFullPath($ROOT).TrimEnd('\') + '\'
    $dataFull = [IO.Path]::GetFullPath($DATA).TrimEnd('\') + '\'
    while ($L.IsListening) {
      $res = $null
      try {
        $ctx = $L.GetContext()
        $res = $ctx.Response
        $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath)
        if ($rel -eq '/' -or -not $rel) { $rel = '/index.html' }
        if ($rel.StartsWith('/data/')) { $base = $dataFull; $rel = $rel.Substring(6) } else { $base = $rootFull; $rel = $rel.TrimStart('/') }
        $full = [IO.Path]::GetFullPath([IO.Path]::Combine($base, ($rel -replace '/', '\')))
        $res.Headers.Add('Cache-Control', 'no-store, max-age=0')
        if ($full.StartsWith($base, [StringComparison]::OrdinalIgnoreCase) -and [IO.File]::Exists($full)) {
          $ext = [IO.Path]::GetExtension($full).ToLower()
          $res.ContentType = if ($mime.ContainsKey($ext)) { $mime[$ext] } else { 'application/octet-stream' }
          # share read/write/delete so the watcher can replace state.json while it is being served
          $fs = New-Object IO.FileStream($full, [IO.FileMode]::Open, [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
          try { $res.ContentLength64 = $fs.Length; $fs.CopyTo($res.OutputStream) } finally { $fs.Dispose() }
        } else {
          $res.StatusCode = 404
          $b = [Text.Encoding]::UTF8.GetBytes('404')
          $res.OutputStream.Write($b, 0, $b.Length)
        }
        $res.OutputStream.Close()
      } catch {
        if ($res) { try { $res.Abort() } catch {} }
      }
    }
  })
  [void]$ps.BeginInvoke()
  return "http://localhost:$Port/"
}

# Keeps the page served (with a heartbeat) after the watching itself is finished.
function Wait-Forever([string]$msg) {
  if (-not $pageUrl) { return }
  Set-Phase 'done' $msg
  Write-Line "$msg The page stays up at $pageUrl - Ctrl+C (or close this window) to stop." Cyan
  while ($true) { Start-Sleep -Seconds 5; Save-State }
}

# ---- HTTP ------------------------------------------------------------------------

function New-Client {
  $wc = New-Object Net.WebClient
  $wc.Headers.Add('User-Agent', $UA)
  $wc.Headers.Add('Cache-Control', 'no-cache')
  $wc.Encoding = [Text.Encoding]::UTF8
  return $wc
}

function Get-Text([string]$url) {
  $wc = New-Client
  try { return $wc.DownloadString($url) } finally { $wc.Dispose() }
}

function Save-Url([string]$url, [string]$path) {
  $wc = New-Client
  try { $wc.DownloadFile($url + '?_=' + [DateTime]::UtcNow.Ticks, $path) } finally { $wc.Dispose() }
}

# HEAD request with a cache-buster. Returns the HTTP status (404 = not posted yet), 0 = network error.
function Get-HttpStatus([string]$url) {
  $resp = $null
  try {
    $req = [Net.HttpWebRequest]::Create($url + '?_=' + [DateTime]::UtcNow.Ticks)
    $req.Method = 'HEAD'
    $req.UserAgent = $UA
    $req.Timeout = 8000
    $req.Headers.Add('Cache-Control', 'no-cache')
    $resp = $req.GetResponse()
    return [int]$resp.StatusCode
  } catch {
    $e = $_.Exception
    while ($e -and -not ($e -is [Net.WebException])) { $e = $e.InnerException }
    if ($e -and $e.Response) { $code = [int]$e.Response.StatusCode; $e.Response.Close(); return $code }
    return 0
  } finally {
    if ($resp) { $resp.Close() }
  }
}

function Get-ResultPdfUrl([string]$file, [datetime]$day) { "$Base/instit/annceresult/press/preanre/$($day.Year)/$file" }

# ---- schedule (TreasuryDirect data feed) -----------------------------------------

function ConvertTo-Auction($r) {
  $day = [datetime]::ParseExact(([string]$r.competitiveAuctionCloseDate).Substring(0, 10), 'yyyy-MM-dd', $Inv)
  $time = [string]$r.competitiveAuctionCloseTime
  $close = $day.AddHours(13)
  $t = [datetime]::MinValue
  if ([datetime]::TryParseExact($time, 'hh:mm tt', $Inv, [Globalization.DateTimeStyles]::None, [ref]$t)) { $close = $day.Add($t.TimeOfDay) }
  $desc = [string]$r.securityDescription
  if (-not $desc) { $desc = "$($r.securityTerm) $($r.type)" }
  if ($r.reopening -eq 'Yes' -and $r.type -ne 'Bill' -and $r.type -ne 'CMB') { $desc += ' (reopening)' }
  [pscustomobject]@{
    Cusip     = [string]$r.cusip
    Desc      = $desc
    Date      = $day
    Time      = $time
    CloseEt   = $close
    ResultPdf = [string]$r.treasuryAuctionResultsPressReleaseFileName
    Offering  = $r.offeringAmount
  }
}

function Get-Auctions([int]$PastDays = 0) {
  $url = "$Base/TA_WS/securities/announced?format=json&pagesize=60"
  if ($PastDays -gt 0) { $url = "$Base/TA_WS/securities/auctioned?format=json&days=$PastDays" }
  $raw = (Get-Text $url) | ConvertFrom-Json
  foreach ($r in $raw) {
    if ($r.competitiveAuctionCloseDate) { ConvertTo-Auction $r }
  }
}

function Select-Session($all, $doneKeys) {
  $now = Get-NowEt
  $cands = @($all | Where-Object {
      -not $_.ResultPdf -and
      ($null -eq $CloseKey -or $_.Time -eq $CloseKey) -and
      ($null -eq $DateFilter -or $_.Date -eq $DateFilter) -and
      $_.CloseEt.AddMinutes($GiveUpMinutes) -gt $now -and
      -not $doneKeys.ContainsKey($_.CloseEt.ToString('yyyyMMddHHmm'))
    } | Sort-Object CloseEt)
  if ($cands.Count -eq 0) { return $null }
  $first = $cands[0]
  [pscustomobject]@{
    Key     = $first.CloseEt.ToString('yyyyMMddHHmm')
    Date    = $first.Date
    CloseEt = $first.CloseEt
    Targets = @($cands | Where-Object { $_.CloseEt -eq $first.CloseEt })
  }
}

# ---- identifying + showing a results PDF -----------------------------------------

function Get-Pdftotext {
  $c = Get-Command pdftotext -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  foreach ($p in @(
      'C:\Program Files\Git\mingw64\bin\pdftotext.exe',
      'C:\Program Files\Git\usr\bin\pdftotext.exe',
      'C:\Program Files (x86)\Git\mingw64\bin\pdftotext.exe')) {
    if (Test-Path $p) { return $p }
  }
  return $null
}
$Pdftotext = Get-Pdftotext

# Which of the expected CUSIPs is this results PDF for?
# Returns the CUSIP, 'other' (readable but none of ours), or $null (couldn't tell).
function Get-ResultCusip([string]$pdf, [string]$file, [string[]]$expected) {
  if ($Pdftotext) {
    $txt = "$pdf.txt"
    try { & $Pdftotext -q $pdf $txt 2>$null } catch {}
    if (Test-Path $txt) {
      # the PDF draws dot leaders through the text ("9...1..2..8..2..C..RV5"), so compare letters+digits only
      $flat = ((Get-Content -Path $txt -Raw) -replace '[^A-Za-z0-9]', '').ToUpper()
      Remove-Item $txt -ErrorAction SilentlyContinue
      if ($flat.Length -gt 200) {
        foreach ($c in $expected) { if ($c -and $flat.Contains($c.ToUpper())) { return $c } }
        return 'other'
      }
    }
  }
  try {
    [xml]$x = Get-Text ("$Base/xml/" + [IO.Path]::ChangeExtension($file, '.xml'))
    $n = $x.SelectSingleNode('//CUSIP')
    if ($n -and $n.InnerText) { return $n.InnerText.Trim() }
  } catch {}
  return $null
}

# Headline numbers from the results XML (posted alongside the PDF). $null if not up yet.
function Get-Summary([string]$file, [int]$Tries = 5) {
  $x = $null
  $xmlUrl = "$Base/xml/" + [IO.Path]::ChangeExtension($file, '.xml')
  for ($i = 0; $i -lt $Tries -and -not $x; $i++) {
    try { [xml]$x = Get-Text ($xmlUrl + '?_=' + [DateTime]::UtcNow.Ticks) } catch { if ($i -lt $Tries - 1) { Start-Sleep -Seconds 2 } }
  }
  if (-not $x) { return $null }

  function V([string]$name) { $n = $x.SelectSingleNode("//$name"); if ($n) { return $n.InnerText.Trim() }; return '' }
  function N([string]$name) { $v = 0.0; [void][double]::TryParse((V $name), [Globalization.NumberStyles]::Any, $Inv, [ref]$v); return $v }

  $label = 'High yield'; $hi = V 'HighYield'; $at = V 'AllottedAtHighYieldPercentage'; $md = V 'MedianYield'; $lo = V 'LowYield'
  if (-not $hi -and (V 'HighRate')) {
    $label = 'High rate'; $hi = V 'HighRate'; $at = V 'AllottedAtHighRatePercentage'; $md = V 'MedianRate'; $lo = V 'LowRate'
  }
  if (-not $hi -and (V 'HighDiscountMargin')) {
    $label = 'High margin'; $hi = V 'HighDiscountMargin'; $at = V 'AllottedAtHighDiscountMarginPercentage'; $md = V 'MedianDiscountMargin'; $lo = V 'LowDiscountMargin'
  }
  $pd = N 'PrimaryDealersCompetitiveParAwarded'
  $di = N 'DirectBiddersCompetitiveParAwarded'
  $ii = N 'IndirectBiddersCompetitiveParAwarded'
  $tot = $pd + $di + $ii
  $pct = { param($v) if ($tot -gt 0) { (100 * $v / $tot).ToString('0.0', $Inv) } else { '' } }

  [ordered]@{
    label      = $label
    high       = $hi
    allotted   = $at
    median     = $md
    low        = $lo
    investRate = V 'InvestmentRate'
    btc        = V 'BidToCoverRatio'
    indirect   = & $pct $ii
    direct     = & $pct $di
    dealers    = & $pct $pd
    offering   = Format-Money (V 'OfferingAmount')
  }
}

function Write-Summary($m) {
  Write-Line ('  {0,-13} {1} %   (allotted at high {2} %)' -f $m.label, $m.high, $m.allotted) Green
  if ($m.median -or $m.low) { Write-Line ('  {0,-13} {1} / {2}' -f 'Median / low', $m.median, $m.low) }
  if ($m.investRate) { Write-Line ('  {0,-13} {1} %' -f 'Invest. rate', $m.investRate) }
  Write-Line ('  {0,-13} {1}' -f 'Bid-to-cover', $m.btc) Green
  if ($m.indirect) {
    Write-Line ('  {0,-13} indirect {1} %   direct {2} %   dealers {3} %' -f 'Awarded', $m.indirect, $m.direct, $m.dealers) Green
  }
}

function Get-FinalPath($target, [string]$file) {
  $safe = ($target.Desc -replace '[^A-Za-z0-9\-]+', '-').Trim('-')
  Join-Path $DataDir ('{0}_{1}.pdf' -f [IO.Path]::GetFileNameWithoutExtension($file), $safe)
}

function New-ResultRecord($target, [string]$file, [string]$localPdf, $detectedEt, $closeEt, [bool]$isNew) {
  [ordered]@{
    id          = [IO.Path]::GetFileNameWithoutExtension($file)
    desc        = $target.Desc
    cusip       = $target.Cusip
    date        = $target.Date.ToString('yyyy-MM-dd', $Inv)
    closeUtc    = $(if ($closeEt) { ConvertTo-UtcIso $closeEt } else { $null })
    detectedUtc = $(if ($detectedEt) { ConvertTo-UtcIso $detectedEt } else { $null })
    isNew       = $isNew
    pdf         = 'data/' + [Uri]::EscapeDataString([IO.Path]::GetFileName($localPdf))
    url         = Get-ResultPdfUrl $file $target.Date
    summary     = $null
  }
}

# A drop: put it on the page first (fastest), then print + fetch the numbers.
function Open-Result($target, [string]$file, [string]$tmpPath, [datetime]$detectedEt, $closeEt) {
  $final = Get-FinalPath $target $file
  Move-Item -Force -Path $tmpPath -Destination $final
  $rec = New-ResultRecord $target $file $final $detectedEt $closeEt $true
  Add-ResultRecord $rec
  $script:State.phase = 'found'
  $script:State.message = "$($target.Desc) results are out"
  Save-State

  if ($OpenExternal) {
    try { Start-Process -FilePath $final } catch { Write-Line "  couldn't open the PDF automatically: $($_.Exception.Message)" Yellow }
  }

  Write-Line ''
  Write-Line ('*** RESULTS OUT:  {0}   CUSIP {1} ***' -f $target.Desc, $target.Cusip) Green
  $when = '  Got it   {0}  /  {1}' -f (Format-Et $detectedEt), (Format-Local $detectedEt)
  if ($closeEt) { $when += ('   ({0} after the close)' -f (Format-Span ($detectedEt - $closeEt))) }
  Write-Line $when
  Write-Line "  Saved    $final"
  if ($pageUrl) { Write-Line "  Page     $pageUrl" }
  Write-Line "  Online   $(Get-ResultPdfUrl $file $target.Date)" DarkGray
  if (-not $UsePage) { Invoke-Sound }

  $sum = Get-Summary $file
  if ($sum) {
    $rec.summary = $sum
    Save-State
    Write-Summary $sum
    Set-Title ('RESULTS OUT - {0} {1}% btc {2}' -f $target.Desc, $sum.high, $sum.btc)
  } else {
    Write-Line '  (the results XML is not posted yet - numbers are in the PDF)' DarkGray
    Set-Title "RESULTS OUT - $($target.Desc)"
  }
  Write-Line ''
}

# The page starts out showing the most recent published result, labelled PREVIOUS.
function Add-PreviousResult($all) {
  $pick = $all | Where-Object { $_.ResultPdf -and ($null -eq $CloseKey -or $_.Time -eq $CloseKey) } |
    Sort-Object CloseEt -Descending | Select-Object -First 1
  if (-not $pick) { return }
  $final = Get-FinalPath $pick $pick.ResultPdf
  if (-not (Test-Path $final)) {
    $tmp = "$final.part"
    try { Save-Url (Get-ResultPdfUrl $pick.ResultPdf $pick.Date) $tmp; Move-Item -Force $tmp $final }
    catch { Remove-Item $tmp -ErrorAction SilentlyContinue; return }
  }
  $rec = New-ResultRecord $pick $pick.ResultPdf $final $null $pick.CloseEt $false
  $rec.summary = Get-Summary $pick.ResultPdf -Tries 1
  Add-ResultRecord $rec -Append
  Save-State
}

# ---- watching one auction session -----------------------------------------------

function Watch-Session($s, $all, [switch]$IsReplay) {
  $day      = $s.Date
  $ymd      = $day.ToString('yyyyMMdd')
  $sameDay  = @($all | Where-Object { $_.Date -eq $day })
  $kMax     = [Math]::Max(4, $sameDay.Count + 2)
  $expected = @($sameDay | ForEach-Object { $_.Cusip }) + @($s.Targets | ForEach-Object { $_.Cusip }) | Select-Object -Unique

  $pending = @{}
  foreach ($t in $s.Targets) { $pending[$t.Cusip] = $t }

  # results already listed in the feed for this date (e.g. the 11:30 bills) - no need to fetch those
  $known = @{}
  if (-not $IsReplay) { foreach ($a in $sameDay) { if ($a.ResultPdf) { $known[$a.ResultPdf] = $a.Cusip } } }
  $seen404 = @{}

  $giveUp    = $s.CloseEt.AddMinutes($GiveUpMinutes)
  $fastUntil = $s.CloseEt.AddMinutes($FastMinutes)
  if ($IsReplay) { $giveUp = (Get-NowEt).AddMinutes(3); $fastUntil = $giveUp }
  $nextApi = (Get-NowEt).AddSeconds(15)
  $poll = 0
  $names = ($s.Targets | ForEach-Object { $_.Desc }) -join ', '
  Set-Title "Auction watch - polling for $names"
  Write-Line ("FAST POLLING  R_{0}_<n>.pdf every {1} s  -  waiting for {2}" -f $ymd, $IntervalSeconds, $names) Cyan
  $script:State.session = New-SessionRecord $s
  $script:State.poll = $null
  Set-Phase 'polling' "Polling for $names"

  while ($pending.Count -gt 0) {
    if ((Get-NowEt) -gt $giveUp) {
      $miss = ($pending.Values | ForEach-Object { $_.Desc }) -join ', '
      Write-Line ("Gave up {0} min after the close - no results PDF seen for: {1}" -f $GiveUpMinutes, $miss) Yellow
      Set-Phase 'gaveup' "Gave up $GiveUpMinutes min after the close - no results PDF seen for $miss"
      return
    }
    $poll++
    $lastCode = $null; $lastFile = $null
    $misses = 0

    for ($k = 1; $k -le $kMax -and $pending.Count -gt 0; $k++) {
      $f = "R_${ymd}_$k.pdf"
      if ($known.ContainsKey($f)) {
        $c = $known[$f]
        if ($pending.ContainsKey($c)) {
          # the feed already lists this result (we started late) - fetch it directly
          $tmp = Join-Path $DataDir "_$f"
          try { Save-Url (Get-ResultPdfUrl $f $day) $tmp } catch { continue }
          Open-Result $pending[$c] $f $tmp (Get-NowEt) $s.CloseEt
          $pending.Remove($c)
        }
        continue
      }

      $url = Get-ResultPdfUrl $f $day
      $code = Get-HttpStatus $url
      $lastCode = $code; $lastFile = $f
      if ($code -ne 200) {
        if ($code -eq 404) { $seen404[$f] = $true }
        $misses++
        if ($misses -ge 2) { break }     # files are numbered in release order; two misses in a row = nothing further yet
        continue
      }

      # a results PDF we haven't looked at yet
      $detected = Get-NowEt
      $tmp = Join-Path $DataDir "_$f"
      try { Save-Url $url $tmp } catch { Write-Line "  $f is up but the download failed ($($_.Exception.Message)) - retrying" Yellow; continue }
      $c = Get-ResultCusip $tmp $f $expected
      if (-not $c) {
        # couldn't read it: if it appeared while we watched (or after the close) it's ours
        if ($seen404.ContainsKey($f) -or $detected -ge $s.CloseEt) { $c = @($pending.Keys)[0] } else { $c = 'other' }
      }
      $known[$f] = $c
      if ($pending.ContainsKey($c)) {
        Open-Result $pending[$c] $f $tmp $detected $s.CloseEt
        $pending.Remove($c)
      } else {
        $o = $sameDay | Where-Object { $_.Cusip -eq $c } | Select-Object -First 1
        $what = if ($o) { "$($o.Desc) ($($o.Time))" } else { 'a different auction' }
        Write-Line "  $f is $what - not the one we're waiting for, ignoring" DarkGray
        Remove-Item $tmp -ErrorAction SilentlyContinue
      }
    }
    if ($pending.Count -eq 0) { break }

    # backstop: the data feed (updates 1-2 min after the PDF, but catches any naming surprise)
    if ((Get-NowEt) -ge $nextApi) {
      $nextApi = (Get-NowEt).AddSeconds(15)
      try {
        foreach ($a in @(Get-Auctions -PastDays 3)) {
          if ($a.ResultPdf -and $pending.ContainsKey($a.Cusip) -and -not $known.ContainsKey($a.ResultPdf)) {
            $tmp = Join-Path $DataDir "_$($a.ResultPdf)"
            Save-Url (Get-ResultPdfUrl $a.ResultPdf $a.Date) $tmp
            $known[$a.ResultPdf] = $a.Cusip
            Open-Result $pending[$a.Cusip] $a.ResultPdf $tmp (Get-NowEt) $s.CloseEt
            $pending.Remove($a.Cusip)
          }
        }
      } catch {}
      if ($pending.Count -eq 0) { break }
    }

    $now = Get-NowEt
    $pollState = if ($lastCode -eq 404) { 'not posted yet' } elseif ($lastCode -eq 0) { 'network error' } elseif ($lastCode) { "HTTP $lastCode" } else { 'waiting' }
    $rel = if ($now -lt $s.CloseEt) { 'close in ' + (Format-Span ($s.CloseEt - $now)) } else { '+' + (Format-Span ($now - $s.CloseEt)) + ' after close' }
    Write-Status ('  {0}  poll #{1}  {2}: {3}   ({4})' -f (Format-Et $now), $poll, $lastFile, $pollState, $rel)
    $script:State.poll = [ordered]@{ count = $poll; file = $lastFile; status = $pollState; atUtc = [DateTime]::UtcNow.ToString('o', $Inv) }
    Set-Phase 'polling' ('Polling for ' + (($pending.Values | ForEach-Object { $_.Desc }) -join ', '))

    $sleep = if ($now -lt $fastUntil) { $IntervalSeconds } else { 10 }
    Start-Sleep -Seconds $sleep
  }
}

# ---- main ------------------------------------------------------------------------

$CloseKey   = ConvertTo-CloseKey $CloseTime
$DateFilter = if ($Date) { ConvertTo-Day $Date } else { $null }
$label      = if ($CloseKey) { "$($CloseKey.TrimStart('0')) ET" } else { 'any-time' }

$script:State.watching = $label
if ($UsePage) {
  Save-State
  $pageUrl = Start-Page
  if ($pageUrl -and -not $NoBrowser) { try { Start-Process $pageUrl } catch {} }
}

if ($Demo) {
  Write-Line "Demo: fetching the most recent published $label auction result..." Cyan
  $pick = @(Get-Auctions) | Where-Object { $_.ResultPdf -and ($null -eq $CloseKey -or $_.Time -eq $CloseKey) } |
    Sort-Object CloseEt -Descending | Select-Object -First 1
  if (-not $pick) { throw "No published $label result in the current feed." }
  if ($pageUrl) {
    Set-Phase 'demo' "Demo - the latest published $label result drops onto this page in 5 seconds"
    Write-Line "  Page: $pageUrl  - the result drops onto it in 5 s"
    Start-Sleep -Seconds 5
  }
  $tmp = Join-Path $DataDir "_$($pick.ResultPdf)"
  Save-Url (Get-ResultPdfUrl $pick.ResultPdf $pick.Date) $tmp
  Open-Result $pick $pick.ResultPdf $tmp (Get-NowEt) $null
  Wait-Forever 'Demo finished.'
  return
}

if ($Replay) {
  $rd = ConvertTo-Day $Replay
  $days = [int][Math]::Ceiling(((Get-NowEt).Date - $rd).TotalDays) + 2
  $all = @(Get-Auctions -PastDays $days)
  $targets = @($all | Where-Object { $_.Date -eq $rd -and ($null -eq $CloseKey -or $_.Time -eq $CloseKey) } | Sort-Object CloseEt)
  if ($targets.Count -eq 0) { throw "No $label auction on $($rd.ToString('yyyy-MM-dd')) in TreasuryDirect's feed." }
  $first = $targets[0]
  $s = [pscustomobject]@{
    Key = 'replay'; Date = $rd; CloseEt = $first.CloseEt
    Targets = @($targets | Where-Object { $_.CloseEt -eq $first.CloseEt })
  }
  Write-Line ("Replay of {0}: pretending we don't know any result file names, scanning like a live drop..." -f $rd.ToString('ddd dd MMM yyyy', $Inv)) Cyan
  if ($pageUrl) {
    $script:State.session = New-SessionRecord $s
    Set-Phase 'replay' ('Replay of ' + $rd.ToString('ddd dd MMM yyyy', $Inv) + ' - starting in 4 seconds')
    Start-Sleep -Seconds 4
  }
  Watch-Session $s $all -IsReplay
  Wait-Forever 'Replay finished.'
  return
}

Write-Line ''
Write-Line 'Treasury auction-results watcher' Cyan
Write-Line "  Watching   : $label auctions$(if ($DateFilter) { ' on ' + $DateFilter.ToString('yyyy-MM-dd') })"
if ($pageUrl) { Write-Line "  Page       : $pageUrl   <-- keep this open; the PDF appears on it" Green }
Write-Line "  Saves to   : $DataDir"
if ($OpenExternal) { Write-Line '  PDF viewer : opens each new result too' }
if (-not $Pdftotext) { Write-Line '  (pdftotext not found - will identify PDFs from the XML instead)' DarkGray }
Write-Line '  Leave this window open. Ctrl+C to stop.'

$doneKeys = @{}
$shown = $null
$prevLoaded = $false
while ($true) {
  try { $all = @(Get-Auctions) }
  catch {
    $msg = "Couldn't read the TreasuryDirect schedule ($($_.Exception.Message)) - retrying in 60 s"
    Write-Line ("  {0}  {1}" -f (Format-Et (Get-NowEt)), $msg) Yellow
    Set-Phase 'error' $msg
    Start-Sleep -Seconds 60
    continue
  }
  if ($UsePage -and -not $prevLoaded) { try { Add-PreviousResult $all } catch {}; $prevLoaded = $true }

  $s = Select-Session $all $doneKeys
  if (-not $s) {
    if ($DateFilter) { Write-Line "No unpublished $label auction on $($DateFilter.ToString('yyyy-MM-dd')) - nothing to watch." Yellow; break }
    if ($shown -ne 'none') {
      Write-Line ''
      Write-Line "No upcoming $label auction is announced yet. Re-checking the schedule every 15 minutes." Yellow
      Set-Title 'Auction watch - no auction announced yet'
      $script:State.session = $null
      $shown = 'none'
    }
    Set-Phase 'none' "No upcoming $label auction announced yet - re-checking the schedule every 15 min"
    $until = (Get-NowEt).AddMinutes(15)
    $tick = 0
    while ((Get-NowEt) -lt $until) {
      Write-Status ('  {0}  next schedule check in {1}' -f (Format-Et (Get-NowEt)), (Format-Span ($until - (Get-NowEt))))
      Start-Sleep -Seconds 1
      if ((++$tick % 5) -eq 0) { Save-State }
    }
    continue
  }

  $startAt = $s.CloseEt.AddSeconds(-$LeadSeconds)
  $names = ($s.Targets | ForEach-Object { $_.Desc }) -join ', '
  if ($shown -ne $s.Key) {
    Write-Line ''
    Write-Line ('=' * 70) DarkCyan
    Write-Line (' NEXT DROP   {0}   auction closes {1} ET  ({2} your time)' -f $s.CloseEt.ToString('ddd dd MMM yyyy', $Inv), $s.CloseEt.ToString('h:mm tt', $Inv), (ConvertTo-LocalTime $s.CloseEt).ToString('HH:mm', $Inv)) White
    foreach ($t in $s.Targets) { Write-Line ('   {0,-26} CUSIP {1}   {2}' -f $t.Desc, $t.Cusip, (Format-Money $t.Offering)) White }
    Write-Line (' Fast polling starts {0}  ({1})' -f (Format-Et $startAt), (Format-Local $startAt)) DarkCyan
    Write-Line ('=' * 70) DarkCyan
    Set-Title ('Auction watch - next: {0}  {1} ET' -f $names, $s.CloseEt.ToString('ddd h:mm tt', $Inv))
    $script:State.session = New-SessionRecord $s
    $shown = $s.Key
  }

  if ((Get-NowEt) -lt $startAt) {
    Set-Phase 'countdown' "Next: $names"
    # count down; re-read the schedule every 30 min in case it changes
    $until = (Get-NowEt).AddMinutes(30)
    if ($startAt -lt $until) { $until = $startAt }
    $tick = 0
    while ((Get-NowEt) -lt $until) {
      Write-Status ('  {0}   fast polling in {1}' -f (Format-Et (Get-NowEt)), (Format-Span ($startAt - (Get-NowEt))))
      Start-Sleep -Seconds 1
      if ((++$tick % 5) -eq 0) { Save-State }
    }
    if ((Get-NowEt) -lt $startAt) { continue }
    try { $all = @(Get-Auctions) } catch {}
  }

  Watch-Session $s $all
  $doneKeys[$s.Key] = $true
  if ($Once -or $DateFilter) { break }
  Write-Line 'Looking for the next one...' DarkCyan
}
Wait-Forever 'Finished watching.'

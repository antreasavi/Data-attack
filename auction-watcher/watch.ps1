<#
  auction-watcher / watch.ps1

  Waits for the next Treasury auction-results PDF on TreasuryDirect
  (Auctions -> Announcements, Data & Results), grabs it the moment it is posted,
  and opens it. By default it watches the 1:00 PM ET note/bond auctions.

  How it works
    1. Reads the auction schedule from TreasuryDirect's own data feed
       (the same feed the "Announcements, Data & Results" page is built from)
       to find the next 1:00 PM auction and its CUSIP.
    2. Sleeps until 1 minute before the close.
    3. Polls the results file names directly  .../preanre/<yyyy>/R_<yyyymmdd>_<n>.pdf
       every 2 s. The PDF lands ~1:02 PM ET, 1-2 minutes BEFORE the website's
       table / data feed updates, so this is the fastest public source.
    4. When a new R_ file appears it downloads it, checks the CUSIP inside is
       the auction it is waiting for, opens it, beeps, and prints the headline
       numbers (high yield, bid-to-cover, indirect/direct/dealer takedown).
    5. Moves on to the next 1:00 PM auction (use -Once to stop instead).

  Examples
    powershell -ExecutionPolicy Bypass -File watch.ps1
    powershell -ExecutionPolicy Bypass -File watch.ps1 -CloseTime "11:30 AM"   # bill auctions
    powershell -ExecutionPolicy Bypass -File watch.ps1 -CloseTime any          # every auction
    powershell -ExecutionPolicy Bypass -File watch.ps1 -Date 2026-11-09 -Once
    powershell -ExecutionPolicy Bypass -File watch.ps1 -Demo                   # open latest result now
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
  [switch]$Once,                     # stop after one auction session
  [switch]$NoOpen,                   # download but don't open the PDF
  [switch]$NoSound,
  [switch]$Demo,                     # test: download + open the most recent published result now
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

# ---- small helpers -------------------------------------------------------------

function Get-NowEt { [TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $EtZone) }

function ConvertTo-LocalTime([datetime]$et) {
  [TimeZoneInfo]::ConvertTime([DateTime]::SpecifyKind($et, 'Unspecified'), $EtZone, [TimeZoneInfo]::Local)
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

# ---- identifying + opening a results PDF -----------------------------------------

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

function Show-Summary([string]$file) {
  $x = $null
  $xmlUrl = "$Base/xml/" + [IO.Path]::ChangeExtension($file, '.xml')
  for ($i = 0; $i -lt 5 -and -not $x; $i++) {
    try { [xml]$x = Get-Text ($xmlUrl + '?_=' + [DateTime]::UtcNow.Ticks) } catch { Start-Sleep -Seconds 2 }
  }
  if (-not $x) { Write-Line '  (the results XML is not posted yet - numbers are in the PDF)' DarkGray; return $null }

  function V([string]$name) { $n = $x.SelectSingleNode("//$name"); if ($n) { return $n.InnerText.Trim() }; return '' }
  function N([string]$name) { $v = 0.0; [void][double]::TryParse((V $name), [Globalization.NumberStyles]::Any, $Inv, [ref]$v); return $v }

  $label = 'High yield'; $hi = V 'HighYield'; $at = V 'AllottedAtHighYieldPercentage'; $md = V 'MedianYield'; $lo = V 'LowYield'
  if (-not $hi -and (V 'HighRate')) {
    $label = 'High rate'; $hi = V 'HighRate'; $at = V 'AllottedAtHighRatePercentage'; $md = V 'MedianRate'; $lo = V 'LowRate'
  }
  if (-not $hi -and (V 'HighDiscountMargin')) {
    $label = 'High margin'; $hi = V 'HighDiscountMargin'; $at = V 'AllottedAtHighDiscountMarginPercentage'; $md = V 'MedianDiscountMargin'; $lo = V 'LowDiscountMargin'
  }
  $btc = V 'BidToCoverRatio'
  $pd = N 'PrimaryDealersCompetitiveParAwarded'
  $di = N 'DirectBiddersCompetitiveParAwarded'
  $ii = N 'IndirectBiddersCompetitiveParAwarded'
  $tot = $pd + $di + $ii

  Write-Line ('  {0,-13} {1} %   (allotted at high {2} %)' -f $label, $hi, $at) Green
  if ($md -or $lo) { Write-Line ('  {0,-13} {1} / {2}' -f 'Median / low', $md, $lo) }
  if ((V 'InvestmentRate')) { Write-Line ('  {0,-13} {1} %' -f 'Invest. rate', (V 'InvestmentRate')) }
  Write-Line ('  {0,-13} {1}' -f 'Bid-to-cover', $btc) Green
  if ($tot -gt 0) {
    Write-Line ('  {0,-13} indirect {1:0.0} %   direct {2:0.0} %   dealers {3:0.0} %' -f 'Awarded', (100 * $ii / $tot), (100 * $di / $tot), (100 * $pd / $tot)) Green
  }
  return "$hi% btc $btc"
}

function Open-Result($target, [string]$file, [string]$tmpPath, [datetime]$detectedEt, $closeEt) {
  $safe = ($target.Desc -replace '[^A-Za-z0-9\-]+', '-').Trim('-')
  $final = Join-Path $DataDir ('{0}_{1}.pdf' -f [IO.Path]::GetFileNameWithoutExtension($file), $safe)
  Move-Item -Force -Path $tmpPath -Destination $final
  if (-not $NoOpen) {
    try { Start-Process -FilePath $final } catch { Write-Line "  couldn't open the PDF automatically: $($_.Exception.Message)" Yellow }
  }

  Write-Line ''
  Write-Line ('*** RESULTS OUT:  {0}   CUSIP {1} ***' -f $target.Desc, $target.Cusip) Green
  $when = '  Got it   {0}  /  {1}' -f (Format-Et $detectedEt), (Format-Local $detectedEt)
  if ($closeEt) { $when += ('   ({0} after the close)' -f (Format-Span ($detectedEt - $closeEt))) }
  Write-Line $when
  Write-Line "  Saved    $final"
  Write-Line "  Online   $(Get-ResultPdfUrl $file $target.Date)" DarkGray
  Invoke-Sound
  $headline = Show-Summary $file
  Set-Title ("RESULTS OUT - {0} {1}" -f $target.Desc, $headline)
  Write-Line ''
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

  while ($pending.Count -gt 0) {
    if ((Get-NowEt) -gt $giveUp) {
      Write-Line ("Gave up {0} min after the close - no results PDF seen for: {1}" -f $GiveUpMinutes, (($pending.Values | ForEach-Object { $_.Desc }) -join ', ')) Yellow
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
    $state = if ($lastCode -eq 404) { 'not posted yet' } elseif ($lastCode -eq 0) { 'network error' } elseif ($lastCode) { "HTTP $lastCode" } else { 'waiting' }
    $rel = if ($now -lt $s.CloseEt) { 'close in ' + (Format-Span ($s.CloseEt - $now)) } else { '+' + (Format-Span ($now - $s.CloseEt)) + ' after close' }
    Write-Status ('  {0}  poll #{1}  {2}: {3}   ({4})' -f (Format-Et $now), $poll, $lastFile, $state, $rel)

    $sleep = if ($now -lt $fastUntil) { $IntervalSeconds } else { 10 }
    Start-Sleep -Seconds $sleep
  }
}

# ---- main ------------------------------------------------------------------------

$CloseKey   = ConvertTo-CloseKey $CloseTime
$DateFilter = if ($Date) { ConvertTo-Day $Date } else { $null }
$label      = if ($CloseKey) { "$($CloseKey.TrimStart('0')) ET" } else { 'any-time' }

if ($Demo) {
  Write-Line "Demo: fetching the most recent published $label auction result..." Cyan
  $pick = @(Get-Auctions) | Where-Object { $_.ResultPdf -and ($null -eq $CloseKey -or $_.Time -eq $CloseKey) } |
    Sort-Object CloseEt -Descending | Select-Object -First 1
  if (-not $pick) { throw "No published $label result in the current feed." }
  $tmp = Join-Path $DataDir "_$($pick.ResultPdf)"
  Save-Url (Get-ResultPdfUrl $pick.ResultPdf $pick.Date) $tmp
  Open-Result $pick $pick.ResultPdf $tmp (Get-NowEt) $null
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
  Watch-Session $s $all -IsReplay
  return
}

Write-Line ''
Write-Line 'Treasury auction-results watcher' Cyan
Write-Line "  Watching   : $label auctions$(if ($DateFilter) { ' on ' + $DateFilter.ToString('yyyy-MM-dd') })"
Write-Line "  Saves to   : $DataDir"
Write-Line "  PDF reader : $(if ($NoOpen) { 'off (-NoOpen)' } else { 'opens automatically' })"
if (-not $Pdftotext) { Write-Line '  (pdftotext not found - will identify PDFs from the XML instead)' DarkGray }
Write-Line '  Leave this window open. Ctrl+C to stop.'

$doneKeys = @{}
$shown = $null
while ($true) {
  try { $all = @(Get-Auctions) }
  catch {
    Write-Line ("  {0}  couldn't read the TreasuryDirect schedule ({1}) - retrying in 60 s" -f (Format-Et (Get-NowEt)), $_.Exception.Message) Yellow
    Start-Sleep -Seconds 60
    continue
  }

  $s = Select-Session $all $doneKeys
  if (-not $s) {
    if ($DateFilter) { Write-Line "No unpublished $label auction on $($DateFilter.ToString('yyyy-MM-dd')) - nothing to watch." Yellow; break }
    if ($shown -ne 'none') {
      Write-Line ''
      Write-Line "No upcoming $label auction is announced yet. Re-checking the schedule every 15 minutes." Yellow
      Set-Title 'Auction watch - no auction announced yet'
      $shown = 'none'
    }
    $until = (Get-NowEt).AddMinutes(15)
    while ((Get-NowEt) -lt $until) { Write-Status ('  {0}  next schedule check in {1}' -f (Format-Et (Get-NowEt)), (Format-Span ($until - (Get-NowEt)))); Start-Sleep -Seconds 1 }
    continue
  }

  $startAt = $s.CloseEt.AddSeconds(-$LeadSeconds)
  if ($shown -ne $s.Key) {
    Write-Line ''
    Write-Line ('=' * 70) DarkCyan
    Write-Line (' NEXT DROP   {0}   auction closes {1} ET  ({2} your time)' -f $s.CloseEt.ToString('ddd dd MMM yyyy', $Inv), $s.CloseEt.ToString('h:mm tt', $Inv), (ConvertTo-LocalTime $s.CloseEt).ToString('HH:mm', $Inv)) White
    foreach ($t in $s.Targets) { Write-Line ('   {0,-26} CUSIP {1}   {2}' -f $t.Desc, $t.Cusip, (Format-Money $t.Offering)) White }
    Write-Line (' Fast polling starts {0}  ({1})' -f (Format-Et $startAt), (Format-Local $startAt)) DarkCyan
    Write-Line ('=' * 70) DarkCyan
    Set-Title ('Auction watch - next: {0}  {1} ET' -f (($s.Targets | ForEach-Object { $_.Desc }) -join ', '), $s.CloseEt.ToString('ddd h:mm tt', $Inv))
    $shown = $s.Key
  }

  if ((Get-NowEt) -lt $startAt) {
    # count down; re-read the schedule every 30 min in case it changes
    $until = (Get-NowEt).AddMinutes(30)
    if ($startAt -lt $until) { $until = $startAt }
    while ((Get-NowEt) -lt $until) {
      Write-Status ('  {0}   fast polling in {1}' -f (Format-Et (Get-NowEt)), (Format-Span ($startAt - (Get-NowEt))))
      Start-Sleep -Seconds 1
    }
    if ((Get-NowEt) -lt $startAt) { continue }
    try { $all = @(Get-Auctions) } catch {}
  }

  Watch-Session $s $all
  $doneKeys[$s.Key] = $true
  if ($Once -or $DateFilter) { break }
  Write-Line 'Looking for the next one...' DarkCyan
}

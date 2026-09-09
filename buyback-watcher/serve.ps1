<#
  buyback-watcher / serve.ps1
  Tiny static file server for this folder so the alert page can fetch data/state.json.
  Sends no-cache headers so the page always sees the latest state.
    powershell -ExecutionPolicy Bypass -File serve.ps1 -Port 8844
#>
param([int]$Port = 8844)

$root = $PSScriptRoot
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
try {
  $listener.Start()
} catch {
  Write-Host "Could not bind http://localhost:$Port/  -  $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Try a different port:  serve.ps1 -Port 8850" -ForegroundColor Yellow
  return
}
Write-Host "Serving $root" -ForegroundColor Cyan
Write-Host "  http://localhost:$Port/        (Ctrl+C to stop)" -ForegroundColor Cyan

$mime = @{
  '.html' = 'text/html; charset=utf-8'
  '.css'  = 'text/css; charset=utf-8'
  '.js'   = 'application/javascript; charset=utf-8'
  '.json' = 'application/json; charset=utf-8'
  '.pdf'  = 'application/pdf'
  '.svg'  = 'image/svg+xml'
  '.ico'  = 'image/x-icon'
  '.png'  = 'image/png'
}

try {
  while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    $req = $ctx.Request
    $res = $ctx.Response
    try {
      $rel = [Uri]::UnescapeDataString($req.Url.LocalPath)
      if ($rel -eq '/' -or [string]::IsNullOrWhiteSpace($rel)) { $rel = '/index.html' }
      $rel = $rel.TrimStart('/')
      $file = Join-Path $root ($rel -replace '/', '\')
      $full = [IO.Path]::GetFullPath($file)

      $res.Headers.Add('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
      $res.Headers.Add('Access-Control-Allow-Origin', '*')

      if ($full.StartsWith([IO.Path]::GetFullPath($root)) -and (Test-Path $full -PathType Leaf)) {
        $ext = [IO.Path]::GetExtension($full).ToLower()
        $res.ContentType = if ($mime.ContainsKey($ext)) { $mime[$ext] } else { 'application/octet-stream' }
        $bytes = [IO.File]::ReadAllBytes($full)
        $res.ContentLength64 = $bytes.Length
        $res.OutputStream.Write($bytes, 0, $bytes.Length)
      } else {
        $res.StatusCode = 404
        $b = [Text.Encoding]::UTF8.GetBytes("404 Not Found: $rel")
        $res.OutputStream.Write($b, 0, $b.Length)
      }
    } catch {
      try { $res.StatusCode = 500 } catch {}
    } finally {
      $res.OutputStream.Close()
    }
  }
} finally {
  $listener.Stop()
}

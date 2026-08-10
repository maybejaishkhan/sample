<#
.SYNOPSIS
Uploads raw scanner reports to a DefectDojo instance via its REST API.

.DESCRIPTION
For every known report file present under -RawDir this calls DefectDojo's API
v2 import-scan (or reimport-scan with -Mode reimport) so the results land in
DefectDojo. Product/engagement context is auto-created by DefectDojo from the
names passed here, so nothing needs to be set up in the UI beforehand.

Report file -> scan type mapping defaults to this pipeline's well-known file
names (kept in sync with pipelines/variables/security.yml) and can be
extended/overridden with -ScanTypes (comma-separated "FILE=SCAN_TYPE" pairs):

    trufflehog.json  -> Trufflehog Scan
    semgrep.json     -> Semgrep JSON Report
    msdo.sarif       -> SARIF
    zap.xml          -> ZAP Scan

Environment variables (secrets are read from the environment so they never
appear on the command line):

    DEFECTDOJO_URL               Base URL, e.g. https://dd.example.com (no trailing /)
    DEFECTDOJO_API_TOKEN         API v2 token, sent as `Authorization: Token <token>`
    DEFECTDOJO_SCM_URI           Optional source code management URI (e.g. repo URL)
    DEFECTDOJO_SCM_BRANCH        Optional branch name (e.g. main)

Requires curl (built into Windows 10 1803+ / Server 2019+; curl.exe is used
when available).

Exit codes:
    0 - every present report was imported (or none were present)
    1 - at least one import failed
    2 - configuration error (missing setting/directory/curl)
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RawDir,
    [ValidateSet('import', 'reimport')][string]$Mode = 'reimport',
    [Parameter(Mandatory = $true)][string]$Product,
    [string]$ProductType = '',
    [Parameter(Mandatory = $true)][string]$Engagement,
    [string]$ScanTypes = '',
    [switch]$Insecure
)

$ErrorActionPreference = 'Stop'

$url = $env:DEFECTDOJO_URL
$token = $env:DEFECTDOJO_API_TOKEN

if ([string]::IsNullOrWhiteSpace($url) -or [string]::IsNullOrWhiteSpace($token)) {
    Write-Host "ERROR: DEFECTDOJO_URL and DEFECTDOJO_API_TOKEN must be set." -ForegroundColor Red
    exit 2
}
if (-not (Test-Path -LiteralPath $RawDir -PathType Container)) {
    Write-Host "ERROR: raw reports directory '$RawDir' not found." -ForegroundColor Red
    exit 2
}

# Prefer curl.exe (Windows) and fall back to curl (Linux/macOS) for local runs.
$curl = (Get-Command curl.exe -ErrorAction SilentlyContinue).Source
if (-not $curl) { $curl = (Get-Command curl -ErrorAction SilentlyContinue).Source }
if (-not $curl) {
    Write-Host "ERROR: curl not found on this agent." -ForegroundColor Red
    exit 2
}

# Default report file -> DefectDojo scan type mapping. -ScanTypes overrides/adds
# entries (comma-separated "FILE=SCAN_TYPE" pairs).
$defaultScanTypes = [ordered]@{
    'trufflehog.json' = 'Trufflehog Scan'
    'semgrep.json'    = 'Semgrep JSON Report'
    'msdo.sarif'      = 'SARIF'
    'zap.xml'         = 'ZAP Scan'
}
$scanTypes = @{}
foreach ($pair in $ScanTypes -split ',') {
    $pair = $pair.Trim()
    if (-not $pair) { continue }
    $parts = $pair -split '=', 2
    if ($parts.Count -ne 2 -or [string]::IsNullOrWhiteSpace($parts[0])) {
        Write-Host "ERROR: invalid scan type mapping '$pair' (expected FILE=SCAN_TYPE)." -ForegroundColor Red
        exit 2
    }
    $scanTypes[$parts[0]] = $parts[1]
}
foreach ($key in $defaultScanTypes.Keys) {
    if (-not $scanTypes.ContainsKey($key)) { $scanTypes[$key] = $defaultScanTypes[$key] }
}

$endpoint = if ($Mode -eq 'import') { 'import-scan' } else { 'reimport-scan' }
$apiUrl = "$($url.TrimEnd('/'))/api/v2/$endpoint/"
$today = Get-Date -Format 'yyyy-MM-dd'

# When product/engagement names are given and the objects do not exist yet,
# DefectDojo auto-creates them (requires engagement_end, which we set to today).
$baseArgs = @('-s', '-S')
if ($Insecure) { $baseArgs += '-k' }
$baseArgs += @('-X', 'POST', $apiUrl, '-H', "Authorization: Token $token")

$imported = @()
$failed = @()
foreach ($file in ($scanTypes.Keys | Sort-Object)) {
    $path = Join-Path $RawDir $file
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Write-Host "skip: $file (report not present)"
        continue
    }
    $scanType = $scanTypes[$file]

    $form = @(
        "-F", "scan_date=$today",
        "-F", "engagement_end=$today",
        "-F", "minimum_severity=Info",
        "-F", "active=true",
        "-F", "verified=true",
        "-F", "close_old_findings=true",
        "-F", "deduplication_on_engagement=true",
        "-F", "product_name=$Product",
        "-F", "engagement_name=$Engagement",
        "-F", "scan_type=$scanType",
        "-F", "test_title=$scanType",
        "-F", "file=@$path"
    )
    if ($ProductType) { $form += @("-F", "product_type_name=$ProductType") }
    if ($env:DEFECTDOJO_SCM_URI) { $form += @("-F", "source_code_management_uri=$($env:DEFECTDOJO_SCM_URI)") }
    if ($env:DEFECTDOJO_SCM_BRANCH) { $form += @("-F", "source_code_management_branch=$($env:DEFECTDOJO_SCM_BRANCH)") }

    # -w appends the HTTP status on its own line; it is the last stdout line.
    $output = & $curl @baseArgs @form '-w' "`n%{http_code}" 2>$null
    $httpCode = ""
    if ($output) { $httpCode = ($output | Select-Object -Last 1).ToString().Trim() }

    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($httpCode)) {
        $failed += $file
        Write-Host "ERROR: $file -> $scanType (curl exit $LASTEXITCODE)" -ForegroundColor Red
        continue
    }

    $code = 0
    if (-not [int]::TryParse($httpCode, [ref]$code)) { $code = 0 }
    if ($code -ge 200 -and $code -lt 300) {
        $imported += $file
        Write-Host "ok: $file -> $scanType (HTTP $httpCode)"
    } else {
        $failed += $file
        Write-Host "ERROR: $file -> $scanType (HTTP $httpCode): $($output -join ' ')" -ForegroundColor Red
    }
}

Write-Host "imported $($imported.Count) report(s): $($imported -join ', ')"
if ($failed.Count -gt 0) {
    Write-Host "failed $($failed.Count) report(s): $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
exit 0

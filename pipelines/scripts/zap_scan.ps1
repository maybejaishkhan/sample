<#
.SYNOPSIS
    Runs an OWASP ZAP automated scan against a target URL.

.DESCRIPTION
    Uses the OWASP ZAP instance that is ALREADY INSTALLED on the deployment VM.
    This script never downloads or installs ZAP.

    Flow:
      1. Start ZAP in headless daemon mode
      2. Wait for the ZAP REST API
      3. Spider the target
      4. Run an active scan
      5. Export zap.json / zap.xml / zap.html into OutputDirectory
      6. Shut ZAP down

.PARAMETER TargetUrl
    URL to scan. Comes from the ZapTarget pipeline variable.

.PARAMETER OutputDirectory
    Folder where reports are written (reports/raw on the agent).

.PARAMETER ZapPath
    Fully qualified path to the pre-installed ZAP launcher (zap.bat on Windows).

.PARAMETER ApiHost / ApiPort
    Where the ZAP daemon listens for its REST API.

.PARAMETER TimeoutSeconds
    Overall timeout for spider + active scan. Partial results are still
    exported if the timeout is hit.

.PARAMETER JsonReportName / XmlReportName / HtmlReportName
    Report file names. Keep in sync with pipelines/variables/security.yml.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetUrl,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [string]$ZapPath = 'C:\Program Files\ZAP\Zed Attack Proxy\zap.bat',
    [string]$ApiHost = '127.0.0.1',
    [int]$ApiPort = 8090,
    [int]$TimeoutSeconds = 600,

    [string]$JsonReportName = 'zap.json',
    [string]$XmlReportName = 'zap.xml',
    [string]$HtmlReportName = 'zap.html'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $ZapPath)) {
    throw "OWASP ZAP not found at '$ZapPath'. Configure ZapPath in pipelines/variables/deployment.yml."
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$apiBase = "http://${ApiHost}:${ApiPort}"

# ZAP's spider does not fall back to IPv4 like .NET's Invoke-WebRequest does.
# On Windows 'localhost' commonly resolves to the IPv6 loopback (::1) first,
# and this sample app only binds IPv4 (0.0.0.0), so the spider would silently
# find nothing. Normalize localhost to 127.0.0.1 for the scan.
$scanTarget = $TargetUrl -replace '(?i)^http://localhost(?=[:/]|$)', 'http://127.0.0.1'
if ($scanTarget -ne $TargetUrl) {
    Write-Host "Scan target normalized: $TargetUrl -> $scanTarget"
}
$escapedUrl = [uri]::EscapeDataString($scanTarget)

# ----------------------------------------------------------------------------
# 1. Start the ZAP daemon
# ----------------------------------------------------------------------------
Write-Host "Starting ZAP daemon from $ZapPath ..."
# TODO: Replace `api.disablekey=true` with a proper API key (and store it as a
# pipeline secret) before production use. Also consider network/scope config to
# restrict what ZAP may crawl.

# ZAP needs a Java runtime (ZAP 2.15+ requires Java 11+, 2.16+ requires 17+).
# Report it up front so a missing JRE fails with a clear message instead of a
# silent 2-minute timeout.
$java = Get-Command java -ErrorAction SilentlyContinue
if (-not $java) {
    Write-Warning 'Java was not found on PATH. ZAP requires a Java runtime; install one (e.g. OpenJDK 17) on the VM.'
}
else {
    # java writes its version to stderr. Windows PowerShell 5.1 treats native
    # stderr as an error when $ErrorActionPreference = 'Stop', so temporarily
    # relax it for this diagnostic.
    $previousEap = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $javaVersion = (& $java.Source -version 2>&1 | Out-String).Trim()
    $ErrorActionPreference = $previousEap
    Write-Host "  java: $javaVersion"
}

# Pre-flight: confirm the app is actually reachable from the agent BEFORE
# blaming ZAP. Deploy probes localhost:5000, but the app must still be up when
# DAST runs minutes later.
try {
    $probe = Invoke-WebRequest -Uri $scanTarget -UseBasicParsing -TimeoutSec 10
    Write-Host "Target is reachable from the agent (HTTP $([int]$probe.StatusCode))."
}
catch {
    throw "Target $scanTarget is not reachable from the agent. The deployed app may not be running: $_"
}

# Capture the daemon's own output so a failed start is diagnosable. Fall back to
# a plain launch if the redirect is not supported.
$zapStdout = Join-Path $OutputDirectory 'zap-daemon.stdout.log'
$zapStderr = Join-Path $OutputDirectory 'zap-daemon.stderr.log'
# zap.bat references the ZAP jar with a relative path, so it must run with the
# ZAP install directory as its working directory.
$zapHome = Split-Path -Parent $ZapPath
try {
    $zapProcess = Start-Process -FilePath $ZapPath `
        -ArgumentList @(
            '-daemon',
            '-host', $ApiHost,
            '-port', "$ApiPort",
            '-config', 'api.disablekey=true'
        ) `
        -WorkingDirectory $zapHome `
        -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $zapStdout `
        -RedirectStandardError $zapStderr
}
catch {
    Write-Warning "Could not redirect ZAP output ($_); launching without redirect."
    $zapProcess = Start-Process -FilePath $ZapPath `
        -ArgumentList @(
            '-daemon',
            '-host', $ApiHost,
            '-port', "$ApiPort",
            '-config', 'api.disablekey=true'
        ) `
        -WorkingDirectory $zapHome `
        -PassThru -WindowStyle Hidden
}

try {
    # --------------------------------------------------------------------------
    # 2. Wait for the ZAP REST API
    # --------------------------------------------------------------------------
    $apiReady = $false
    $apiDeadline = (Get-Date).AddMinutes(2)
    do {
        try {
            $null = Invoke-RestMethod -Uri "$apiBase/JSON/core/view/version" -TimeoutSec 5
            $apiReady = $true
        }
        catch {
            Start-Sleep -Seconds 3
        }
    } while (-not $apiReady -and (Get-Date) -lt $apiDeadline)

    if (-not $apiReady) {
        # Surface the daemon's own output - it usually explains the failure.
        $stderr = Get-Content $zapStderr -ErrorAction SilentlyContinue | Select-Object -Last 30
        $stdout = Get-Content $zapStdout -ErrorAction SilentlyContinue | Select-Object -Last 30
        if ($stderr) {
            Write-Host '--- ZAP daemon stderr (last 30 lines) ---'
            $stderr | ForEach-Object { Write-Host $_ }
        }
        if ($stdout) {
            Write-Host '--- ZAP daemon stdout (last 30 lines) ---'
            $stdout | ForEach-Object { Write-Host $_ }
        }
        throw "ZAP REST API did not become ready at $apiBase within 2 minutes."
    }
    Write-Host "ZAP REST API is ready at $apiBase"

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

    # --------------------------------------------------------------------------
    # 3. Spider
    # --------------------------------------------------------------------------
    Write-Host "Spidering $scanTarget ..."
    $spiderStart = Invoke-RestMethod -Uri "$apiBase/JSON/spider/action/scan/?url=$escapedUrl" -TimeoutSec 60
    $spiderId = $spiderStart.scan

    do {
        Start-Sleep -Seconds 5
        $spiderStatus = Invoke-RestMethod -Uri "$apiBase/JSON/spider/view/status/?scanId=$spiderId" -TimeoutSec 30
    } while ($spiderStatus.status -ne '100' -and $stopwatch.Elapsed.TotalSeconds -lt $TimeoutSeconds)
    Write-Host "Spider finished (status $($spiderStatus.status))."

    # --------------------------------------------------------------------------
    # 4. Active scan
    # --------------------------------------------------------------------------
    # ascan (and the report exports below) only accept URLs that exist in ZAP's
    # site tree. The spider may store the root with or without a trailing slash,
    # so resolve the exact node from the site tree instead of guessing.
    $siteUrl = $scanTarget
    try {
        $sites = Invoke-RestMethod -Uri "$apiBase/JSON/core/view/sites/" -TimeoutSec 30
        $siteNode = @($sites.sites) | Where-Object { $_.TrimEnd('/') -eq $scanTarget.TrimEnd('/') } |
            Select-Object -First 1
        if ($siteNode) {
            $siteUrl = [string]$siteNode
            Write-Host "Active scan target resolved to site node: $siteUrl"
        }
        else {
            Write-Warning "Target $scanTarget not found in ZAP site tree. Sites in tree: $((@($sites.sites)) -join ', ')"
            # Dump the daemon log - it usually shows ZAP's own connection errors.
            $stderr = Get-Content $zapStderr -ErrorAction SilentlyContinue | Select-Object -Last 20
            $stdout = Get-Content $zapStdout -ErrorAction SilentlyContinue | Select-Object -Last 20
            if ($stderr) {
                Write-Host '--- ZAP daemon stderr (last 20 lines) ---'
                $stderr | ForEach-Object { Write-Host $_ }
            }
            if ($stdout) {
                Write-Host '--- ZAP daemon stdout (last 20 lines) ---'
                $stdout | ForEach-Object { Write-Host $_ }
            }
        }
    }
    catch {
        Write-Warning "Could not list ZAP sites ($_); scanning with the target URL as given."
    }
    $siteUrlEscaped = [uri]::EscapeDataString($siteUrl)

    # Make sure the seed URL exists in the tree even if the spider found
    # nothing; ascan refuses URLs that are not in the scan tree.
    try {
        $null = Invoke-RestMethod -Uri "$apiBase/JSON/core/action/accessUrl/?url=$escapedUrl" -TimeoutSec 60
    }
    catch {
        Write-Warning "Could not seed $scanTarget into the ZAP site tree ($_)."
    }

    Write-Host "Running active scan against $siteUrl ..."
    $scanStart = Invoke-RestMethod -Uri "$apiBase/JSON/ascan/action/scan/?url=$siteUrlEscaped&recurse=true" -TimeoutSec 60
    $scanId = $scanStart.scan

    do {
        Start-Sleep -Seconds 5
        $scanStatus = Invoke-RestMethod -Uri "$apiBase/JSON/ascan/view/status/?scanId=$scanId" -TimeoutSec 30
    } while ($scanStatus.status -ne '100' -and $stopwatch.Elapsed.TotalSeconds -lt $TimeoutSeconds)
    Write-Host "Active scan finished (status $($scanStatus.status))."

    if ($stopwatch.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
        Write-Warning "Scan hit the $TimeoutSeconds s timeout; exporting partial results."
    }

    # --------------------------------------------------------------------------
    # 5. Export reports
    # --------------------------------------------------------------------------
    $jsonReport = Invoke-WebRequest -Uri "$apiBase/OTHER/core/other/jsonreport/?baseurl=$siteUrlEscaped" -UseBasicParsing -TimeoutSec 120
    [System.IO.File]::WriteAllText((Join-Path $OutputDirectory $JsonReportName), $jsonReport.Content, [System.Text.Encoding]::UTF8)

    $xmlReport = Invoke-WebRequest -Uri "$apiBase/OTHER/core/other/xmlreport/?baseurl=$siteUrlEscaped" -UseBasicParsing -TimeoutSec 120
    [System.IO.File]::WriteAllText((Join-Path $OutputDirectory $XmlReportName), $xmlReport.Content, [System.Text.Encoding]::UTF8)

    $htmlReport = Invoke-WebRequest -Uri "$apiBase/OTHER/core/other/htmlreport/?baseurl=$siteUrlEscaped" -UseBasicParsing -TimeoutSec 120
    [System.IO.File]::WriteAllText((Join-Path $OutputDirectory $HtmlReportName), $htmlReport.Content, [System.Text.Encoding]::UTF8)

    Write-Host "Reports written to $OutputDirectory :"
    Write-Host "  - $JsonReportName"
    Write-Host "  - $XmlReportName"
    Write-Host "  - $HtmlReportName"
}
finally {
    # --------------------------------------------------------------------------
    # 6. Shut ZAP down
    # --------------------------------------------------------------------------
    try {
        $null = Invoke-RestMethod -Uri "$apiBase/JSON/core/action/shutdown/" -TimeoutSec 10
    }
    catch {
        # daemon may already be gone
    }
    if ($zapProcess -and -not $zapProcess.HasExited) {
        Stop-Process -Id $zapProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host 'ZAP daemon stopped.'
}

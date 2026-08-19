<#
.SYNOPSIS
    Deploys the pipeline artifact onto the Windows VM.

.DESCRIPTION
    Runs on the deployment VM. Stops the running application (Windows service,
    when configured), copies the new build output into SitePath, starts the
    application again, and waits until it is reachable.

    The application can be hosted two ways (mutually exclusive):
      * a Windows service  (WindowsServiceName)
      * a self-hosted app  (StartCommand, e.g. "dotnet WebSample.dll")

.PARAMETER SitePath
    Destination folder on the VM, e.g. C:\site.

.PARAMETER SourcePath
    Folder containing the downloaded build artifact, e.g.
    $(Pipeline.Workspace)\drop.

.PARAMETER WindowsServiceName
    Name of the Windows service hosting the app. Empty = not a service.

.PARAMETER ApplicationUrl
    URL probed after deployment to confirm the app is reachable. Empty = skip.

.PARAMETER StartCommand
    Command used to launch a self-hosted app from SitePath. Empty = not used.

.PARAMETER WaitTimeoutSeconds
    Seconds to poll ApplicationUrl before giving up.

.PARAMETER ProbeIntervalSeconds
    Seconds between reachability probes.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SitePath,

    [Parameter(Mandatory = $true)]
    [string]$SourcePath,

    [string]$WindowsServiceName = '',
    [string]$ApplicationUrl = '',
    [string]$StartCommand = '',
    [int]$WaitTimeoutSeconds = 300,
    [int]$ProbeIntervalSeconds = 5,
    [string]$SampleArtifactFileName = 'WebSample.dll'
)

$ErrorActionPreference = 'Stop'

Write-Host '== Deploy start =='
Write-Host "Source: $SourcePath"
Write-Host "Target: $SitePath"

# ----------------------------------------------------------------------------
# 1. Stop the application (if applicable)
# ----------------------------------------------------------------------------
if ($WindowsServiceName) {
    $service = Get-Service -Name $WindowsServiceName -ErrorAction SilentlyContinue
    if ($service -and $service.Status -ne 'Stopped') {
        Write-Host "Stopping Windows service: $WindowsServiceName"
        Stop-Service -Name $WindowsServiceName -Force -ErrorAction Continue
        $service.WaitForStatus('Stopped', (New-TimeSpan -Seconds 30))
    }
    else {
        Write-Host "Windows service '$WindowsServiceName' is not present or already stopped."
    }
}

# ----------------------------------------------------------------------------
# 2. Copy the new build output
# ----------------------------------------------------------------------------
if (-not (Test-Path $SourcePath)) {
    throw "Source path does not exist: $SourcePath"
}
New-Item -ItemType Directory -Force -Path $SitePath | Out-Null

robocopy $SourcePath $SitePath /E /XD .git /NFL /NDL /NJH /NJS /NC /NS /NP
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -ge 8) {
    throw "robocopy failed with exit code $robocopyExit"
}
# robocopy exits 0-7 on success; leaving $LASTEXITCODE set makes the PowerShell
# task report this job as failed. Reset it so the script's own exit governs.
$global:LASTEXITCODE = 0
Write-Host "Files copied to $SitePath (robocopy exit code $robocopyExit)."

# ----------------------------------------------------------------------------
# 3. Start the application (if applicable)
# ----------------------------------------------------------------------------
if ($WindowsServiceName) {
    $service = Get-Service -Name $WindowsServiceName -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "Starting Windows service: $WindowsServiceName"
        Start-Service -Name $WindowsServiceName
    }
}
elseif ($StartCommand) {
    Write-Host "Starting application: $StartCommand (workdir $SitePath)"
    # TODO: For production, prefer a Windows service so the app survives
    # agent restarts and is supervised. Start-Process is used here so the sample
    # self-hosted app can run end-to-end.

    # Pre-flight checks so a broken launch fails with a useful message instead of
    # silently timing out in the reachability probe below.
    if (-not (Test-Path (Join-Path $SitePath $SampleArtifactFileName))) {
        throw "Deployment payload in $SitePath does not contain $SampleArtifactFileName."
    }
    $dotnetExe = Get-Command dotnet -ErrorAction SilentlyContinue
    if (-not $dotnetExe) {
        throw "The 'dotnet' command was not found on PATH. Install the .NET runtime on the VM (or set StartCommand to the full path to dotnet.exe)."
    }
    Write-Host "Using dotnet: $($dotnetExe.Source)"
    & $dotnetExe.Source --list-runtimes

    $stdoutLog = Join-Path $SitePath 'app.stdout.log'
    $stderrLog = Join-Path $SitePath 'app.stderr.log'
    Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/c', $StartCommand `
        -WorkingDirectory $SitePath `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog
}

# ----------------------------------------------------------------------------
# 4. Wait until the application is reachable
# ----------------------------------------------------------------------------
if ($ApplicationUrl) {
    $deadline = (Get-Date).AddSeconds($WaitTimeoutSeconds)
    $reachable = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $ApplicationUrl -UseBasicParsing -TimeoutSec 10
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                $reachable = $true
                break
            }
        }
        catch {
            # not reachable yet - keep probing
        }
        Start-Sleep -Seconds $ProbeIntervalSeconds
    }

    if (-not $reachable) {
        # Surface the app's own output - it usually explains why it is not up.
        $stdoutLog = Join-Path $SitePath 'app.stdout.log'
        $stderrLog = Join-Path $SitePath 'app.stderr.log'
        $stderr = Get-Content $stderrLog -ErrorAction SilentlyContinue | Select-Object -Last 20
        $stdout = Get-Content $stdoutLog -ErrorAction SilentlyContinue | Select-Object -Last 20
        if ($stderr) {
            Write-Host '--- app stderr (last 20 lines) ---'
            $stderr | ForEach-Object { Write-Host $_ }
        }
        if ($stdout) {
            Write-Host '--- app stdout (last 20 lines) ---'
            $stdout | ForEach-Object { Write-Host $_ }
        }
        throw "Application did not become reachable at $ApplicationUrl within $WaitTimeoutSeconds s."
    }
    Write-Host "Application is reachable at $ApplicationUrl"
}

Write-Host '== Deploy complete =='
# Explicit success exit - a stale $LASTEXITCODE (e.g. from robocopy) would
# otherwise make the Azure Pipelines PowerShell task mark this job as failed.
exit 0

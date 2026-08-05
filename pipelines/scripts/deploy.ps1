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
    [int]$ProbeIntervalSeconds = 5
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
    Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/c', $StartCommand `
        -WorkingDirectory $SitePath `
        -WindowStyle Hidden
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
        throw "Application did not become reachable at $ApplicationUrl within $WaitTimeoutSeconds s."
    }
    Write-Host "Application is reachable at $ApplicationUrl"
}

Write-Host '== Deploy complete =='

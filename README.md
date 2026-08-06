# Azure DevOps Security Pipeline

A modular Azure DevOps pipeline that builds, secures, deploys and
dynamically-scans a small sample web application on a Windows VM.

## Contents

| Path                    | Description                                                        |
| ----------------------- | ------------------------------------------------------------------ |
| `pipelines/`            | The Azure DevOps pipeline (see `pipelines/README.md` for details)  |
| `src/WebSample/`        | Sample ASP.NET Core app built by the Build stage and deployed to the VM |
| `.hidden/security-tests/` | Intentional test fixtures (fake secrets, unsafe code) used to validate the security stages. Git-ignored (GitHub blocks malicious content), so copy onto the scanner workdir to scan them |

## Pipeline

```
Build ──► SAST ──► MSDO ──► Deploy ──► DAST ──► Publish
```

- **Build** publishes `src/WebSample` into the `drop` artifact.
- **SAST** runs TruffleHog and Semgrep in parallel.
- **MSDO** runs Microsoft Security DevOps.
- **Deploy** deploys the `drop` artifact to `C:\site` on the Windows VM.
- **DAST** scans the deployed app with the OWASP ZAP that is already
  installed on the VM.
- **Publish** aggregates all reports and publishes them as artifacts; it
  always runs, even when a security stage fails.

Point the Azure DevOps pipeline at `pipelines/azure-pipelines.yml`.

# Azure DevOps Security Pipeline

A modular Azure DevOps pipeline that builds, secures, deploys and
dynamically-scans a small sample web application on a Windows VM.

## Contents

| Path                    | Description                                                        |
| ----------------------- | ------------------------------------------------------------------ |
| `pipelines/`            | The Azure DevOps pipeline (see `pipelines/README.md` for details)  |
| `src/WebSample/`        | Sample ASP.NET Core app built by the Build stage and deployed to the VM |
| `.hidden/security-tests/` | Intentional test fixtures (fake secrets, unsafe code) used to validate the security stages. Git-ignored (GitHub blocks malicious content), so copy onto the scanner workdir to scan them |
| `owasp-zap-doc.md`      | DAST tool evaluation and approval proposal (OWASP ZAP)             |
| `developer-doc.md`      | Developer guide: what the pipeline does, what you can change, how the build works |
| `design-architecture-doc.md` | Design/architecture doc: tool choices, reasoning, deployment, modification |
| `doc.md`                | Full implementation reference for the pipeline                     |

## Pipeline

```
Build ──► SAST ──► MSDO ──► Deploy ──► DAST ──► Publish ──► DefectDojo (optional)
```

- **Build** publishes `src/WebSample` into the `drop` artifact.
- **SAST** runs TruffleHog and Semgrep in parallel.
- **MSDO** runs Microsoft Security DevOps.
- **Deploy** deploys the `drop` artifact to `C:\site` on the Windows VM.
- **DAST** scans the deployed app with the OWASP ZAP that is already
  installed on the VM.
- **Publish** aggregates all reports into an HTML dashboard; it always runs,
  even when a security stage fails.
- **DefectDojo** (optional) uploads the scanner reports for central triage.

Point the Azure DevOps pipeline at `pipelines/azure-pipelines.yml`.

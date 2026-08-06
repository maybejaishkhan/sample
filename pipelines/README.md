# Azure DevOps Pipeline

Production-ready, modular pipeline for building, securing, deploying and
dynamic-scanning a Windows-VM-hosted application.

## Pipeline shape

```
Build ──► SAST ──► MSDO ──► Deploy ──► DAST ──► Publish
```

| Stage    | What it does                                                        |
| -------- | ------------------------------------------------------------------- |
| Build    | Produces the deployment artifact (sample app by default)             |
| SAST     | TruffleHog (secrets) + Semgrep (static analysis), run in parallel   |
| MSDO     | Microsoft Security DevOps -> SARIF                                   |
| Deploy   | Deployment job on the Windows VM -> copies app to `C:\site`          |
| DAST     | OWASP ZAP (already installed on the VM) scans the deployed app       |
| Publish  | Aggregates everything into reports; **always runs**                 |

The Publish stage uses `condition: always()`, so if a security stage fails the
reports are still generated and published.

## Layout

```
pipelines/
├── azure-pipelines.yml        # thin orchestrator: variables + stage templates
├── variables/                 # every configurable value lives here
│   ├── global.yml             #   cross-cutting (agents, python, paths)
│   ├── build.yml              #   build mode, artifact name, project path
│   ├── security.yml           #   scanner versions/rules, policy gates
│   └── deployment.yml         #   VM env, site path, service/self-hosted, ZAP
├── templates/                 # one file per stage; jobs + steps fully inline
│   ├── build.yml              #   creates the deployment artifact
│   ├── sast.yml               #   TruffleHog + Semgrep jobs (parallel)
│   ├── msdo.yml               #   Microsoft Security DevOps job
│   ├── deploy.yml             #   deployment job to the Windows VM
│   ├── dast.yml               #   OWASP ZAP deployment job on the VM
│   └── publish.yml            #   aggregation + report publishing (always)
├── scripts/                   # Python aggregator + PowerShell helpers
│   ├── aggregate.py           #   parsers -> combined.json
│   ├── generate_html.py       #   combined.json -> index.html dashboard
│   ├── security_summary.py    #   combined.json -> summary.json/.md
│   ├── policy_check.py        #   per-scanner policy gate (fail on critical/high)
│   ├── deploy.ps1             #   runs on the VM: stop/copy/start/wait
│   ├── zap_scan.ps1           #   runs on the VM: headless ZAP scan
│   ├── parser/                #   one parser per scanner (return Finding[])
│   └── shared/                #   Finding model + parser dispatcher
```
Reports are **not stored in the repository**. They are written to the agent's
artifact staging area (`$(Build.ArtifactStagingDirectory)/reports/...`) and
published as pipeline artifacts (`reports-raw`, `reports-html`,
`reports-summary`) by the Publish stage.

## Configuration

Point the pipeline at `pipelines/azure-pipelines.yml` in Azure DevOps.

Per-environment values (machine name, site path, URLs, secrets) belong in the
`variables/deployment.yml` template. In production, override them with variable
groups / library secrets rather than editing the files per branch.

Before the first real run:

* Create the Azure DevOps **Environment** (`DeploymentEnvironment`) and register
  the Windows VM as a **VM resource** (`VmResourceName`) with a deployment agent.
* Install OWASP ZAP on the VM (`ZapPath`).
* If `MicrosoftSecurityDevOps@1` does not resolve, install the *Microsoft
  Security DevOps* extension in the organization (see
  `templates/msdo.yml`).
* Bump `TrufflehogVersion` / `SemgrepVersion` / `ZapTimeout` to taste.

## Testing the security stage

Intentional test fixtures live in `.hidden/security-tests/` (git-ignored, since
GitHub blocks malicious content):

* `secrets/*` - fake secrets (AWS keys, GitHub/Slack tokens, `postgres://`
  connection strings, a PEM private key) in formats TruffleHog detects
  reliably.
* `code/*.py` - deliberate vulnerabilities (SQL injection, command injection,
  XSS, path traversal, SSRF, unsafe `eval()`/`pickle`/`yaml.load`, weak
  crypto, hardcoded credentials) that Semgrep's `p/security-audit` flags.
* `malware/eicar.txt` - the EICAR anti-malware signature, caught by the MSDO
  AntiMalware tool.
* `web/login.html` - an insecure form (no CSRF, password autocomplete).

The fixtures are not checked out by `checkout: self` because they are
git-ignored. To scan them in a pipeline run, copy `.hidden/security-tests/`
onto the agent/VM workdir first (e.g. place them in
`$(Build.SourcesDirectory)/security-tests` before the SAST stage runs).

With the default gates (`FailOnCritical`/`FailOnHigh` = true) the Semgrep job
finds an ERROR/high finding, so the **build fails** at the SAST stage - while
the Publish stage still runs and produces all reports. To verify detection
without failing the build, set `FailOnCritical: false` / `FailOnHigh: false`.

## Adding a new scanner (Trivy, Checkov, Gitleaks, ...)

Exactly three things change:

1. **Job** inside the relevant stage template (`templates/sast.yml` for static
   tools), following the existing pattern:
   install -> run (`continueOnError`) -> archive (`PublishPipelineArtifact`,
   always) -> `policy_check`.
2. **Parser module** `scripts/parser/<scanner>.py` returning `List[Finding]`,
   then register the output file name in `scripts/shared/dispatch.py`.
3. **Variable updates** in `pipelines/variables/security.yml` (report file
   name, artifact name, version).

Nothing else needs to change - the Publish stage picks new files up
automatically because aggregation is driven by the dispatcher.

## Running the aggregator locally

The scripts create their output folders on demand, so for local testing use any
directory (e.g. `pipelines/reports/...` locally is fine - it just isn't
committed):

```bash
pipelines/scripts/aggregate.py --raw pipelines/reports/raw \
    --output pipelines/reports/summary/combined.json

pipelines/scripts/generate_html.py --combined pipelines/reports/summary/combined.json \
    --output pipelines/reports/html/index.html

pipelines/scripts/security_summary.py --combined pipelines/reports/summary/combined.json \
    --json pipelines/reports/summary/summary.json \
    --markdown pipelines/reports/summary/summary.md
```

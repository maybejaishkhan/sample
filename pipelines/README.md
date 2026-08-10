# Azure DevOps Pipeline

Production-ready, modular pipeline for building, securing, deploying and
dynamic-scanning a Windows-VM-hosted application.

## Pipeline shape

```
Build ──► SAST ──► MSDO ──► Deploy ──► DAST ──► Publish ──► DefectDojo (optional)
```

| Stage       | What it does                                                        |
| ----------- | ------------------------------------------------------------------- |
| Build       | Produces the deployment artifact (sample app by default)             |
| SAST        | TruffleHog (secrets) + Semgrep (static analysis), run in parallel   |
| MSDO        | Microsoft Security DevOps -> SARIF                                   |
| Deploy      | Deployment job on the Windows VM -> copies app to `C:\site`          |
| DAST        | OWASP ZAP (already installed on the VM) scans the deployed app       |
| Publish     | Aggregates everything into reports; **always runs**                 |
| DefectDojo  | Uploads the scanner reports to a DefectDojo instance (**optional**) |

The Publish stage uses `condition: always()`, so if a security stage fails the
reports are still generated and published.

The DefectDojo stage is skipped unless `EnableDefectDojo` is `true`. When
enabled it downloads each scanner's own artifact and imports its report via the
DefectDojo API v2 (`import-scan`/`reimport-scan`): TruffleHog, Semgrep JSON,
MSDO SARIF and ZAP XML. Product/engagement context is auto-created on the
DefectDojo side, so nothing needs to be set up in the UI.

## Layout

```
pipelines/
├── azure-pipelines.yml        # thin orchestrator: variables + stage templates
├── variables/                 # every configurable value lives here
│   ├── global.yml             #   cross-cutting (agents, python, paths)
│   ├── build.yml              #   build mode, artifact name, project path
│   ├── security.yml           #   scanner versions/rules, policy gates, DefectDojo
│   └── deployment.yml         #   VM env, site path, service/self-hosted, ZAP
├── templates/                 # one file per stage; jobs + steps fully inline
│   ├── build.yml              #   creates the deployment artifact
│   ├── sast.yml               #   TruffleHog + Semgrep jobs (parallel)
│   ├── msdo.yml               #   Microsoft Security DevOps job
│   ├── deploy.yml             #   deployment job to the Windows VM
│   ├── dast.yml               #   OWASP ZAP deployment job on the VM
│   ├── publish.yml            #   aggregation + HTML dashboard publishing (always)
│   └── defectdojo.yml         #   optional: upload reports to DefectDojo
├── scripts/                   # Python aggregator + PowerShell helpers
│   ├── aggregate.py           #   parsers -> combined.json
│   ├── generate_html.py       #   combined.json -> index.html dashboard
│   ├── policy_check.py        #   per-scanner policy gate (fail on critical/high)
│   ├── import_defectdojo.ps1  #   uploads raw reports to DefectDojo (REST API, curl)
│   ├── import_defectdojo.py   #   same uploader, for Linux/local use
│   ├── deploy.ps1             #   runs on the VM: stop/copy/start/wait
│   ├── zap_scan.ps1           #   runs on the VM: headless ZAP scan
│   ├── parser/                #   one parser per scanner (return Finding[])
│   └── shared/                #   Finding model + parser dispatcher
```
Reports are **not stored in the repository**. They are written to the agent's
artifact staging area (`$(Build.ArtifactStagingDirectory)/reports/...`) and the
Publish stage publishes a single `reports-html` artifact (a one-page dashboard)
plus the per-scanner artifacts (`trufflehog`, `semgrep`, `msdo`, `zap`) that
each scanner job publishes itself.

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

## DefectDojo integration

The optional `DefectDojo` stage uploads the scanner reports to a DefectDojo
instance (`templates/defectdojo.yml` + `scripts/import_defectdojo.ps1`). To
enable it:

1. Set `EnableDefectDojo: true` in `variables/security.yml`.
2. Set the base URL (`DefectDojoUrl`, e.g. `http://<server>:<port>`) and the
   API v2 token (`DefectDojoApiToken`) as a **secret** - use a variable group
   / library secret rather than editing the variable file.
3. Optionally change `DefectDojoProductName`, `DefectDojoProductTypeName` and
   `DefectDojoEngagementName`; DefectDojo auto-creates them on first import.
4. Make sure the job's agent pool (`DefectDojoPool`, e.g. `cloud-poc`) can
   reach the server. If you have a dedicated agent for it, set
   `DefectDojoAgentName` (e.g. `defect-dojo`) and the job is pinned to that
   agent via an `Agent.Name -equals` demand. For a hosted agent use
   `DefectDojoPool: ubuntu-latest` and leave `DefectDojoAgentName` empty.

`DefectDojoImportMode` controls whether each run creates a fresh Test
(`import`) or updates one Test per scan type and closes stale findings
(`reimport`, the default).

Scan type mapping:

| Report file  | DefectDojo scan type   |
| ------------ | ---------------------- |
| `trufflehog.json` | `Trufflehog Scan`   |
| `semgrep.json`    | `Semgrep JSON Report` |
| `msdo.sarif`      | `SARIF`              |
| `zap.xml`         | `ZAP Scan`           |

The import step is a PowerShell script (`import_defectdojo.ps1`) so it runs on
the hosted Linux image **and** self-hosted Windows agents; it uses `curl`, which
is built into Windows 10 1803+ / Server 2019+ and preinstalled on Linux.

To test the upload locally (a running DefectDojo instance is required):

```bash
DEFECTDOJO_URL=http://<server>:<port> \
DEFECTDOJO_API_TOKEN=<token> \
python3 pipelines/scripts/import_defectdojo.py \
    --raw pipelines/reports/raw \
    --product sample-app \
    --engagement CI-CD \
    --scan-type trufflehog.json="Trufflehog Scan"
```

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

TruffleHog findings are treated as `high` whether the secret is verified or
not, so the TruffleHog job fails on *unverified* results as well (TruffleHog's
own `--fail` only exits non-zero for verified secrets). Set
`FailOnHigh: false` to stop gating on TruffleHog results entirely.

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

If the DefectDojo stage is enabled, also add a `--scan-type` line in
`templates/defectdojo.yml` mapping the new report file to its DefectDojo scan
type.

## Running the aggregator locally

The scripts create their output folders on demand, so for local testing use any
directory (e.g. `pipelines/reports/...` locally is fine - it just isn't
committed):

```bash
pipelines/scripts/aggregate.py --raw pipelines/reports/raw \
    --output pipelines/reports/summary/combined.json

pipelines/scripts/generate_html.py --combined pipelines/reports/summary/combined.json \
    --output pipelines/reports/html/index.html
```

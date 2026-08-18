# Azure DevOps Security Pipeline — Team Documentation

This document explains the end-to-end CI/CD pipeline in this repository: what it
does, how it is structured, how to set it up, and how to troubleshoot it. It is
written for anyone on the team who needs to operate or modify the pipeline,
whether or not they have seen it before.

---

## 1. What this pipeline does

Every push to `main` (and every PR against `main`) triggers a fully automated
pipeline that:

1. **Builds** a small ASP.NET Core web application into a deployable artifact.
2. **Scans the source code** for security issues (static analysis).
3. **Deploys** the built application to a Windows VM.
4. **Scans the running application** (dynamic analysis).
5. **(Optional)** Uploads the scan results to a DefectDojo instance for central
   triage.

In short: **build → secure → deploy → test → (triage).**

The pipeline is deliberately modular. The main entry file is thin and simply
chains together one template per stage. Almost everything is configurable
through a small set of variable files, so most day-to-day changes never require
touching pipeline logic.

> Note: the repository contains a *sample* application (`src/WebSample/`) used
> to exercise the whole flow. To build a real application, change the build
> variables (see section 6) — no template changes are required.

---

## 2. High-level flow

```
Build ──► SAST ──► Deploy ──► DAST ──► DefectDojo (optional)
```

| # | Stage      | Where it runs         | What it does                                                     |
|---|------------|-----------------------|------------------------------------------------------------------|
| 1 | Build      | Hosted Linux agent    | Publishes the app and stores it as the `drop` artifact           |
| 2 | SAST       | Hosted Linux agent    | Static analysis: TruffleHog (secrets) + Semgrep (code), in parallel |
| 3 | Deploy     | Self-hosted Windows VM | Copies the artifact to `C:\site` and starts the app             |
| 4 | DAST       | Self-hosted Windows VM | OWASP ZAP scans the running app (spider + active scan)          |
| 5 | DefectDojo | `DefectDojoPool` agent | Uploads the scanner reports to a DefectDojo instance (**optional**) |

> Diagram: a Mermaid source of this flow lives at `diagrams/pipeline-flow.mmd`
> (git-ignored; render it with any Mermaid tool or paste it into
> mermaid.live). It is kept out of this document so the doc renders cleanly on
> plain markdown viewers.

**DefectDojo** is an optional final stage, gated on the `EnableDefectDojo`
variable. It runs after SAST/DAST and downloads each scanner's artifact, so the
reports are uploaded even when a scan stage failed (it uses
`succeededOrFailed()`). Imports happen via the DefectDojo API v2 (see
`scripts/import_defectdojo.ps1`).

---

## 3. Repository layout

```
├── doc.md                      # this document
├── global.json                 # pins the .NET SDK version used to build
├── diagrams/                   # Mermaid diagram sources (git-ignored, local-only)
├── src/
│   └── WebSample/              # sample ASP.NET Core web app (net10.0)
│       ├── WebSample.csproj
│       ├── Program.cs          # endpoints: /  /health  /echo
│       └── appsettings.json    # binds to http://0.0.0.0:5000
└── pipelines/
    ├── azure-pipelines.yml     # main pipeline: loads variables + stage templates
    ├── variables/              # every configurable value lives here
    │   ├── global.yml          #   agents, Python version, report path
    │   ├── build.yml           #   build mode, project path, artifact name
    │   ├── security.yml        #   scanner versions/rules, policy gates, DefectDojo
    │   └── deployment.yml      #   VM settings, app hosting, ZAP
    ├── templates/              # one file per stage
    │   ├── build.yml           #   stage 1
    │   ├── sast.yml            #   stage 2
    │   ├── deploy.yml          #   stage 3
    │   ├── dast.yml            #   stage 4
    │   └── defectdojo.yml      #   stage 5 (optional)
    └── scripts/                # the brains: Python + PowerShell
        ├── policy_check.py     #   fail a job on critical/high findings
        ├── import_defectdojo.ps1 #  upload raw reports to DefectDojo (curl, runs on any agent)
        ├── import_defectdojo.py #  same uploader, for Linux/local use
        ├── deploy.ps1          #   runs on the VM: stop/copy/start/wait
        ├── zap_scan.ps1        #   runs on the VM: headless ZAP scan
        ├── parser/             #   one parser per scanner
        └── shared/             #   common Finding model + dispatcher
```

### The three layers

1. **Orchestration** (`azure-pipelines.yml`) — which stages run and in what order.
2. **Templates** (`templates/*.yml`) — *how* each stage runs (its jobs and steps).
3. **Variables** (`variables/*.yml`) — *what* values each stage uses.

The rule of thumb: **configuration changes go in `variables/`, behaviour changes
go in `templates/` or `scripts/`.** There is no hardcoded path, URL, or version
buried inside a stage template.

---

## 4. The sample application

`src/WebSample/` is a minimal ASP.NET Core web app (target framework `net10.0`):

| Route   | Behaviour                                   |
|---------|---------------------------------------------|
| `/`     | Returns the text `WebSample is running.`    |
| `/health` | Returns JSON `{ "status": "ok" }`         |
| `/echo?q=...` | Reflects user input back to the browser (see warning below) |

It binds to `http://0.0.0.0:5000` (`appsettings.json`) and is hosted on the VM
as a **Windows service** (service name `WebSample` — see `WindowsServiceName` in
`deployment.yml`). The deployed files live in `C:\site`.

> **Security note:** the `/echo` endpoint deliberately echoes user input without
> escaping. This is an intentional sample flaw so that Semgrep and OWASP ZAP
> actually have something to flag — it demonstrates how findings flow into the
> reports. **Do not copy this pattern into a real application.**

---

## 5. Stage-by-stage walkthrough

### Stage 1 — Build (`templates/build.yml`, hosted Linux agent)

Produces a single deployable artifact called `drop`.

- **Publish mode** (default, `BuildMode = publish`): runs
  `dotnet restore` + `dotnet publish` on `src/WebSample/WebSample.csproj`
  (framework `net10.0`, configuration `Release`), verifies the output file
  named by `SampleArtifactFileName` (`WebSample.dll`) was produced in
  `BuildOutputDir`, then publishes it as the `drop` artifact.
- **Copy mode** (`BuildMode = copy`): instead of compiling, it packages a
  directory verbatim (excluding `.git`, `bin`, `obj`). Useful for static
  content or pre-compiled output.

No security scanning happens here.

### Stage 2 — SAST (`templates/sast.yml`, hosted Linux agent)

Two independent jobs run **in parallel** — if one fails, the other still runs.

| Job        | Scanner                 | What it checks                     | Report file(s)          |
|------------|-------------------------|-------------------------------------|-------------------------|
| `TruffleHog` | [TruffleHog](https://github.com/trufflesecurity/trufflehog) | Leaked secrets/credentials in git history | `trufflehog.json` |
| `Semgrep`   | [Semgrep](https://semgrep.dev) | Static code analysis (ruleset `p/security-audit`) | `semgrep.json`, `semgrep.sarif` |

Both jobs follow the same four-step pattern:

1. **Install** the scanner.
2. **Scan** the repository (`continueOnError: true`, so output is always archived).
3. **Archive** results as a pipeline artifact (`condition: always()` and
   `continueOnError: true`, so re-running a stage doesn't fail because the same
   artifact name already exists).
4. **Policy gate**: runs `policy_check.py`, which fails the job if critical/high
   findings exist (see section 7).

Because the policy-gate step also runs on `always()`, a scanner that crashes
(and therefore produces no report) also fails the job — the pipeline never
silently passes a broken scan.

### Stage 3 — Deploy (`templates/deploy.yml`, self-hosted Windows VM)

Downloads the `drop` artifact into `DeploySourcePath` and runs
`scripts/deploy.ps1`, which executes **directly on the VM** through the
self-hosted agent:

1. **Stop** the Windows service (`WindowsServiceName`, e.g. `WebSample`).
2. **Copy** the new build output into `C:\site` with `robocopy`.
3. **Start** the Windows service again. (A self-hosted `StartCommand` mode also
   exists for apps that are not registered as a service.)
4. **Wait** until the app answers at `ApplicationUrl` (`http://localhost:5000`),
   polling every 5 seconds for up to 300 seconds.

The app is hosted as a **Windows service** (registered on the VM, e.g. with
NSSM) rather than a bare process, because a process started from the Deploy job
is killed when the job ends — the agent terminates its per-job process tree — so
a plain `Start-Process` would not survive until the DAST stage.

`deploy.ps1` includes pre-flight checks, resets the stale `$LASTEXITCODE` left by
`robocopy` (whose success codes are 0–7, i.e. non-zero), and logs the app's own
stdout/stderr on failure, so a bad deployment fails with a useful message
instead of a silent timeout.

### Stage 4 — DAST (`templates/dast.yml`, self-hosted Windows VM)

Runs **OWASP ZAP** (already installed on the VM) against the deployed
application. The pipeline never downloads or installs ZAP.

Flow inside `zap_scan.ps1`:

1. Pre-flight checks: ZAP exists, Java is present, and the target app is
   reachable from the agent.
2. Start ZAP in headless daemon mode (its REST API listens on port 8090).
3. **Spider** the target to discover URLs.
4. **Active scan** the discovered URLs.
5. Export `zap.json`, `zap.xml`, and `zap.html` (written with BOM-less UTF-8).
6. Shut the daemon down.

Results are archived as the `zap` artifact and a policy gate runs. Because the
scan runs on the VM itself, the target is addressed as `localhost`/`127.0.0.1`
(the script normalizes `localhost` to `127.0.0.1` for ZAP, which does not fall
back to IPv4 the way .NET's HTTP client does). The script ends with an explicit
`exit 0` so a stale `$LASTEXITCODE` from a native command cannot fail the job.

### Stage 5 — DefectDojo (`templates/defectdojo.yml`, agent from `DefectDojoPool`, optional)

Uploads the scanner reports to a DefectDojo instance so findings can be
triaged centrally. The stage only runs when `EnableDefectDojo` is `true`.

- Depends on `[SAST, DAST]` and downloads each scanner's own artifact
  (`trufflehog`, `semgrep`, `zap`), so it imports exactly the raw reports the
  scans produced. Each download is best-effort, and the stage uses
  `succeededOrFailed()`, so whatever the scans produced is still uploaded even
  when a scan stage failed.
- Runs `scripts/import_defectdojo.ps1` (PowerShell + curl), which calls the
  DefectDojo API v2 `import-scan` / `reimport-scan` endpoint once per report
  file with the matching scan type: `trufflehog.json` → *Trufflehog Scan*,
  `semgrep.json` → *Semgrep JSON Report*, `zap.xml` → *ZAP Scan*.
- Product type, product and engagement are **created via the API** by the
  import script when they do not exist (the import-scan endpoint itself only
  auto-creates the engagement), using `DefectDojoProductTypeName`,
  `DefectDojoProductName` and `DefectDojoEngagementName`.
- `DefectDojoImportMode` (`reimport` by default) keeps one Test per scan type
  inside the engagement and closes findings that disappear, instead of stacking
  a new Test per run.

> Note: this pipeline previously ran a Microsoft Security DevOps (MSDO) stage
> whose SARIF was also imported as *SARIF*. That stage was removed; if you want
> SARIF imports back, add a scanner that emits SARIF and map its file via
> `DEFECTDOJO_SCAN_TYPES` in `templates/defectdojo.yml`.

Authentication uses a DefectDojo API v2 token passed as a **secret**
(`DefectDojoApiToken`) and the base URL (`DefectDojoUrl`); both must be
overridden per environment. The job's agent pool (`DefectDojoPool`) must be able
to reach the server — set `DefectDojoAgentName` to pin the job to a specific
agent in the pool (e.g. a dedicated `defect-dojo` agent) via an
`Agent.Name -equals` demand.

---

## 6. Configuration

Everything configurable lives in `pipelines/variables/`. Values that are
machine-specific or environment-specific (the VM pool, paths, URLs) live in
`deployment.yml` and are expected to be overridden per environment (e.g. with a
variable group).

### `global.yml` — cross-cutting

| Variable               | Default                  | Purpose                          |
|------------------------|--------------------------|----------------------------------|
| `AgentImage`           | `ubuntu-latest`          | Hosted image for Linux jobs      |
| `PythonVersion`        | `3.11`                   | Python used by the policy check  |
| `RawReportsDirFull`    | `$(Build.ArtifactStagingDirectory)/reports/raw` | Where raw scanner files land |
| `ScriptsDir`           | `pipelines/scripts`      | Where the Python scripts live    |

Reports are always written to the agent's staging area — **never committed to
the repository**.

### `build.yml` — build settings

| Variable           | Default                                   | Purpose                                    |
|--------------------|-------------------------------------------|--------------------------------------------|
| `BuildConfiguration` | `Release`                               | Build configuration                        |
| `ArtifactName`     | `drop`                                     | Name of the deployable artifact            |
| `SampleProjectPath`| `src/WebSample/WebSample.csproj`           | Project published in `publish` mode        |
| `PublishFramework` | `net10.0`                                  | Target framework (matches `global.json`)   |
| `BuildMode`        | `publish`                                  | `publish` or `copy`                        |
| `CopySourcePath`   | `$(Build.SourcesDirectory)`                | Source path for `copy` mode                |
| `BuildOutputDir`   | `$(Build.ArtifactStagingDirectory)/out`    | Where the build stages its output          |
| `SampleArtifactFileName` | `WebSample.dll`                       | File that must exist after publish (used by Build and Deploy) |

### `security.yml` — scanner settings

Key items: `SemgrepRules` (`p/security-audit`), `SemgrepVersion` (empty = latest),
`TrufflehogVersion`, `TrufflehogArch` (`linux_amd64`), plus:

- **Policy gates:** `FailOnCritical = true`, `FailOnHigh = true` — findings at
  these severities fail the job. TruffleHog findings are always mapped to
  `high` (verified or not), so with `FailOnHigh = true` even *unverified*
  secrets fail the build.
- **Report file names:** `semgrep.json`, `semgrep.sarif`, `trufflehog.json`,
  `zap.json`, `zap.xml`, `zap.html`. These must match what the scanners write
  and what the Python parsers expect.
- **Artifact names:** `trufflehog`, `semgrep`, `zap` — the DefectDojo stage
  downloads these by name, so keep them in sync if renamed.
- **DefectDojo:** `EnableDefectDojo` (default `false`) turns the optional
  DefectDojo stage on/off; `DefectDojoUrl` + `DefectDojoApiToken` (a **secret**)
  point at the instance; `DefectDojoProductName` / `DefectDojoProductTypeName` /
  `DefectDojoEngagementName` select (and create) the product type/product/
  engagement; `DefectDojoImportMode` controls `import` vs `reimport`;
  `DefectDojoPool` + `DefectDojoAgentName` select the agent pool and (optionally)
  pin the job to a specific agent.

### `deployment.yml` — VM + DAST settings

| Variable             | Default                                           | Purpose                                  |
|----------------------|---------------------------------------------------|------------------------------------------|
| `VmPool`             | `cloud-poc`                                       | Self-hosted agent pool on the VM         |
| `DeploySourcePath`   | `$(Pipeline.Workspace)/drop`                      | Where the Deploy job downloads the artifact |
| `SitePath`           | `C:\site`                                         | Where the app is deployed on the VM      |
| `ApplicationUrl`     | `http://localhost:5000`                           | Reachability probe + DAST target         |
| `WindowsServiceName` | `WebSample`                                       | Windows service that hosts the app (stopped/started around the copy) |
| `StartCommand`       | *(empty)*                                         | Self-hosted launch command; leave empty when using a Windows service |
| `WaitTimeoutSeconds` | `300`                                             | Deploy probe timeout                     |
| `ProbeIntervalSeconds`| `5`                                              | Deploy probe interval                    |
| `ZapPath`            | `C:\Program Files\ZAP\Zed Attack Proxy\zap.bat`   | Pre-installed ZAP launcher on the VM     |
| `ZapTarget`          | `$(ApplicationUrl)`                               | URL ZAP scans                            |
| `ZapTimeout`         | `600`                                             | ZAP spider + active-scan budget          |
| `ZapApiPort`         | `8090`                                            | ZAP REST API port                        |

**Hosting modes are mutually exclusive.** If `WindowsServiceName` is set, the
app is stopped/started as a service; otherwise `StartCommand` launches a
self-hosted app. Leave one empty. The service must already be registered on the
VM (e.g. via NSSM) — the pipeline only stops/starts it, it does not create it.

---

## 7. Policy gates and the severity model

All scanner reports are normalized into a single model with five severities:
`critical`, `high`, `medium`, `low`, `info`.

Each security job ends with `policy_check.py`. It fails the job when the report
contains findings at a gated severity (`FAIL_ON_CRITICAL`, `FAIL_ON_HIGH`,
default both `true`). Its exit codes:

| Exit | Meaning                                             |
|------|-----------------------------------------------------|
| 0    | No findings above the threshold                     |
| 1    | Findings above the threshold (gate violated)        |
| 2    | Report missing/corrupt (a crashed scanner)          |

**TruffleHog special case:** every TruffleHog finding is normalized to `high`,
verified or not. TruffleHog's own `--fail` only exits non-zero for *verified*
secrets, so without this mapping a leak that couldn't be verified would silently
pass the gate. The finding message still marks verified secrets with
`(verified)`.

Because the gate runs on `condition: always()`, a missing report also fails the
job — a broken scanner can never silently pass.

---

## 8. Reports and artifacts

Raw scanner output is archived per scanner (`trufflehog`, `semgrep`, `zap`) by
each scanner job:

| Artifact        | Published by          | Contents                                          |
|-----------------|-----------------------|---------------------------------------------------|
| `trufflehog`, `semgrep`, `zap` | the scanner jobs | Original scanner files (`*.json`, `*.sarif`, `*.xml`, `*.html`) |

Download these from the pipeline run page (Artifacts → drop-down) after any run.
The DefectDojo stage (when enabled) downloads the same artifacts and imports
them (see stage 5).

---

## 9. Prerequisites and setup

### Azure DevOps organization

1. **Point a pipeline at `pipelines/azure-pipelines.yml`** (Pipelines → New
   pipeline → Azure Repos Git → select this repository).
2. Make sure the build can use hosted agents (`ubuntu-latest`) — no extra setup
   needed for those.

### DefectDojo instance (optional)

Only needed when `EnableDefectDojo` is `true`:

1. A running DefectDojo instance (this setup uses one deployed with Docker on
   an Ubuntu server).
2. A base URL (`DefectDojoUrl`, e.g. `http://<server>:<port>`) reachable from
   the `DefectDojoPool` agent.
3. An **API v2 token** (`DefectDojoApiToken`) created in DefectDojo: user icon
   (top right) → **API v2 Key** → copy the generated key. Store it as a
   **secret** (variable group / library secret), never in a variable file.
   It must belong to a user with permission to create products/engagements.
4. Nothing needs to be created in the UI: the import script creates the product
   type, product and engagement via the API on first import.

### The Windows VM (self-hosted agent)

The Deploy and DAST jobs run on the VM through a self-hosted agent. The VM needs:

1. **A self-hosted agent** registered in the pool named by `VmPool`
   (default `cloud-poc`).
2. **The .NET 10 runtime** (e.g. the ASP.NET Core Runtime or Hosting Bundle
   installer) so the deployed app can run. **Restart the agent service after
   installing** so the agent's environment picks up the new `PATH`.
3. **The application registered as a Windows service** named `WebSample` (e.g.
   via NSSM), running the app from `C:\site`. The pipeline only stops/starts this
   service — it does not create it. See section 13 for example registration.
4. **OWASP ZAP** installed at `ZapPath`
   (`C:\Program Files\ZAP\Zed Attack Proxy\zap.bat`), and a **Java runtime**
   (ZAP needs Java 11+, 17+ for newer versions) available on the agent's `PATH`.
5. **Python** on the VM for the ZAP policy gate. If the agent runs as Local
   System, a per-user Python install is not on its `PATH` — install Python
   machine-wide or add it to the system `PATH`. (Alternative: move that gate to
   a hosted job that downloads the `zap` artifact.)
6. Write access to `SitePath` (`C:\site`) for the agent account.

---

## 10. Triggering runs

```yaml
trigger:
  branches: { include: [main] }   # CI on every push
pr:
  branches: { include: [main] }   # PR validation
```

- A push to `main` runs the whole pipeline.
- A pull request against `main` runs it as PR validation.
- You can also run it manually from the Pipelines page (Run pipeline).

---

## 11. Troubleshooting

Practical guidance based on real issues hit during development.

### Pipeline-level

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `A sequence was not expected` in a stage template | Template missing the `stages:` wrapper | Ensure each template starts with `stages:` before `- stage:` |
| Arguments after a certain point silently ignored (e.g. `StartCommand` never bound) | A blank line inside a folded `>-` YAML block injects a literal newline into the value, splitting the argument string | Remove blank lines inside `arguments: >-` blocks |
| DefectDojo runs but reports are missing/empty | The stage depended only on Build, so it ran before scanners produced artifacts | `dependsOn: [SAST, DAST]` (with `succeededOrFailed()` when `EnableDefectDojo`) |

### DefectDojo

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `403 {"detail": "Invalid token."}` | The `DefectDojoApiToken` is not a valid API v2 key (e.g. a login password), or it was revoked/regenerated | Create a key in DefectDojo (user icon → API v2 Key) and set it as a secret variable |
| `400 Product Type "..." does not exist` | The import endpoint does not auto-create the Product Type | The script now creates it via `POST /api/v2/product_types/`; if it still fails, check the token's permissions |
| `400 Product "..." does not exist in Product_Type "..."` | The import endpoint does not auto-create the Product | The script now creates it via `POST /api/v2/products/` |
| Script reports "invalid scan type mapping 'System.Collections.Hashtable'" | The PowerShell task mangles CLI arguments containing `=` | The mapping is passed via the `DEFECTDOJO_SCAN_TYPES` env var, not as a CLI argument |
| Imports fail after a product type "already exists" but DefectDojo says it does not | PowerShell 5.1 mangled the inline JSON body (`-d '{"name":...}'`), so the API rejected it | The script sends JSON from a temp file (`-d @file`) to avoid the 5.1 quoting bug |
| Stage never runs | `EnableDefectDojo` is not `true` | Set `EnableDefectDojo: true` in `variables/security.yml` |

### Deploy / VM

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Application did not become reachable ... within 300s` and no app log | `dotnet` not on the agent's `PATH`, or the .NET runtime not installed | Install the .NET 10 runtime on the VM and restart the agent service |
| Deploy job fails with a non-zero "Process completed with exit code X" even though the copy/start steps looked fine | `robocopy` leaves `$LASTEXITCODE` set (its success codes are 0–7, i.e. non-zero); the PowerShell task treats it as a failure | `deploy.ps1` resets `$LASTEXITCODE` after `robocopy` and ends with an explicit `exit 0` |
| IIS: `Cannot read configuration file due to insufficient permissions` | Agent account cannot read IIS config (`inetsrv\config`) | Run the agent with sufficient rights — or host the app as a Windows service instead (simpler for this sample) |
| App not reachable during DAST but reachable at deploy time | A process started from the Deploy job is killed when the job ends (the agent terminates its per-job process tree) | Register the app as a Windows service (`WindowsServiceName`) so it survives between stages |

### ZAP / DAST

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Unable to access jarfile zap-2.17.0.jar` | `zap.bat` uses a relative jar path; it must run from the ZAP install directory | The script now launches ZAP with its own directory as the working directory |
| `NativeCommandError` from `java -version` | Windows PowerShell 5.1 treats native stderr as an error when `$ErrorActionPreference = 'Stop'` | The script temporarily relaxes EAP around the `java -version` call |
| Spider completes but the site tree is empty; `ascan` says `url_not_found` | ZAP resolved `localhost` to IPv6 (`::1`) while the app binds IPv4 only, so ZAP never reached it | The script normalizes `localhost` → `127.0.0.1` and seeds the URL into the tree |
| ZAP daemon never becomes ready on port 8090 | Java missing on the agent `PATH`, or ZAP can't start | Check the `java:` line and the dumped `zap-daemon.*.log` in the run output |
| Reports exported but the parsers reject them (`json.decoder.JSONDecodeError` / XML parse error) | The report file starts with a UTF-8 BOM (`.NET`'s `Encoding.UTF8` adds one) | `zap_scan.ps1` writes reports with BOM-less UTF-8; the parsers also open files with `utf-8-sig` so a BOM is tolerated either way |
| DAST job fails with a non-zero "Process completed" after the scan looked successful | A stale `$LASTEXITCODE` from a native command (e.g. `java`) | `zap_scan.ps1` ends with an explicit `exit 0` |

### General debugging tips

- The Deploy and ZAP scripts deliberately dump the app's/daemon's own stdout and
  stderr when something isn't reachable — read those lines first; they usually
  state the real error.
- Scanner reports are published as artifacts even on failed runs, so download
  them to see exactly what each scanner found.

---

## 12. Extending the pipeline

### Adding a new scanner (Trivy, Gitleaks, Checkov, …)

Exactly three things change:

1. **A job** in the relevant stage template (`templates/sast.yml` for static
   tools), following the existing pattern:
   `install → run (continueOnError) → archive (always) → policy_check`.
2. **A parser module** `scripts/parser/<scanner>.py` returning a list of
   `Finding` objects, registered in `scripts/shared/dispatch.py`.
3. **Variables** in `pipelines/variables/security.yml` (report file name,
   artifact name, version).

Nothing else changes — the policy gates pick new reports up automatically
because parsing is driven by the dispatcher.

If the DefectDojo stage is enabled, add one more `FILE=SCAN_TYPE` pair to the
`DEFECTDOJO_SCAN_TYPES` environment variable in `templates/defectdojo.yml` so
the new report is uploaded too.

### Building a real application instead of the sample

In `pipelines/variables/build.yml`, set `SampleProjectPath` to your real
project (and keep `BuildMode = publish`). If your main output assembly has a
different name, set `SampleArtifactFileName` too. No template changes needed.

### Recommended production hardening (marked TODO in the code)

- Replace ZAP's `api.disablekey=true` with a real API key stored as a pipeline
  secret, and restrict what ZAP may crawl.
- Bump scanner versions (e.g. `TrufflehogVersion`) to recent releases.

> The sample app is already hosted as a Windows service (so it survives
> restarts and is supervised) — the earlier "convert to a Windows service"
> hardening item is done. The self-hosted `StartCommand` path remains available
> for apps that are not registered as a service.

---

## 13. Setting up this pipeline for another repository

The pipeline is intentionally reusable: it contains no repository-specific
business logic, only variables. Reusing it for another repo is a
configuration exercise. Here is the full checklist.

### 1. Copy the pipeline into the target repo

Copy the whole `pipelines/` directory (and `global.json` if you want to pin the
same .NET SDK) into the target repository, keeping the folder layout intact.
The pipeline resolves every path relative to the repo root, so it works from any
repository as long as `pipelines/` is present.

### 2. Point Azure DevOps at it

In the target project: **Pipelines → New pipeline → Azure Repos Git → select the
repo → Existing Azure Pipelines YAML file → `pipelines/azure-pipelines.yml`.**

Then confirm the organization prerequisites from section 9:

- Hosted agent pools (`ubuntu-latest`) are usable.
- The **self-hosted VM pool** (`VmPool`, default `cloud-poc`) exists and the VM
  has a registered agent.

### 3. Adjust the build to your project

In `pipelines/variables/build.yml`:

| Variable            | Change it to                                             |
|---------------------|----------------------------------------------------------|
| `SampleProjectPath` | Your project path, e.g. `src/MyApp/MyApp.csproj`          |
| `PublishFramework`  | Your target framework (e.g. `net8.0`)                     |
| `BuildMode`         | Keep `publish`, or use `copy` to ship pre-built files     |
| `ArtifactName`      | Keep `drop` unless you rename it consistently             |
| `SampleArtifactFileName` | Your main output assembly (e.g. `MyApp.dll`)          |

`SampleArtifactFileName` is what the Build stage verifies after publishing and
what `deploy.ps1` pre-flights in `SitePath`, so no template/script edits are
needed when renaming your assembly.

If your repo's SDK differs, either adjust `global.json` or remove it.

### 4. Point the deployment at your VM / service

In `pipelines/variables/deployment.yml`:

| Variable             | Change it to                                                     |
|----------------------|------------------------------------------------------------------|
| `VmPool`             | Your self-hosted agent pool name                                 |
| `SitePath`           | Where the app is deployed on the VM (e.g. `C:\site`)             |
| `ApplicationUrl`     | The URL your app listens on (must match the app's binding)       |
| `WindowsServiceName` | The name of your app's Windows service on the VM                 |
| `StartCommand`       | Leave empty when using a service; otherwise the launch command   |

**Register the app as a Windows service on the VM** (the pipeline only
stops/starts it). With NSSM, for example:

```bat
nssm install WebSample "C:\Program Files\dotnet\dotnet.exe" "C:\site\WebSample.dll"
nssm set WebSample AppDirectory C:\site
nssm start WebSample
```

Also make sure `ApplicationUrl` matches the port your application actually binds
to — the Deploy probe and the ZAP scan both use it.

### 5. Tune the scanners

In `pipelines/variables/security.yml`:

- `SemgrepRules` (e.g. `p/security-audit`) and `SemgrepConfigFile` for custom
  rules.
- `TrufflehogVersion` / `SemgrepVersion` — bump to recent releases.
- `FailOnCritical` / `FailOnHigh` — the gate that breaks the build.
- Report file names and artifact names normally stay at their defaults; change
  them only if you also update the parsers in `scripts/parser/` and the
  dispatcher in `scripts/shared/dispatch.py`.

The SAST jobs scan the whole repository (`$(Build.SourcesDirectory)`), and the
ZAP stage is already target-agnostic, so no per-repo logic is needed there.

### 6. Adjust triggers (optional)

The default triggers in `azure-pipelines.yml` run on `main`. Change them to
match your repo's branch strategy if it differs.

### 7. Verify

1. Run the pipeline once with a low-impact change (or from the Pipelines page).
2. Confirm Build produces the artifact, SAST produces findings, Deploy starts
   the service, DAST scans it, and DefectDojo (when enabled) imports the
   reports.
3. If a stage fails, see section 11 — the scripts are written to print the
   actual error rather than fail silently.
# Design & Architecture — Security Pipeline

**Audience:** the team (engineers, security, infra)
**Scope:** *why* the pipeline is designed the way it is, the tool choices and
our reasoning, how everything fits together, and how to deploy/modify it.
For line-by-line implementation details, see `doc.md`.

---

## 1. Overview

We run a fully automated, security-gated CI/CD pipeline that builds a web
application, runs a layered set of security scans, deploys it to a Windows VM,
actively scans the running app, and centralises findings for triage.

```
Build → SAST → MSDO → Deploy → DAST → Publish → DefectDojo (optional)
```

The design goal is a **shift-left, defence-in-depth** pipeline where security
gates are enforced automatically and every result is captured — even on
failure — so the team always knows what happened.

## 2. Design goals and principles

1. **Shift left, layer it** — several complementary scanners at different
   stages (source → build → runtime) so no single tool is a single point of
   failure.
2. **Gate, don't just report** — critical/high findings fail the pipeline;
   nothing security-relevant is deployable without sign-off.
3. **Never lose reports** — the reporting stage always runs, so a failing
   scanner can't destroy visibility.
4. **Configuration over code** — the team changes behaviour through variables,
   not pipeline code. Most day-to-day changes are one variable.
5. **Modular and reusable** — one thin orchestrator, one file per stage, so
   the pipeline is readable and portable to other repositories.
6. **Self-hosted where it matters** — the DAST scanner and findings store run
   in our own environment (data control, cost).

## 3. Architecture diagram

> **TODO:** add the architecture diagram here (build it in
> `diagrams/architecture.mmd`, see `diagrams/pipeline-flow.mmd` for the stage
> flow). Suggested content: Azure DevOps orchestrator → hosted agents
> (Linux/Windows) for Build/SAST/MSDO/Publish; self-hosted Windows VM for
> Deploy/DAST; DefectDojo (Docker on Ubuntu) receiving imports; artifacts
> flowing between stages; the HTML dashboard.

```
[ Developers / Repo ] ─► [ Azure DevOps Pipeline ]
                              │
        ┌─────────────────────┼──────────────────────┐
        ▼                     ▼                      ▼
   Hosted Linux         Hosted Windows         Self-hosted Windows VM
   (Build, SAST,        (MSDO)                 (Deploy + DAST/ZAP)
   Publish, optional
   DefectDojo)
        │                     │                      │
        └──────── artifacts ──┴──────────────────────┘
                              ▼
                      [ Publish → HTML dashboard ]
                              ▼
                 [ DefectDojo (Docker, Ubuntu) ]  (optional)
```

*(ASCII sketch — replace with a proper diagram, see TODO.)*

## 4. Tool selection and rationale

### 4.1 Azure DevOps (orchestration)

- **What:** the CI/CD platform hosting the pipeline (YAML templates, hosted
  agents, artifacts, PR triggers).
- **Why:** already the org's DevOps platform; first-class YAML pipelines,
  hosted agents, artifact staging, and simple integration with Azure Repos/PRs.
  The pipeline is written to be portable (see section 9) in case that changes.

### 4.2 .NET / ASP.NET Core (sample application)

- **What:** a minimal web app (`src/WebSample/`, `net10.0`) that the pipeline
  builds, deploys and scans.
- **Why:** gives every stage something real to work on end-to-end. It is
  replaceable via variables — the pipeline contains no app-specific logic.

### 4.3 TruffleHog (secret detection)

- **What:** scans the repository (and git history) for leaked secrets —
  API keys, tokens, connection strings, private keys.
- **Why:** secrets are the highest-likelihood, highest-impact leak; catching
  them at the source is cheap. TruffleHog is open source, actively maintained,
  and detects hundreds of secret types.
- **Design decision:** unverified secrets are still treated as **high** — a
  secret that can't be verified would otherwise silently pass (TruffleHog's
  own `--fail` only fails on verified results), which is not acceptable.

### 4.4 Semgrep (static analysis)

- **What:** pattern-based static analysis over the codebase.
- **Why:** fast, runs on any language, ships high-quality rulesets
  (`p/security-audit`), and supports custom rules via a config file — a good
  ratio of findings-per-noise for CI.

### 4.5 Microsoft Security DevOps / MSDO (supplemental scanning)

- **What:** a bundle of Microsoft security tools (BinSkim, Bandit, Checkov,
  Terrascan, Trivy, template analyzers, malware) producing one SARIF report.
- **Why:** broad coverage with near-zero configuration — binaries,
  dependencies, IaC templates, and malware signatures in one task. Windows-only,
  hence the Windows hosted agent.

### 4.6 OWASP ZAP (dynamic analysis)

- **What:** active DAST against the *deployed* app (spider + active scan).
- **Why:** the de-facto standard open-source DAST — free (Apache 2.0), OWASP
  flagship, actively maintained, fully automatable (headless + REST API), and
  self-hosted so scan traffic stays in our environment. See
  `owasp-zap-doc.md` for the full evaluation and the approval case.

### 4.7 DefectDojo (finding management) — optional

- **What:** a vulnerability management platform where all scanner findings are
  imported and triaged.
- **Why:** aggregating findings from many scanners in one place (with
  deduplication, severity, and history) makes triage and remediation tracking
  sustainable. Self-hosted (Docker) — findings stay in our control.

### 4.8 Reporting scripts (Python)

- **What:** `aggregate.py` normalises every scanner's output into one model;
  `generate_html.py` renders a single-page dashboard.
- **Why:** scanner formats differ wildly; a common model decouples scanners
  from reporting. Adding a scanner is then purely additive.

### 4.9 Self-hosted agents (Windows VM)

- **What:** the Deploy and DAST jobs run directly on the target Windows VM.
- **Why:** deploy-on-target (no extra hop), ZAP is pre-installed there, and
  the app is hosted as a Windows service so it survives between stages.

## 5. Pipeline flow and stage design

| # | Stage      | Runs on                 | Input → Output                                    | Gate |
|---|------------|-------------------------|---------------------------------------------------|------|
| 1 | Build      | Hosted Linux            | repo → `drop` artifact                            | —    |
| 2 | SAST       | Hosted Linux            | repo → `trufflehog.json`, `semgrep.json`/`.sarif` | policy_check |
| 3 | MSDO       | Hosted Windows          | repo → `msdo.sarif`                               | policy_check |
| 4 | Deploy     | Self-hosted VM          | `drop` → running app on `C:\site`                 | reachability probe |
| 5 | DAST       | Self-hosted VM          | running app → `zap.json`/`.xml`/`.html`           | policy_check |
| 6 | Publish    | Hosted Linux (**always**) | all reports → `reports-html` dashboard          | —    |
| 7 | DefectDojo | `DefectDojoPool` agent  | all reports → DefectDojo imports                  | —    |

**Key decisions:**

- **Publish always runs** (`condition: always()`) so a failed scan never
  removes the reports.
- **Parallel SAST jobs** (TruffleHog + Semgrep) so one slow scanner doesn't
  block the other.
- **Each scanner archives its output** before any gate, so a gate failure
  still leaves the raw data available.
- **Policy gates run on `always()`** — a scanner that crashes (produces no
  report) fails the job instead of passing silently.
- **Deploy/DAST run on the VM itself** so the scan sees the real deployment,
  and `localhost` is normalised to `127.0.0.1` for ZAP's IPv4 expectations.

## 6. Data and artifact flow

```
Scanner jobs ──► publish raw artifacts (trufflehog, semgrep, msdo, zap)
     │
     ├─► Publish ──► aggregate.py ──► combined.json ──► generate_html.py ──► reports-html
     │
     └─► DefectDojo ──► import-scan per report (Trufflehog Scan, Semgrep JSON
                        Report, SARIF, ZAP Scan)
```

- Reports live in the agent's **staging area** only — never in the repository.
- The normalized model (`Finding` with tool/category/severity/rule/file/line)
  is the contract between scanners and reporting; new scanners plug in via a
  parser + a dispatcher entry.

## 7. Configuration architecture

Configuration is layered, deliberately:

```
azure-pipelines.yml
 ├── global.yml      (cross-cutting: agents, Python, report paths/names)
 ├── build.yml       (build mode, project, framework, artifact)
 ├── security.yml    (scanner versions/rules, policy gates, MSDO, DefectDojo)
 └── deployment.yml  (VM pool/paths, service, ZAP, publish toggle)
```

- **Behaviour** belongs in `templates/*.yml`; **values** belong in
  `variables/*.yml`.
- **Environment overrides** use Azure variable groups / library secrets (e.g.
  `DefectDojoUrl`, `DefectDojoApiToken`) so per-environment values never sit in
  the repo.
- **Secrets** (API tokens) are never committed — they are provided as secret
  variables.

## 8. Deployment guide

### 8.1 Azure DevOps

1. Create a pipeline pointing at `pipelines/azure-pipelines.yml`.
2. Install the **Microsoft Security DevOps** extension (needed for the MSDO
   stage).
3. Hosted agents `ubuntu-latest` / `windows-latest` are used automatically.

### 8.2 The Windows VM

1. Register a self-hosted agent in the pool named by `VmPool` (`cloud-poc`).
2. Install the **.NET 10 runtime**; restart the agent after install so `PATH`
   updates.
3. Register the app as a **Windows service** (`WindowsServiceName`, e.g.
   `WebSample`) running from `SitePath` (`C:\site`) — the pipeline only
   stops/starts it.
4. Install **OWASP ZAP** at `ZapPath` and a **Java runtime** on `PATH`.
5. Ensure the agent account can write to `SitePath` and reach `ApplicationUrl`.

### 8.3 DefectDojo (optional)

1. Run DefectDojo (we use Docker on an Ubuntu server).
2. Set `EnableDefectDojo: true`, `DefectDojoUrl`, and `DefectDojoApiToken`
   (API v2 key, as a secret).
3. Set `DefectDojoPool` (and optionally `DefectDojoAgentName`) so the import
   job runs where it can reach the instance.
4. Nothing needs to be created in the UI — the import script creates the
   product type, product, and engagement via the API on first import.

## 9. Modifying the pipeline

### Adding a new scanner
1. A **job** in the relevant stage template, following the existing pattern:
   install → run (`continueOnError`) → archive (always) → `policy_check`.
2. A **parser module** `scripts/parser/<scanner>.py` + a dispatcher entry.
3. **Variables** in `security.yml` (report file name, artifact name, version),
   and if DefectDojo is enabled, a `FILE=SCAN_TYPE` mapping in the
   `DEFECTDOJO_SCAN_TYPES` env var.

Nothing else changes — aggregation, reporting and DefectDojo pick it up
automatically.

### Building a real application
Change `SampleProjectPath` (and `SampleArtifactFileName` if the assembly name
differs) in `build.yml`. No template changes.

### Porting to another repository
Copy `pipelines/` and `global.json`; adjust variables; point Azure DevOps at
the file. The pipeline has no repo-specific logic.

### Tuning gates
`FailOnCritical` / `FailOnHigh` in `security.yml` control what fails the
build. `PublishReports` toggles the dashboard.

## 10. Security and risk considerations

- **Defence in depth:** secrets, static code, binaries/IaC/malware, and
  runtime behaviour are all scanned — no single tool is the only control.
- **Gates are strict:** verified *and* unverified secrets fail; missing
  reports fail (no silent passes).
- **DAST is controlled:** ZAP scans our own deployed sample in a sandboxed
  VM, never production; `ZapTimeout` bounds the scan.
- **Data control:** DAST traffic and findings stay in-house; DefectDojo is
  self-hosted; the dashboard is a build artifact, not a third-party SaaS.
- **Secrets hygiene:** tokens are pipeline secrets; the fixture secrets in
  `.hidden/` are git-ignored so malicious content can't be pushed.

## 11. Operational notes

- Publish always runs, so check the run page for `reports-html` even when a
  stage failed.
- Scanner raw outputs are per-scanner artifacts (`trufflehog`, `semgrep`,
  `msdo`, `zap`).
- For troubleshooting specific stages, see `doc.md` section 11 (symptom →
  cause → fix tables).

## 12. Roadmap / hardening

- **Diagram:** complete the architecture diagram (see TODO in section 3).
- **Scan policies:** tune ZAP's scan policy and Semgrep rules to reduce
  noise for our stack.
- **Version bumps:** keep `TrufflehogVersion` / `SemgrepVersion` current.
- **ZAP API key:** replace ZAP's disabled API key with a real secret.
- **More scanners:** e.g. SCA/container scanning (Trivy/Checkov) following the
  "add a scanner" pattern.
- **Notifications:** alert the team when a gate fails, not just via the
  pipeline result.

# Developer Guide — Our Security Pipeline

This guide explains, for developers, how the pipeline works at a conceptual
level, which knobs you are allowed (and expected) to turn, and how to change
the build to point at your own project. You should not need to read the
pipeline implementation to work with it day to day.

> Implementation detail lives in `doc.md`. This document is about what you
> need to *do* and *change*, not how the pipeline is written.

---

## 1. What the pipeline does (30-second version)

Every time you push to `main` (or open a PR against it), this happens
automatically:

1. **Build** — compiles the application into a deployable artifact.
2. **SAST** — scans the source code for secrets and code vulnerabilities.
3. **Deploy** — copies the built app to the Windows VM and starts it.
4. **DAST** — actively attacks the running app (OWASP ZAP) to find
   runtime vulnerabilities.
5. **DefectDojo** *(optional)* — uploads the findings to DefectDojo for
   central triage.

```
Build → SAST → Deploy → DAST → (DefectDojo)
```

**DefectDojo is optional** (off by default). When enabled it still uploads
whatever the scans produced, even if a scan stage failed.

## 2. Conceptual model

Think of the pipeline in four layers:

| Layer          | Who touches it                          | What it does                          |
|----------------|-----------------------------------------|---------------------------------------|
| **Code**       | Everyone (normal dev workflow)          | The source being built and scanned    |
| **Build**      | App owners                              | How your app is compiled and packaged |
| **Security**   | Security-minded config                   | Which scanners run and what fails the build |
| **Deploy/DAST**| Infra/VM owners                         | Where the app runs and how it's scanned |

Changes to **code** require no pipeline knowledge. Changes to **build**,
**security**, or **deployment** are done through **variables** (see section 4),
not by editing pipeline files.

## 3. The stages, conceptually

### Build
Turns your code into the thing that gets deployed. Two modes:
- **`publish`** (default): `dotnet publish` your project.
- **`copy`**: package a directory as-is (no compilation) — good for static
  sites or pre-built output.

### SAST (static analysis)
Two scanners run in parallel over the repository:
- **TruffleHog** — looks for leaked secrets/credentials in the code and
  history.
- **Semgrep** — looks for bug/vulnerability patterns in code
  (ruleset `p/security-audit`).

### Deploy
Copies the artifact to the Windows VM and starts the app (as a Windows
service). Nothing to do day-to-day unless you own the VM.

### DAST (dynamic analysis)
OWASP ZAP (already installed on the VM) attacks the *running* app: it crawls
it, then actively probes it for vulnerabilities. This catches things that only
exist at runtime.

### DefectDojo (optional)
Uploads the scanner reports to DefectDojo for central triage. Off by default;
see the `EnableDefectDojo` variable.

## 4. What you can change (variables)

All configuration lives in `pipelines/variables/`. You change values there;
you never edit the pipeline templates. These are the ones you are most likely
to touch:

### Build (`build.yml`) — most relevant to app developers

| Variable                 | Default                                   | What it does                              |
|--------------------------|-------------------------------------------|-------------------------------------------|
| `SampleProjectPath`      | `src/WebSample/WebSample.csproj`          | The project that gets compiled            |
| `BuildConfiguration`     | `Release`                                 | `Release` / `Debug`                       |
| `PublishFramework`       | `net10.0`                                 | Target framework                          |
| `BuildMode`              | `publish`                                 | `publish` (compile) or `copy` (no compile)|
| `CopySourcePath`         | `$(Build.SourcesDirectory)`               | What to copy when `BuildMode = copy`      |
| `SampleArtifactFileName` | `WebSample.dll`                           | Output file the build verifies exists     |
| `ArtifactName`           | `drop`                                    | Name of the deployable artifact           |
| `BuildOutputDir`         | `$(Build.ArtifactStagingDirectory)/out`   | Where build output is staged (rarely touched) |

### Security (`security.yml`) — when you need to tune scanners

| Variable                | Default          | What it does                                   |
|-------------------------|------------------|------------------------------------------------|
| `SemgrepRules`          | `p/security-audit` | Semgrep ruleset (or a rules file path)       |
| `SemgrepVersion`        | *(empty)*        | Empty = latest from PyPI                       |
| `TrufflehogVersion`     | `3.63.10`        | TruffleHog version to install                  |
| `TrufflehogDepth`       | *(empty)*        | Git history depth scanned (empty = full)       |
| `FailOnCritical`        | `true`           | Critical findings fail the build               |
| `FailOnHigh`            | `true`           | High findings fail the build                   |

> **Important:** TruffleHog findings are treated as `high` whether the secret
> is verified or not — a leaked secret that couldn't be *verified* still fails
> the build. There is no way to "silently pass" secrets.

### Deployment (`deployment.yml`) — infra/VM owners

| Variable               | Default                                             | What it does                         |
|------------------------|-----------------------------------------------------|--------------------------------------|
| `VmPool`               | `cloud-poc`                                         | Self-hosted agent pool (the VM)      |
| `SitePath`             | `C:\site`                                           | Where the app is deployed on the VM  |
| `ApplicationUrl`       | `http://localhost:5000`                             | App URL used by deploy probe + DAST  |
| `WindowsServiceName`   | `WebSample`                                         | Windows service hosting the app      |
| `ZapTarget`            | `$(ApplicationUrl)`                                 | URL OWASP ZAP scans                  |
| `ZapTimeout`           | `600`                                               | Scan budget (seconds)                |

### DefectDojo (`security.yml`) — optional, off by default

| Variable                     | Default       | What it does                           |
|------------------------------|---------------|----------------------------------------|
| `EnableDefectDojo`           | `false`       | Turn the DefectDojo stage on/off       |
| `DefectDojoUrl`              | *(empty)*     | Base URL of the instance               |
| `DefectDojoApiToken`         | *(secret)*    | API v2 key — store as a **secret**     |
| `DefectDojoProductName`      | `sample-app`  | Product in DefectDojo                  |
| `DefectDojoEngagementName`   | `CI-CD`       | Engagement in DefectDojo               |

### Usually left alone

`global.yml` (`AgentImage`, `PythonVersion`, report path, `ScriptsDir`) and
the report/artifact file names in `security.yml` — only touch these if you
know what you are doing.

## 5. Making the build your own

Point the pipeline at your project in `pipelines/variables/build.yml`:

```yaml
- name: SampleProjectPath
  value: src/MyApp/MyApp.csproj
- name: SampleArtifactFileName
  value: MyApp.dll      # must match your main output assembly
```

That is normally **all** you need. If your main assembly has a different name,
set `SampleArtifactFileName` — both the build verification and the deploy
pre-flight check use it, so you don't touch any pipeline code.

If you aren't compiling (static site, pre-built files), set:

```yaml
- name: BuildMode
  value: copy
- name: CopySourcePath
  value: src/my-static-site
```

## 6. Why the build might fail

- **Policy gate violated** — a scanner found critical/high findings. Open the
  run, download that scanner's artifact (e.g. `trufflehog`, `semgrep`, `zap`),
  and see exactly what was flagged and where.
- **Missing report** — a scanner crashed without producing output; the gate
  fails deliberately so a broken scan can never silently pass.
- **Unverified secret** — remember TruffleHog counts unverified secrets as
  `high`; rotate/remove it rather than trying to bypass the gate.

To temporarily allow a scan to fail without failing the build (e.g. while you
triage a backlog), set `FailOnCritical: false` and/or `FailOnHigh: false` in
`security.yml`. Do this knowingly — it weakens the gate.

## 7. Reports

- Each scanner publishes its raw output as its own artifact (`trufflehog`,
  `semgrep`, `zap`).
- Reports are **never committed** to the repo — download them from the run
  page (Artifacts → drop-down).
- When DefectDojo is enabled, the same reports are imported there for central
  triage.

## 8. Common tasks

| I want to...                                        | I do...                                                         |
|-----------------------------------------------------|-----------------------------------------------------------------|
| Build my own app                                    | Change `SampleProjectPath` (and `SampleArtifactFileName`)       |
| See what a scan found                               | Open the run → download the scanner's artifact                  |
| Stop the build failing on scanner findings          | Set `FailOnCritical`/`FailOnHigh` to `false` (temporarily)      |
| Bump a scanner version                              | Change `TrufflehogVersion` / `SemgrepVersion`                   |
| Change what Semgrep checks                          | Change `SemgrepRules`                                            |
| Point DAST at a different URL                       | Change `ZapTarget` / `ApplicationUrl`                            |
| Turn on DefectDojo                                  | Set `EnableDefectDojo: true` + the connection secrets            |
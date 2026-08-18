# OWASP ZAP — DAST Tool Adoption Proposal

**Audience:** Senior leadership / approval board
**Topic:** Selection of OWASP ZAP as our Dynamic Application Security Testing (DAST) tool
**Status:** For review and approval

---

## Executive summary

We propose adopting **OWASP ZAP (Zed Attack Proxy)** as our DAST tool. It runs
an automated "active scan" against our deployed web application on every
pipeline run, finding vulnerabilities that only exist at runtime (SQL
injection, cross-site scripting, broken access control, etc.).

OWASP ZAP is:

- **Free and open source** (Apache 2.0) — no licence fees, no per-scan or
  per-seat costs, and no vendor lock-in.
- **An OWASP flagship project**, continuously maintained by OWASP with
  commercial backing from Checkmarx.
- **Purpose-built for CI/CD automation** — it runs headless, exposes a REST
  API, and is the de-facto standard for free DAST.
- **Self-hosted** — all scanning happens inside our own environment, so scan
  data never leaves our infrastructure.

It is already installed on our deployment VM and wired into the pipeline, so
adoption costs nothing additional. We recommend approving OWASP ZAP for
ongoing use.

---

## 1. Background: why we need DAST

Static analysis (SAST) inspects source code but cannot prove how the running
application behaves. **Dynamic analysis (DAST)** exercises the *deployed*
application over HTTP the way an attacker would, which catches a distinct
class of defects:

- Runtime-only issues (misconfiguration, exposed endpoints, verbose errors).
- Framework/version-specific behaviour not visible in source.
- Input-handling flaws (XSS, SQL injection, path traversal) confirmed against
  the live app.
- Regressions introduced by configuration changes or deployment steps.

DAST is complementary to SAST, not a replacement — SAST finds issues early and
cheaply; DAST confirms what an attacker can actually reach.

## 2. Evaluation criteria

We selected our DAST tool against the following criteria, weighted by what
matters for a continuously-run, CI-integrated security scan:

| # | Criterion                  | Why it matters                                                     |
|---|----------------------------|---------------------------------------------------------------------|
| 1 | Cost / licensing           | Recurring per-seat or per-scan fees scale badly with CI usage       |
| 2 | Automation & CI support    | Must run headless, unattended, on every pipeline run                |
| 3 | Feature completeness       | Spidering, passive + active scanning, scan policies, reporting      |
| 4 | Community & maintenance    | Longevity, security of the tool itself, speed of bug fixes          |
| 5 | Data control / residency   | Where scan traffic and results are processed/stored                 |
| 6 | Extensibility              | Custom checks, scripts, integrations (e.g. our finding-management)  |
| 7 | Ease of integration        | Fit with our existing stack (Azure DevOps, Windows VM, DefectDojo)  |
| 8 | Documentation & training   | Ability for the team to learn and operate it                        |

## 3. Candidates compared

| Tool                    | Model            | Approx. cost               | CI automation | OSS | Notes |
|-------------------------|------------------|----------------------------|---------------|-----|-------|
| **OWASP ZAP**           | Open source      | Free (Apache 2.0)          | Excellent     | ✅  | OWASP flagship, REST API, headless, Docker |
| Burp Suite Community    | Open source (limited) | Free                | Limited       | ✅  | Manual tool; no automated active scan in the free tier |
| Burp Suite Professional | Commercial       | ~$449/seat/year            | Good (Pro)    | ❌  | Strong manual testing; per-seat licence, cost for CI scale |
| Burp Suite Enterprise   | Commercial       | ~$4k/year (per site)       | Excellent     | ❌  | Purpose-built for CI but a significant recurring cost |
| Acunetix (Invicti)      | Commercial       | High (per asset/year)      | Good          | ❌  | Strong scanner, closed source, licensing cost |
| Netsparker / Invicti    | Commercial       | High                       | Good          | ❌  | Proof-based scanning, commercial pricing |
| Veracode DAST           | Commercial SaaS  | High (platform)            | Good          | ❌  | Strong, but cloud SaaS + platform lock-in |
| HCL AppScan / Qualys WAS| Commercial       | High                       | Good          | ❌  | Enterprise suites, heavy licensing |
| Other OSS (Nikto, w3af, Arachni, Wapiti) | Open source | Free           | Poor–ok       | ✅  | Not a full, actively-maintained DAST platform |

**Shortlist:** ZAP, Burp Suite (Pro/Enterprise), and one commercial scanner.
All commercial candidates were excluded for recurring licensing cost,
closed-source distribution, and (for SaaS options) moving scan traffic to a
third-party cloud. ZAP delivers the same core capability for free.

## 4. Why OWASP ZAP

### 4.1 Cost and licensing
ZAP is distributed under the **Apache 2.0** licence. There are no seat
licences, no per-scan charges, and no annual renewal. Because DAST runs on
every pipeline run, per-scan pricing would otherwise be a material ongoing
cost. Using ZAP keeps the security budget focused on remediation rather than
tooling.

### 4.2 Proven, actively maintained
ZAP is one of the **OWASP flagship projects** and is the most widely used
open-source DAST tool. Development is actively funded and maintained by OWASP
and Checkmarx. It ships regular releases (we currently use **2.17.0**) with
an active community, a public issue tracker, and security fixes released
promptly.

### 4.3 Feature set
ZAP covers the full DAST workflow:

- **Traditional and AJAX spider** to discover URLs and page structure.
- **Passive scanning** (analyses all traffic for weaknesses without changing
  requests).
- **Active scanning** with configurable **scan policies** per vulnerability
  class.
- **Fuzzing**, **WebSocket** support, and session/authentication handling.
- **Scripting console** and a marketplace of add-ons for custom checks.
- **HTML / JSON / XML report** output (and SARIF via add-on) — we consume the
  XML/JSON reports in the pipeline.

### 4.4 Automation and CI/CD
ZAP was designed to be driven headlessly:

- **Headless daemon mode** with a **REST API** (which our pipeline script
  uses to run the spider and active scan and export reports).
- An **Automation Framework** for declarative, reproducible scan definitions.
- Official **Docker image** and CI integrations (GitHub Actions, etc.).
- Runs identically on Windows, Linux and in containers — no GUI required.

This is exactly the shape required to run a scan on every build with no manual
intervention.

### 4.5 Data control and residency
ZAP runs **inside our environment** (on our deployment VM), so scan traffic
and results never leave our infrastructure. Commercial SaaS scanners would
require sending application traffic and results to a third-party cloud. For an
application under development this is a meaningful data-governance advantage.

### 4.6 Integration with our stack
ZAP is already integrated and proven in our pipeline:

1. The pipeline deploys the app to the Windows VM.
2. `zap_scan.ps1` starts ZAP headless, runs the spider and active scan, and
   exports `zap.json` / `zap.xml` / `zap.html`.
3. Results are archived, gated by policy, and imported into DefectDojo (which
    has first-class `ZAP Scan` support).

No re-work or additional tooling is required to adopt it.

## 5. How we use it (deployment summary)

- ZAP is **pre-installed on the deployment VM** (`ZapPath`), never downloaded
  by the pipeline.
- The **DAST stage** runs after a successful deploy and scans
  `ApplicationUrl` (the running app) with a spider + active scan.
- **Policy gate:** critical/high ZAP findings fail the build (see
  `FailOnCritical` / `FailOnHigh`).
- All ZAP outputs are archived, gated by policy, and imported into DefectDojo.

All behaviour is configurable through pipeline variables (scan target, timeout,
ZAP API port, report names) — no pipeline code changes are needed for tuning.

## 6. Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| False positives from active scanning | Wasted triage time | Scan policies and severity gating; findings triaged in DefectDojo; ZAP's active scanner can be tuned |
| Scan duration | Slower pipelines | Scans the deployed sample app (single page set); `ZapTimeout` caps the budget; scans run on the VM, not a shared agent |
| Active scan against a fragile app | Availability | DAST runs against our own deployed sample in a controlled environment; it is not run against production |
| Tool maintenance | Project lapses | OWASP flagship + Checkmarx backing; regular releases; team tracks `ZapTimeout`/version bumps in variables |
| Unverified secrets style false confidence | — | Policy gate fails on critical/high ZAP findings; results land in DefectDojo for review |

## 7. Conclusion and decision requested

OWASP ZAP is the strongest fit among the evaluated DAST tools for a
continuously-run, CI-integrated security pipeline:

- **Free**, open source, no licence or per-scan cost.
- **Active, industry-standard** project (OWASP flagship).
- **Fully automatable** and already integrated into our pipeline.
- **Self-hosted**, keeping scan data in our environment.

**Decision requested:** approval to use OWASP ZAP as our DAST tool as
described above. No budget or procurement action is required.

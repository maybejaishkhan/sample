---
marp: true
theme: default
paginate: true
style: |
  /* ============ Base ============ */
  section {
    font-family: Inter, sans-serif;
    background: #f5f7fa;
    color: #1a2b3c;
    padding: 56px 64px;
    letter-spacing: 0.1px;
  }
  h1 { color: #0b1b2b; font-weight: 700; }
  h2 {
    color: #0078d4;
    font-size: 40px;
    font-weight: 700;
    margin: 0 0 8px 0;
    padding-bottom: 12px;
    border-bottom: 3px solid #0078d4;
    display: inline-block;
  }
  h3 { color: #0b1b2b; font-size: 26px; margin: 18px 0 8px 0; }
  p, li { font-size: 22px; line-height: 1.55; }
  li { margin: 6px 0; }
  a { color: #0078d4; text-decoration: none; }
  code {
    background: #e8eef4;
    color: #b5192d;
    font-size: 0.9em;
    padding: 2px 6px;
    border-radius: 4px;
  }
  section::after {
    color: #7a8ba0;
    font-size: 14px;
  }
  section footer {
    color: #7a8ba0;
    font-size: 13px;
    letter-spacing: 0.4px;
  }

  /* ============ Utilities ============ */
  .center { text-align: center; }
  .muted { color: #5c6f82; }
  .small { font-size: 18px; }
  .tiny { font-size: 15px; color: #5c6f82; }
  .accent { color: #0078d4; }
  .ok { color: #107c10; }
  .bad { color: #c50f1f; }
  .mt { margin-top: 18px; }
  .mb { margin-bottom: 12px; }

  /* ============ Layout helpers ============ */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; margin-top: 18px; }
  .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 22px; margin-top: 18px; }

  .card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 5px solid #0078d4;
    border-radius: 10px;
    padding: 20px 22px;
    box-shadow: 0 2px 8px rgba(11, 27, 43, 0.06);
  }
  .card h3 { margin-top: 0; font-size: 22px; }
  .card p, .card li { font-size: 19px; }
  .card ul { padding-left: 20px; margin: 6px 0; }

  .chip {
    display: inline-block;
    background: #eaf2fb;
    color: #005a9e;
    border: 1px solid #cfe3f5;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 16px;
    font-weight: 600;
    margin: 3px 4px 3px 0;
  }

  .pill {
    display: inline-block;
    border-radius: 6px;
    padding: 3px 12px;
    font-size: 16px;
    font-weight: 700;
    color: #fff;
    margin-right: 8px;
  }
  .pill-blue { background: #0078d4; }
  .pill-green { background: #107c10; }
  .pill-orange { background: #d83b01; }
  .pill-navy { background: #1b3a5b; }
  .pill-slate { background: #5c6f82; }

  .tool-logo {
    display: flex;
    align-items: center;
    gap: 18px;
  }
  .flow-img {
    width: 100%;
    max-height: 400px;
    object-fit: contain;
    margin-top: 6px;
  }
  .tool-logo img {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    border: 2px solid #dde6ef;
    background: #fff;
    object-fit: contain;
    padding: 4px;
  }

  .divider {
    background: linear-gradient(135deg, #0b1b2b 0%, #0f2b46 45%, #0078d4 100%);
    color: #ffffff;
  }
  .divider h1 {
    color: #ffffff;
    font-size: 52px;
    margin: 0;
  }
  .divider .rule {
    width: 90px;
    height: 5px;
    background: #50e6ff;
    border-radius: 3px;
    margin: 18px 0;
  }

  .lead {
    background: linear-gradient(160deg, #0b1b2b 0%, #123a5e 60%, #0078d4 130%);
    color: #ffffff;
  }
  .lead h1 { color: #fff; font-size: 58px; margin: 0; }
  .lead h3 { color: #50e6ff; font-weight: 600; font-size: 26px; letter-spacing: 1px; }
  .lead .byline { color: #cfe0f0; font-size: 21px; margin-top: 24px; }
  .lead .logos { display: flex; gap: 16px; margin-top: 30px; }
  .lead .logos img {
    width: 52px; height: 52px; border-radius: 50%;
    background: #fff; padding: 6px; object-fit: contain;
  }

  .big { font-size: 60px; font-weight: 800; color: #0078d4; }

  .quote {
    font-size: 30px;
    font-style: italic;
    color: #0b1b2b;
    border-left: 6px solid #0078d4;
    padding-left: 22px;
    margin-top: 26px;
  }

  table { font-size: 18px; border-collapse: collapse; width: 100%; margin-top: 14px; }
  th {
    background: #0f2b46;
    color: #fff;
    text-align: left;
    padding: 10px 14px;
  }
  td { padding: 9px 14px; border-bottom: 1px solid #e2e8f0; }
  tr:nth-child(even) td { background: #eef3f8; }
---

<!-- _class: lead -->
<!-- _paginate: false -->

<div class="center" style="margin-top:40px">

## **Cloud Pipelines POC**

# Moving Delivery to Cloud-Based CI/CD


<div class="byline">
Presented by <b>Jay Ntongwe</b><br/>
</div>

<br><br>

<div class="logos" style="justify-content:center">
  <img src="https://avatars.githubusercontent.com/u/6844498?v=4" alt="Azure" width="64" height="64"/>
  <img src="https://avatars.githubusercontent.com/u/6154722?v=4" alt="Microsoft"width="64" height="64"/>
  <img src="https://avatars.githubusercontent.com/u/79229934?v=4" alt="TruffleHog"width="64" height="64"/>
  <img src="https://avatars.githubusercontent.com/u/29760937?v=4" alt="Semgrep"width="64" height="64"/>
  <img src="https://avatars.githubusercontent.com/u/6716868?v=4" alt="OWASP ZAP"width="64" height="64"/>
  <img src="https://avatars.githubusercontent.com/u/35606478?v=4" alt="DefectDojo"width="64" height="64"/>
</div>
<span class="tiny" style="color:#9db8d2">Azure DevOps · Azure Pipelines · Shift-Left Security</span>

</div>

---

<!-- _class: divider -->
# Agenda

<div class="rule"></div>

<div class="grid-2 small">

<div>

1. **Why change**: the manual FTP status quo
2. **The vision**: cloud pipelines in Azure
3. **Pipeline at a glance**
4. **Stage-by-stage tour**: Build, SAST, MSDO, Deploy, DAST, Publish, DefectDojo
5. **Security-first design**: policy gates & reports

</div>

<div>

6. **How it's built**: a modular, reusable pipeline
7. **Before vs. after**
8. **Benefits for the org**
9. **What's next**: production hardening
10. **Q&A**

</div>

</div>

---

<!-- _class: divider -->
# Where we are today

<div class="rule"></div>

### Shipping over FTP: manual, unguarded, unverifiable

---

# The status quo: manual FTP delivery

<div class="grid-2">

<div class="card">
<h3>Today's workflow</h3>
<ul>
<li>Developer builds <b>locally</b></li>
<li>Files uploaded to the server by <b>hand over FTP</b></li>
<li>Copy-paste, drag-drop, "it works on my machine"</li>
<li>Manual smoke test after upload</li>
<li>No central record of what shipped or when</li>
</ul>
</div>

<div class="card">
<h3>The problems</h3>
<ul>
<li><b>No security checks</b>: vulnerabilities ship silently</li>
<li><b>No version traceability</b>: what's on the server?</li>
<li><b>Human error</b>: wrong file, wrong server, partial upload</li>
<li><b>No audit trail</b>: who deployed what, and why?</li>
<li><b>No central triage</b>: findings live nowhere</li>
</ul>
</div>

</div>

<div class="quote">
Security, consistency, and trust in delivery are hard to achieve when the last mile is a manual upload.
</div>

---

<!-- _class: divider -->
# The Vision

<div class="rule"></div>

### Move delivery into the cloud: automated, secure, and auditable on Azure

---

# The vision: cloud-based pipelines

<div class="grid-2">

<div class="card">
<h3>Automated end-to-end</h3>
<p>Every push to <code>main</code>, <code>master</code> or <code>develop</code>: and every pull request against them: triggers the full pipeline automatically:</p>
<p><b>build → secure → deploy → test → report → (triage)</b></p>
</div>

<div class="card">
<h3>Security by design</h3>
<ul>
<li><b>SAST</b>: static analysis & secret scanning</li>
<li><b>MSDO</b>: Microsoft Security DevOps</li>
<li><b>DAST</b>: dynamic testing of the live app</li>
<li><b>Policy gates</b>: block critical & high findings</li>
<li><b>Reports</b>: always published, never lost</li>
</ul>
</div>

</div>

<div class="mt">
<img src="https://avatars.githubusercontent.com/u/6844498?v=4" width="36"/>
&nbsp; <span style="font-size:24px; font-weight:600; color:#0b1b2b">Azure Pipelines + Azure DevOps = one repeatable, auditable release path</span>
</div>

---

# The pipeline at a glance

<img src="presentation/assets/pipeline-flow.svg" alt="Pipeline flow" class="flow-img" />

<div class="grid-3 small mt">

<div class="card" style="text-align:center"><b class="accent">Always runs</b><br/>Publish reports even when a scan fails: findings are never lost.</div>
<div class="card" style="text-align:center"><b class="accent">Gated</b><br/>Critical/high findings fail the build before anything ships.</div>
<div class="card" style="text-align:center"><b class="accent">Optional</b><br/>DefectDojo triage switches on via a single flag.</div>

</div>

---

# What runs where

| # | Stage | Runs on | Purpose |
|---|-------|---------|---------|
| 1 | **Build** | Hosted Linux | Publishes the app into the `drop` artifact |
| 2 | **SAST** | Hosted Linux | TruffleHog (secrets) + Semgrep (code) in parallel |
| 3 | **MSDO** | Hosted Windows | Microsoft Security DevOps → SARIF |
| 4 | **Deploy** | Self-hosted Windows VM | Installs the app as a Windows service |
| 5 | **DAST** | Self-hosted Windows VM | OWASP ZAP scans the running app |
| 6 | **Publish** | Hosted Linux | Aggregates findings → HTML dashboard, <b>always runs</b> |
| 7 | **DefectDojo** | `DefectDojoPool` agent | Uploads reports for central triage, <b>optional</b> |

<div class="tiny mt">The main pipeline file is intentionally thin: it chains one template per stage. Most changes never touch pipeline logic.</div>

---

<!-- _class: divider -->
# Stage-by-stage tour

<div class="rule"></div>

###### Build → SAST → MSDO → Deploy → DAST → Publish → (DefectDojo)

---

# Build & SAST

<div class="grid-2">

<div class="card">
<h3><span class="pill pill-blue">1</span> Build</h3>
<ul>
<li>Runs <code>dotnet restore</code> + <code>dotnet publish</code> on the sample app</li>
<li>Verifies the output exists, then publishes the <code>drop</code> artifact</li>
<li>A <code>copy</code> mode also ships pre-built/static content</li>
<li>No security scanning here: that comes next</li>
</ul>
</div>

<div class="card">
<h3><span class="pill pill-blue">2</span> SAST: two jobs in parallel</h3>
<div class="tool-logo mb">
<img src="https://avatars.githubusercontent.com/u/79229934?v=4" alt="TruffleHog"/>
<div>
<b>TruffleHog</b> scans the git history for leaked secrets & credentials
</div>
</div>
<div class="tool-logo">
<img src="https://avatars.githubusercontent.com/u/29760937?v=4" alt="Semgrep"/>
<div>
<b>Semgrep</b> performs static code analysis with rules
</div>
</div>
</div>

</div>

<div class="tiny mt">Each SAST job: <b>install → scan → archive results → policy gate</b>. If one scanner fails, the other still runs :output is always kept.</div>

---

# MSDO & Deploy

<div class="grid-2">

<div class="card">
<h3><span class="pill pill-blue">3</span> MSDO</h3>
<div class="tool-logo mb">
<img src="https://avatars.githubusercontent.com/u/6154722?v=4" alt="Microsoft"/>
<div><b>Microsoft Security DevOps</div>
</div>
<ul>
<li>BinSkim, Bandit, Checkov, Terrascan, Trivy & more</li>
<li>Runs on a hosted <b>Windows</b> agent</li>
<li>Emits one consolidated <b>SARIF</b> report</li>
</ul>
</div>

<div class="card">
<h3><span class="pill pill-blue">4</span> Deploy</h3>
<ul>
<li>Runs on the <b>self-hosted Windows VM</b> via agent pool <code>cloud-poc</code></li>
<li>Stops the service → copies the artifact to <code>C:\site</code> → starts it</li>
<li>App is hosted as a <b>Windows service</b> (survives between stages)</li>
<li>Probes <code>http://localhost:5000</code> until it answers</li>
</ul>
</div>

</div>

---

# DAST & Publish

<div class="grid-2">

<div class="card">
<h3><span class="pill pill-blue">5</span> DAST</h3>
<div class="tool-logo mb">
<img src="https://avatars.githubusercontent.com/u/6716868?v=4" alt="OWASP ZAP"/>
<div><b>OWASP ZAP</b>: already installed on the VM, never downloaded by the pipeline</div>
</div>
<ul>
<li>Starts ZAP headless, then <b>spiders</b> the app</li>
<li>Runs an <b>active scan</b> against discovered URLs</li>
<li>Exports <code>zap.json</code> + <code>zap.xml</code> + <code>zap.html</code></li>
</ul>
</div>

<div class="card">
<h3><span class="pill pill-blue">6</span> Publish</h3>
<ul>
<li>Downloads every scanner's raw artifact</li>
<li>Aggregates into one normalized <code>combined.json</code></li>
<li>Renders a single-page <b>HTML dashboard</b> (severity cards + tables)</li>
<li>Publishes <code>reports-html</code> + per-scanner artifacts</li>
<li><b>Runs even when scans fail</b>: <code>condition: always()</code></li>
</ul>
</div>

</div>

---

# DefectDojo: central triage (optional)

<div class="grid-2">

<div class="card">
<h3><span class="pill pill-green">7</span> Optional, flag-driven</h3>
<div class="tool-logo mb">
<img src="https://avatars.githubusercontent.com/u/35606478?v=4" alt="DefectDojo"/>
<div><b>DefectDojo</b>: single source of truth for findings</div>
</div>
<ul>
<li>Enabled with one variable: <code>EnableDefectDojo</code></li>
<li>Imports each report via the <b>API v2</b> (auth = secret token)</li>
<li>Product, product-type & engagement auto-created</li>
<li><code>reimport</code> mode closes findings that disappear</li>
</ul>
</div>

<div class="card">
<h3>Report → scan type mapping</h3>
<table>
<tr><th>Report</th><th>DefectDojo type</th></tr>
<tr><td><code>trufflehog.json</code></td><td>Trufflehog Scan</td></tr>
<tr><td><code>semgrep.json</code></td><td>Semgrep JSON Report</td></tr>
<tr><td><code>msdo.sarif</code></td><td>SARIF</td></tr>
<tr><td><code>zap.xml</code></td><td>ZAP Scan</td></tr>
</table>
</div>

</div>

<div class="tiny mt">All scanners → one dashboard + one triage backlog. Findings get tracked, assigned, and closed: not just printed.</div>

---

<!-- _class: divider -->
# Security-first design

<div class="rule"></div>

### Gates, severity model, and the "never lose a report" rule

---

# Policy gates & severity model

<div class="grid-2">

<div class="card">
<h3>A single severity model</h3>
<p>Every scanner's output is normalized into five severities:</p>
<p>
<span class="pill pill-slate">info</span>
<span class="pill pill-slate">low</span>
<span class="pill pill-orange">medium</span>
<span class="pill pill-navy">high</span>
<span class="pill pill-navy">critical</span>
</p>
<p class="small">All findings flow through one parser + one gate: consistency across tools.</p>
</div>

<div class="card">
<h3>Policy gates that mean it</h3>
<ul>
<li><code>FailOnCritical</code> & <code>FailOnHigh</code> are <b>on</b></li>
<li>Findings above the threshold <b>fail the job</b> → no risky deploy</li>
<li>TruffleHog findings are always <b>high</b>: even unverified secrets fail</li>
<li>A <b>missing/corrupt report</b> also fails (exit code 2): a broken scanner can never silently pass</li>
<li>Deploy/DAST are skipped on failure, but <b>Publish still runs</b></li>
</ul>
</div>

</div>

<div class="quote">
Gates make security a <b>hard requirement</b>, not a nice-to-have: while the always-on Publish stage guarantees we never lose the evidence.
</div>

---

# A reusable, modular pipeline

<div class="grid-3">

<div class="card">
<h3>Orchestration</h3>
<p class="small"><code>azure-pipelines.yml</code>: which stages run and in what order. Thin by design.</p>
</div>

<div class="card">
<h3>Templates</h3>
<p class="small">One file per stage under <code>pipelines/templates/</code>: <i>how</i> each stage runs.</p>
</div>

<div class="card">
<h3>Variables</h3>
<p class="small">Every configurable value in <code>pipelines/variables/</code>: <i>what</i> each stage uses.</p>
</div>

</div>

<div class="grid-2 mt">

<div class="card">
<h3>The rule of thumb</h3>
<p class="small"><b>Configuration changes go in <code>variables/</code>; behaviour changes go in <code>templates/</code> or <code>scripts/</code>.</b> No hardcoded path, URL, or version buried in a template.</p>
</div>

<div class="card">
<h3>Easy to extend</h3>
<p class="small">Adding a scanner (Trivy, Gitleaks, Checkov…) touches exactly <b>three</b> things: a job, a parser, and variables. Aggregation picks it up automatically.</p>
</div>

</div>

<div class="tiny mt">The same pipeline can be reused for another repository with configuration only: no business logic baked in.</div>

---

# Before vs. after

<table>
<tr><th></th><th>Before: manual FTP</th><th>After: cloud pipelines</th></tr>
<tr><td><b>Delivery</b></td><td class="bad">Hand-built, manually uploaded</td><td class="ok">Automated build → artifact on every push & PR</td></tr>
<tr><td><b>Security</b></td><td class="bad">None at delivery time</td><td class="ok">SAST + MSDO + DAST, gated on critical/high</td></tr>
<tr><td><b>Traceability</b></td><td class="bad">"It's on the server, I think"</td><td class="ok">Every run is versioned & auditable</td></tr>
<tr><td><b>Deploy</b></td><td class="bad">Drag-and-drop, error-prone</td><td class="ok">Robocopy to <code>C:\site</code>, service-managed, health-probed</td></tr>
<tr><td><b>Findings</b></td><td class="bad">Never tracked centrally</td><td class="ok">HTML dashboard + optional DefectDojo triage</td></tr>
<tr><td><b>Consistency</b></td><td class="bad">Depends on the person</td><td class="ok">Identical, repeatable pipeline for everyone</td></tr>
</table>

---

# What this means for the org

<div class="grid-2">

<div class="card">
<h3>Benefits</h3>
<ul>
<li><span class="ok">✓</span> <b>Shift-left security</b>: issues found before they ship</li>
<li><span class="ok">✓</span> <b>Faster, safer releases</b>: CI/CD replaces the FTP chore</li>
<li><span class="ok">✓</span> <b>Full audit trail</b>: who, what, when, and the evidence</li>
<li><span class="ok">✓</span> <b>One view of risk</b>: dashboard + central triage</li>
<li><span class="ok">✓</span> <b>Reusable</b>: onboard more apps with configuration only</li>
</ul>
</div>

<div class="card">
<h3>Proof it works</h3>
<ul>
<li>Sample app ships with <b>deliberate flaws</b> (<code>/echo</code> reflects input unescaped)</li>
<li>Deliberate fixtures: fake secrets, SQLi/XSS/SSRF code, EICAR malware sample</li>
<li>Scanners <b>actually flag them</b>: and the policy gates block the build</li>
<li>Reports land as downloadable artifacts on <b>every</b> run</li>
</ul>
</div>

</div>

<div class="tiny mt">The pipeline isn't just a demo: it fails loudly on real findings and keeps the evidence, which is exactly what production needs.</div>

---

<!-- _class: divider -->
# What's next

<div class="rule"></div>

### From POC to production hardening

---

# Roadmap & hardening

<div class="grid-2">

<div class="card">
<h3>Production hardening <span class="tiny">(tracked in the code)</span></h3>
<ul>
<li>Replace ZAP's open daemon key with a <b>real API key</b> stored as a secret</li>
<li>Restrict what ZAP may crawl</li>
<li>Wire the dashboard's file links to a <b>real code host</b></li>
<li>Bump scanner versions to recent releases</li>
</ul>
</div>

<div class="card">
<h3>Going live</h3>
<ul>
<li>Point build variables at a <b>real project</b>: no template changes needed</li>
<li>Per-environment overrides via <b>variable groups / library secrets</b></li>
<li>Enable <b>DefectDojo</b> for central, tracked triage</li>
<li>Register the VM service with <b>NSSM</b> so the app survives restarts</li>
</ul>
</div>

</div>

<div class="quote">
From a POC that proves the concept to a platform the whole org can adopt: without changing how developers write code.
</div>

---

<!-- _class: lead -->
<!-- _paginate: false -->

<div class="center" style="margin-top:60px">

# Thank you

## Moving to cloud-based pipelines isn't just about speed:

### it's about shipping with confidence.

<div class="byline" style="margin-top:34px">
<b>Jay Ntongwe</b><br/>
<span class="tiny" style="color:#9db8d2">Azure · Azure DevOps · Secure Delivery</span>
</div>

<div class="logos" style="justify-content:center">
  <img src="https://avatars.githubusercontent.com/u/6844498?v=4" alt="Azure"/>
  <img src="https://avatars.githubusercontent.com/u/6154722?v=4" alt="Microsoft"/>
  <img src="https://avatars.githubusercontent.com/u/79229934?v=4" alt="TruffleHog"/>
  <img src="https://avatars.githubusercontent.com/u/29760937?v=4" alt="Semgrep"/>
  <img src="https://avatars.githubusercontent.com/u/6716868?v=4" alt="OWASP ZAP"/>
  <img src="https://avatars.githubusercontent.com/u/35606478?v=4" alt="DefectDojo"/>
</div>

<div class="tiny" style="color:#9db8d2; margin-top:26px">Questions & discussion</div>

</div>

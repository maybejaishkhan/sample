---
theme: default
layout: cover
title: Cloud Pipelines POC
info: |
  ## Cloud Pipelines POC
  Moving delivery to cloud-based CI/CD on Azure & Azure DevOps.
  Presented by Jay Ntongwe.
author: Jay Ntongwe
keywords: Azure, Azure DevOps, CI/CD, Security, SAST, DAST
class: text-left
transition: slide-left
---

<div class="cover-inner">

## Cloud Pipelines POC

# Moving Delivery to Cloud-Based CI/CD


<div class="cover-byline">
Presented by <b>Jay Ntongwe</b><br/>
<span style="font-size:15px; color:#9db8d2;">Azure DevOps · Azure Pipelines · Shift-Left Security</span>
</div>

<div class="logos">
  <img src="/azure.png" alt="Azure"/>
  <img src="/microsoft.png" alt="Microsoft"/>
  <img src="/trufflehog.png" alt="TruffleHog"/>
  <img src="/semgrep.png" alt="Semgrep"/>
  <img src="/zap.png" alt="OWASP ZAP"/>
  <img src="/defectdojo.png" alt="DefectDojo"/>
</div>

</div>

---
layout: section
---

# Agenda

<div class="rule"></div>

<div class="grid-2 small">

<div>

1. Why we are moving off manual FTP
2. The vision: cloud pipelines in Azure
3. The pipeline at a glance
4. Walking through each stage
5. Policy gates and reports

</div>

<div>

6. How it is built: modular and reusable
7. Before and after
8. What this means for the org
9. What is next
10. Q&A

</div>

</div>

---
layout: section
---

# Where we are today

<div class="rule"></div>

### Shipping over FTP. Manual, unguarded, unverifiable.

---
layout: default
---

# The status quo: manual FTP delivery

<div class="grid-2">

<div class="card">
<h3>Today's workflow</h3>
<ul>
<li>A developer builds locally</li>
<li>Files get uploaded by hand over FTP</li>
<li>Copy-paste and drag-drop, "works on my machine"</li>
<li>A manual smoke test after the upload</li>
<li>No central record of what shipped, or when</li>
</ul>
</div>

<div class="card">
<h3>The problems</h3>
<ul>
<li>No security checks, so vulnerabilities ship quietly</li>
<li>No version traceability. What is actually on the server?</li>
<li>Human error: wrong file, wrong server, partial uploads</li>
<li>No audit trail. Who deployed what, and why?</li>
<li>Findings have nowhere to live</li>
</ul>
</div>

</div>

<div class="quote" style="margin-top:24px;">
When the last mile is a manual upload, you cannot fully trust what you shipped. And you cannot prove it either.
</div>

---
layout: section
---

# The Vision

<div class="rule"></div>

### Delivery in the cloud. Automated, secure, and auditable on Azure.

---
layout: default
---

# The vision: cloud-based pipelines

<div class="grid-2">

<div class="card">
<h3>Automated end to end</h3>
<p>Every push or pull request made against <code>main</code>, runs the whole pipeline:</p>
<p><b>build, secure, deploy, test, report, and optionally triage</b></p>
</div>

<div class="card">
<h3>Security by design</h3>
<ul>
<li><b>SAST</b> for static analysis and secret scanning</li>
<li><b>DAST</b> against the live app</li>
<li><b>Policy gates</b> that block critical and high findings</li>
<li><b>Reports</b>: per-scanner artifacts, kept even when a scan fails</li>
</ul>
</div>

</div>

<div class="center mt">
<br>
&nbsp; <span style="font-size:22px; font-weight:600; color:#0b1b2b">One repeatable, auditable release path, built on Azure Pipelines and Azure DevOps.</span>
</div>

---
layout: default
---

# The pipeline at a glance

<img src="/pipeline-flow.svg" alt="Pipeline flow" class="flow-img" />

<div class="grid-3 mt">

<div class="highlight-card" style="text-align:center"><b class="accent">Never lost</b><br/>Each scanner publishes its raw artifact even when a scan fails, so findings are never lost.</div>
<div class="highlight-card" style="text-align:center"><b class="accent">Gated</b><br/>Critical or high findings stop the build before anything ships.</div>
<div class="highlight-card" style="text-align:center"><b class="accent">Optional</b><br/>DefectDojo triage turns on with a single flag.</div>

</div>

---
layout: default
---

# What runs where

| # | Stage | Runs on | Purpose |
|---|-------|---------|---------|
| 1 | **Build** | Hosted Linux | Publishes the app into the `drop` artifact |
| 2 | **SAST** | Hosted Linux | TruffleHog (secrets) + Semgrep (code) in parallel |
| 3 | **Deploy** | Self-hosted Windows VM | Installs the app as a Windows service |
| 4 | **DAST** | Self-hosted Windows VM | OWASP ZAP scans the running app |
| 5 | **DefectDojo** | `DefectDojoPool` agent | Uploads reports for central triage, **optional** |

<div class="tiny mt">The main pipeline file is deliberately thin. It just chains one template per stage, so most changes never touch the pipeline logic.</div>

---
layout: section
---

# Stage-by-stage tour

<div class="rule"></div>

### Build, SAST, Deploy, DAST, then optionally DefectDojo.

---
layout: default
---

# Build & SAST

<div class="grid-2">

<div class="card">
<h3><span class="pill pill-blue">1</span> Build</h3>
<ul>
<li>Runs <code>dotnet restore</code> and <code>dotnet publish</code> on the sample app</li>
<li>Checks the output exists, then publishes it as the <code>drop</code> artifact</li>
<li>A <code>copy</code> mode can also ship pre-built or static content</li>
<li>No scanning here. That is the next stage's job.</li>
</ul>
</div>

<div class="card">
<h3><span class="pill pill-blue">2</span> SAST, two jobs in parallel</h3>
<div class="tool-logo mb">
<img src="/trufflehog.png" alt="TruffleHog"/>
<div><b>TruffleHog</b> walks the git history for leaked secrets and credentials</div>
</div>
<div class="tool-logo">
<img src="/semgrep.png" alt="Semgrep"/>
<div><b>Semgrep</b> runs static analysis with the <code>p/security-audit</code> rule set</div>
</div>
</div>

</div>

<div class="tiny mt">Each job follows the same pattern: install, scan, archive results, then a policy gate. If one scanner fails, the other still runs, and its output is always kept.</div>

---
layout: default
---

# Deploy

<div class="grid-2">

<div class="card">
<h3><span class="pill pill-blue">3</span> Deploy</h3>
<ul>
<li>Runs on the <b>self-hosted Windows VM</b> in the <code>cloud-poc</code> pool</li>
<li>Stops the service, copies files to <code>C:\site</code>, starts it again</li>
<li>Hosted as a <b>Windows service</b> so it survives between stages</li>
<li>Waits until the app answers at <code>http://localhost:5000</code></li>
</ul>
</div>

</div>

<div class="tiny mt">Deploy and DAST run on the VM itself, so the scans never leave the machine that serves the app.</div>

---
layout: default
---

# DAST

<div class="grid-2">

<div class="card">
<h3><span class="pill pill-blue">4</span> DAST</h3>
<div class="tool-logo mb">
<img src="/zap.png" alt="OWASP ZAP"/>
<div><b>OWASP ZAP</b> is already installed on the VM. The pipeline never downloads it.</div>
</div>
<ul>
<li>Starts ZAP headless, spiders the app, then runs an active scan</li>
<li>Exports <code>zap.json</code>, <code>zap.xml</code>, and <code>zap.html</code></li>
</ul>
</div>

</div>

---
layout: default
---

# DefectDojo, central triage (optional)

<div class="grid-2">

<div class="card">
<h3><span class="pill pill-green">5</span> Optional and flag-driven</h3>
<div class="tool-logo mb">
<img src="/defectdojo.png" alt="DefectDojo"/>
<div><b>DefectDojo</b> becomes the single source of truth for findings</div>
</div>
<ul>
<li>Enabled with one variable: <code>EnableDefectDojo</code></li>
<li>Imports each report through the <b>API v2</b> using a secret token</li>
<li>Product, product type, and engagement are created automatically</li>
<li><code>reimport</code> mode closes findings that disappear</li>
</ul>
</div>

<div class="card">
<h3>Report to scan type mapping</h3>
<table class="map-table">
<tr><th>Report</th><th>DefectDojo type</th></tr>
<tr><td><code>trufflehog.json</code></td><td>Trufflehog Scan</td></tr>
<tr><td><code>semgrep.json</code></td><td>Semgrep JSON Report</td></tr>
<tr><td><code>zap.xml</code></td><td>ZAP Scan</td></tr>
</table>
</div>

</div>

<div class="tiny mt">Each scanner's report is published as its own artifact + optional DefectDojo triage, so findings get tracked, assigned, and closed instead of just printed.</div>

---
layout: section
---

# Security-first design

<div class="rule"></div>

### Gates, a shared severity model, and a rule about never losing a report.

---
layout: default
---

# Policy gates & severity model

<div class="grid-2">

<div class="card">
<h3>A single severity model</h3>
<p>Every scanner's output normalizes into five levels:</p>
<p>
<span class="pill pill-slate">info</span>
<span class="pill pill-slate">low</span>
<span class="pill pill-orange">medium</span>
<span class="pill pill-navy">high</span>
<span class="pill pill-navy">critical</span>
</p>
<p class="small">One parser, one gate, so the tools stay consistent with each other.</p>
</div>

<div class="card">
<h3>Policy gates that mean it</h3>
<ul>
<li><code>FailOnCritical</code> and <code>FailOnHigh</code> are on</li>
<li>Anything above the threshold fails the job, so nothing risky ships</li>
<li>TruffleHog findings always count as high, even unverified ones</li>
<li>A missing or corrupt report fails too, so a broken scanner cannot pass silently</li>
<li>Deploy and DAST skip when a gate trips, but every scanner still publishes its raw artifact</li>
</ul>
</div>

</div>

<div class="quote" style="margin-top:24px;">
The gates make security a hard requirement. And because every scanner publishes its artifact even on failed runs, we never lose the evidence.
</div>

---
layout: default
---

# A reusable, modular pipeline

<div class="grid-3">

<div class="card">
<h3>Orchestration</h3>
<p class="small"><code>azure-pipelines.yml</code> decides which stages run and in what order. Deliberately thin.</p>
</div>

<div class="card">
<h3>Templates</h3>
<p class="small">One file per stage under <code>pipelines/templates/</code>. They define how each stage runs.</p>
</div>

<div class="card">
<h3>Variables</h3>
<p class="small">Every configurable value lives in <code>pipelines/variables/</code>. They define what each stage uses.</p>
</div>

</div>

<div class="grid-2 mt">

<div class="card">
<h3>The rule of thumb</h3>
<p class="small"><b>Configuration changes go in <code>variables/</code>. Behaviour changes go in <code>templates/</code> or <code>scripts/</code>.</b> No path, URL, or version is hardcoded in a template.</p>
</div>

<div class="card">
<h3>Easy to extend</h3>
<p class="small">Adding a scanner like Trivy, Gitleaks, or Checkov touches three things: a job, a parser, and variables. Aggregation picks it up automatically, and the same pipeline can be reused for another repository.</p>
</div>

</div>

---
layout: default
---

# Before vs. after

| | Before, manual FTP | After, cloud pipelines |
|---|---|---|
| **Delivery** | <span class="bad">Hand-built, manually uploaded</span> | <span class="ok">Automated build on every push and PR</span> |
| **Security** | <span class="bad">None at delivery time</span> | <span class="ok">SAST and DAST, gated on critical/high</span> |
| **Traceability** | <span class="bad">"It is on the server, I think"</span> | <span class="ok">Every run is versioned and auditable</span> |
| **Deploy** | <span class="bad">Drag-and-drop, error-prone</span> | <span class="ok">Robocopy to `C:\site`, service-managed, health-probed</span> |
| **Findings** | <span class="bad">Never tracked centrally</span> | <span class="ok">per-scanner artifacts, optional DefectDojo triage</span> |
| **Consistency** | <span class="bad">Depends on the person</span> | <span class="ok">The same pipeline for everyone, every time</span> |

---
layout: default
---

# What this means for the org

<div class="grid-2">

<div class="card">
<h3>Benefits</h3>
<ul>
<li><span class="check"></span> <b>Shift-left security</b>: issues get caught before they ship</li>
<li><span class="check"></span> <b>Faster, safer releases</b>: CI/CD replaces the FTP chore</li>
<li><span class="check"></span> <b>A full audit trail</b>: who, what, when, and the evidence</li>
<li><span class="check"></span> <b>One view of risk</b>: per-scanner artifacts plus central triage</li>
<li><span class="check"></span> <b>Reusable</b>: onboard more apps with configuration only</li>
</ul>
</div>

<div class="card">
<h3>Proof it works</h3>
<ul>
<li>The sample app ships with <b>deliberate flaws</b>, like <code>/echo</code> reflecting input unescaped</li>
<li>Test fixtures include fake secrets, SQLi, XSS, and SSRF code, plus an EICAR sample</li>
<li>The scanners actually flag them, and the policy gates block the build</li>
<li>Reports land as downloadable artifacts on every run</li>
</ul>
</div>

</div>

<div class="tiny mt">This is not just a demo. It fails loudly on real findings and keeps the evidence, which is exactly what production needs.</div>

---
layout: cover
---

<div class="cover-inner" style="margin-top:40px;">

# Thank You

Questions & discussion

</div>

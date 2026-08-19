// Minimal sample application used by the Azure DevOps pipeline to exercise the
// Build -> Deploy -> DAST flow end-to-end.
//
// NOTE: /echo intentionally reflects user input unescaped. This is a *sample*
// finding that lets OWASP ZAP and Semgrep demonstrate how results flow into the
// aggregated report. Do not use this pattern in a real application.

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.MapGet("/", () => Results.Text("WebSample is running."));

app.MapGet("/health", () => Results.Json(new { status = "ok" }));

app.MapGet("/echo", (string? q) => Results.Text($"Echo: {q}"));

app.Run();

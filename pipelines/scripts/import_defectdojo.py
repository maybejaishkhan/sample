#!/usr/bin/env python3
"""Upload raw scanner reports to a DefectDojo instance via the REST API.

For every known report file present under ``--raw`` this calls DefectDojo's
API v2 ``import-scan`` (or ``reimport-scan`` with ``--mode reimport``) so the
results land in DefectDojo. Product/engagement context is auto-created by
DefectDojo from the names passed here, so nothing needs to be set up in the UI
beforehand.

Report file -> scan type mapping defaults to this pipeline's well-known file
names (kept in sync with pipelines/variables/security.yml) and can be
extended/overridden with ``--scan-type FILE=SCAN_TYPE``:

    trufflehog.json  -> Trufflehog Scan
    semgrep.json     -> Semgrep JSON Report
    zap.xml          -> ZAP Scan

Environment variables (secrets are read from the environment so they never
appear on the command line):

    DEFECTDOJO_URL               Base URL, e.g. https://dd.example.com (no trailing /)
    DEFECTDOJO_API_TOKEN         API v2 token, sent as `Authorization: Token <token>`
    DEFECTDOJO_SCM_URI           Optional source code management URI (e.g. repo URL)
    DEFECTDOJO_SCM_BRANCH        Optional branch name (e.g. main)

Exit codes:
    0 - every present report was imported (or none were present)
    1 - at least one import failed
    2 - configuration error (missing setting/dependency/directory)
"""

import argparse
import datetime
import os
import sys
from urllib.parse import quote

try:
    import requests
except ImportError:  # pragma: no cover - environment issue, not tested
    print("ERROR: the 'requests' package is required (pip install requests)",
          file=sys.stderr)
    sys.exit(2)

#: Default raw report file name -> DefectDojo scan_type name. Overridable via
#: ``--scan-type`` (the pipeline passes the mapping from its variables so the
#: report file names stay defined in one place).
DEFAULT_SCAN_TYPES = {
    "trufflehog.json": "Trufflehog Scan",
    "semgrep.json": "Semgrep JSON Report",
    "zap.xml": "ZAP Scan",
}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True,
                        help="Directory containing raw scanner reports")
    parser.add_argument("--mode", choices=("import", "reimport"),
                        default="reimport",
                        help="Use import-scan (new test per run) or "
                             "reimport-scan (update a single test per scan "
                             "type within the engagement). Default: reimport")
    parser.add_argument("--product", required=True,
                        help="DefectDojo product name (auto-created if missing)")
    parser.add_argument("--engagement", required=True,
                        help="DefectDojo engagement name (auto-created if missing)")
    parser.add_argument("--product-type", default="",
                        help="Product type name (optional; auto-created if missing)")
    parser.add_argument("--scan-type", action="append", default=[],
                        metavar="FILE=SCAN_TYPE",
                        help="Override/add a report file to scan type mapping "
                             "(repeatable)")
    parser.add_argument("--insecure", action="store_true",
                        help="Skip TLS certificate verification (self-signed "
                             "DefectDojo certificates)")
    args = parser.parse_args()

    url = _env("DEFECTDOJO_URL")
    token = _env("DEFECTDOJO_API_TOKEN")
    scm_uri = _env("DEFECTDOJO_SCM_URI")
    scm_branch = _env("DEFECTDOJO_SCM_BRANCH")

    if not url or not token:
        print("ERROR: DEFECTDOJO_URL and DEFECTDOJO_API_TOKEN must be set.",
              file=sys.stderr)
        return 2
    if not os.path.isdir(args.raw):
        print(f"ERROR: raw reports directory {args.raw} not found.", file=sys.stderr)
        return 2

    endpoint = "import-scan" if args.mode == "import" else "reimport-scan"
    api_url = f"{url.rstrip('/')}/api/v2/{endpoint}/"

    scan_types = dict(DEFAULT_SCAN_TYPES)
    for override in args.scan_type:
        file_name, sep, scan_type = override.partition("=")
        if not sep or not file_name:
            print(f"ERROR: invalid --scan-type {override!r} (expected FILE=SCAN_TYPE)",
                  file=sys.stderr)
            return 2
        scan_types[file_name] = scan_type

    # Payload shared by every import. When product/engagement names are given
    # and the objects do not exist yet, DefectDojo auto-creates them (requires
    # engagement_end, which we set to the scan date).
    today = datetime.date.today().isoformat()
    payload = {
        "scan_date": today,
        "engagement_end": today,
        "minimum_severity": "Info",
        "active": True,
        "verified": True,
        "close_old_findings": True,
        "deduplication_on_engagement": True,
        "auto_create_context": True,
        "product_name": args.product,
        "engagement_name": args.engagement,
    }
    if args.product_type:
        payload["product_type_name"] = args.product_type
    if scm_uri:
        payload["source_code_management_uri"] = scm_uri
    if scm_branch:
        payload["source_code_management_branch"] = scm_branch

    headers = {"Authorization": f"Token {token}"}
    verify = not args.insecure
    session = requests.Session()

    # The import-scan endpoint does NOT auto-create the Product Type or the
    # Product - it only auto-creates the Engagement - so ensure the product
    # type, product and engagement exist via the API first. auto_create_context
    # is also passed to the import for versions that honour it.
    product_type_id = None
    if args.product_type:
        pt_response = session.post(
            f"{url}/api/v2/product_types/",
            headers=headers,
            json={"name": args.product_type},
            verify=verify,
            timeout=60,
        )
        if pt_response.status_code in (200, 201):
            product_type_id = pt_response.json().get("id")
            print(f"Created product type '{args.product_type}'.")
        else:
            for item in session.get(
                f"{url}/api/v2/product_types/?name={quote(args.product_type)}",
                headers=headers, verify=verify, timeout=60,
            ).json().get("results", []):
                if item.get("name") == args.product_type:
                    product_type_id = item.get("id")
                    break
            if product_type_id:
                print(f"Product type '{args.product_type}' already exists.")
            else:
                print(f"WARNING: could not ensure product type '{args.product_type}' "
                      f"(HTTP {pt_response.status_code}) - continuing.", file=sys.stderr)

    product_id = None
    if product_type_id:
        for item in session.get(
            f"{url}/api/v2/products/?name={quote(args.product)}",
            headers=headers, verify=verify, timeout=60,
        ).json().get("results", []):
            if item.get("name") == args.product and item.get("prod_type") == product_type_id:
                product_id = item.get("id")
                break
        if product_id:
            print(f"Product '{args.product}' already exists.")
        else:
            product_response = session.post(
                f"{url}/api/v2/products/",
                headers=headers,
                json={"name": args.product, "prod_type": product_type_id,
                      "description": args.product},
                verify=verify,
                timeout=60,
            )
            if product_response.status_code in (200, 201):
                product_id = product_response.json().get("id")
                print(f"Created product '{args.product}'.")
            else:
                print(f"WARNING: could not ensure product '{args.product}' "
                      f"(HTTP {product_response.status_code}) - continuing.", file=sys.stderr)

    if product_id:
        engagements = session.get(
            f"{url}/api/v2/engagements/?product={product_id}",
            headers=headers, verify=verify, timeout=60,
        ).json().get("results", [])
        if any(e.get("name") == args.engagement for e in engagements):
            print(f"Engagement '{args.engagement}' already exists.")
        else:
            engagement_response = session.post(
                f"{url}/api/v2/engagements/",
                headers=headers,
                json={"name": args.engagement, "product": product_id,
                      "engagement_type": "CI/CD",
                      "target_start": today, "target_end": today},
                verify=verify,
                timeout=60,
            )
            if engagement_response.status_code in (200, 201):
                print(f"Created engagement '{args.engagement}'.")
            else:
                print(f"WARNING: could not ensure engagement '{args.engagement}' "
                      f"(HTTP {engagement_response.status_code}) - continuing.",
                      file=sys.stderr)

    imported: list = []
    failed: list = []
    for file_name, scan_type in sorted(scan_types.items()):
        path = os.path.join(args.raw, file_name)
        if not os.path.isfile(path):
            print(f"skip: {file_name} (report not present)")
            continue

        # test_title lets reimport-scan find/update the same test on each run
        # instead of stacking a new test per pipeline run.
        request_payload = dict(payload, scan_type=scan_type, test_title=scan_type)

        with open(path, "rb") as handle:
            try:
                response = session.post(
                    api_url,
                    headers=headers,
                    data=request_payload,
                    files={"file": (file_name, handle)},
                    verify=verify,
                    timeout=120,
                )
            except requests.RequestException as exc:
                failed.append(file_name)
                print(f"ERROR: {file_name} -> {scan_type} "
                      f"(request failed): {exc}", file=sys.stderr)
                continue

        if response.ok:
            imported.append(file_name)
            print(f"ok: {file_name} -> {scan_type} (HTTP {response.status_code})")
        else:
            failed.append(file_name)
            print(f"ERROR: {file_name} -> {scan_type} "
                  f"(HTTP {response.status_code}): {response.text[:500]}",
                  file=sys.stderr)

    print(f"imported {len(imported)} report(s): {', '.join(imported) if imported else 'none'}")
    if failed:
        print(f"failed {len(failed)} report(s): {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def audit_generated_server(server_dir: str | Path) -> dict[str, Any]:
    root = Path(server_dir)
    build_report = _read_json(root / "pack2serve" / "build-report.json")
    validation_report = _read_optional_json(root / "pack2serve" / "validation-report.json")

    manual_actions = list(build_report.get("manual_actions", []))
    copied = list(build_report.get("copied_overrides", []))
    classifications = Counter(item.get("classification", "") for item in copied)
    unknown_examples = [
        item.get("destination", "")
        for item in copied
        if item.get("classification") == "unknown-isolated"
    ][:20]
    client_isolated = classifications["client-isolated"] + classifications["client-remote-isolated"]
    validation_status = validation_report.get("status") if validation_report else None

    checks = [
        _check(
            "remote-files",
            "pass" if not manual_actions else "fail",
            f"{len(manual_actions)} manual action(s)",
            manual_actions[:20],
        ),
        _check(
            "unknown-overrides",
            "pass" if classifications["unknown-isolated"] == 0 else "warning",
            f"{classifications['unknown-isolated']} unknown override file(s)",
            unknown_examples,
        ),
        _check(
            "client-isolated-content",
            "info" if client_isolated else "pass",
            f"{client_isolated} client-only or client-scoped file(s) isolated",
            {
                "client-isolated": classifications["client-isolated"],
                "client-remote-isolated": classifications["client-remote-isolated"],
            },
        ),
        _check(
            "startup-validation",
            "pass" if validation_status == "started" else "fail" if validation_status else "warning",
            validation_status or "not-run",
            validation_report.get("hints", []) if validation_report else [],
        ),
    ]
    level = _level(checks, validation_status)
    result = {
        "level": level,
        "serverEquivalent": level == "verified-equivalent",
        "pack": {
            "name": build_report.get("pack", {}).get("name", ""),
            "format": build_report.get("pack", {}).get("format", ""),
            "minecraftVersion": build_report.get("pack", {}).get("minecraft_version", ""),
            "loader": build_report.get("pack", {}).get("loader", {}),
        },
        "summary": {
            "manualActions": len(manual_actions),
            "unknownOverrides": classifications["unknown-isolated"],
            "clientIsolated": client_isolated,
            "validationStatus": validation_status or "not-run",
        },
        "checks": checks,
        "notes": _notes(level),
    }
    output_path = root / "pack2serve" / "compatibility-report.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _level(checks: list[dict[str, Any]], validation_status: str | None) -> str:
    by_id = {check["id"]: check for check in checks}
    if by_id["remote-files"]["status"] == "fail":
        return "incomplete"
    if validation_status and validation_status != "started":
        return "not-startable"
    if not validation_status:
        return "generated-not-validated"
    if by_id["unknown-overrides"]["status"] == "warning":
        return "startable-with-differences"
    return "verified-equivalent"


def _notes(level: str) -> list[str]:
    if level == "verified-equivalent":
        return [
            "All required remote files are resolved, no unknown overrides were isolated, and startup validation reached Done.",
            "Client-only files may still be isolated because a dedicated server should not load client-only content.",
        ]
    if level == "startable-with-differences":
        return [
            "The server starts, but some override files could not be safely classified as server content.",
            "Review _unknown-overrides before claiming parity with a LAN-hosted client instance.",
        ]
    if level == "generated-not-validated":
        return ["The server files were generated, but startup validation has not proven the server reaches Done yet."]
    if level == "not-startable":
        return ["Startup validation did not reach Done. Inspect pack2serve/validation-report.json and server logs."]
    return ["Some required files still need manual resolution before the server can be considered complete."]


def _check(id: str, status: str, message: str, details: Any) -> dict[str, Any]:
    return {
        "id": id,
        "status": status,
        "message": message,
        "details": details,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _read_json(path)

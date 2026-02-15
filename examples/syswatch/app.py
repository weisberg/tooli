"""System Health Inspector example app.

Monitor system resources with structured output for agents.
Showcases: ReadOnly annotation, paginated list commands, structured error codes,
stdlib OS calls (platform, os, shutil).
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from typing import Annotated, Any

from tooli import Option, Tooli
from tooli.annotations import ReadOnly
from tooli.errors import InputError, ToolRuntimeError

app = Tooli(name="syswatch", help="System health inspection tools")


@app.command(annotations=ReadOnly)
def status() -> dict[str, Any]:
    """System overview: OS, hostname, Python version, CPU count, load averages."""
    info: dict[str, Any] = {
        "hostname": platform.node(),
        "os": platform.system(),
        "os_version": platform.version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }

    try:
        load = os.getloadavg()
        info["load_avg_1m"] = round(load[0], 2)
        info["load_avg_5m"] = round(load[1], 2)
        info["load_avg_15m"] = round(load[2], 2)
    except (OSError, AttributeError):
        info["load_avg_1m"] = None
        info["load_avg_5m"] = None
        info["load_avg_15m"] = None

    return info


@app.command(paginated=True, annotations=ReadOnly)
def processes(
    *,
    sort_by: Annotated[str, Option(help="Sort by: pid or name")] = "pid",
    name_filter: Annotated[str | None, Option(help="Filter by process name substring")] = None,
) -> list[dict[str, Any]]:
    """List running processes."""
    if sort_by not in ("pid", "name"):
        raise InputError(
            message=f"Invalid sort field: {sort_by}. Use 'pid' or 'name'.",
            code="E4001",
            details={"sort_by": sort_by},
        )

    system = platform.system()

    if system in ("Darwin", "Linux"):
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise ToolRuntimeError(
                message=f"Failed to list processes: {exc}",
                code="E4002",
            ) from exc

        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:
            return []

        procs: list[dict[str, Any]] = []
        for line in lines[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue

            proc = {
                "user": parts[0],
                "pid": int(parts[1]),
                "cpu_percent": float(parts[2]),
                "mem_percent": float(parts[3]),
                "name": parts[10].split()[0] if parts[10] else "",
                "command": parts[10],
            }

            if name_filter and name_filter.lower() not in proc["command"].lower():
                continue

            procs.append(proc)
    else:
        raise ToolRuntimeError(
            message=f"Process listing not supported on {system}",
            code="E4003",
            details={"platform": system},
        )

    if sort_by == "name":
        procs.sort(key=lambda p: p["name"].lower())
    else:
        procs.sort(key=lambda p: p["pid"])

    return procs


@app.command(paginated=True, annotations=ReadOnly)
def disk(
    *,
    path: Annotated[str, Option(help="Path to check disk usage for")] = "/",
) -> list[dict[str, Any]]:
    """Disk usage statistics for a given path."""
    target = os.path.expanduser(path)
    if not os.path.exists(target):
        raise InputError(
            message=f"Path does not exist: {path}",
            code="E4004",
            details={"path": path},
        )

    try:
        usage = shutil.disk_usage(target)
    except OSError as exc:
        raise ToolRuntimeError(
            message=f"Failed to get disk usage for '{path}': {exc}",
            code="E4005",
            details={"path": path},
        ) from exc

    total_gb = round(usage.total / (1024**3), 2)
    used_gb = round(usage.used / (1024**3), 2)
    free_gb = round(usage.free / (1024**3), 2)
    percent_used = round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0

    return [{
        "mount": target,
        "total_gb": total_gb,
        "used_gb": used_gb,
        "free_gb": free_gb,
        "percent_used": percent_used,
    }]


@app.command(paginated=True, annotations=ReadOnly)
def network() -> list[dict[str, Any]]:
    """Network interface information."""
    system = platform.system()

    if system == "Darwin":
        cmd = ["ifconfig"]
    elif system == "Linux":
        cmd = ["ip", "-brief", "addr"]
    else:
        raise ToolRuntimeError(
            message=f"Network info not supported on {system}",
            code="E4006",
            details={"platform": system},
        )

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise ToolRuntimeError(
            message=f"Failed to get network info: {exc}",
            code="E4007",
        ) from exc

    interfaces: list[dict[str, Any]] = []

    if system == "Darwin":
        current: dict[str, Any] | None = None
        for line in result.stdout.splitlines():
            if not line.startswith(("\t", " ")) and ":" in line:
                if current is not None:
                    interfaces.append(current)
                iface_name = line.split(":")[0]
                current = {"interface": iface_name, "addresses": [], "status": "unknown"}
            elif current is not None:
                stripped = line.strip()
                if stripped.startswith("status:"):
                    current["status"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("inet "):
                    parts = stripped.split()
                    current["addresses"].append({"type": "ipv4", "address": parts[1]})
                elif stripped.startswith("inet6"):
                    parts = stripped.split()
                    current["addresses"].append({"type": "ipv6", "address": parts[1]})
        if current is not None:
            interfaces.append(current)
    elif system == "Linux":
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                iface: dict[str, Any] = {
                    "interface": parts[0],
                    "status": parts[1],
                    "addresses": [],
                }
                for addr in parts[2:]:
                    if "." in addr:
                        iface["addresses"].append({"type": "ipv4", "address": addr.split("/")[0]})
                    elif ":" in addr:
                        iface["addresses"].append({"type": "ipv6", "address": addr.split("/")[0]})
                interfaces.append(iface)

    return interfaces


@app.command(annotations=ReadOnly)
def watch(
    *,
    interval: Annotated[float, Option(help="Seconds between checks")] = 1.0,
    checks: Annotated[int, Option(help="Number of snapshots to take")] = 1,
) -> dict[str, Any]:
    """Take system metric snapshots (limited count for agent safety)."""
    if checks < 1:
        raise InputError(
            message="Checks must be at least 1",
            code="E4008",
            details={"checks": checks},
        )
    if checks > 60:
        raise InputError(
            message="Maximum 60 checks allowed per invocation",
            code="E4009",
            details={"checks": checks},
        )

    snapshots: list[dict[str, Any]] = []
    for i in range(checks):
        snapshot: dict[str, Any] = {
            "check": i + 1,
            "cpu_count": os.cpu_count(),
        }

        try:
            load = os.getloadavg()
            snapshot["load_avg_1m"] = round(load[0], 2)
            snapshot["load_avg_5m"] = round(load[1], 2)
            snapshot["load_avg_15m"] = round(load[2], 2)
        except (OSError, AttributeError):
            snapshot["load_avg_1m"] = None
            snapshot["load_avg_5m"] = None
            snapshot["load_avg_15m"] = None

        try:
            usage = shutil.disk_usage("/")
            snapshot["disk_used_percent"] = round((usage.used / usage.total) * 100, 1)
        except OSError:
            snapshot["disk_used_percent"] = None

        snapshots.append(snapshot)

        if i < checks - 1:
            time.sleep(interval)

    return {
        "check_count": len(snapshots),
        "interval_seconds": interval,
        "snapshots": snapshots,
    }


if __name__ == "__main__":
    app()

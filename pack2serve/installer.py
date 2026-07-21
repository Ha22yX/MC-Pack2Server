from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from pack2serve.loader import LoaderInstallPlan


@dataclass(frozen=True)
class LoaderInstallResult:
    status: str
    artifact_path: str
    executed: bool
    command: list[str]
    return_code: int | None
    stdout: str
    stderr: str

    def to_json_dict(self) -> dict[str, object]:
        return asdict(self)


class LoaderInstaller:
    def install(
        self,
        server_dir: str | Path,
        plan: LoaderInstallPlan,
        *,
        execute_installers: bool = False,
    ) -> LoaderInstallResult:
        root = Path(server_dir)
        artifact_path = root / plan.artifact_path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        _download(plan.download_url, artifact_path)

        if plan.kind == "direct-server-jar":
            self._write_start_script(root, plan)
            result = LoaderInstallResult(
                status="installed",
                artifact_path=str(artifact_path.relative_to(root)).replace("\\", "/"),
                executed=False,
                command=[],
                return_code=None,
                stdout="",
                stderr="",
            )
        elif execute_installers:
            command = _command_with_managed_java(root, plan.install_command)
            proc = subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=600,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            if proc.returncode != 0:
                repaired = _repair_failed_maven_libraries(root, proc.stdout)
                if repaired:
                    retry = subprocess.run(
                        command,
                        cwd=root,
                        capture_output=True,
                        text=True,
                        timeout=600,
                    )
                    stdout = (
                        stdout
                        + "\n[pack2serve] Repaired failed installer libraries: "
                        + ", ".join(repaired)
                        + "\n[pack2serve] Retrying loader installer.\n"
                        + retry.stdout
                    )
                    stderr = stderr + retry.stderr
                    proc = retry
            result = LoaderInstallResult(
                status="installed" if proc.returncode == 0 else "failed",
                artifact_path=str(artifact_path.relative_to(root)).replace("\\", "/"),
                executed=True,
                command=command,
                return_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
            )
            if result.status == "installed":
                self._write_installer_start_script(root)
        else:
            result = LoaderInstallResult(
                status="downloaded",
                artifact_path=str(artifact_path.relative_to(root)).replace("\\", "/"),
                executed=False,
                command=plan.install_command,
                return_code=None,
                stdout="",
                stderr="",
            )

        self._write_result(root, result)
        return result

    def _write_start_script(self, root: Path, plan: LoaderInstallPlan) -> None:
        jar = plan.server_jar or plan.artifact_path
        (root / "start.ps1").write_text(
            "$ErrorActionPreference = 'Stop'\n"
            f"{_powershell_java_prelude()}"
            "$args = @('-Xms1G', '-Xmx4G')\n"
            f"& $java @args -jar '{jar}' nogui\n",
            encoding="utf-8",
        )

    def _write_installer_start_script(self, root: Path) -> None:
        run_bat = root / "run.bat"
        if run_bat.exists():
            (root / "start.ps1").write_text(
                "$ErrorActionPreference = 'Stop'\n"
                f"{_powershell_java_prelude(include_path=True)}"
                "& (Join-Path $PSScriptRoot 'run.bat')\n",
                encoding="utf-8",
            )
            return

        legacy_jar = _find_legacy_forge_jar(root)
        if legacy_jar:
            (root / "start.ps1").write_text(
                "$ErrorActionPreference = 'Stop'\n"
                f"{_powershell_java_prelude()}"
                "$args = @('-Xms1G', '-Xmx4G')\n"
                f"& $java @args -jar '{legacy_jar.name}' nogui\n",
                encoding="utf-8",
            )

    def _write_result(self, root: Path, result: LoaderInstallResult) -> None:
        out = root / "pack2serve" / "loader-install-result.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(result.to_json_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def load_loader_plan(path: str | Path) -> LoaderInstallPlan:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return LoaderInstallPlan(
        loader=data["loader"],
        loader_version=data["loader_version"],
        minecraft_version=data["minecraft_version"],
        kind=data["kind"],
        download_url=data["download_url"],
        artifact_name=data["artifact_name"],
        artifact_path=data["artifact_path"],
        install_command=list(data["install_command"]),
        launch_command=list(data["launch_command"]),
        server_jar=data.get("server_jar"),
        notes=list(data.get("notes", [])),
    )


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Pack2Serve/0.1.0"})
    temp = destination.with_suffix(destination.suffix + ".tmp")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temp.open("wb") as output:
            shutil.copyfileobj(response, output)
    except (urllib.error.URLError, OSError) as exc:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to download loader artifact {url}: {exc}") from exc
    temp.replace(destination)


_MAVEN_COORDINATE = re.compile(r"^[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:[A-Za-z0-9_.+-]+$")


def _repair_failed_maven_libraries(root: Path, stdout: str) -> list[str]:
    urls_by_coordinate: dict[str, str] = {}
    failed_coordinates: list[str] = []
    current_coordinate = ""
    collecting_failures = False

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("Considering library "):
            current_coordinate = line.removeprefix("Considering library ").strip()
            continue
        if line.startswith("Downloading library from ") and current_coordinate:
            urls_by_coordinate[current_coordinate] = line.removeprefix("Downloading library from ").strip()
            continue
        if line.startswith("These libraries failed to download"):
            collecting_failures = True
            continue
        if collecting_failures and _MAVEN_COORDINATE.match(line):
            failed_coordinates.append(line)

    repaired: list[str] = []
    for coordinate in failed_coordinates:
        url = urls_by_coordinate.get(coordinate)
        if not url:
            continue
        destination = _maven_library_path(root, coordinate, url)
        if not destination.exists():
            _download(url, destination)
        repaired.append(coordinate)
    return repaired


def _maven_library_path(root: Path, coordinate: str, url: str) -> Path:
    group, artifact, version = coordinate.split(":", 2)
    file_name = Path(unquote(urlparse(url).path)).name or f"{artifact}-{version}.jar"
    return root / "libraries" / Path(group.replace(".", "/")) / artifact / version / file_name


def _command_with_managed_java(root: Path, command: list[str]) -> list[str]:
    if not command or command[0].lower() != "java":
        return command
    local_java = _find_managed_java(root)
    if local_java is None:
        return command
    return [str(local_java), *command[1:]]


def _find_managed_java(root: Path) -> Path | None:
    for relative in (
        "pack2serve/runtime/java/bin/java.exe",
        "pack2serve/runtime/java/bin/java.cmd",
        "pack2serve/runtime/java/bin/java",
    ):
        candidate = root / relative
        if candidate.exists():
            return candidate
    return None


def _powershell_java_prelude(*, include_path: bool = False) -> str:
    prelude = (
        "$java = 'java'\n"
        "$localJava = Join-Path $PSScriptRoot 'pack2serve\\runtime\\java\\bin\\java.exe'\n"
        "if (Test-Path $localJava) { $java = $localJava }\n"
    )
    if include_path:
        prelude += (
            "$localJavaBin = Join-Path $PSScriptRoot 'pack2serve\\runtime\\java\\bin'\n"
            "if (Test-Path $localJavaBin) { $env:PATH = $localJavaBin + ';' + $env:PATH }\n"
        )
    return prelude


def _find_legacy_forge_jar(root: Path) -> Path | None:
    candidates = sorted(
        path
        for path in root.glob("forge-*.jar")
        if "installer" not in path.name.lower()
    )
    return candidates[0] if candidates else None

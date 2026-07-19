from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

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
            proc = subprocess.run(
                plan.install_command,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=600,
            )
            result = LoaderInstallResult(
                status="installed" if proc.returncode == 0 else "failed",
                artifact_path=str(artifact_path.relative_to(root)).replace("\\", "/"),
                executed=True,
                command=plan.install_command,
                return_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
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
            "$java = 'java'\n"
            "$args = @('-Xms1G', '-Xmx4G')\n"
            f"& $java @args -jar '{jar}' nogui\n",
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
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temp.open("wb") as output:
            shutil.copyfileobj(response, output)
    except (urllib.error.URLError, OSError) as exc:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to download loader artifact {url}: {exc}") from exc
    temp.replace(destination)

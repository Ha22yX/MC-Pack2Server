from __future__ import annotations

import argparse
import json
from pathlib import Path

from pack2serve.builder import ServerBuilder
from pack2serve.downloader import ArtifactCache, CurseForgeTemplateMirrorProvider
from pack2serve.installer import LoaderInstaller, load_loader_plan
from pack2serve.parser import parse_modpack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pack2serve")
    subcommands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subcommands.add_parser("inspect", help="Inspect a modpack archive")
    inspect_parser.add_argument("pack", type=Path)

    build_parser = subcommands.add_parser("build", help="Generate a server project")
    build_parser.add_argument("pack", type=Path)
    build_parser.add_argument("--target", type=Path, required=True)
    build_parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    build_parser.add_argument("--download", action="store_true")
    build_parser.add_argument(
        "--curseforge-mirror",
        action="append",
        default=[],
        help="No-key CurseForge mirror URL template with {projectID} and {fileID}",
    )

    install_parser = subcommands.add_parser(
        "install-loader", help="Download and optionally execute the generated loader install plan"
    )
    install_parser.add_argument("server_dir", type=Path)
    install_parser.add_argument("--execute-installers", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "inspect":
        pack = parse_modpack(args.pack)
        print(
            json.dumps(
                {
                    "format": pack.format,
                    "name": pack.name,
                    "version": pack.version,
                    "minecraftVersion": pack.minecraft_version,
                    "loader": {
                        "name": pack.loader.name,
                        "version": pack.loader.version,
                    },
                    "remoteFiles": len(pack.remote_files),
                    "overrideRoot": pack.override_root,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "build":
        cache = ArtifactCache(args.cache)
        curseforge_providers = [
            CurseForgeTemplateMirrorProvider(
                cache=cache,
                name=f"curseforge-mirror-{index + 1}",
                url_template=template,
            )
            for index, template in enumerate(args.curseforge_mirror)
        ]
        report = ServerBuilder(
            cache_dir=args.cache,
            download_remote=args.download,
            curseforge_providers=curseforge_providers,
        ).build(args.pack, args.target)
        print(
            json.dumps(
                {
                    "target": str(report.target_dir),
                    "format": report.pack.format,
                    "name": report.pack.name,
                    "minecraftVersion": report.pack.minecraft_version,
                    "loader": report.pack.loader.__dict__,
                    "remoteFiles": len(report.downloads),
                    "copiedOverrides": len(report.copied_overrides),
                    "manualActions": len(report.manual_actions),
                    "java": report.java.__dict__,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "install-loader":
        plan_path = args.server_dir / "pack2serve" / "loader-install-plan.json"
        plan = load_loader_plan(plan_path)
        result = LoaderInstaller().install(
            args.server_dir,
            plan,
            execute_installers=args.execute_installers,
        )
        print(json.dumps(result.to_json_dict(), ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

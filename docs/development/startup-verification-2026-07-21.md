# Startup verification - 2026-07-21

This note records the end-to-end startup verification pass for the five local sample packs.

## Final sample results

| Pack | Format | Remote files | Manual actions | Client remote isolated | Loader install | Startup validation |
| --- | --- | ---: | ---: | ---: | --- | --- |
| BattleArmory TACZ | Modrinth `.mrpack` | 90 | 0 | 8 | installed | started |
| Utopia Adventure | Modrinth `.mrpack` | 413 | 0 | 15 | installed | started |
| RLCraft 2.9.3 | CurseForge `.zip` | 187 | 0 | 0 | installed | started |
| Into the Backrooms | CurseForge `.zip` | 36 | 0 | 5 | installed | started |
| Re-Console LTS NeoForge | Modrinth `.mrpack` | 115 | 0 | 92 | installed | started |

Validation directories:

- `data/servers/startup-verification-2026-07-21/battlearmory-tacz`
- `data/servers/startup-verification-2026-07-21/utopia-adventure`
- `data/servers/startup-verification-2026-07-21/rlcraft`
- `data/servers/startup-verification-2026-07-21/into-the-backrooms`
- `data/servers/startup-verification-2026-07-21/re-console-neoforge`

Each directory contains:

- `pack2serve/build-report.json`
- `pack2serve/loader-install-result.json`
- `pack2serve/java-install-result.json`
- `pack2serve/validation-report.json`
- `logs/pack2serve-validation.log`

## Fixes made during this pass

1. Remote client-only isolation now applies to downloaded Modrinth and CurseForge artifacts.
   - Modrinth `env.server=unsupported` is respected.
   - Known client-side mod ids are isolated to `_client-overrides/mods/` instead of being copied to server `mods/`.
   - Localized jar names such as `【无缝音乐】moremusic-0.1.4+1.20.1.jar` are matched by embedded mod id.

2. Loader installers now prefer the generated portable Java runtime.
   - `install-java` can be run before `install-loader`.
   - Forge and NeoForge installers use `pack2serve/runtime/java/bin/java.exe` when present.
   - Generated `start.ps1` also prefers the project runtime and prepends its `bin` directory for `run.bat` launches.

3. Validation is less eager about benign class-probe warnings.
   - Optional `ClassNotFoundException` and invalid-dist mixin probes no longer fail validation before Minecraft reaches `Done (...)`.
   - Port and non-zero-return hints are suppressed when startup has already been confirmed.

4. Validation now cleans up process trees on Windows.
   - Failed or timed-out PowerShell/cmd wrapper processes are stopped with their child Java process to reduce file locks in later rebuilds.

## Client-only mod ids learned from samples

The current filename/slug-based isolation list includes:

`combatsense`, `continuity`, `entity-model-features`, `entity-texture-features`, `firstperson`, `hide-experimental-warning`, `iris`, `itemphysiclite`, `jecharacters`, `just-zoom`, `legacyskins`, `mcwifipnp`, `modmenu`, `moremusic`, `not-enough-animations`, `oculus`, `rubidium`, `skinlayers3d`, `smoothswapping`, `sodium`, `sodiumextras`.

This is intentionally conservative and should eventually be replaced or supplemented by jar metadata inspection.

# Compatibility audit - 2026-07-21

Pack2Serve must not claim that a generated dedicated server is identical to a client-hosted LAN world unless that claim is backed by evidence.

## Compatibility levels

| Level | Meaning |
| --- | --- |
| `verified-equivalent` | Required remote files are resolved, no unknown override files are isolated, and startup validation reaches `Done (...)`. |
| `startable-with-differences` | Startup validation reaches `Done (...)`, but some files could not be safely classified as dedicated-server content. |
| `generated-not-validated` | Files were generated, but startup validation has not proven that the server reaches `Done (...)`. |
| `not-startable` | Startup validation ran and did not reach `Done (...)`. |
| `incomplete` | Required downloads or other manual actions remain unresolved. |

Client-only files are intentionally isolated. A dedicated server should not load client-only mods, shader packs, screenshots, options files, or launcher-specific client data. These isolated files are useful for parity review, but they are not necessarily part of a valid server runtime.

## Current five-sample audit

| Pack | Level | Server-equivalent | Manual actions | Unknown overrides | Startup validation |
| --- | --- | --- | ---: | ---: | --- |
| BattleArmory TACZ | `startable-with-differences` | no | 0 | 11 | started |
| Into the Backrooms | `verified-equivalent` | yes | 0 | 0 | started |
| Re-Console LTS NeoForge | `startable-with-differences` | no | 0 | 206 | started |
| RLCraft 2.9.3 | `startable-with-differences` | no | 0 | 1158 | started |
| Utopia Adventure | `startable-with-differences` | no | 0 | 282 | started |

## What is not guaranteed yet

- Formats beyond Modrinth `.mrpack` and CurseForge `.zip`.
- Private, blocked, or removed CurseForge files if no no-key mirror can resolve them.
- Server compatibility for arbitrary client-only mods not yet detected by filename, manifest environment, or future jar metadata inspection.
- Full gameplay parity. Reaching `Done (...)` proves the server starts, not that every recipe, quest, worldgen rule, datapack, and client integration behaves identically.
- External services such as voice chat UDP ports, web integrations, auth dependencies, or mod-specific backend services.

## Next hardening targets

1. Inspect jar metadata (`fabric.mod.json`, `mods.toml`, `neoforge.mods.toml`, `quilt.mod.json`) to classify client/server/both more accurately.
2. Add dedicated support for FTB, Technic, ATLauncher, and MultiMC-style exported instances.
3. Add a client-parity manifest that lists every file from the original pack and explains whether it was copied, downloaded, isolated, ignored, or unresolved.
4. Add multiplayer probe checks after startup: TCP connect, status ping, and optional sample client handshake.
5. Add port planning for secondary services such as Simple Voice Chat.

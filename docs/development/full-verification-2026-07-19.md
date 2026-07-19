# 五个整合包端到端验证报告

日期：2026-07-19

本报告记录 Pack2Serve 对 5 个真实整合包的导入、解析、服务器目录生成、Loader 安装、Java 运行时安装、EULA 接受和启动验证结果。验证目标是判断当前项目距离“丢入整合包即可生成并托管运行服务器”还有哪些明确缺口。

## 验证样本

| 样本 | 格式 | MC | Loader | 远程文件 | 覆盖文件 |
| --- | --- | --- | --- | ---: | ---: |
| BattleArmory TACZ 1.6.4-hotfix.2 | Modrinth `.mrpack` | 1.20.1 | Forge 47.4.20 | 90 | 1619 |
| 乌托邦探险之旅 3.5.2 | Modrinth `.mrpack` | 1.20.1 | Fabric Loader 0.18.4 | 413 | 2694 |
| RLCraft 1.12.2 Release v2.9.3 | CurseForge `.zip` | 1.12.2 | Forge 14.23.5.2860 | 187 | 3381 |
| Into the Backrooms Found Footage 2.0.3 | CurseForge `.zip` | 1.20.1 | Fabric 0.18.4 | 36 | 39 |
| Re-Console LTS 26.06.0 | Modrinth `.mrpack` | 1.21.1 | NeoForge 21.1.233 | 115 | 1855 |

## 总结结论

| 样本 | 构建补齐 | Loader | Java | 启动验证 | 结论 |
| --- | --- | --- | --- | --- | --- |
| BattleArmory TACZ | Modrinth 远程文件已落地，人工项 0 | 已安装 Forge | JRE 17 | crashed | 生成链路完成；运行时模组依赖冲突，需要服务端兼容诊断 |
| 乌托邦探险之旅 | Modrinth 远程文件已落地，人工项 0 | 已安装 Fabric | JRE 17 | failed | 生成链路完成；首次完整日志显示 `moremusic` 调用客户端 Fabric API，后续复跑受 Windows 文件锁影响 |
| RLCraft | CurseForge 默认无 Key provider 已补齐 187/187，人工项 0 | 已安装 Forge | JRE 8 | started | 自动补齐、安装、启动验证均通过 |
| Into the Backrooms | CurseForge 默认无 Key provider 已补齐 36/36，人工项 0 | 已安装 Fabric | JRE 17 | failed | 自动补齐完成；运行验证受本机 Windows `logs/latest.log` 文件锁影响 |
| Re-Console LTS | Modrinth 远程文件已落地，人工项 0 | 已安装 NeoForge | JRE 21 | failed | NeoForge 安装链路完成；启动器报 `NoSuchElementException: No value present`，需要进一步定位 run.bat/argfile 或包兼容问题 |

## 关键发现

1. Modrinth `.mrpack` 解析和下载链路已经可用。
   BattleArmory、乌托邦、Re-Console 三个 Modrinth 样本均能解析 `modrinth.index.json`，读取 Minecraft/Loader 依赖，下载 manifest 中远程文件，并复制 overrides。

2. CurseForge `.zip` 默认无 Key 自动补齐链路已可用。
   Pack2Serve 会解析 `manifest.json` 的 `projectID/fileID`，从 `modlist.html` 恢复 slug，优先复用 `data/cache/curseforge/<projectID>/<fileID>/`，再尝试 `curse.tools` 和 Curse Maven 风格 provider。RLCraft 187/187、Into the Backrooms 36/36 均已补齐到人工项 0。

3. Loader 安装链路覆盖了 Fabric、Forge、NeoForge。
   Fabric 生成 `server.jar`；Forge/NeoForge 通过 installer 生成 `run.bat` 或旧版 Forge 根目录 jar。此次验证修复了 installer 执行后 `start.ps1` 仍指向 `server.jar` 的问题。

4. Java 运行时安装链路可用。
   MC 1.12.2 使用 JRE 8，MC 1.20.1 使用 JRE 17，MC 1.21.1 使用 JRE 21。此次验证修复了 Forge/NeoForge `run.bat` 不继承项目内 Java 的问题，现在 `start.ps1` 会把 `pack2serve/runtime/java/bin` 放入 PATH 前面。

5. “完整生成”不等于“整合包一定能无人工修复启动”。
   BattleArmory 和乌托邦的 Modrinth 文件已补齐，但启动时仍遇到模组级问题。面板需要把生成状态、下载完整性、Loader/Java 安装状态、启动验证状态拆开显示。

## 本次验证推动的代码修复

- Forge/NeoForge installer 执行成功后自动重写 `start.ps1`，优先调用 `run.bat`，旧版 Forge 则回退到根目录 `forge-*.jar`。
- `install-java` 会让 `run.bat` 通过 PATH 使用项目内 Java，避免系统 Java 版本污染验证。
- 验证器输出解码改为 UTF-8 `errors=replace`，避免中文/异常字节导致报告生成崩溃。
- CLI stdout/stderr 自动配置为 UTF-8，避免 Windows 控制台输出 JSON 时报编码错误。
- 验证器新增 Java 版本不兼容、`MissingModsException`、`NoClassDefFoundError`、端口占用、可忽略 optional mixin class probe 等常见日志识别。
- 新增 CurseForge 默认 no-key provider 链、Curse Maven fallback、`modlist.html` slug 解析、`projectID/fileID` cache-first 复用和 `curseforge_resolution` 报告。

## 后续开发建议

1. CurseForge 无 Key方案需要继续提升 provider 稳定性和速度。
   当前样本已能补齐到 `manual_actions=0`，但第三方 provider 仍可能超时或失效。后续应加入并发下载、短超时重试、更多镜像 provider 和进度报告。

2. 增加服务端兼容扫描。
   对 Fabric/Forge/NeoForge mod jar 读取 metadata，识别 client-only、server-only、依赖缺失、版本范围不匹配，在真正启动前给出可操作报告。

3. 启动验证要隔离进程和文件锁。
   Windows 下长时间验证可能留下 Java 进程或文件句柄。面板托管层需要记录 PID、优雅停止、超时强制停止和启动目录锁检测。

4. 面板状态模型建议拆为四段。
   `parsed`、`files_resolved`、`runtime_ready`、`boot_verified`。这样可以准确表达“目录生成成功，但包自身不能开服”。

## 验证命令

```powershell
python -m pack2serve.cli build "<pack>" --target-dir "data\servers\full-verification\<server>" --download
python -m pack2serve.cli install-loader "data\servers\full-verification\<server>" --execute-installers
python -m pack2serve.cli install-java "data\servers\full-verification\<server>"
python -m pack2serve.cli accept-eula "data\servers\full-verification\<server>" --i-agree
python -m pack2serve.cli validate-server "data\servers\full-verification\<server>" --timeout 300
python -m unittest discover -s tests -v
```

单元测试结果：38 tests OK。

# Phase 4 / 5 本地交付与验证

版本：0.5.0。第四阶段治理闭环与第五阶段 Web 控制台已实现，并提供可编译、可启动的 Tauri Windows 客户端。本记录不代表客户生产环境验收或全部 59 项 AC 均已覆盖。

## 已交付

- 复盘仅由真人显式触发；独立 RETROSPECTIVE 子运行，父交付状态不变。同版本请求幂等，支持显式重做与终止后的异常复盘。
- 冻结全部原始产物正文、哈希、完整事件、门禁与部署信息；伪造运行身份、版本、终态及证据链接被拒绝。
- 长期记忆先待审，真人批准后发布。支持项目/Agent 隔离、过期过滤、撤销、版本替换及有审计的回滚；审核队列和冲突版本均按项目隔离。
- 注册了项目权限的 Worker 只收到 ACTIVE 正式记忆，作为不可信材料传入；撤销后后续调用不再携带该记忆。未注册主体不可检索。
- Skill 演进提案审批与记忆审批分离。发布 Skill 必须匹配已批准提案、精确包哈希和可信 SKILL_VERIFICATION 通过证据；当前运行的有效配置保持不可变。
- React 六个管理页面：交付运行与父子关系、门禁与发布、复盘与记忆、角色与模型、Skills/MCP、预算与审计。
- Web 可启动三角色流程、确认 G1、申请/批准/拒绝许可、部署/回滚/对账、取消、巡检、手动复盘与审查记忆。HTTP MCP 可登记隔离版本、人工批准与停用；Skill ZIP 可隔离导入和人工绑定。
- 配置草稿经服务端 RuntimeConfig 校验。显式勾选模型运行时为新 Run 固化配置；不勾选则使用可复现脚本角色。密钥只使用 env: 引用。
- HTTP 监听本机回环；校验 Host、Origin 和会话 CSRF 令牌；浏览器提交不能指定调用者身份。旧工作台写接口也加入 CSRF 校验。

## 启动

在配置好 `JAVA_HOME` 并将 Maven 加入 `PATH` 后，从仓库根目录执行：

```powershell
$env:AGENTLOOP_MAVEN_REPOSITORY = Join-Path (Get-Location) '.agentloop/m2'
.\.venv\Scripts\python.exe frontend/server.py --port 8439 --data-dir .agentloop/phase45-v2 --java-home $env:JAVA_HOME --maven (Get-Command mvn.cmd).Source
```

浏览器打开 `http://127.0.0.1:8439/console/`。也可通过顶部切换入口进入 `/workbench`。

首次检出后在 `frontend/console` 执行 `npm ci`、`npm run build`。构建产物在 `frontend/console/dist`，不提交 node_modules、dist 或 Rust target。

Tauri 客户端：先启动上述本地服务，然后运行 `frontend/console/src-tauri/target/debug/agentloop-desktop.exe`。从源码构建用 `cargo build --manifest-path frontend/console/src-tauri/Cargo.toml`。客户端仅访问专属本机服务，不暴露 shell/文件系统命令。当前提供开发构建，尚未制作签名安装程序或打包 Python/Maven 运行环境。

发布前需按 `phase3-runtime.md` 启动独立本地 HTTP 部署代理，并在本地服务进程中配置相同的 `AGENTLOOP_DEPLOY_AGENT_TOKEN`。代理未启动或令牌未配置时，操作会保留真实失败/未知状态，不会伪报发布成功。

## 实测证据

- `docs/phase45-validation.json`：首次全量回归 495 passed，3 skipped。3 项 Java 专用集成未在该命令中启用。
- 第四阶段治理、HTTP 链和旧门面专项回归 34 项通过。原始 JUnit 报告仅保留在本地。
- 最终变更后的关联回归 68 项通过，包含旧研发返工与 Git 合并恢复。此项与全量记录分别计数。
- React/Vite 生产构建通过；Tauri cargo check 与 cargo build 通过，Windows 进程启动后有有效主窗口。
- 浏览器实际操作 `phase45-browser`：G1 人工确认 → 三角色研发 → 真实 Maven/Spring 测试 → 人工发布许可 → 本地 HTTP 发布 → G3 通过 → DELIVERY COMPLETED → 手动复盘 → 一条记忆人工批准为 ACTIVE。
- 浏览器重载后完成状态、报告和正式记忆仍可读取。1280px、390px 断点无页面横向溢出，最终页面未观察到控制台错误。

## 范围限制

- 发布实测是本地静态 HTTP 产物；不是客户生产 Spring 服务。角色和 Curator 使用确定性脚本，此轮没有成功在线模型质量证据。
- 桌面客户端依赖另行启动的本机后端，不是包含 Python、JDK 与 Maven 的独立安装包。
- 企业 IdP、OS 沙箱、签名分发、完整人工安全复核及全部 AC 覆盖仍需单独验收；生产能力在该控制台中禁用。
- Web MCP 仅登记 HTTP 配置，不执行任意 stdio 命令。stdio 和受信测试证明由主机 CLI/执行器管理。
- 演进提案中的提示词/任意配置建议不会自动改写运行配置；人工审核后仍须通过配置草稿的新 Run 路径生效。

实现参考：[Tauri 配置](https://v2.tauri.app/reference/config/)、[Tauri 与 Vite](https://v2.tauri.app/start/frontend/vite/)。

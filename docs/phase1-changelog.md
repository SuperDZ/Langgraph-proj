# Phase 1 首批变更记录

日期：2026-10-21。

- 增加三个部门的可组合 LangGraph 子图、角色交换 Schema、角色 Profile 和严格输出校验。
- 增加内容寻址 Artifact 原文仓库、版本绑定和篡改检查。
- 增加 Run 独立 Git 工作区、受限补丁、提交记录、固定测试保护与真实 Maven/JUnit 执行器。
- 实现研发内部开发—审查—测试返工、次数上限和 Leader 入口/出口边界。
- 接入 G1 人工确认与 G2 原文证据核验，增加显式假身份授权后的本地部署模拟器。
- 增加 Spring Boot 参数校验 Bug 样例、快速编排用例、真实 HTTP 集成用例及证据导出命令。
- 保留 Phase 0 验证报告；新增 Phase 1 报告，明确记录 Java 用例执行或跳过状态。
- 本批没有在线模型调用、远端部署、Git 提交/推送或记忆写入。

范围与剩余工作见 `src/agentloop/PHASE1.md`；实测结果以 `docs/phase1-validation.json` 为准。

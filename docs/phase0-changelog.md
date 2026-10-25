# Phase 0 首批实施记录

日期：2026-10-19。需求基线：`notes/multi_agent_loop_platform_design_v1.2.md`。

## 本批变更

- 修复现有骨架的循环导入、pytest 目录、缺失的 Run 根标识默认值和无效测试准备流程。
- 新增 SQLite 持久仓储、追加审计表及唯一索引；服务方法使用可回滚事务，CAS 冲突不覆盖先写状态。
- 修复 G1 人工确认摘要错配与 PENDING 无法重评估问题；决策从可信 RBAC 仓储读取身份和项目角色，撤销使依赖门禁失效。
- 新增发布授权基础服务，区分申请与真人批准；真实部署入口保持关闭。
- 新增真实 LangGraph 澄清子图、持久 checkpoint、独立进程恢复和幂等 CLI 演示。
- 补充状态矩阵、门禁、路由、角色隔离、进程恢复、故障回滚和 week2 回归测试；新增带逐用例结果的追踪报告生成器。
- 增加安装元数据、依赖锁定快照和 Windows CI 配置；本批没有创建提交、推送或远端 CI 运行。
- 修正规格中的 REQ 范围、Release Action 大小写及 test-runner 服务器白名单三处一致性问题，没有修改既定业务规则。

## 验证与边界

执行命令、环境版本和结果见 `docs/phase0-validation.json` 及 `src/agentloop/README.md`。关联测试通过不代表整条 AC 已完整验收。完整部门子图、真实模型、开发测试闭环、生产部署、Skills/MCP 管理和记忆治理继续按后续 Phase 实施。

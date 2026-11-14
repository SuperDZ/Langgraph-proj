# AgentLoop项目讲解 · DESIGN.md

## 一、需求对齐（6 维度）

| 维度 | 结论 |
| --- | --- |
| 主题 | AgentLoop —— 基于 LangGraph 的多 Agent 研发 Loop 平台（src/agentloop，Phase 0–5，v0.5.0） |
| 目标 | 项目讲解 / 技术分享：讲清产品定位、组织与流程架构、五阶段演进、验证证据与能力边界 |
| 受众 | 技术团队 / 学习分享听众（有工程背景，不需要科普 LangGraph 本身） |
| 场合 | 项目分享与复盘 |
| 调性 | 务实、证据驱动、克制的工程风；数字必须落判断，边界如实呈现 |
| 页数 | 13 页（自估：定位 1 + 架构 1 + 阶段 3 + 验证 1 + 边界 1 + 封面/目录/3 章节页/结尾） |

风格路由：通用 scenario（技术分享）→ 科技蓝配色。

## 二、全局视觉约定

### ① 画布与安全区

- 画布 1280×720；页面 padding 上下 60px / 左右 60px；内容区 1160×600
- 页尾（仅内容页）：顶边 y = 670，字号 14px；左侧品牌行「AgentLoop · 多 Agent 研发 Loop 平台」，右侧页码
- 封面 / 目录 / 章节页 / 结尾页无页尾

### ② 配色方案（科技蓝）

| 槽位 | Hex | 用途 |
| --- | --- | --- |
| 主色 | `#2563EB` | 顶条 / 编号块 / 标题强调 / 流程链主干 |
| 辅色 | `#06B6D4` | 卡片底饰 / 图表第二序列 / 分隔线 |
| 强调色 | `#F59E0B` | 关键数字 / 门禁徽标 / 核心结论词（一页 ≤ 3 处） |
| 底色 | `#FFFFFF` | 主背景 |
| 正文色 | `#1E293B` | 主文字 |
| muted | `#64748B` | 辅助说明 / 页尾 |
| 细线 | `#E5E7EB` | 1px 贯通分区线 |
| 浅底 | `#EFF6FF` / `#F1F5F9` | 浅色填充卡 |

色彩面积：主色 ≤ 60% / 辅色 ≤ 30% / 强调色 ≤ 10%（Hero 页强调可提到 15–20%）。禁用阴影、渐变铺面、彩虹色。

### ③ 字体系统

- 中文：微软雅黑（Microsoft YaHei）；西文/数字：Arial（同族，不额外换字体，巨型锚点数字除外）
- 字号阶梯：封面主标 88 / 章节编号 120 / 章节名 54 / 巨型数据 96–110 / 页面主标 34 / 卡片小标 24 / 正文 19（密集页 18）/ 脚注·页码 14
- 行高：正文 1.5；标题 1.2；脚注 1.4。段间距 < T（标题-正文 28–36px）< 分区间距 G（≥ 32px）

### ④ 视觉母题

- 内容页主标题下 1px 贯通细线（#E5E7EB，贯通 1160px）
- 章节编号块统一：主色圆角方块（radius 8）+ 白色编号
- 门禁徽标统一：G1/G2/G3 圆角胶囊（G1 主色 / G2 强调色 / G3 辅色）

### ⑤ 配图清单（跨页全局）

全篇结构化图形均使用内联 SVG（架构图 / 流程链 / 时间轴 / 环形治理图），不使用生成图片，保证视觉类型统一。

| 载体 | 等级 | 使用页 |
| --- | --- | --- |
| 组织架构 SVG（Orchestrator + 三部门 + Curator） | L1 | P5 |
| 主流程链 SVG（含 G1/G2/G3 门禁节点） | L1 | P5 |
| 横向时间轴 SVG（Phase 0→1→G2 整改） | L1 | P7 |
| 阶段双面板（Phase 2 / Phase 3） | L1 | P8 |
| 治理闭环 SVG（复盘→记忆→Skill 演进） | L1 | P9 |
| 数据读数条 + 巨型数字 | L1 | P11 |

## 三、页面规划（13 页）

### P1 封面（type: cover, hero, peak）

- layout：大字报式（超大标题 + 副标 + 大留白，无图）
- visual：L3 编号母题；visual_role: anchor（大字即锚点）
- density：字数约 40 / 图 0 / 留白约 55%（Hero 允许）
- anti_pattern：禁止数据指标与数据说明；禁止四层以上信息
- description：主标「AgentLoop」88px Bold；副标「多 Agent 研发 Loop 平台 —— 从编排内核到受控发布」；说明层一行：「可配置 · 可恢复 · 可审计 · 可持续积累经验」；信息层：Langgraph-proj / 2026-10。

### P2 目录（type: catalog, supporting, valley）

- layout：经典纵排（左上大字「目录 CONTENTS」+ 贯通细线 + 三行章节清单）
- visual：L3；visual_role: evidence
- density：字数约 60 / 图 0 / 留白约 55%（目录页留白主导）
- anti_pattern：禁止统计装饰块、阅读顺序条、全篇主线预告、每章简述
- description：三章：01 平台定位与总体架构 P03–05；02 五阶段交付演进 P06–09；03 验证体系与能力边界 P10–12。

### P3 章节页 01（type: section, transition）

- layout：章节大字（编号 01 特大 + 章节名 + 一行简述）
- visual：L3；visual_role: atmosphere
- anti_pattern：禁止看点列表、本章结论条、大段导语
- description：01 · 平台定位与总体架构；简述「产品定义、组织模型与三道质量门禁」。

### P4 产品定位：四项设计承诺（type: content, hero, peak）

- layout：非对称 5:7——左侧巨型数字「4」+ 承诺标签；右侧四条承诺竖排（可配置 / 可恢复 / 可审计 / 可持续积累经验）各带一行说明；底部结论条
- visual：巨型数字 110px（L1，anchor）
- density：字数约 220 / 图 0 / 留白约 25%
- anti_pattern：禁止四等宽卡片横排；禁止把巨型数字塞进角落
- description：产品定义一句话（模拟软件组织的明确职责，不模拟无效的层层审批）；四项承诺：可配置（平台/部门/Agent/任务四级）、可恢复（checkpoint + 幂等 + 对账）、可审计（不可变产物 + 事件 + 门禁记录）、可持续积累经验（复盘 + 人工审记忆）；输入 Bug 报告/功能需求/技术改造，输出 Spec/架构/代码/测试/安全/部署/复盘。结论条：「质量结论只能来自确定性检查，不能来自模型自报」。

### P5 组织模型与主流程（type: content, supporting, valley）

- layout：上下两带——上带组织架构 SVG（Orchestrator → 产品/专家/研发三部门 + Experience Curator 治理线）；下带主流程链 SVG（澄清→产品→专家审计→G1→研发循环→G2→发布授权→部署→G3→交付/恢复）；底部一行读数条（3 部门 / 13 角色 / 3 门禁）
- visual：L1 双 SVG；visual_role: evidence
- density：字数约 200 / 图 2 / 留白约 18%
- anti_pattern：禁止把流程做成等宽卡片；禁止漏掉 G3 失败恢复分支
- description：三部门硬规则（产品/研发/专家，测试是研发内单一 Agent）；Leader 边界（入口分派+出口验收+外部整改+升级，内部流转不逐轮审批）；G1 前置确认 / G2 研发与安全放行 / G3 部署后独立观察；G3 失败必经 DEPLOYMENT_RECOVERY。结论：LoopRouter 确定性路由，Agent 不能自选目标。

### P6 章节页 02（type: section, transition）

- layout：章节大字，与 P3 同版式
- description：02 · 五阶段交付演进；简述「从编排内核到治理闭环，五个阶段逐层交付」。

### P7 Phase 0–1：编排内核与研发闭环（type: content, supporting, valley）

- layout：横向时间轴（e）——三个节点交替挂上下：Phase 0（10-19）编排内核、Phase 1（10-21）部门子图闭环、G2 整改补批；每节点一张小事件卡
- visual：L1 时间轴 SVG；visual_role: evidence
- density：字数约 260 / 图 1 / 留白约 20%
- anti_pattern：禁止竖排三卡片；禁止把验证数字做成无判断的罗列
- description：Phase 0：确定性状态机（Phase/Status 正交、CAS、终态保护）、SQLite 仓储+审计事件、G1/G2/G3 评估、LangGraph interrupt/Command 真实中断恢复、RBAC 审批与 Capability 交集；Phase 1：父图串联 Product→Expert→Engineering→Security 子图，真实 Spring Boot Bug（/hello 缺参 500→修后 400；第一轮 2 失败→第二轮 4 通过，每轮独立 Git Commit）；证据 docs/phase0-validation.json、phase1-validation.json。结论：部门子图与父图持久边界按 LangGraph Subgraphs 实现。

### P8 Phase 2–3：真实执行层与受控发布（type: content, supporting, valley）

- layout：左标题色块 + 右内容（m）双面板上下叠——上 Phase 2 执行层、下 Phase 3 并行研发与受控发布；每面板左侧阶段色块（0.3.0 / 0.4.0）+ 右侧 3 行能力 + 一个验证数字
- visual：L1 阶段面板；visual_role: evidence
- density：字数约 300 / 图 0 / 留白约 16%
- anti_pattern：禁止两阶段等宽对半；禁止只有数字没有判断
- description：Phase 2：四级配置（平台→部门→Agent→任务，求交集 deny 优先）+ 不可变快照、后备模型链、Token/成本预算预占结算、Skills 隔离导入与人工绑定、MCP stdio/HTTP/SSE 真实客户端与逐次写审批；383 passed（含 80 专项 + 2 真实 Java）。Phase 3：三 Worktree 并行开发+冲突工单、不可变发布包（绑定源 Commit）、独立执行器 + 人工范围许可、G3 失败→回滚/对账（BLOCKED / NEEDS_RECONCILIATION）、可恢复取消与巡检子 Run；457 passed。结论：权限取四级交集，Backend/Frontend/DevOps 永远拿不到部署能力。

### P9 Phase 4/5：治理闭环与管理控制台（type: content, supporting, valley）

- layout：左侧治理闭环 SVG（复盘→候选记忆→人工审批→正式记忆→Skill 演进）+ 右侧控制台能力竖排 3 条 + 底部实测链路条
- visual：L1 环形治理 SVG；visual_role: evidence
- density：字数约 260 / 图 1 / 留白约 18%
- anti_pattern：禁止把 React 页面列表做成六宫格均分
- description：复盘仅真人显式触发（RETROSPECTIVE 子 Run，父交付状态不变，冻结原始产物与事件）；长期记忆人工审批后才发布（项目/Agent 隔离、撤销、版本替换、可审计回滚）；Skill 演进需批准提案+包哈希+验证证据；React 六管理页 + Tauri Windows 客户端（仅访问本机会话，CSRF/Host/Origin 校验）；浏览器实测：G1 确认→三角色研发→Maven/Spring 测试→发布许可→本地 HTTP 发布→G3→复盘→记忆批准；495 passed。结论：经验可以积累，但不能自动提权。

### P10 章节页 03（type: section, transition）

- layout：章节大字，与 P3/P6 同版式
- description：03 · 验证体系与能力边界；简述「证据链怎么建，边界在哪里」。

### P11 验证体系与证据链（type: content, hero, peak）

- layout：巨型数字+洞察（5.3a）——左侧巨型「495」passed + 0 failed（0.5.0 全量回归）；右侧四行证据读数（阶段数字递进 383→457→495、真实 Java/Maven/Spring 集成、REQ-001–049 / AC 追踪报告、安装包逐字节一致）
- visual：巨型数字 110px（L1，anchor）
- density：字数约 230 / 图 0 / 留白约 22%
- anti_pattern：禁止堆数字不给判断；禁止等宽四卡片
- description：数字判断：383→457→495 是同一套回归随阶段扩容，不是三次独立集；验证证据形态：docs/*-validation.json + JUnit XML + 单 Run 证据导出（原文产物+哈希+门禁+事件）+ 安装包源码一致性；边界提醒：REQ/AC 关联只证明有相应用例，不等于全部需求已交付。结论：「证据可回溯」是产品能力，不是文档习惯。

### P12 能力边界与后续方向（type: content, supporting, valley）

- layout：卡片组 + 底部结论条（d）——上排 2 张大卡（当前边界 / 后续方向），卡内各 4 条编号短句；底部浅底结论条
- visual：L3；visual_role: evidence
- density：字数约 280 / 图 0 / 留白约 18%
- anti_pattern：禁止把边界写成免责声明小字；禁止四等宽小卡
- description：当前边界：角色为可复现脚本（无在线模型质量证据，DeepSeek 预检 401）；发布实测为本地静态 HTTP 目标而非生产服务；本地受限补丁检查不是 OS 沙箱；企业 IdP / 完整 SAST / 签名分发未接入。后续方向：真实模型链路验收、容器/进程隔离执行器、企业身份与生产发布 Provider、完整漏洞扫描与安全复核。结论条：「边界被显式记录而不是掩盖——这是平台可信度的一部分」。

### P13 结尾页（type: ending, hero, peak）

- layout：收束金句 + 落款（b）——一句总结大字居中偏左 + 细线 + 落款
- visual：L3；visual_role: anchor
- anti_pattern：禁止只写「谢谢」；禁止塞联系方式凑版面
- description：金句「确定性编排 · 人工门禁 · 全链路证据」+ 一行收束：AgentLoop 把「一次交付」变成可审计、可恢复、可持续积累的研发 Loop。落款：Langgraph-proj · AgentLoop 0.5.0 · 2026-10。

## 四、节奏与版式纪律

- Hero 页：P1 / P4 / P11 / P13（4/13 ≈ 31%，相邻之间均隔 Supporting/Section）
- 非对称版式 ≥ 40%：P1、P4、P5、P7、P8、P9、P11、P12 均为非对称或图文错落
- 相邻页版式互不相同；连续 Supporting 不超过 3 页（P7-P8-P9 之间以 P6 章节页断开）
- 同类内容页标题位置（y=60 起）与页尾位置全篇固定

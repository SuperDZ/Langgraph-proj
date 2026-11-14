
"use strict";

/* ================= 常量 ================= */

const PHASES = [
  ["INTAKE", "接入"], ["PRODUCT", "产品"], ["PRODUCT_AUDIT", "产品审计"],
  ["ARCHITECTURE", "架构"], ["G1", "门禁一"], ["ENGINEERING", "研发"],
  ["SECURITY_REVIEW", "安全审查"], ["G2", "门禁二"],
  ["RELEASE_AUTHORIZATION", "发布授权"], ["DEPLOYMENT", "部署"],
  ["G3", "门禁三"], ["DEPLOYMENT_RECOVERY", "部署恢复"], ["DELIVERY", "交付"],
];
const GATE_PHASES = new Set(["G1", "G2", "G3"]);
const STATUS_LABELS = { CREATED: "已创建", RUNNING: "运行中", WAITING_APPROVAL: "等待审批", BLOCKED: "已阻断",
  COMPLETED: "已完成", FAILED: "执行失败", CANCELLED: "已取消", PAUSED_FOR_HUMAN: "等待答复",
  NEEDS_RECONCILIATION: "等待对账", CANCELLING: "取消处理中", PENDING: "待处理" };
const phaseLabel = phase => PHASES.find(([name]) => name === phase)?.[1] || phase || "等待启动";
const stateLabel = status => STATUS_LABELS[status] || status || "等待启动";

const AGENTS = {
  "product-analyst":    { dept: "product",    label: "产品分析师"  },
  "ux-agent":           { dept: "product",    label: "UX 体验"     },
  "product-leader":     { dept: "product",    label: "产品 Leader" },
  "product-expert":     { dept: "product",    label: "产品专家"    },
  "architecture-expert":{ dept: "expert",     label: "架构专家"    },
  "expert-leader":      { dept: "expert",     label: "专家 Leader" },
  "engineering-leader": { dept: "engineering",label: "研发 Leader" },
  "backend":            { dept: "engineering",label: "Backend"     },
  "testing":            { dept: "testing",    label: "测试"        },
  "code-review":        { dept: "review",     label: "Code Review" },
  "security-expert":    { dept: "security",   label: "安全专家"    },
  "GATE_EVALUATOR":     { dept: "gate",       label: "门禁评估器"  },
  "orchestrator":       { dept: "system",     label: "编排器"      },
  "system":             { dept: "system",     label: "系统"        },
  "local-simulator":    { dept: "deploy",     label: "部署模拟器"  },
  "demo-owner":         { dept: "human",      label: "人工授权"    },
};
const DEPT = {
  product:     { c: "#4E7FA6", shape: "sq",     label: "产品部门" },
  expert:      { c: "#7C6BA8", shape: "di",     label: "专家部门" },
  engineering: { c: "#3E8E7E", shape: "bar",    label: "研发部门" },
  testing:     { c: "#B07D3E", shape: "tri",    label: "测试" },
  review:      { c: "#5E6C85", shape: "ring",   label: "代码审查" },
  security:    { c: "#C4574D", shape: "shield", label: "安全" },
  gate:        { c: "#2E2A25", shape: "di",     label: "门禁评估" },
  system:      { c: "#8C8479", shape: "dot",    label: "系统" },
  deploy:      { c: "#4E7FA6", shape: "chev",   label: "部署" },
  human:       { c: "#5F8558", shape: "ring",   label: "人工" },
};

/* ================= 工具 ================= */

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const short = (s, n = 10) => !s ? "—" : (s.length <= n ? s : s.slice(0, n) + "…");
const fmtTime = iso => {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? String(iso).slice(0, 19)
    : new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit",
      minute: "2-digit", second: "2-digit", hour12: false }).format(date);
};
const rand = (a, b) => a + Math.random() * (b - a);
let toastTimer;
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2800);
}

/* ================= 幕场景生成 ================= */

function sceneHTML(phase) {
  switch (phase) {
    case "INTAKE":
      return Array.from({ length: 14 }, () => {
        const ang = rand(0, Math.PI * 2), dist = rand(180, 380);
        return `<span class="dotm" style="left:${rand(20, 80)}%;top:${rand(22, 78)}%;
          --dx:${(Math.cos(ang) * dist).toFixed(0)}px;--dy:${(Math.sin(ang) * dist * .6).toFixed(0)}px;
          animation-delay:${rand(0, 2.4).toFixed(2)}s"></span>`;
      }).join("") + `<span class="core"></span>`;
    case "PRODUCT": {
      const cells = [];
      for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) {
        const hl = (r * 4 + c) % 5 === 2;
        cells.push(`<span class="sq${hl ? " hl" : ""}"
          style="left:${26 + c * 12}%;top:${30 + r * 15}%;
          --dx:${rand(-140, 140).toFixed(0)}px;--dy:${rand(-90, 90).toFixed(0)}px;
          --d:${((r * 4 + c) * .13).toFixed(2)}s;--o:${hl ? .9 : .18}"></span>`);
      }
      return cells.join("");
    }
    case "PRODUCT_AUDIT": {
      const cells = [];
      for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) {
        cells.push(`<span class="sq${(r + c) % 3 === 1 ? " hl" : ""}"
          style="left:${22 + c * 15}%;top:${26 + r * 18}%;--d:${((r * 4 + c) * .18).toFixed(2)}s"></span>`);
      }
      return cells.join("") + `<span class="scanline"></span>`;
    }
    case "ARCHITECTURE": {
      const layout = [[-120, -20, 1.5], [-40, 18, 2.2], [40, -34, 1.1], [110, 8, 1.8], [-4, 44, .8]];
      return `<div class="iso">` + layout.map(([gx, gy, h], i) =>
        `<span class="pillar" style="--gx:${gx}px;--gy:${gy}px;--h:${h};--d:${(i * .3).toFixed(2)}s"></span>`).join("") + `</div>`;
    }
    case "G1":
      return `<span class="panel l"></span><span class="panel r"></span><span class="seal">G1</span>`;
    case "G2":
      return [0, .55, 1.1].map(d => `<span class="pulse" style="--d:${d}s"></span>`).join("")
        + `<span class="core-d"></span>`;
    case "G3": {
      const ticks = Array.from({ length: 12 }, (_, i) =>
        `<span class="tick" style="left:${14 + i * 6.4}%;--d:${(i * .14).toFixed(2)}s"></span>`).join("");
      return [0, .6, 1.2].map(d => `<span class="wave" style="--d:${d}s"></span>`).join("") + ticks;
    }
    case "ENGINEERING":
      return Array.from({ length: 9 }, (_, i) =>
        `<span class="bar" style="left:${20 + (i % 2) * 22}%;top:${20 + i * 6.6}%;
          --w:${14 + (i * 37 % 46)}%;--d:${(i * .22).toFixed(2)}s"></span>`).join("")
        + `<span class="caret" style="left:44%;top:79%"></span>`;
    case "SECURITY_REVIEW":
      return `<span class="scope"></span><span class="sweep"></span>` +
        Array.from({ length: 3 }, () =>
          `<span class="blip" style="left:${rand(38, 62).toFixed(0)}%;top:${rand(32, 64).toFixed(0)}%;--d:${(1 + rand(0, 1.4)).toFixed(2)}s"></span>`).join("");
    case "RELEASE_AUTHORIZATION":
      return `<span class="orbit"></span><span class="keyhole"></span><span class="key"></span>`;
    case "DEPLOYMENT":
      return Array.from({ length: 9 }, (_, i) =>
        `<span class="chev" style="left:${44 + rand(-7, 7).toFixed(0)}%;top:${rand(38, 62).toFixed(0)}%;--d:${(i * .24).toFixed(2)}s"></span>`).join("")
        + `<span class="pad"></span>`;
    case "DEPLOYMENT_RECOVERY":
      return Array.from({ length: 8 }, (_, i) =>
        `<span class="chev" style="left:${rand(24, 70).toFixed(0)}%;top:${16 + i * 8.6}%;--d:${(i * .2).toFixed(2)}s"></span>`).join("");
    case "DELIVERY": {
      const sparks = Array.from({ length: 12 }, () =>
        `<span class="spark" style="left:${rand(16, 84).toFixed(0)}%;top:${rand(46, 72).toFixed(0)}%;--d:${rand(0, 2.6).toFixed(2)}s"></span>`).join("");
      return [0, .65, 1.3].map(d => `<span class="wave" style="--d:${d}s"></span>`).join("")
        + `<span class="check">✓</span>` + sparks;
    }
    default:
      return `<span class="dotm" style="left:50%;top:50%"></span>`;
  }
}

const SCENE_CLASS = {
  INTAKE: "sc-intake", PRODUCT: "sc-product", PRODUCT_AUDIT: "sc-audit",
  ARCHITECTURE: "sc-arch", G1: "sc-gate", ENGINEERING: "sc-engr",
  SECURITY_REVIEW: "sc-radar", G2: "sc-shield",
  RELEASE_AUTHORIZATION: "sc-auth", DEPLOYMENT: "sc-deploy",
  G3: "sc-sonar", DEPLOYMENT_RECOVERY: "sc-recovery", DELIVERY: "sc-delivery",
};

/* ================= 回放轨道 ================= */

let DATA = null, TRACK = [], cursor = -1, playing = false, timer = null;

function buildTrack(events) {
  let phase = "INTAKE", agent = null, status = "CREATED";
  return (events || []).map(e => {
    const pm = /([A-Z0-9_]+)->([A-Z0-9_]+)/.exec(e.payload_ref || "");
    if (e.type === "RUN_PHASE_CHANGED" && pm && PHASES.some(p => p[0] === pm[2])) phase = pm[2];
    if (e.type === "RUN_STATUS_CHANGED" && pm) status = pm[2];
    const known = AGENTS[e.actor_id];
    if (known && (e.actor_type === "AGENT" || known.dept !== "system"
        || e.type === "WORKER_OUTPUT_RECORDED")) agent = e.actor_id;
    if (e.type.startsWith("GATE_")) agent = "GATE_EVALUATOR";
    if (e.type === "DEPLOYMENT_RESULT_RECORDED") agent = "local-simulator";
    return { e, phase, agent, status };
  });
}

/* ================= 舞台应用 ================= */

function applyFrame(i) {
  if (!TRACK.length) return;
  $("#stage").dataset.idle = "false";
  cursor = Math.max(0, Math.min(TRACK.length - 1, i));
  const f = TRACK[cursor];
  const { phase, agent, status, e } = f;

  const idx = Math.max(0, PHASES.findIndex(p => p[0] === phase));
  $("#hud-no").textContent = `${String(idx + 1).padStart(2, "0")} / 13`;
  $("#hud-name").textContent = phaseLabel(phase);
  $("#hud-zh").textContent = phase.replaceAll("_", " ");
  $("#ribbon-now").textContent = `${PHASES[idx][1]} · ${phase}`;
  const badgeCls = /BLOCKED|FAILED|REJECTED|CANCEL/.test(status) ? "bad"
    : /COMPLETED/.test(status) ? "solid" : /RUNNING|WAITING/.test(status) ? "wait" : "";
  $("#hud-status").textContent = stateLabel(status);
  $("#hud-status").className = "status-badge " + badgeCls;

  const host = $("#scenes");
  if (host.dataset.phase !== phase) {
    host.dataset.phase = phase;
    host.innerHTML = `<div class="scene ${SCENE_CLASS[phase] || ""} on">${sceneHTML(phase)}</div>`;
  }

  const meta = AGENTS[agent] || { dept: "system", label: "系统" };
  const d = DEPT[meta.dept];
  document.documentElement.style.setProperty("--agent-c", d.c);
  const roleEl = $("#agent-role");
  if (roleEl.textContent !== meta.label) {
    roleEl.textContent = meta.label;
    $("#agent-dept").textContent = meta.dept.toUpperCase() + " · " + d.label;
    const b = $("#agent-badge");
    b.classList.remove("swap"); void b.offsetWidth; b.classList.add("swap");
    renderAgentLayer(meta.dept);
  }

  document.querySelectorAll(".rb").forEach((s, si) => {
    s.classList.toggle("past", si !== idx && TRACK.slice(0, cursor + 1).some(f => f.phase === s.dataset.phase));
    s.classList.toggle("now", si === idx);
    if (si === idx) s.setAttribute("aria-current", "step");
    else s.removeAttribute("aria-current");
  });

  $("#t-idx").textContent = `${cursor + 1}/${TRACK.length}`;
  $("#t-type").textContent = e.type;
  $("#progress-fill").style.width = ((cursor + 1) / TRACK.length * 100) + "%";
  $("#progress").setAttribute("aria-valuemax", String(TRACK.length));
  $("#progress").setAttribute("aria-valuenow", String(cursor + 1));
  $("#progress").setAttribute("aria-valuetext", `事件 ${cursor + 1} / ${TRACK.length}，${phaseLabel(phase)}`);
  document.querySelectorAll(".ev").forEach((r, ri) =>
    r.classList.toggle("playing", ri === cursor));
}

function renderAgentLayer(dept) {
  const d = DEPT[dept];
  $("#agent-layer").innerHTML = Array.from({ length: 6 }, () =>
    `<span class="motif m-${d.shape}" style="left:${rand(6, 90).toFixed(0)}%;top:${rand(10, 84).toFixed(0)}%;
      --d:${rand(-5, 0).toFixed(2)}s"></span>`).join("");
}

/* ================= 回放控制 ================= */

const BASE_MS = 950;
function schedule() {
  clearTimeout(timer);
  if (!playing) return;
  const speed = parseFloat($("#t-speed").value) || 1;
  if (cursor >= TRACK.length - 1) { setPlaying(false); return; }
  timer = setTimeout(() => {
    applyFrame(cursor + 1);
    schedule();
  }, BASE_MS * speed);
}
function setPlaying(on) {
  if (!TRACK.length) on = false;
  playing = on;
  $("#t-play").textContent = on ? "⏸" : "▶";
  $("#t-play").setAttribute("aria-label", MODE === "workbench" ? "跟随最新事件" : on ? "暂停回放" : "播放回放");
  clearTimeout(timer);
  if (on) {
    if (!TRACK.length) { playing = false; return; }
    if (cursor >= TRACK.length - 1) applyFrame(0);
    schedule();
  }
}
function seek(i) {
  if (!TRACK.length) return;
  const wasPlaying = playing;
  playing = false; clearTimeout(timer);
  applyFrame(i);
  if (wasPlaying) { playing = true; schedule(); }
  $("#t-play").textContent = playing ? "⏸" : "▶";
}

/* ================= 面板渲染 ================= */

function renderPanels(data, sourceName) {
  DATA = data;
  TRACK = buildTrack(data.events);

  $("#ribbon").innerHTML = PHASES.map(([en, zh], i) =>
    `<button class="rb${GATE_PHASES.has(en) ? " gate" : ""}" data-i="${
      TRACK.findIndex(f => f.phase === en)}" data-phase="${en}"
      aria-label="${zh}，阶段 ${i + 1}"
      title="${String(i + 1).padStart(2, "0")} ${en} · ${zh}"><span>${i + 1}</span></button>`).join("");

  const gates = { G1: null, G2: null, G3: null };
  for (const { e } of TRACK) {
    if (e.type !== "GATE_RESULT_RECORDED") continue;
    const m = String(e.payload_ref || "").match(/^(G[123]):([A-Z_]+)->([A-Z_]+)/);
    if (m) gates[m[1]] = { status: m[3],
      digest: (/digest=([^;]+)/.exec(e.payload_ref) || [])[1] || "—", ts: e.timestamp };
  }
  $("#d-gates").innerHTML = Object.entries(gates).map(([gid, g]) => {
    const st = g ? g.status : "NOT_EVALUATED";
    const cls = st === "PASSED" ? "passed" : /REJECTED/.test(st) ? "rejected"
      : st === "PENDING" ? "pending" : "stale";
    return `<div class="grow"><div class="gid">${gid}</div>
      <div class="ginfo"><span class="gstatus ${cls}">${st}</span>
      <div class="gmeta" title="${esc(g?.digest || "")}">${esc(short(g?.digest, 30))}</div>
      <div class="gmeta">${fmtTime(g?.ts)}</div></div></div>`;
  }).join("");

  const FILTERS = [
    ["all", "全部", () => true],
    ["gate", "门禁", t => t.startsWith("GATE_")],
    ["release", "审批与发布", t => /APPROVAL|RELEASE_|DEPLOYMENT/.test(t)],
    ["work", "工作与返工", t => /TEST|REWORK|CHECK_TRIGGERED|WORKER|DEPARTMENT|ISSUE|BASELINE/.test(t)],
    ["state", "状态迁移", t => /RUN_/.test(t)],
  ];
  const catOf = e => { for (let i = 1; i < FILTERS.length; i++) if (FILTERS[i][2](e.type)) return FILTERS[i][0]; return "other"; };
  const MARKS = { GATE: "◆", APPROVAL: "■", RELEASE: "■", DEPLOYMENT: "■",
    TEST: "▲", WORKER: "▲", REWORK: "▲", RUN_: "·" };
  const markOf = t => { for (const k in MARKS) if (t.startsWith(k)) return MARKS[k]; return "·"; };

  $("#filters").innerHTML = FILTERS.map(([id, label], i) =>
    `<button class="btn ${i === 0 ? "active" : ""}" data-filter="${id}">${label}</button>`).join("");

  $("#timeline").innerHTML = TRACK.map((f, i) => {
    const e = f.e, ag = AGENTS[e.actor_id];
    return `<div class="ev" data-type="${esc(e.type)}" data-i="${i}" role="button" tabindex="0" aria-expanded="false">
      <span class="seq">${String(e.sequence ?? i + 1).padStart(3, "0")}</span>
      <span class="type"><span class="mark" style="color:${ag ? DEPT[ag.dept].c : "var(--muted)"}">${markOf(e.type)}</span>${esc(e.type)}</span>
      <span class="time">${fmtTime(e.timestamp)}</span>
      <span class="actor-line">${esc(e.actor_id || "—")}${e.actor_type ? " · " + e.actor_type : ""} — ${esc(e.payload_ref || "")}</span>
      <div class="payload-full">${esc(e.payload_ref || "（无载荷）")}${esc(e.idempotency_key ? "\nidempotency: " + e.idempotency_key : "")}</div>
    </div>`;
  }).join("") + (TRACK.length > 40
    ? `<button class="ev-more" id="more" hidden>显示全部事件 ▼</button>` : "");

  const groups = new Map();
  for (const a of (data.artifacts || [])) {
    const t = a.metadata?.type ?? "UNKNOWN";
    if (!groups.has(t)) groups.set(t, []);
    groups.get(t).push(a);
  }
  $("#d-artifacts").innerHTML = [...groups.entries()].map(([type, list]) =>
    `<div class="arow"><button class="arow-head" data-type="${esc(type)}">
      <span class="t">${esc(type)}</span>
      <span class="pl">${esc(short(list[0].metadata.producer_task_id, 22))}</span>
      <span class="c">${list.length}</span></button>
      <div class="arow-body"><pre>${esc(list.map(a =>
        "// " + short(a.metadata.artifact_id, 20) + " · " + fmtTime(a.metadata.created_at) + "\n" +
        JSON.stringify(a.body ?? a, null, 2)).join("\n\n"))}</pre></div></div>`).join("")
    || `<p style="color:var(--muted);font-size:.85rem">暂无产物记录。</p>`;

  const s = data.summary || {};
  $("#d-boundary").innerHTML = `<div class="bnd"><p>${esc(data.boundary || data.evidence_boundary || "（无边界声明。）")}</p>
    <div class="src">RUN ${esc(s.run_id || "—")} · MODE ${esc(s.mode || "—")} · STATE v${esc(s.state_version ?? "—")}<br>
    ${TRACK.length} 事件 · 来源 ${esc(sourceName)}</div></div>`;
  $("#colophon-source").textContent =
    `${sourceName} · ${TRACK.length} 事件`;

  $("#metric-gates").textContent = Object.values(gates).filter(g => g?.status === "PASSED").length;
  $("#metric-artifacts").textContent = (data.artifacts || []).length;
  $("#metric-events").textContent = TRACK.length;
  $("#nav-events").textContent = TRACK.length;
  $("#activity-count").textContent = `${TRACK.length} 条事件`;
  const phase = data.summary?.phase || TRACK.at(-1)?.phase;
  $("#metric-phase").textContent = phaseLabel(phase);
  $("#metric-status").textContent = data.summary?.status ? stateLabel(data.summary.status) : "准备好后，启动第一个任务";
  $("#activity-list").innerHTML = TRACK.length ? TRACK.slice(-3).reverse().map(({ e }, i) =>
    `<button class="activity-row" data-event-index="${TRACK.length - 1 - i}">
      <span class="activity-symbol">${markOf(e.type)}</span><span><strong>${esc(eventLabel(e.type))}</strong>
      <small>${esc(AGENTS[e.actor_id]?.label || e.actor_id || "系统")} · ${esc(e.type)}</small></span>
      <time>${esc(fmtTime(e.timestamp))}</time></button>`).join("")
    : `<div class="empty-activity"><span class="empty-icon">↳</span><div><strong>协作轨迹将在这里出现</strong>
      <p>启动任务后，实时查看阶段变化、角色输出与门禁决策。</p></div><span class="empty-caption">WAITING FOR EVENTS</span></div>`;

  clampRows();
}

function eventLabel(type) {
  return ({ RUN_CREATED: "已创建交付任务", RUN_PHASE_CHANGED: "交付阶段已更新", RUN_STATUS_CHANGED: "运行状态已更新",
    GATE_RESULT_RECORDED: "质量门禁已评估", WORKER_OUTPUT_RECORDED: "角色提交了工作产物", TEST_RESULT_RECORDED: "测试结果已记录",
    APPROVAL_REQUEST_CREATED: "新增待审批事项", APPROVAL_DECIDED: "人工审批已决策", BASELINE_UPDATED: "交付基线已更新",
    RELEASE_AUTHORIZATION_REQUESTED: "发布授权待审批", DEPLOYMENT_RESULT_RECORDED: "部署结果已记录" })[type] || "新增运行记录";
}

function resetView() {
  setPlaying(false);
  document.documentElement.style.removeProperty("--agent-c");
  cursor = -1;
  renderPanels({ events: [], artifacts: [], summary: {}, boundary: "本地工作台使用脚本角色、真实本地测试与模拟发布。" }, "等待运行");
  $("#stage").dataset.idle = "true";
  $("#scenes").innerHTML = "";
  delete $("#scenes").dataset.phase;
  $("#agent-layer").innerHTML = "";
  $("#hud-no").textContent = "READY WHEN YOU ARE";
  $("#hud-name").textContent = "从一个任务开始";
  $("#hud-zh").textContent = "描述目标，启动一次可追溯的协作。";
  $("#hud-status").textContent = "待启动";
  $("#hud-status").className = "status-badge";
  $("#agent-role").textContent = "团队已就绪";
  $("#agent-dept").textContent = "等待任务分配";
  $("#t-idx").textContent = "0/0";
  $("#t-type").textContent = "等待事件";
  $("#progress-fill").style.width = "0%";
  for (const key of ["aria-valuenow", "aria-valuemax"]) $("#progress").setAttribute(key, "0");
  $("#progress").setAttribute("aria-valuetext", "暂无事件");
  for (const id of ["btn-g1", "btn-auth", "btn-reject", "btn-resume", "btn-export", "action-notice"]) $("#" + id).classList.add("hidden");
}

function clampRows() {
  const rows = [...document.querySelectorAll(".ev:not(.dim)")];
  const more = $("#more");
  rows.forEach((r, i) => { r.style.display = i >= 40 ? "none" : ""; });
  if (!more) return;
  if (rows.length > 40) {
    more.hidden = false;
    more.textContent = `显示其余 ${rows.length - 40} 条事件 ▼`;
    more.onclick = () => { rows.forEach(r => r.style.display = ""); more.hidden = true; };
  } else more.hidden = true;
}

/* ================= 模式：工作台 / 回放 ================= */

let MODE = "workbench", pollTimer = null, lastEventCount = -1;
let viewGeneration = 0, requestPending = false, replayData = null, pollVersion = 0;
let activeRunId = null;
const POLL_MS = 1600;

function setMode(m) {
  setPlaying(false);
  viewGeneration++;
  MODE = m;
  document.body.dataset.mode = m;
  document.querySelectorAll("[data-mode-btn]").forEach(b => {
    b.classList.toggle("active", b.dataset.modeBtn === m);
    b.setAttribute("aria-pressed", String(b.dataset.modeBtn === m));
  });
  $("#pipeline-mode").textContent = m === "workbench" ? "LIVE PIPELINE" : "EVIDENCE REPLAY";
  $("#metric-phase-label").textContent = m === "workbench" ? "当前阶段" : "交付结果";
  $("#t-play").setAttribute("aria-label", m === "workbench" ? "跟随最新事件" : "播放回放");
  clearTimeout(pollTimer);
  resetView();
  if (m === "workbench") {
    lastEventCount = -1;
    poll();
  } else {
    setLive(null, "回放模式：载入证据 JSON 或拖入文件");
    if (replayData) load(replayData.raw, replayData.name);
    else {
      $("#hud-name").textContent = "回看每一次交付";
      $("#hud-zh").textContent = "载入证据文件，重现协作过程。";
      $("#hud-no").textContent = "YOUR DELIVERY, REPLAYED";
    }
  }
}

function setLive(kind, text) {
  const dot = $("#live-dot");
  dot.className = "live-dot" + (kind === true ? " on" : kind === "wait" ? " wait" : kind === false ? " err" : "");
  $("#live-text").textContent = text;
  $("#connection-dot").className = dot.className;
  $("#connection-text").textContent = MODE === "replay" ? "证据回放" : kind === true ? "服务已连接" : kind === "wait" ? "任务执行中" : kind === false ? "连接或作业异常" : "连接中";
}

async function poll() {
  if (MODE !== "workbench") return;
  const runId = $("#in-run").value.trim() || "wb-1";
  // Polling may observe edited input before blur/change; clear the entire old run view first.
  if (activeRunId !== runId) {
    activeRunId = runId;
    viewGeneration++;
    lastEventCount = -1;
    resetView();
  }
  const generation = viewGeneration, version = ++pollVersion;
  if (!/^[A-Za-z0-9_-]{1,80}$/.test(runId)) {
    setLive(false, "运行标识格式不正确，请使用字母、数字、下划线或连字符。");
    $("#btn-start").disabled = true;
    return;
  }
  try {
    const res = await fetch(`/api/state?run_id=${encodeURIComponent(runId)}`,
      { signal: AbortSignal.timeout(5000) });
    const data = await res.json();
    if (generation !== viewGeneration || version !== pollVersion || MODE !== "workbench" || runId !== ($("#in-run").value.trim() || "wb-1")) return;
    if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
    applyServerState(data, runId);
  } catch (_) {
    if (generation !== viewGeneration || version !== pollVersion) return;
    setLive(false, "无法连接工作台服务 — 请运行 python frontend/server.py");
    for (const id of ["btn-start", "btn-g1", "btn-auth", "btn-reject", "btn-resume"]) $("#" + id).disabled = true;
  }
  if (generation === viewGeneration && MODE === "workbench") pollTimer = setTimeout(poll, POLL_MS);
}

function applyServerState(data, runId) {
  const job = data.job || {}, a = data.actions || {};
  const count = (data.events || []).length;
  if (!data.exists && TRACK.length) resetView();

  if (job.busy) setLive("wait", `执行中 · ${job.kind || "job"} · run=${job.run_id || runId}`);
  else if (job.error) setLive(false, `作业失败：${job.error}`);
  else if (!data.exists) setLive(true, "服务已连接 · 等待启动运行");
  else setLive(true, `服务已连接 · ${stateLabel(data.summary?.status)}`);

  // 事件变化才重建面板（避免打断展开状态）
  if (count !== lastEventCount && data.exists) {
    const wasEnd = cursor >= TRACK.length - 1 || cursor < 0;
    renderPanels(data, "实时 · " + runId);
    applyFrame(wasEnd ? TRACK.length - 1 : Math.min(cursor, TRACK.length - 1));
  }
  lastEventCount = count;

  // 介入按钮
  const busy = !!job.busy || requestPending;
  const terminal = ["COMPLETED", "FAILED", "CANCELLED"].includes(data.summary?.status);
  const waiting = a.confirm_g1 || a.authorize || a.resume;
  $("#btn-start").disabled = busy || terminal || waiting;
  $("#btn-start").textContent = busy ? "任务执行中…" : terminal ? "运行已结束" : data.exists ? "继续运行 →" : "启动运行 →";
  for (const id of ["in-run", "in-task", "in-g1", "in-sec"]) $("#" + id).disabled = busy;
  $("#in-run").disabled = requestPending;
  for (const id of ["in-task", "in-g1", "in-sec"]) $("#" + id).disabled = busy || !!data.exists;
  for (const id of ["btn-g1", "btn-auth", "btn-reject", "btn-resume"]) $("#" + id).disabled = busy;
  $("#btn-g1").classList.toggle("hidden", !(a.confirm_g1 && !busy));
  $("#btn-auth").classList.toggle("hidden", !(a.authorize && !busy));
  $("#btn-reject").classList.toggle("hidden", !(a.reject_authorization && !busy));
  $("#btn-resume").classList.toggle("hidden", !(a.resume && !busy));
  $("#btn-export").classList.toggle("hidden", !data.exists);
  const notice = job.error ? `执行异常：${job.error}` : data.stale ? "状态正在同步，当前显示上次确认结果。"
    : a.confirm_g1 ? "等待你的确认：需求与架构已准备好，确认后进入研发。"
    : a.authorize ? "等待发布决策：本次操作为本地模拟发布。"
    : a.resume ? "流程已阻断。请先查看审计记录并排除原因，再恢复运行。"
    : terminal ? "本次运行已结束。可导出证据，或更换运行标识开始新任务。" : "";
  $("#action-notice").textContent = notice;
  $("#action-notice").classList.toggle("hidden", !notice);
  $("#metric-phase").textContent = phaseLabel(data.summary?.phase);
  $("#metric-status").textContent = data.exists ? stateLabel(data.summary?.status) : "准备好后，启动第一个任务";
}

async function api(path, body) {
  if (requestPending) return;
  requestPending = true;
  for (const id of ["btn-start", "btn-g1", "btn-auth", "btn-reject", "btn-resume", "in-run"]) $("#" + id).disabled = true;
  try {
    const session = await fetch('/api/hello').then(r => r.json());
    const res = await fetch(path, { method: "POST",
      headers: { "Content-Type": "application/json", "X-AgentLoop-CSRF": session.csrf },
      body: JSON.stringify(body), signal: AbortSignal.timeout(8000) });
    const data = await res.json();
    if (!res.ok || data.error) toast("失败：" + (data.error || res.status));
    else toast("已下发：" + (data.dispatched || path));
  } catch (err) {
    toast("请求失败：" + err.message);
  } finally { requestPending = false; }
  clearTimeout(pollTimer); pollTimer = setTimeout(poll, 400);
}

$("#btn-start").addEventListener("click", () => {
  if (!$("#in-run").reportValidity()) return;
  api("/api/start", { run_id: $("#in-run").value.trim() || "wb-1",
    task: $("#in-task").value.trim() || undefined,
    require_confirmation: $("#in-g1").checked,
    security_example: $("#in-sec").checked });
});
$("#btn-g1").addEventListener("click", () =>
  api("/api/confirm_g1", { run_id: $("#in-run").value.trim() || "wb-1" }));
$("#btn-auth").addEventListener("click", () =>
  api("/api/authorize", { run_id: $("#in-run").value.trim() || "wb-1", decision: "APPROVE" }));
$("#btn-reject").addEventListener("click", () => {
  if (confirm("拒绝本次模拟发布？Run 将进入 BLOCKED。"))
    api("/api/authorize", { run_id: $("#in-run").value.trim() || "wb-1", decision: "REJECT" });
});
$("#btn-resume").addEventListener("click", () =>
  api("/api/resume", { run_id: $("#in-run").value.trim() || "wb-1" }));
$("#btn-export").addEventListener("click", async () => {
  const runId = $("#in-run").value.trim() || "wb-1";
  try {
    const res = await fetch(`/api/export?run_id=${encodeURIComponent(runId)}`);
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.error || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${runId}-evidence.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast("证据已导出：可在「回放」模式载入");
  } catch (err) { toast("导出失败：" + err.message); }
});
$("#in-run").addEventListener("change", () => {
  try { localStorage.setItem("agentloop-run", $("#in-run").value.trim()); } catch (_) { /* Optional local preference. */ }
  viewGeneration++; lastEventCount = -1; resetView(); clearTimeout(pollTimer); poll();
});

document.querySelectorAll("[data-mode-btn]").forEach(b =>
  b.addEventListener("click", () => setMode(b.dataset.modeBtn)));

/* ================= 回放载入 ================= */

function load(raw, name) {
  if (!raw || !Array.isArray(raw.events) || !Array.isArray(raw.artifacts)
      || raw.events.some(e => !e || typeof e.type !== "string")
      || raw.artifacts.some(a => !a || !a.metadata || typeof a.metadata !== "object")) {
    throw new Error("证据文件需要有效的 events 与 artifacts 数组。");
  }
  if (MODE !== "replay") return;
  replayData = { raw, name };
  renderPanels(raw, name);
  applyFrame(0);
  setPlaying(false);
  setLive(null, `已载入 ${name} · ${TRACK.length} 条事件`);
}

$("#file")?.remove();
const fileInput = document.createElement("input");
fileInput.type = "file"; fileInput.accept = ".json"; fileInput.hidden = true;
document.body.appendChild(fileInput);
fileInput.addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  fileInput.value = "";
  f.text().then(t => load(JSON.parse(t), f.name)).catch(err => toast("解析失败：" + err.message));
});
addEventListener("dragenter", e => {
  if (MODE !== "replay") return;
  e.preventDefault(); $("#drop").classList.add("on");
});
addEventListener("dragover", e => { if (MODE === "replay") e.preventDefault(); });
addEventListener("dragleave", e => { if (MODE !== "replay") return; $("#drop").classList.remove("on"); });
addEventListener("drop", e => {
  if (MODE !== "replay") return;
  e.preventDefault(); $("#drop").classList.remove("on");
  const f = e.dataTransfer.files[0]; if (!f) return;
  f.text().then(t => load(JSON.parse(t), f.name))
    .then(() => toast("已载入 " + f.name))
    .catch(err => toast("解析失败：" + err.message));
});
// 回放模式提供载入按钮（在审计抽屉标题旁）
const btnLoad = document.createElement("button");
btnLoad.className = "btn"; btnLoad.textContent = "载入 JSON";
btnLoad.addEventListener("click", () => {
  if (MODE !== "replay") setMode("replay");
  fileInput.click();
});
$(".d-head").appendChild(btnLoad);
$("#btn-replay-load").addEventListener("click", () => fileInput.click());

/* ================= 一次性事件绑定 ================= */

$("#t-play").addEventListener("click", () => {
  if (MODE === "workbench") seek(TRACK.length - 1);
  else setPlaying(!playing);
});
$("#t-prev").addEventListener("click", () => seek(cursor - 1));
$("#t-next").addEventListener("click", () => seek(cursor + 1));
$("#progress").addEventListener("click", ev => {
  const rect = ev.currentTarget.getBoundingClientRect();
  seek(Math.round((ev.clientX - rect.left) / rect.width * (TRACK.length - 1)));
});
$("#progress").addEventListener("keydown", e => {
  const targets = { ArrowRight: cursor + 1, ArrowLeft: cursor - 1, Home: 0, End: TRACK.length - 1 };
  if (e.key in targets) { e.preventDefault(); seek(targets[e.key]); }
});
$("#t-speed").addEventListener("change", () => { if (playing) schedule(); });
document.addEventListener("visibilitychange", () => {
  if (document.hidden && playing) setPlaying(false);
});

$("#ribbon").addEventListener("click", ev => {
  const b = ev.target.closest(".rb");
  if (!b) return;
  const i = +b.dataset.i;
  if (i < 0) { toast("本次运行未经过「" + b.dataset.phase + "」阶段"); return; }
  seek(i);
});

let auditOpener = null;
function selectPane(name) {
  document.querySelectorAll(".d-tab").forEach(t => {
    const selected = t.dataset.pane === name;
    t.classList.toggle("on", selected);
    t.setAttribute("aria-selected", String(selected));
    t.tabIndex = selected ? 0 : -1;
  });
  document.querySelectorAll(".d-pane").forEach(p => p.classList.toggle("on", p.dataset.pane === name));
}
const openAudit = (pane) => {
  if ($("#audit-view").hidden) auditOpener = document.activeElement;
  if (pane) selectPane(pane);
  $("#workspace").hidden = true;
  $("#audit-view").hidden = false;
  $(".breadcrumb strong").textContent = "运行审计";
  document.querySelectorAll(".nav-item").forEach(button => {
    const selected = button.dataset.openPane === (pane || $(".d-tab.on").dataset.pane);
    button.classList.toggle("selected", selected);
    if (selected) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  window.scrollTo(0, 0);
  $(".d-tab.on").focus();
};
const closeAudit = () => {
  $("#audit-view").hidden = true;
  $("#workspace").hidden = false;
  $(".breadcrumb strong").textContent = "交付工作台";
  document.querySelectorAll(".nav-item").forEach(button => {
    const selected = button.hasAttribute("data-nav-home");
    button.classList.toggle("selected", selected);
    if (selected) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  auditOpener?.focus();
};
$("#btn-drawer").addEventListener("click", () => openAudit());
$("#d-close").addEventListener("click", closeAudit);
document.querySelectorAll("[data-open-pane]").forEach(b => b.addEventListener("click", () => openAudit(b.dataset.openPane)));
$("[data-nav-home]").addEventListener("click", closeAudit);
$("#activity-list").addEventListener("click", e => {
  const row = e.target.closest("[data-event-index]");
  if (!row) return;
  seek(Number(row.dataset.eventIndex)); openAudit("events");
  $(".ev.playing")?.scrollIntoView({ block: "center" });
});

$("#d-tabs").addEventListener("click", ev => {
  const t = ev.target.closest(".d-tab");
  if (!t) return;
  selectPane(t.dataset.pane);
});
$("#d-tabs").addEventListener("keydown", e => {
  const tabs = [...document.querySelectorAll(".d-tab")], current = tabs.indexOf(document.activeElement);
  if (current < 0) return;
  const index = ({ ArrowRight: (current + 1) % tabs.length, ArrowLeft: (current + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 })[e.key];
  if (index === undefined) return;
  e.preventDefault(); selectPane(tabs[index].dataset.pane); tabs[index].focus();
});

$("#timeline").addEventListener("click", ev => {
  const row = ev.target.closest(".ev");
  if (!row) return;
  if (ev.altKey || ev.metaKey) { seek(+row.dataset.i); closeAudit(); return; }
  row.classList.toggle("open");
  row.setAttribute("aria-expanded", String(row.classList.contains("open")));
});
$("#timeline").addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && e.target.matches(".ev")) {
    e.preventDefault(); e.target.click();
  }
});
$("#filters").addEventListener("click", ev => {
  const btn = ev.target.closest("[data-filter]");
  if (!btn) return;
  document.querySelectorAll("[data-filter]").forEach(b => b.classList.toggle("active", b === btn));
  const map = {
    all: () => true,
    gate: t => t.startsWith("GATE_"),
    release: t => /APPROVAL|RELEASE_|DEPLOYMENT/.test(t),
    work: t => /TEST|REWORK|CHECK_TRIGGERED|WORKER|DEPARTMENT|ISSUE|BASELINE/.test(t),
    state: t => /RUN_/.test(t),
  };
  const f = map[btn.dataset.filter];
  document.querySelectorAll(".ev").forEach(r =>
    r.classList.toggle("dim", !f(r.dataset.type || "")));
  clampRows();
});

$("#d-artifacts").addEventListener("click", ev => {
  const head = ev.target.closest(".arow-head");
  if (!head) return;
  const row = head.parentElement;
  const willOpen = !row.classList.contains("open");
  document.querySelectorAll(".arow.open").forEach(r => r.classList.remove("open"));
  row.classList.toggle("open", willOpen);
});

const stage = $("#stage");
stage.addEventListener("pointermove", ev => {
  const r = stage.getBoundingClientRect();
  const nx = (ev.clientX - r.left) / r.width - .5;
  const ny = (ev.clientY - r.top) / r.height - .5;
  $("#parallax").style.setProperty("--ry", (nx * 4) + "deg");
  $("#parallax").style.setProperty("--rx", (-ny * 3) + "deg");
});
stage.addEventListener("pointerleave", () => {
  $("#parallax").style.setProperty("--ry", "0deg");
  $("#parallax").style.setProperty("--rx", "0deg");
});

/* ================= 主题 ================= */
/* 视觉基线已对齐 console，页面固定深色工业风，不再提供明暗切换。
   注意：不要写 document.documentElement.dataset.theme，
   scenes.css 的 [data-theme="dark"] 令牌优先级高于 workbench.css 的 :root，会把配色覆回旧绿色系。 */

/* ================= 启动 ================= */

try {
  const savedRun = localStorage.getItem("agentloop-run");
  if (/^[A-Za-z0-9_-]{1,80}$/.test(savedRun || "")) $("#in-run").value = savedRun;
} catch (_) { /* The default run remains usable when storage is unavailable. */ }
setMode("workbench");
window.__seek = seek;
window.__apply = applyFrame;
window.__errors = [];
addEventListener("error", e => window.__errors.push(String(e.message)));

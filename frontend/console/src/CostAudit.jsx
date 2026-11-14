import React,{useMemo,useState} from 'react';
import Icon from './Icon';

/*
 * 成本与审计 —— 对标 Datadog Cost / Grafana Logs / OpenTelemetry 的信息表达：
 *   预算额度看“已用 / 授予”双进度条，事件看可筛选的追加式时间线，证据看可校验的哈希卡片。
 * 所有数字均来自后端持久记录；无记录时明确显示空态，不做任何估算或补全。
 */

const EVENT_TEXT = {
  RUN_CREATED:'运行已创建',
  RUN_PHASE_CHANGED:'阶段跃迁',
  RUN_STATUS_CHANGED:'状态变更',
  RUN_STATE_VERSION_CONFLICT:'状态版本冲突',
  INVALID_TRANSITION_REJECTED:'非法跃迁被拒',
  GATE_EVALUATION_STARTED:'门禁评估开始',
  GATE_RESULT_RECORDED:'门禁结论已记录',
  GATE_RESULT_INVALIDATED:'门禁结论失效',
  APPROVAL_REQUEST_CREATED:'审批请求已创建',
  APPROVAL_REQUEST_DECIDED:'审批已裁决',
  APPROVAL_REQUEST_REVOKED:'审批已撤销',
  CLARIFICATION_REQUESTED:'发起澄清',
  CLARIFICATION_ANSWERED:'澄清已答复',
  ISSUE_RAISED:'问题已提出',
  ISSUE_ROUTED:'问题已路由',
  ACCESS_DENIED:'访问被拒',
  UNTRUSTED_INSTRUCTION_DETECTED:'检出不可信指令',
  RELEASE_CREATED:'发布单已创建',
  RELEASE_AUTHORIZATION_REQUESTED:'请求发布授权',
  RELEASE_AUTHORIZATION_DECIDED:'发布授权已裁决',
  RELEASE_AUTHORIZATION_REVOKED:'发布授权已撤销',
  DEPLOYMENT_ATTEMPTED:'部署已尝试',
  DEPLOYMENT_RESULT_RECORDED:'部署结果已记录',
  RECONCILIATION_RECORDED:'对账已记录',
  WORKER_OUTPUT_RECORDED:'执行者产出已记录',
  DEPARTMENT_ACCEPTED:'部门已接收',
  CHECK_TRIGGERED:'触发检查',
  TEST_EXECUTED:'测试已执行',
  LOCAL_REWORK:'本地返工',
  EXTERNAL_REWORK:'跨部门返工',
  ISSUE_RESOLVED:'问题已解决',
  BASELINE_CHANGED:'基线已变更',
  RUNTIME_AUDIT:'运行时审计',
  RETROSPECTIVE_REQUESTED:'已请求复盘',
  RETROSPECTIVE_COMPLETED:'复盘已完成',
  MEMORY_PROPOSAL_SUBMITTED:'记忆提案已提交',
  MEMORY_PROPOSAL_DECIDED:'记忆提案已裁决',
  MEMORY_REVOKED:'记忆已撤销',
  BUDGET_BLOCKED:'预算被阻断',
  BUDGET_INCREASE_APPROVED:'预算增额已批准',
  MODEL_USAGE:'模型用量已结算',
  SKILL_QUARANTINED:'Skill 已隔离',
  SKILL_APPROVED:'Skill 已批准',
  SKILL_BOUND:'Skill 已绑定',
  SKILL_DISABLED:'Skill 已停用',
  MCP_QUARANTINED:'MCP 已隔离',
  MCP_APPROVED:'MCP 已批准',
  MCP_DISABLED:'MCP 已停用',
  MCP_UNINSTALLED:'MCP 已卸载',
};

const RISK_EVENTS = new Set([
  'RUN_STATE_VERSION_CONFLICT','INVALID_TRANSITION_REJECTED','ACCESS_DENIED',
  'UNTRUSTED_INSTRUCTION_DETECTED','BUDGET_BLOCKED',
]);

const TRUST_TEXT = {
  HUMAN_SIGNED:'人工签署',
  MODEL_GENERATED:'模型生成',
  SYSTEM_DERIVED:'系统派生',
  UNVERIFIED:'未验证',
};

const EVENT_TYPE_GROUPS = [
  {key:'run',label:'运行生命周期',match:t=>/^RUN_|^INVALID_/.test(t)},
  {key:'gate',label:'门禁与审批',match:t=>/^GATE_|^APPROVAL_|^CLARIFICATION_/.test(t)},
  {key:'issue',label:'问题与返工',match:t=>/^ISSUE_|^WORKER_|^DEPARTMENT_|^CHECK_|^TEST_|^LOCAL_|^EXTERNAL_|^BASELINE/.test(t)},
  {key:'release',label:'发布与部署',match:t=>/^RELEASE_|^DEPLOYMENT_|^RECONCILIATION/.test(t)},
  {key:'knowledge',label:'知识与记忆',match:t=>/^RETROSPECTIVE_|^MEMORY_/.test(t)},
  {key:'governance',label:'治理与扩展',match:t=>/^SKILL_|^MCP_|^BUDGET_|^MODEL_USAGE|^RUNTIME_AUDIT/.test(t)},
];

function eventGroup(type){
  const hit = EVENT_TYPE_GROUPS.find(g=>g.match(type));
  return hit ? hit.key : 'other';
}

function formatTokens(n){
  const value = Number(n) || 0;
  if (value >= 1000000) return (value/1000000).toFixed(value>=10000000?0:1)+'M';
  if (value >= 1000) return (value/1000).toFixed(value>=10000?0:1)+'K';
  return String(value);
}

function formatMicroUsd(n){
  const value = Number(n) || 0;
  if (value === 0) return '$0';
  const usd = value/1000000;
  if (usd >= 100) return '$'+usd.toFixed(0);
  if (usd >= 1) return '$'+usd.toFixed(2);
  return '$'+usd.toFixed(4);
}

function formatTime(value){
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = n=>String(n).padStart(2,'0');
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function usageTone(ratio,overrun){
  if (overrun) return 'bad';
  if (ratio >= 0.9) return 'warn';
  if (ratio >= 0.7) return 'live';
  return 'ok';
}

function UsageBar({ratio,overrun,label,detail}){
  const pct = Math.max(0,Math.min(1,ratio||0));
  const tone = usageTone(pct,overrun);
  return <div className="usage-cell">
    <div className="usage-meta"><span>{label}</span><b>{detail}</b></div>
    <div className="usage-bar" role="meter" aria-valuenow={Math.round(pct*100)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <i className={'tone-'+tone} style={{width:(pct*100).toFixed(1)+'%'}}/>
    </div>
  </div>;
}

export default function CostAudit({budgets=[],budgetSummary=null,events=[],artifacts=[],onCopy}){
  const [query,setQuery]=useState('');
  const [group,setGroup]=useState('all');
  const [openEvent,setOpenEvent]=useState('');
  const [openArtifact,setOpenArtifact]=useState('');

  const limits = (budgetSummary&&budgetSummary.limits)||null;
  const usedTokens = budgetSummary?Number(budgetSummary.tokens)||0:0;
  const usedCost = budgetSummary?Number(budgetSummary.cost_micro_usd_estimate)||0:0;
  const calls = (budgetSummary&&budgetSummary.calls)||[];
  const tokenLimit = limits?Number(limits.initial_tokens||limits.tokens)||0:0;
  const costLimit = limits?Number(limits.initial_cost||limits.cost)||0:0;
  const tokenRatio = tokenLimit?usedTokens/tokenLimit:0;
  const costRatio = costLimit?usedCost/costLimit:0;

  // 运行时审计事件只带 Artifact ID，真实动作名在归档体里（与后端 audit 路径一致）
  const actionMap = useMemo(()=>{
    const map={};
    artifacts.forEach(a=>{
      const body=a.body;
      if(a.metadata&&a.metadata.type==='RUNTIME_AUDIT'&&body&&body.action){
        map[a.metadata.artifact_id]=body.action;
      }
    });
    return map;
  },[artifacts]);

  const labelOf=e=>{
    if(e.type==='RUNTIME_AUDIT'){
      const action=actionMap[e.payload_ref];
      if(action) return action;
    }
    return e.type;
  };

  const groups = useMemo(()=>{
    const present=new Set(events.map(e=>eventGroup(labelOf(e))));
    return EVENT_TYPE_GROUPS.filter(g=>present.has(g.key)).concat(
      present.has('other')?[{key:'other',label:'其他',match:()=>true}]:[]);
  },[events,actionMap]);

  const filtered = useMemo(()=>{
    const needle=query.trim().toLowerCase();
    return events.filter(e=>{
      const label=labelOf(e);
      if(group!=='all'&&eventGroup(label)!==group) return false;
      if(!needle) return true;
      return `${label} ${e.type} ${e.actor_id} ${e.actor_type||''} ${e.payload_ref||''}`.toLowerCase().includes(needle);
    });
  },[events,query,group,actionMap]);

  const riskCount = events.filter(e=>RISK_EVENTS.has(labelOf(e))).length;
  const actorCount = new Set(events.map(e=>e.actor_id)).size;

  return <>
    <section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="chart" size={16}/><h2>预算与成本</h2></div>
        <span className="settings-chip">MICRO-USD · 实际结算</span>
      </div>
      {limits? <>
        <div className="budget-grid">
          <div className="budget-card">
            <div className="budget-card-head"><span>令牌预算</span><Icon name="cpu" size={14}/></div>
            <UsageBar ratio={tokenRatio} overrun={limits.overrun}
              label={`${formatTokens(usedTokens)} / ${formatTokens(tokenLimit)} tok`}
              detail={tokenLimit?Math.round(tokenRatio*100)+'%':'—'}/>
            <div className="budget-foot">剩余 {formatTokens(Math.max(0,tokenLimit-usedTokens))} tok 可用</div>
          </div>
          <div className="budget-card">
            <div className="budget-card-head"><span>成本预算</span><Icon name="zap" size={14}/></div>
            <UsageBar ratio={costRatio} overrun={limits.overrun}
              label={`${formatMicroUsd(usedCost)} / ${formatMicroUsd(costLimit)}`}
              detail={costLimit?Math.round(costRatio*100)+'%':'—'}/>
            <div className="budget-foot">剩余 {formatMicroUsd(Math.max(0,costLimit-usedCost))} 可用</div>
          </div>
          <div className="budget-card">
            <div className="budget-card-head"><span>模型调用</span><Icon name="activity" size={14}/></div>
            <div className="budget-figure"><b>{calls.length}</b><span>次已结算调用</span></div>
            <div className="budget-foot">{calls.filter(c=>c.status==='RESERVED').length} 条预占未结算</div>
          </div>
        </div>
        <div className="usage-ledger">
          <div className="usage-ledger-head">
            <span>用量流水</span>
            <code>{limits.root}</code>
          </div>
          {calls.length? <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>角色</th><th>运行</th><th>令牌</th><th>成本</th><th>状态</th></tr></thead>
              <tbody>{calls.map(c=>(
                <tr key={c.id}>
                  <td><span className="type-tag">{c.role}</span></td>
                  <td><code className="phase-code">{c.run_id}</code></td>
                  <td className="mono-num">{formatTokens(c.tokens)}</td>
                  <td className="mono-num">{formatMicroUsd(c.cost)}</td>
                  <td><span className={'status-pill '+(c.status==='SETTLED'?'tone-ok':c.status==='RESERVED'?'tone-live':'tone-warn')}>
                    <i className="status-dot"/>{c.status==='SETTLED'?'已结算':c.status==='RESERVED'?'预占中':c.status}
                  </span></td>
                </tr>
              ))}</tbody>
            </table>
          </div> : <p className="empty">暂无模型调用记录。预算已授予但还没有发生任何真实用量。</p>}
        </div>
      </> : <p className="empty">当前运行没有预算记录。没有模型调用时不显示虚构费用。</p>}
    </section>

    <section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="terminal" size={16}/><h2>完整事件审计</h2></div>
        <span className="settings-chip">{events.length} EVENTS</span>
      </div>
      <div className="run-table-toolbar">
        <label className="table-search">
          <Icon name="search" size={14}/>
          <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索事件类型、主体或载荷"/>
        </label>
        <div className="status-filters">
          <button type="button" className={'chip'+(group==='all'?' active':'')} onClick={()=>setGroup('all')}>全部<i>{events.length}</i></button>
          {groups.map(g=>(
            <button type="button" key={g.key} className={'chip'+(group===g.key?' active':'')} onClick={()=>setGroup(g.key)}>
              {g.label}<i>{events.filter(e=>eventGroup(labelOf(e))===g.key).length}</i>
            </button>
          ))}
        </div>
      </div>
      <div className="audit-summary">
        <span><Icon name="file" size={12}/>{filtered.length} / {events.length} 条</span>
        <span><Icon name="circle-dot" size={12}/>{actorCount} 个主体</span>
        {riskCount>0&&<span className="warn-text"><Icon name="alert-triangle" size={12}/>{riskCount} 条风险事件</span>}
      </div>
      {filtered.length? <div className="event-stream">
        {filtered.map(e=>{
          const expanded = openEvent===e.event_id||openEvent===e.idempotency_key;
          const label = labelOf(e);
          const risky = RISK_EVENTS.has(label);
          const isAudit = e.type==='RUNTIME_AUDIT'&&actionMap[e.payload_ref];
          return <article key={e.event_id||e.idempotency_key} className={'event-row'+(risky?' risky':'')+(expanded?' open':'')}>
            <button type="button" className="event-row-head" onClick={()=>setOpenEvent(expanded?'':e.event_id||e.idempotency_key)} aria-expanded={expanded}>
              <span className="event-seq">#{e.sequence}</span>
              <span className="event-type">{EVENT_TEXT[label]||label}</span>
              {isAudit&&<span className="type-tag">AUDIT</span>}
              <span className="event-actor"><Icon name="circle-dot" size={11}/>{e.actor_id}</span>
              <span className="event-time">{formatTime(e.timestamp)}</span>
              <Icon name="chevron-down" size={14} className={expanded?'flip':''}/>
            </button>
            <div className="event-payload">{e.payload_ref||'—'}</div>
            {expanded&&<div className="event-raw"><pre>{JSON.stringify(e,null,2)}</pre></div>}
          </article>;
        })}
      </div> : <p className="empty">没有符合条件的事件。事件日志为追加式，不可修改或删除。</p>}
    </section>

    <section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="lock" size={16}/><h2>不可变交付证据</h2></div>
        <span className="settings-chip">{artifacts.length} ARTIFACTS</span>
      </div>
      {artifacts.length? <div className="artifact-grid">
        {artifacts.map(a=>{
          const meta=a.metadata||{};
          const expanded = openArtifact===meta.artifact_id;
          return <article key={meta.artifact_id} className={'artifact-card'+(expanded?' open':'')}>
            <div className="artifact-head">
              <span className="artifact-type"><Icon name="file" size={14}/>{meta.type||'ARTIFACT'}</span>
              <span className="artifact-trust">{TRUST_TEXT[meta.trust_level]||meta.trust_level||'—'}</span>
            </div>
            <div className="artifact-hash">
              <code>{(meta.sha256||'').slice(0,24)}</code>
              <button type="button" className="icon-button visible" title="复制 SHA-256"
                onClick={()=>onCopy&&onCopy(meta.sha256,`SHA-256 ${meta.type||''}`)}><Icon name="copy" size={13}/></button>
            </div>
            <dl className="artifact-meta">
              <div><dt>URI</dt><dd>{meta.uri||'—'}</dd></div>
              <div><dt>产出者</dt><dd>{meta.producer_task_id||'—'}</dd></div>
              <div><dt>版本</dt><dd>{meta.version||'—'}</dd></div>
              <div><dt>时间</dt><dd>{formatTime(meta.created_at)}</dd></div>
            </dl>
            <button type="button" className="artifact-toggle" onClick={()=>setOpenArtifact(expanded?'':meta.artifact_id)}>
              <Icon name={expanded?'chevron-down':'chevron-right'} size={13}/>
              {expanded?'收起内容':'查看内容'}
            </button>
            {expanded&&<pre className="artifact-body">{JSON.stringify(a.body,null,2)}</pre>}
          </article>;
        })}
      </div> : <p className="empty">当前运行没有归档证据。证据一经写入即不可覆盖。</p>}
    </section>
  </>;
}

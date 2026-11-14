import React,{useMemo,useState} from 'react';
import Icon from './Icon';

/*
 * 复盘与记忆 —— 对标 Linear Issue 详情 / Confluence 审阅流的表达：
 *   复盘是被触发的独立动作，提案是可裁决的卡片，记忆是可检索可回滚的版本化条目。
 * 置信度一律以计量条呈现，不伪装成百分比精确结论；证据一律以可点开的引用呈现。
 */

const PROPOSAL_TEXT = {
  PENDING_HUMAN_REVIEW:'待人工审核',
  APPROVED:'已批准',
  REJECTED:'已拒绝',
  REVOKED:'已撤销',
};

const MEMORY_STATUS_TEXT = {
  ACTIVE:'生效中',
  DEPRECATED:'已废弃',
  REVOKED:'已撤销',
};

const SCOPE_TEXT = {
  AGENT:'智能体',
  DEPARTMENT:'部门',
  PROJECT:'项目',
  SHARED:'共享',
};

const MATURITY_TEXT = {
  OBSERVED:'观察所得',
  CANDIDATE:'候选',
  VALIDATED:'已验证',
  PUBLISHED:'已发布',
  DEPRECATED:'已废弃',
};

function proposalTone(status){
  if (status==='APPROVED') return 'tone-ok';
  if (status==='PENDING_HUMAN_REVIEW') return 'tone-warn';
  if (status==='REJECTED') return 'tone-bad';
  return 'tone-live';
}

function memoryTone(status){
  if (status==='ACTIVE') return 'tone-ok';
  if (status==='DEPRECATED') return 'tone-warn';
  return 'tone-bad';
}

function formatTime(value){
  if (!value) return '—';
  const date=new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad=n=>String(n).padStart(2,'0');
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function ConfidenceMeter({value}){
  const pct=Math.max(0,Math.min(1,Number(value)||0));
  return <div className="meter" title={`置信度 ${pct.toFixed(2)}`}>
    <span className="meter-track"><i style={{width:(pct*100).toFixed(1)+'%'}}/></span>
    <span>{pct.toFixed(2)}</span>
  </div>;
}

function ActionTile({icon,title,desc,enabled,blockedOn,onClick,busy,tone}){
  return <button type="button" className={'action-tile'+(enabled?' ready':'')+(tone?' '+tone:'')} disabled={!enabled||busy} onClick={onClick}>
    <span className="action-tile-icon"><Icon name={icon} size={16}/></span>
    <span className="action-tile-body">
      <strong>{title}</strong>
      <small>{desc}</small>
      {!enabled&&blockedOn&&<em><Icon name="lock" size={11}/>{blockedOn}</em>}
    </span>
    <Icon name="arrow-right" size={14} className="action-tile-go"/>
  </button>;
}

function EvolutionCard({proposal,act,busy}){
  const[verification,setVerification]=useState('');
  const[hash,setHash]=useState('');
  const[proof,setProof]=useState('');
  const pending = proposal.status==='PENDING_HUMAN_REVIEW';
  const publishable = proposal.status==='APPROVED'&&proposal.kind==='SKILL';
  return <article className="evolution-card">
    <div className="evolution-head">
      <span className="type-tag">{proposal.kind}</span>
      <strong>{proposal.target}</strong>
      <span className={'status-pill '+proposalTone(proposal.status)}><i className="status-dot"/>{PROPOSAL_TEXT[proposal.status]||proposal.status}</span>
    </div>
    <p className="evolution-summary">{proposal.summary}</p>
    <div className="evolution-plan">
      <span className="evolution-plan-label">验证计划</span>
      <p>{proposal.verification_plan}</p>
    </div>
    {proposal.verification_result&&<div className="evolution-verified">
      <Icon name="check-circle" size={13}/>独立验证结果：{proposal.verification_result}
    </div>}
    {pending&&<div className="evolution-actions">
      <label className="field">
        <span className="field-label">独立验证结果</span>
        <span className="field-control"><Icon name="terminal" size={14}/><input value={verification} onChange={e=>setVerification(e.target.value)} placeholder="记录实际执行的验证命令与结论"/></span>
      </label>
      <div className="evolution-buttons">
        <button type="button" className="primary-action" disabled={busy||!verification.trim()} onClick={()=>act('evolution-review',{proposal_id:proposal.proposal_id,decision:'APPROVE',verification})}>
          <Icon name="check" size={14}/>审核通过
        </button>
        <button type="button" className="secondary" disabled={busy} onClick={()=>act('evolution-review',{proposal_id:proposal.proposal_id,decision:'REJECT'})}>
          <Icon name="x" size={14}/>拒绝提案
        </button>
      </div>
    </div>}
    {publishable&&<div className="evolution-actions">
      <div className="evolution-grid">
        <label className="field">
          <span className="field-label">已隔离导入的 Skill 内容哈希</span>
          <span className="field-control"><Icon name="lock" size={14}/><input value={hash} onChange={e=>setHash(e.target.value)} placeholder="sha256"/></span>
        </label>
        <label className="field">
          <span className="field-label">可信 SKILL_VERIFICATION 证据 ID</span>
          <span className="field-control"><Icon name="file" size={14}/><input value={proof} onChange={e=>setProof(e.target.value)} placeholder="artifact id"/></span>
        </label>
      </div>
      <div className="evolution-buttons">
        <button type="button" className="primary-action" disabled={busy||!hash||!proof} onClick={()=>act('evolution-publish',{proposal_id:proposal.proposal_id,hash,verification_artifact_id:proof,role:'backend'})}>
          <Icon name="rocket" size={14}/>发布已验证版本到 Backend
        </button>
      </div>
      <p className="hint">保留当前运行快照；新配置须显式选择该版本。</p>
    </div>}
  </article>;
}

export default function Knowledge({selected,reports=[],proposals=[],memories=[],evolutions=[],busy,act,reason,setReason,query,setQuery}){
  const[openProposal,setOpenProposal]=useState('');
  const[openMemory,setOpenMemory]=useState('');

  const filteredMemories = useMemo(()=>{
    const needle=(query||'').trim().toLowerCase();
    if (!needle) return memories;
    return memories.filter(m=>`${m.title} ${m.content} ${m.scope_type} ${m.scope_id||''}`.toLowerCase().includes(needle));
  },[memories,query]);

  const status = selected?.status;
  const canRetrospect = status==='COMPLETED';
  const canAnomaly = status==='FAILED'||status==='CANCELLED';

  const activeCount = memories.filter(m=>m.status==='ACTIVE').length;

  return <>
    <section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="refresh" size={16}/><h2>手动复盘</h2></div>
        <span className="settings-chip">HUMAN TRIGGERED</span>
      </div>
      <p className="hint">复盘读取冻结的原始证据，生成独立子运行；不会重开父交付或自动发布记忆。</p>
      <div className="action-tiles">
        <ActionTile icon="activity" title="生成交付复盘" desc="针对已完成交付，汇总全过程证据与结论"
          enabled={!!canRetrospect} blockedOn={status?`当前运行状态为 ${status}`:'请先选择运行'} tone="ok"
          busy={busy} onClick={()=>act('retrospect')}/>
        <ActionTile icon="alert-triangle" title="生成异常复盘" desc="针对失败或取消的运行，复盘异常路径"
          enabled={!!canAnomaly} blockedOn={status?`当前运行状态为 ${status}`:'请先选择运行'} tone="warn"
          busy={busy} onClick={()=>act('retrospect',{anomaly:true})}/>
      </div>
      {reports.length? <div className="report-list">
        {reports.map(r=>{
          const id=r.record&&r.record.retrospective_run_id;
          const summary=(r.report&&(r.report.summary||r.report.title))||'';
          const opened=openProposal===id;
          return <article key={id} className={'report-card'+(opened?' open':'')}>
            <button type="button" className="report-head" onClick={()=>setOpenProposal(opened?'':id)} aria-expanded={opened}>
              <span className="report-icon"><Icon name="file" size={14}/></span>
              <span className="report-title">{summary||'复盘报告'}</span>
              <code>{id}</code>
              <Icon name="chevron-down" size={14} className={opened?'flip':''}/>
            </button>
            {opened&&<div className="report-body">
              <dl className="report-meta">
                <div><dt>复盘运行</dt><dd>{id}</dd></div>
                <div><dt>模式</dt><dd>{(r.record&&r.record.mode)||'FULL_DELIVERY'}</dd></div>
                <div><dt>创建时间</dt><dd>{formatTime(r.record&&r.record.created_at)}</dd></div>
              </dl>
              <pre className="report-json">{JSON.stringify(r.report,null,2)}</pre>
            </div>}
          </article>;
        })}
      </div> : <p className="empty">尚无复盘报告。只有手动触发才会生成。</p>}
    </section>

    <section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="archive" size={16}/><h2>记忆提案审核</h2></div>
        <span className="settings-chip">{String(proposals.length||0)} PENDING</span>
      </div>
      {proposals.length? <>
        <label className="field">
          <span className="field-label">审核原因 / 补偿说明</span>
          <span className="field-control"><Icon name="pencil" size={14}/><input value={reason||''} onChange={e=>setReason&&setReason(e.target.value)} placeholder="说明批准、拒绝或回滚的依据"/></span>
        </label>
        <div className="proposal-list">
          {proposals.map(p=>{
            const opened=openProposal===p.proposal_id;
            return <article key={p.proposal_id} className={'proposal-card'+(opened?' open':'')}>
              <div className="proposal-head">
                <div className="proposal-title">
                  <span className="proposal-scope">{SCOPE_TEXT[p.scope_type]||p.scope_type}</span>
                  <strong>{p.title}</strong>
                </div>
                <span className={'status-pill '+proposalTone(p.status)}><i className="status-dot"/>{PROPOSAL_TEXT[p.status]||p.status}</span>
              </div>
              <p className="proposal-content">{p.content}</p>
              <div className="proposal-meta">
                <span><Icon name="circle-dot" size={11}/>成熟度 {MATURITY_TEXT[p.maturity]||p.maturity}</span>
                <span><Icon name="clock" size={11}/>{formatTime(p.created_at)}</span>
                <span><Icon name="archive" size={11}/>{(p.source_artifact_ids||[]).length} 条证据</span>
              </div>
              <div className="proposal-confidence">
                <span className="field-label">置信度</span>
                <ConfidenceMeter value={p.confidence}/>
                {p.injection_flagged&&<span className="risk-flag"><Icon name="alert-triangle" size={11}/>注入风险标记</span>}
              </div>
              <div className="proposal-footer">
                <button type="button" className="proposal-evidence" onClick={()=>setOpenProposal(opened?'':p.proposal_id)}>
                  <Icon name="link" size={12}/>{opened?'收起证据引用':'查看证据引用'}
                </button>
                <div className="proposal-actions">
                  <button type="button" className="primary-action" disabled={busy} onClick={()=>act('memory-review',{proposal_id:p.proposal_id,decision:'APPROVE',reason})}>
                    <Icon name="check" size={14}/>批准发布
                  </button>
                  <button type="button" className="secondary" disabled={busy} onClick={()=>act('memory-review',{proposal_id:p.proposal_id,decision:'REJECT',reason})}>
                    <Icon name="x" size={14}/>拒绝
                  </button>
                </div>
              </div>
              {opened&&<div className="proposal-evidence-list">
                {(p.source_artifact_ids||[]).map(id=><code key={id}>{id}</code>)}
              </div>}
            </article>;
          })}
        </div>
      </> : <p className="empty">暂无待审记忆。只有手动复盘才生成候选，且必须经人工批准后才可检索。</p>}
    </section>

    <section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="database" size={16}/><h2>正式记忆与版本</h2></div>
        <span className="settings-chip">{activeCount} / {memories.length} ACTIVE</span>
      </div>
      <div className="run-table-toolbar">
        <label className="table-search">
          <Icon name="search" size={14}/>
          <input aria-label="搜索正式记忆" value={query||''} onChange={e=>setQuery&&setQuery(e.target.value)} placeholder="搜索标题、内容或作用域"/>
        </label>
      </div>
      {filteredMemories.length? <div className="memory-list">
        {filteredMemories.map(m=>{
          const opened=openMemory===m.memory_id;
          return <article key={m.memory_id} className={'memory-card'+(opened?' open':'')}>
            <div className="memory-head">
              <div className="memory-title">
                <strong>{m.title}</strong>
                <span className="type-tag">v{m.version}</span>
                <span className={'status-pill '+memoryTone(m.status)}><i className="status-dot"/>{MEMORY_STATUS_TEXT[m.status]||m.status}</span>
              </div>
              <div className="memory-head-right">
                <ConfidenceMeter value={m.confidence}/>
                <button type="button" className="icon-button visible" title={opened?'收起':'展开'} onClick={()=>setOpenMemory(opened?'':m.memory_id)}>
                  <Icon name={opened?'chevron-down':'chevron-right'} size={14}/>
                </button>
              </div>
            </div>
            <p className="memory-content">{m.content}</p>
            <div className="memory-meta">
              <span><Icon name="layers" size={11}/>{SCOPE_TEXT[m.scope_type]||m.scope_type}{m.scope_id?' / '+m.scope_id:''}</span>
              <span><Icon name="check-circle" size={11}/>批准人 {m.approved_by}</span>
              <span><Icon name="clock" size={11}/>{formatTime(m.approved_at)}</span>
              <span><Icon name="archive" size={11}/>{(m.source_artifact_ids||[]).length} 条证据</span>
            </div>
            {opened&&<div className="memory-foot">
              {(m.source_artifact_ids||[]).map(id=><code key={id}>{id}</code>)}
              <div className="memory-actions">
                {m.status==='ACTIVE'&&<button type="button" className="secondary" disabled={busy} onClick={()=>act('memory-revoke',{memory_id:m.memory_id,reason})}>
                  <Icon name="trash" size={13}/>撤销检索
                </button>}
                {m.status==='DEPRECATED'&&<button type="button" className="primary-action" disabled={busy||!reason} onClick={()=>act('memory-rollback',{memory_id:m.memory_id,reason})}>
                  <Icon name="refresh" size={13}/>回滚到此版本
                </button>}
              </div>
            </div>}
          </article>;
        })}
      </div> : <p className="empty">没有匹配的正式记忆。</p>}
    </section>

    <section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="sparkles" size={16}/><h2>Skills / 配置演进提案</h2></div>
        <span className="settings-chip">{String(evolutions.length||0)} PROPOSALS</span>
      </div>
      <p className="hint">批准提案不直接改动运行中的配置。需要独立测试证据与后续发布。</p>
      {evolutions.length? <div className="evolution-list">
        {evolutions.map(p=><EvolutionCard key={p.proposal_id} proposal={p} act={act} busy={busy}/>)}
      </div> : <p className="empty">暂无演进提案。提案只能由人工复盘触发。</p>}
    </section>
  </>;
}

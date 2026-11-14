import React from 'react';
import Icon from './Icon';
import {StatusPill} from './RunTable';

const GATES = [['G1', '方案确认'], ['G2', '质量审查'], ['G3', '交付验证']];

export function GateTrack({gates = []}) {
  return <ol className="gate-track" aria-label="质量门禁">
    {GATES.map(([id, label]) => {
      const latest = gates.filter(gate => gate.gate_id === id)
        .reduce((last, gate) => !last || gate.created_at >= last.created_at ? gate : last, null);
      return <li key={id}>
        <code>{id}</code><span>{label}</span>
        {latest ? <StatusPill status={latest.status}/> : <small>暂无记录</small>}
      </li>;
    })}
  </ol>;
}

export default function RunContext({run, gates, job, openApprovals, openAudit, openKnowledge, selectRun}) {
  if (!run) return <section className="run-context context-empty" aria-label="运行详情">
    <span className="context-symbol"><Icon name="activity" size={20}/></span>
    <h2>运行详情</h2><p>选择列表中的一条运行，查看当前阶段、质量门禁与下一步操作。</p>
  </section>;
  const needsReview = ['WAITING_APPROVAL', 'PAUSED_FOR_HUMAN', 'NEEDS_RECONCILIATION'].includes(run.status);
  return <section className="run-context" aria-label="运行详情">
    <div className="context-title"><span className="context-symbol"><Icon name="activity" size={20}/></span><StatusPill status={run.status}/></div>
    <h2>{run.run_id}</h2>
    <dl className="context-meta">
      <div><dt>当前阶段</dt><dd><code>{run.phase}</code></dd></div>
      <div><dt>运行类型</dt><dd><code>{run.run_type}</code></dd></div>
      {run.parent_run_id && <div><dt>父运行</dt><dd><button className="context-link" type="button" onClick={() => selectRun(run.parent_run_id)}>{run.parent_run_id}</button></dd></div>}
    </dl>
    <GateTrack gates={gates}/>
    {job?.error && <p className="alert" role="alert">{job.error}</p>}
    <div className="context-actions">
      <button type="button" className={needsReview ? '' : 'secondary'} onClick={openApprovals}>
        <Icon name="shield-check" size={15}/>{needsReview ? '查看待处理事项' : '查看门禁与发布'}<Icon name="arrow-right" size={14}/>
      </button>
      <button type="button" className="secondary" onClick={openAudit}><Icon name="chart" size={15}/>查看证据与审计</button>
      {run.run_type === 'DELIVERY' && run.status === 'COMPLETED' &&
        <button type="button" className="secondary" onClick={openKnowledge}><Icon name="archive" size={15}/>前往复盘</button>}
    </div>
  </section>;
}

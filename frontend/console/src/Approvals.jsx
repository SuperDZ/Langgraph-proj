import React, {useState} from 'react';
import {GateTrack} from './RunContext';
import {StatusPill} from './RunTable';

const OPERATIONS = {
  target: ['登记预发目标', 'target_id', 'port'],
  request: ['申请发布许可', 'target_id'],
  approve: ['批准许可申请', 'request_id'],
  reject: ['拒绝许可申请', 'request_id'],
  deploy: ['部署到预发环境', 'target_id', 'authorization_id'],
  reconcile: ['查询并对账', 'effect_id'],
  rollback: ['回滚部署', 'deployment_id', 'authorization_id'],
  schedule: ['安排周期巡检', 'target_id'],
  tick: ['执行到期巡检'],
  cancel: ['请求取消运行'],
  'settle-cancel': ['结算取消'],
};
const FIELDS = {target_id:'目标标识', port:'代理端口', request_id:'申请标识', authorization_id:'许可标识', deployment_id:'部署标识', effect_id:'外部操作标识'};
const Json = ({value}) => <pre>{JSON.stringify(value, null, 2)}</pre>;

function Clarification({item, busy, version, submit}) {
  const [answer, setAnswer] = useState('');
  return <form className="review-task" onSubmit={event => {
    event.preventDefault();
    if (answer.trim()) submit({question_id:item.question_id, expected_version:version, answer:answer.trim()});
  }}>
    <h3>回答澄清问题</h3><p>{item.question}</p>
    {item.options?.length > 0 && <ul>{item.options.map(option => <li key={option}>{option}</li>)}</ul>}
    <label>澄清答复<textarea rows={2} value={answer} onChange={event => setAnswer(event.target.value)} required/></label>
    <button disabled={busy || !answer.trim()}>提交答复</button>
    <details><summary>问题依据</summary><Json value={{input_digest:item.input_digest, context_artifact_ids:item.context_artifact_ids}}/></details>
  </form>;
}

export default function Approvals({run, data, busy, act, confirmG1, openAudit, openRuns}) {
  const [command, setCommand] = useState('request');
  const [values, setValues] = useState({target_id:'local-staging', port:8766});
  if (!run) return <section className="panel"><h2>选择一条运行</h2><p className="hint">门禁记录与发布许可均绑定到具体运行。</p><button onClick={openRuns}>查看运行列表</button></section>;
  const [label, ...fields] = OPERATIONS[command];
  const records = {
    request_id:data?.authorization_requests?.map(item => item.authorization_request_id),
    authorization_id:data?.authorizations?.map(item => item.authorization_id),
    deployment_id:data?.deployments?.map(item => item.deployment_id),
  };
  const waitingG1 = run.phase === 'G1' && run.status === 'WAITING_APPROVAL';
  const clarifications = (data?.clarifications || []).filter(item => item.status === 'OPEN');
  return <>
    <section className="panel">
      <h2>待处理事项</h2>
      {waitingG1 && <div className="review-task"><h3>确认 Spec 与架构</h3><p>查看本次方案和门禁依据，确认后启动研发。</p>
        <div className="context-actions"><button disabled={busy} onClick={confirmG1}>确认方案并进入研发</button><button className="secondary" onClick={openAudit}>查看方案与证据</button></div>
      </div>}
      {clarifications.map(item => <Clarification key={item.question_id} item={item} version={run.state_version} busy={busy} submit={body => act('clarify', body)}/>)}
      {!waitingG1 && clarifications.length === 0 && <p className="hint">当前没有待确认的方案或待回答的澄清问题。发布与恢复操作见下方。</p>}
      {data?.approvals?.length > 0 && <details><summary>方案审批记录</summary>
        <div className="approval-records">{data.approvals.map(item => <div key={item.approval_id}><strong>{item.subject_type === 'SPEC' ? '需求规格' : '架构方案'}</strong>
          <StatusPill status={item.revoked ? 'REVOKED' : item.decision || 'PENDING'}/><small>版本 {item.request_version} · 有效期至 {new Date(item.expires_at).toLocaleString('zh-CN')}</small>
          <code>{item.input_digest}</code>{item.decision_reason && <p>{item.decision_reason}</p>}</div>)}</div>
      </details>}
    </section>
    <section className="panel"><h2>质量门禁</h2><GateTrack gates={data?.gates}/>
      {data?.gates?.length > 0 && <details><summary>历史记录与输入摘要</summary><Json value={data.gates}/></details>}
    </section>
    {run.run_type === 'DELIVERY' && <section className="panel"><h2>预发与恢复</h2>
      <p className="hint">登记预发目标 → 申请许可 → 人工批准 → 部署验证。部署前须启动独立 HTTP 代理。</p>
      <form onSubmit={event => {event.preventDefault(); if (!busy) act('release', {command, ...Object.fromEntries(fields.map(key => [key, values[key]]))});}}>
        <div className="form-row">
          <label>选择操作<select value={command} onChange={event => setCommand(event.target.value)}>{Object.entries(OPERATIONS).map(([id, [name]]) => <option key={id} value={id}>{name}</option>)}</select></label>
          {fields.map(key => <label key={key}>{FIELDS[key]}{command === 'rollback' && key === 'authorization_id' ? '（选填）' : ''}<input
            required={!(command === 'rollback' && key === 'authorization_id')} value={values[key] ?? ''}
            type={key === 'port' ? 'number' : 'text'} min={key === 'port' ? 1024 : undefined} max={key === 'port' ? 65535 : undefined}
            list={records[key]?.length ? `release-${key}` : undefined}
            onChange={event => setValues({...values, [key]:event.target.value})}/>
            {records[key]?.length > 0 && <datalist id={`release-${key}`}>{records[key].map(id => <option key={id} value={id}/>)}</datalist>}
          </label>)}
        </div>
        <button disabled={busy}>{label}</button>
      </form>
      <details><summary>授权申请与许可</summary><Json value={{requests:data?.authorization_requests, authorizations:data?.authorizations}}/></details>
      <details><summary>发布与部署结果</summary><Json value={{releases:data?.releases, deployments:data?.deployments}}/></details>
    </section>}
  </>;
}

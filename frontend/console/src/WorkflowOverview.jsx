import React from 'react';

const STEPS = [
  {title: '任务输入', detail: '目标与约束', roles: '用户 / 调度器'},
  {title: '产品设计', detail: '需求、体验、验收', roles: '产品团队'},
  {title: '专家审计', detail: '产品审计与架构', roles: '专家团队', gate: 'G1'},
  {title: '并行研发', detail: '前端 / 后端 / DevOps', roles: '研发团队'},
  {title: '测试与审查', detail: '审查、测试、修复', roles: '研发与安全', gate: 'G2'},
  {title: '授权发布', detail: '人工许可后部署', roles: '发布审批 / 运维'},
  {title: '观察交付', detail: '健康检查与证据', roles: '系统 / 用户', gate: 'G3'},
];

export default function WorkflowOverview({compact = false}) {
  return <section className={`workflow-overview ${compact ? 'workflow-compact' : ''}`} aria-labelledby={compact ? 'run-flow-title' : 'config-flow-title'}>
    <div className="workflow-heading">
      <div>
        <span className="settings-kicker">DELIVERY FLOW</span>
        <h2 id={compact ? 'run-flow-title' : 'config-flow-title'}>一次交付如何流转</h2>
      </div>
      <span className="settings-chip">3 道质量门禁</span>
    </div>
    <ol className="flow-steps">
      {STEPS.map((step, index) => <li key={step.title} className="flow-step">
        <div className="flow-step-top"><span>{String(index + 1).padStart(2, '0')}</span>{step.gate && <b>{step.gate}</b>}</div>
        <strong>{step.title}</strong>
        <p>{step.detail}</p>
        {!compact && <small>{step.roles}</small>}
      </li>)}
    </ol>
    {!compact && <div className="workflow-note">
      <span><b>自动返工</b> 审查或测试失败会回到对应研发角色，而不是跳过检查。</span>
      <span><b>人工把关</b> G1 确认方案，发布必须取得独立许可，G3 验证实际结果。</span>
    </div>}
  </section>;
}

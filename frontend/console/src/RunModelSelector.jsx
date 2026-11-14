import React from 'react';
import RoleAvatar, {ROLE_NAMES} from './RoleAvatar';

export default function RunModelSelector({config, effective = {}, credentials = [], value = {}, onChange, busy}) {
  if (!config) return null;
  const roles = Object.keys(config.roles);
  const credentialMap = Object.fromEntries(credentials.map(item => [item.ref, item]));
  return <div className="run-model-selector">
    <div className="run-model-head">
      <div><strong>选择本次运行的角色模型</strong><p>角色按流程自动参与；这里只选择各角色本次使用的模型，不修改全局默认配置。</p></div>
      <button type="button" className="secondary" disabled={busy || !Object.keys(value).length} onClick={() => onChange({})}>全部使用默认</button>
    </div>
    <div className="run-role-grid">
      {roles.map(role => {
        const current = effective[role];
        if (!current) return null;
        const selected = value[role] || current.primary;
        const profile = config.models[selected];
        const allowed = current.policy.models.filter(id => config.models[id]);
        const credential = credentialMap[profile?.secret_ref];
        return <label className="run-role" key={role}>
          <RoleAvatar role={role} size="small"/>
          <span className="run-role-info"><strong>{ROLE_NAMES[role] || role}</strong><small>{role}</small></span>
          <select aria-label={`选择 ${ROLE_NAMES[role] || role} 的模型`} value={selected} disabled={busy} onChange={event => onChange({...value, [role]: event.target.value})}>
            {allowed.map(id => <option key={id} value={id}>{config.models[id].model} · {id}</option>)}
          </select>
          <span className={`run-key-state ${credential?.configured ? 'ready' : ''}`}>{credential?.configured ? 'Key 已配置' : 'Key 未配置'}</span>
        </label>;
      })}
    </div>
  </div>;
}

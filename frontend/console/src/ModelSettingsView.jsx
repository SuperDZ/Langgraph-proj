import React,{useEffect,useRef,useState} from 'react';
import RoleAvatar,{DEPARTMENT_NAMES,ROLE_NAMES} from './RoleAvatar';

const toUSD = value => (Number(value||0)/1e6).toFixed(2);

function initialForm(config,effective,role){
  const current=effective[role],primary=current.primary;
  return {profile_id:primary,profile:{...config.models[primary],...current.models[primary]},
    fallbacks:[...current.fallbacks],token_budget:current.token_budget,cost_budget:current.cost_budget,
    max_steps:current.max_steps,concurrency:current.concurrency};
}

export default function ModelSettingsView({config,effective={},credentials=[],busy,save,openGlobal}){
  const [role,setRole]=useState(null),[values,setValues]=useState({}),[json,setJson]=useState(null),
    [message,setMessage]=useState(''),[isError,setIsError]=useState(false),[pending,setPending]=useState(false),
    [showAdd,setShowAdd]=useState(false),[newCredential,setNewCredential]=useState({name:'',value:''});
  const working=busy||pending;
  async function perform(action,body){
    setPending(true);setMessage('');setIsError(false);
    try{const result=await save(action,body);
      setMessage(action==='agent-config-save'?'Agent 配置已保存，新运行将采用此配置。':
        action==='config-save'?'高级配置已校验并保存。':
        action==='credential-register'?'新 API Key 已登记并加密保存。':
        action==='credential-remove'?'本机保存值已删除；模型引用保持不变。':'凭据已加密保存，后续模型请求可使用。');
      return result;
    }catch(error){setMessage(error.message);setIsError(true);return null;
    }finally{setPending(false);}
  }
  async function saveCredential(ref,remove=false){
    await perform(remove?'credential-remove':'credential-save',{ref,...(remove?{}:{value:(values[ref]||'').trim()})});
    setValues(current=>({...current,[ref]:''}));
  }
  async function registerCredential(event){
    event.preventDefault();
    const name=newCredential.name.trim().toUpperCase();
    if(!/^[A-Z][A-Z0-9_]{0,80}_API_KEY$/.test(name)){setMessage('凭据名称需为大写字母、数字和下划线，并以 _API_KEY 结尾');setIsError(true);return}
    if(!newCredential.value.trim()){setMessage('请粘贴 API Key');setIsError(true);return}
    const result=await perform('credential-register',{ref:'env:'+name,value:newCredential.value.trim()});
    if(result){setNewCredential({name:'',value:''});setShowAdd(false)}
  }
  if(!config) return <section><p>正在读取模型配置…</p></section>;
  const roles=Object.keys(config.roles),configuredCount=credentials.filter(item=>item.configured).length;
  const credentialModels=Object.fromEntries(credentials.map(item=>[item.ref,Object.entries(config.models)
    .filter(([,profile])=>profile.secret_ref===item.ref).map(([id,profile])=>`${id} · ${profile.model}`)]));
  return <div className="model-settings">
    <section className="settings-intro">
      <div><span className="settings-kicker">MODEL CONTROL</span>
        <h2>为每位 Agent 配置合适的模型</h2>
        <p>点击角色卡片设置模型和参数，或在启动新交付时逐角色选择本次模型。</p></div>
      <div className="settings-intro-actions">
        <span className="settings-count">{roles.length}<small>个专业角色</small></span>
        <button className="secondary" type="button" disabled={working} onClick={openGlobal}>全局模型设置</button>
      </div>
    </section>
    {message&&<div className={isError?'alert':'notice'} role={isError?'alert':'status'}>{message}
      <button type="button" onClick={()=>setMessage('')}>关闭</button></div>}
    <section aria-labelledby="agent-model-title">
      <div className="settings-section-title">
        <div><h2 id="agent-model-title">Agent 模型配置</h2><p>模型参数与角色预算集中在同一张配置表单中。</p></div>
        <span className="settings-chip">仅影响新运行</span>
      </div>
      {Object.entries(DEPARTMENT_NAMES).map(([department,name])=>{
        const group=roles.filter(item=>config.roles[item].department===department);
        return group.length?<div className="agent-group" key={department}>
          <h3>{name}<small>{group.length} AGENTS</small></h3>
          <div className="agent-cards">
            {group.map(item=>{
              const current=effective[item],profile=current?.models?.[current.primary]||{},override=config.roles[item].agent?.primary;
              return <button key={item} className="agent-card" onClick={()=>setRole(item)} aria-label={`配置 ${ROLE_NAMES[item]||item} 的模型`} disabled={!current||working}>
                <div className="agent-card-top"><RoleAvatar role={item} size="small"/><span className="agent-edit">配置 ↗</span></div>
                <strong>{ROLE_NAMES[item]||item}</strong><code>{item}</code>
                <div className="agent-model-name">{profile.model||'等待配置'}</div>
                <div className="agent-card-bottom"><span>{override?'角色覆盖':'继承默认'}</span>
                  <span>{profile.thinking==='enabled'?'深度思考':'标准生成'}</span></div>
              </button>;
            })}
          </div>
        </div>:null;
      })}
    </section>
    <section id="model-credentials" tabIndex="-1" aria-labelledby="credentials-title">
      <div className="settings-section-title">
        <div><h2 id="credentials-title">模型 API Key 管理</h2>
          <p>每个模型可使用不同 Key；Key 不回显，也不会进入配置 JSON 或审计记录。</p></div>
        <span className="settings-chip">{configuredCount} / {credentials.length} 已配置</span>
      </div>
      {credentials.map(item=><div className="credential-row" key={item.ref}>
        <div className="credential-name">
          <strong>{item.ref.replace('env:','')}</strong><code>{item.ref}</code>
          <span className={`key-state ${item.configured?'ready':''}`}>{item.configured?'● 已配置':'○ 未配置'} · {item.source==='local_encrypted'?'服务端加密保存':item.source==='environment'?'服务启动环境变量':'等待填写'}</span>
          {credentialModels[item.ref]?.length>0&&<small>用于：{credentialModels[item.ref].join('、')}</small>}
        </div>
        <div className="credential-input">
          <label>新 API Key<input type="password" autoComplete="new-password" spellCheck="false" value={values[item.ref]||''}
            onChange={event=>setValues({...values,[item.ref]:event.target.value})}
            placeholder={item.configured?'输入新 Key 以替换，留空保持原值':'粘贴 API Key'} disabled={working||!item.persist_supported}/></label>
          <div className="credential-actions">
            <button type="button" disabled={working||!item.persist_supported||!(values[item.ref]||'').trim()} onClick={()=>saveCredential(item.ref)}>{item.configured?'更新 Key':'加密保存'}</button>
            {item.configured&&<button type="button" className="secondary" disabled={working||!item.persist_supported}
              onClick={()=>{if(window.confirm(`删除本机保存的 ${item.ref}？模型配置中的引用会保留。`))saveCredential(item.ref,true)}}>删除本机保存值</button>}
          </div>
        </div>
      </div>)}
      {showAdd?<form className="credential-add" onSubmit={registerCredential}>
        <h3>新增 API Key</h3>
        <div className="credential-input">
          <label>凭据名称<input required value={newCredential.name} spellCheck="false" disabled={working}
            onChange={event=>setNewCredential({...newCredential,name:event.target.value.toUpperCase()})} placeholder="例如 DEEPSEEK_BACKUP_API_KEY"/></label>
          <label>API Key<input required type="password" autoComplete="new-password" spellCheck="false" value={newCredential.value}
            onChange={event=>setNewCredential({...newCredential,value:event.target.value})} placeholder="粘贴 API Key" disabled={working||credentials[0]?.persist_supported===false}/></label>
        </div>
        <div className="credential-actions"><button type="submit" disabled={working||credentials[0]?.persist_supported===false}>登记并加密保存</button>
          <button type="button" className="secondary" disabled={working} onClick={()=>setShowAdd(false)}>取消</button></div>
        <p className="hint">新增的 Key 会登记到平台凭据白名单，随后可在全局设置中为任意模型引用。</p>
      </form>:
        <button type="button" className="add-model" disabled={working||credentials[0]?.persist_supported===false} onClick={()=>setShowAdd(true)}>+ 新增 API Key</button>}
      <p className="hint">{credentials[0]?.persist_supported===false?'当前服务未启用加密保存，请通过服务环境变量配置 API Key。':'API Key 由服务端加密保存，服务重启后自动加载。'}“已配置”表示已保存或由环境提供，尚未验证提供方鉴权。</p>
    </section>
    <section className="advanced-settings">
      <details><summary>高级配置 · JSON 与权限策略</summary>
        <p className="hint">需要调整模型目录、网络白名单或四级权限策略时使用。常规模型参数请直接点击 Agent 卡片。</p>
        <label>配置 JSON<textarea className="editor" value={json??JSON.stringify(config,null,2)} onChange={event=>setJson(event.target.value)}/></label>
        <button type="button" disabled={working} onClick={async()=>{
          try{const result=await perform('config-save',{config:JSON.parse(json??JSON.stringify(config))});if(result)setJson(null)}
          catch{setMessage('JSON 格式不正确，请检查后再保存。');setIsError(true)}}}>校验并保存高级配置</button>
      </details>
    </section>
    {role&&<AgentDialog key={role} role={role} config={config} effective={effective} credentials={credentials}
      serverError={isError&&role?message:''} busy={working} onClose={()=>setRole(null)}
      onSave={async form=>{const result=await perform('agent-config-save',{role,...form});if(result)setRole(null)}}/>}
  </div>;
}

function AgentDialog({role,config,effective,credentials,serverError,busy,onClose,onSave}){
  const dialog=useRef(null),[form,setForm]=useState(()=>initialForm(config,effective,role)),[error,setError]=useState('');
  useEffect(()=>{const node=dialog.current;node.showModal();return()=>{if(node.open)node.close()}},[]);
  const update=(field,value)=>setForm(current=>({...current,[field]:value}));
  const profile=form.profile,thinking=profile.thinking==='enabled'||['low','high','max'].includes(profile.reasoning_effort);
  const setProfile=(field,value)=>setForm(current=>({...current,profile:{...current.profile,[field]:value}}));
  const current=effective[role];
  const templates=Object.keys(config.models).filter(id=>(current.policy.models.includes(id)&&(!id.startsWith('agent-')||id===form.profile_id)));
  const credentialMap=Object.fromEntries(credentials.map(item=>[item.ref,item]));
  function selectTemplate(id){setForm(current=>({...current,profile_id:id,profile:{...config.models[id]}}))}
  return <dialog className="agent-dialog" ref={dialog} aria-labelledby="agent-dialog-title"
    onCancel={event=>{busy?event.preventDefault():onClose()}}
    onClick={event=>{if(event.target===event.currentTarget&&!busy)onClose()}}>
    <form onSubmit={event=>{
      event.preventDefault();setError('');
      if(!profile.model.trim()){setError('请填写模型名称');return}
      onSave(form)}}>
      <div className="agent-dialog-head">
        <div className="agent-dialog-title">
          <RoleAvatar role={role} size="small"/>
          <div><span className="settings-kicker">AGENT CONFIGURATION</span>
            <h2 id="agent-dialog-title">{ROLE_NAMES[role]||role}<code>{role}</code></h2>
            <p>独立保存此角色的模型参数，不会改动其他 Agent。</p></div>
        </div>
        <button type="button" className="dialog-close secondary" aria-label="关闭 Agent 配置" disabled={busy} onClick={onClose}>✕</button>
      </div>
      <div className="agent-dialog-body">
        <fieldset disabled={busy}>
          <h3><span>01</span> 模型与调用</h3>
          <div className="settings-form-grid">
            <label>参数模板<select value={form.profile_id} onChange={event=>selectTemplate(event.target.value)}>
              {templates.map(id=><option key={id} value={id}>{id} · {config.models[id].model}</option>)}</select></label>
            <label>模型名称<input required value={profile.model} onChange={event=>setProfile('model',event.target.value)} placeholder="填写提供方支持的模型 ID"/></label>
            <label>服务提供方<input readOnly value={profile.provider||'deepseek'}/></label>
            <label>API Key 引用<select value={profile.secret_ref} onChange={event=>setProfile('secret_ref',event.target.value)}>
              {credentials.map(item=><option key={item.ref} value={item.ref}>{item.ref.replace('env:','')} · {item.configured?'已配置':'未配置'}</option>)}
            </select><small>{credentialMap[profile.secret_ref]?.configured?'当前 Key 已配置':'当前 Key 未配置'}</small></label>
            <label className="span-two">API 地址<input type="url" required value={profile.endpoint} onChange={event=>setProfile('endpoint',event.target.value)}/><small>HTTPS 地址须在平台网络白名单内。</small></label>
          </div>
          <h3><span>02</span> 生成参数</h3>
          <div className="settings-form-grid">
            <label>最大输出 Token<input type="number" min="1" max="32768" required value={profile.max_output_tokens} onChange={event=>setProfile('max_output_tokens',Number(event.target.value))}/></label>
            <label>Temperature<input type="number" min="0" max="2" step="0.05" disabled={thinking} value={thinking?'':(profile.temperature??0)} onChange={event=>setProfile('temperature',Number(event.target.value))}/></label>
            <label>深度思考<select value={profile.thinking} onChange={event=>{
              const enabled=event.target.value==='enabled';
              setForm(current=>({...current,profile:{...current.profile,thinking:event.target.value,temperature:enabled?null:0,reasoning_effort:enabled?'low':'none'}}))}}>
              <option value="disabled">关闭</option><option value="enabled">开启</option></select></label>
            <label>推理强度<select value={profile.reasoning_effort??'none'} onChange={event=>{
              const enabled=event.target.value!=='none';
              setForm(current=>({...current,profile:{...current.profile,reasoning_effort:event.target.value,thinking:enabled?'enabled':'disabled',temperature:enabled?null:0}}))}}>
              <option value="none">不指定</option><option value="low">Low</option><option value="high">High</option><option value="max">Max</option></select></label>
            <label>请求超时（秒）<input type="number" min="1" max="300" required value={profile.timeout_seconds} onChange={event=>setProfile('timeout_seconds',Number(event.target.value))}/></label>
            <label>故障重试次数<input type="number" min="0" max="5" required value={profile.retries} onChange={event=>setProfile('retries',Number(event.target.value))}/></label>
          </div>
          <h3><span>03</span> 角色预算与后备模型</h3>
          <div className="settings-form-grid">
            <label>角色 Token 预算<input type="number" min="1" required value={form.token_budget} onChange={event=>update('token_budget',Number(event.target.value))}/></label>
            <label>角色费用预算（USD）<input type="number" min="0.000001" step="0.000001" required value={toUSD(form.cost_budget)} onChange={event=>update('cost_budget',Math.round(Number(event.target.value)*1e6))}/></label>
            <label>最大执行步数<input type="number" min="1" max="500" required value={form.max_steps} onChange={event=>update('max_steps',Number(event.target.value))}/></label>
            <label>并发上限<input type="number" min="1" max="32" required value={form.concurrency} onChange={event=>update('concurrency',Number(event.target.value))}/></label>
          </div>
          <p className="hint">预算、步数和并发仍受上级策略限制。当前有效预算：{current.token_budget.toLocaleString()} Token / ${toUSD(current.cost_budget)}。</p>
          <div className="fallbacks"><span>后备模型<small>按勾选顺序尝试</small></span>
            {templates.filter(id=>id!==form.profile_id&&id!=='agent-'+role).map(id=>
              <label key={id}><input type="checkbox" checked={form.fallbacks.includes(id)}
                onChange={event=>update('fallbacks',event.target.checked?[...form.fallbacks,id]:form.fallbacks.filter(name=>name!==id))}/>
                {id} · {config.models[id].model}</label>)}</div>
          {(error||serverError)&&<p className="settings-error" role="alert">{error||serverError}</p>}
          <p className="hint">表单仅更新配置；保存不会调用在线模型、消耗 Token 或改写正在运行的配置快照。</p>
        </fieldset>
      </div>
      <div className="agent-dialog-footer">
        <button type="button" className="secondary" disabled={busy} onClick={()=>onSave({inherit:true})}>恢复继承默认</button>
        <div><button type="button" className="secondary" disabled={busy} onClick={onClose}>取消</button>
          <button type="submit" disabled={busy}>{busy?'保存中…':'保存 Agent 配置'}</button></div>
      </div>
    </form>
  </dialog>;
}

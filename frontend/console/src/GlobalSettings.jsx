import React,{useEffect,useRef,useState} from 'react';
import Icon from './Icon';

const toUSD = value => (Number(value||0)/1e6).toFixed(2);
const newProfile = () => ({provider:'deepseek',model:'',secret_ref:'env:DEEPSEEK_API_KEY',endpoint:'https://api.deepseek.com',
  temperature:0,max_output_tokens:2048,timeout_seconds:60,retries:2,thinking:'disabled',reasoning_effort:'none',
  structured_output:true,tool_calling:false,residency:'configured-provider',audit:true,input_rate:1,output_rate:2});

/*
 * 全局模型设置：选项卡式结构（参考 Vercel / Linear 的设置面板）。
 * 「概览与预算」放平台级参数，「可用模型」放模型目录与新增/编辑流程。
 */
export default function GlobalSettings({config,credentials=[],busy,save,onClose}) {
  const dialog=useRef(null),[error,setError]=useState(''),[editing,setEditing]=useState(null),[tab,setTab]=useState('overview');
  const [global,setGlobal]=useState(()=>({
    primary:config?.platform?.primary||'primary',token_budget:config?.platform?.token_budget||500000,
    cost_budget:config?.platform?.cost_budget||1000000,max_steps:config?.platform?.max_steps||60,
    concurrency:config?.platform?.concurrency||1,run_token_budget:config?.run_token_budget||1000000,
    run_cost_budget:config?.run_cost_budget||2000000}));
  useEffect(()=>{const node=dialog.current;node.showModal();return()=>{if(node.open)node.close()}},[]);
  if(!config) return null;
  const models=Object.entries(config.models).filter(([id])=>!id.startsWith('agent-'));
  const credentialMap=Object.fromEntries(credentials.map(item=>[item.ref,item]));
  const canSaveKey=credentials[0]?.persist_supported===true;
  async function perform(action,body){setError('');try{await save(action,body);return true}catch(err){setError(err.message);return false}}
  async function saveGlobal(event){event.preventDefault();await perform('global-config-save',{...global,run_id:'console-config'})}
  async function saveModel(event){
    event.preventDefault();const id=editing.profile_id.trim();
    if(!/^[a-z][a-z0-9-]{0,40}$/.test(id)||id.startsWith('agent-')){setError('模型标识需为 1–41 位小写字母、数字或连字符，且不能以 agent- 开头');return}
    if(!editing.profile.model.trim()){setError('请填写模型名称');return}
    const api_key=canSaveKey?(editing.api_key||'').trim():'';
    const done=await perform('model-profile-save',{profile_id:id,profile:editing.profile,is_new:editing.is_new,api_key:api_key||undefined});
    if(done)setEditing(null);
  }
  async function removeModel(id){
    if(!window.confirm(`删除模型 ${id}？仅未被引用的全局模型可以删除。`))return;
    await perform('model-profile-delete',{profile_id:id});
  }
  function setProfile(field,value){setEditing(current=>({...current,profile:{...current.profile,[field]:value}}))}
  const thinking=editing?.profile.thinking==='enabled'||['low','high','max'].includes(editing?.profile.reasoning_effort);

  return <dialog className="global-dialog" ref={dialog} aria-labelledby="global-settings-title"
    onCancel={event=>{busy?event.preventDefault():onClose()}}
    onClick={event=>{if(event.target===event.currentTarget&&!busy)onClose()}}>
    {!editing?<form onSubmit={saveGlobal}>
      <div className="agent-dialog-head">
        <div><span className="settings-kicker">GLOBAL MODEL SETTINGS</span>
          <h2 id="global-settings-title">全局模型设置</h2>
          <p>配置默认可用模型和全局预算；角色级覆盖仍在“角色与模型”中设置。</p></div>
        <button type="button" className="dialog-close secondary" aria-label="关闭全局设置" disabled={busy} onClick={onClose}>✕</button>
      </div>
      <div className="dialog-tabs" role="tablist" aria-label="全局设置分类">
        <button type="button" role="tab" aria-selected={tab==='overview'} className={tab==='overview'?'active':''}
          onClick={()=>setTab('overview')}><Icon name="sliders" size={13}/>概览与预算</button>
        <button type="button" role="tab" aria-selected={tab==='models'} className={tab==='models'?'active':''}
          onClick={()=>setTab('models')}><Icon name="cpu" size={13}/>可用模型<i>{models.length}</i></button>
      </div>
      <div className="agent-dialog-body">
        <fieldset disabled={busy}>
          {tab==='overview'?<>
            <h3><span>01</span> 默认模型与预算</h3>
            <div className="settings-form-grid">
              <label>默认模型<select value={global.primary} onChange={e=>setGlobal({...global,primary:e.target.value})}>
                {models.map(([id,profile])=><option key={id} value={id}>{profile.model} · {id}</option>)}</select></label>
              <label>并发上限<input type="number" min="1" max="32" required value={global.concurrency} onChange={e=>setGlobal({...global,concurrency:Number(e.target.value)})}/></label>
              <label>平台 Token 预算<input type="number" min="1" required value={global.token_budget} onChange={e=>setGlobal({...global,token_budget:Number(e.target.value)})}/></label>
              <label>平台费用预算（USD）<input type="number" min="0.000001" step="0.000001" required value={toUSD(global.cost_budget)} onChange={e=>setGlobal({...global,cost_budget:Math.round(Number(e.target.value)*1e6)})}/></label>
              <label>最大执行步数<input type="number" min="1" max="500" required value={global.max_steps} onChange={e=>setGlobal({...global,max_steps:Number(e.target.value)})}/></label>
              <label>单次运行 Token 上限<input type="number" min="1" required value={global.run_token_budget} onChange={e=>setGlobal({...global,run_token_budget:Number(e.target.value)})}/></label>
              <label>单次运行费用上限（USD）<input type="number" min="0.000001" step="0.000001" required value={toUSD(global.run_cost_budget)} onChange={e=>setGlobal({...global,run_cost_budget:Math.round(Number(e.target.value)*1e6)})}/></label>
            </div>
            <p className="hint">全局设置只影响新运行；已创建运行的配置快照保持不变。</p>
          </>:<>
            <h3><span>02</span> 可用模型目录</h3>
            <div className="global-model-list">
              {models.map(([id,profile])=>{const credential=credentialMap[profile.secret_ref];
                return <div className="global-model-card" key={id}>
                  <div><strong>{profile.model}</strong><code>{id} · {profile.provider}</code><small>{profile.endpoint}</small></div>
                  <span className={`key-state ${credential?.configured?'ready':''}`}>{credential?.configured?'Key 已配置':'Key 未配置'}</span>
                  <div><button type="button" disabled={busy} onClick={()=>setEditing({profile_id:id,is_new:false,profile:{...profile},api_key:''})}>
                    <Icon name="pencil" size={13}/>编辑</button>
                    <button type="button" className="secondary" disabled={busy} onClick={()=>removeModel(id)}>
                    <Icon name="trash" size={13}/>删除</button></div>
                </div>})}
            </div>
            <button type="button" className="add-model" disabled={busy} onClick={()=>setEditing({profile_id:'',is_new:true,profile:newProfile(),api_key:''})}>
              <Icon name="plus" size={13}/>新增模型</button>
            <p className="hint">被角色引用的模型无法删除；删除只影响新运行的可用模型目录。</p>
          </>}
          {error&&<p className="settings-error" role="alert">{error}</p>}
        </fieldset>
      </div>
      <div className="agent-dialog-footer">
        <button type="button" className="secondary" disabled={busy} onClick={onClose}>关闭</button>
        {tab==='overview'&&<button type="submit" disabled={busy}>{busy?'保存中…':'保存全局设置'}</button>}
      </div>
    </form>:
    <form onSubmit={saveModel}>
      <div className="agent-dialog-head">
        <div><span className="settings-kicker">MODEL PROFILE</span>
          <h2>{editing.is_new?'新增模型':'编辑模型'}</h2>
          <p>新增的模型会加入平台可用模型目录，并自动登记端点与 API Key 引用。</p></div>
        <button type="button" className="dialog-close secondary" aria-label="返回模型列表" disabled={busy} onClick={()=>setEditing(null)}>✕</button>
      </div>
      <div className="agent-dialog-body">
        <fieldset disabled={busy}>
          <h3><span>01</span> 模型标识与调用</h3>
          <div className="settings-form-grid">
            <label>模型标识<input required={editing.is_new} readOnly={!editing.is_new} value={editing.profile_id} onChange={e=>setEditing({...editing,profile_id:e.target.value})} placeholder="例如 secondary"/></label>
            <label>模型名称<input required value={editing.profile.model} onChange={e=>setProfile('model',e.target.value)} placeholder="填写提供方支持的模型 ID"/></label>
            <label>服务提供方<input readOnly value={editing.profile.provider||'deepseek'}/></label>
            <label>API Key 引用<input required list="credential-refs" value={editing.profile.secret_ref} onChange={e=>setProfile('secret_ref',e.target.value.trim())} placeholder="env:DEEPSEEK_API_KEY"/></label>
            <label className="span-two">API 地址<input type="url" required value={editing.profile.endpoint} onChange={e=>setProfile('endpoint',e.target.value)} placeholder="https://api.deepseek.com"/></label>
            <datalist id="credential-refs">{credentials.map(item=><option key={item.ref} value={item.ref}>{item.configured?'已配置':'未配置'}</option>)}</datalist>
          </div>
          <h3><span>02</span> 生成参数</h3>
          <div className="settings-form-grid">
            <label>最大输出 Token<input type="number" min="1" max="32768" required value={editing.profile.max_output_tokens} onChange={e=>setProfile('max_output_tokens',Number(e.target.value))}/></label>
            <label>Temperature<input type="number" min="0" max="2" step="0.05" disabled={thinking} value={thinking?'':(editing.profile.temperature??0)} onChange={e=>setProfile('temperature',Number(e.target.value))}/></label>
            <label>深度思考<select value={editing.profile.thinking} onChange={e=>{const on=e.target.value==='enabled';
              setEditing(current=>({...current,profile:{...current.profile,thinking:e.target.value,temperature:on?null:0,reasoning_effort:on?'low':'none'}}))}}>
              <option value="disabled">关闭</option><option value="enabled">开启</option></select></label>
            <label>推理强度<select value={editing.profile.reasoning_effort??'none'} onChange={e=>{const on=e.target.value!=='none';
              setEditing(current=>({...current,profile:{...current.profile,reasoning_effort:e.target.value,thinking:on?'enabled':'disabled',temperature:on?null:0}}))}}>
              <option value="none">不指定</option><option value="low">Low</option><option value="high">High</option><option value="max">Max</option></select></label>
            <label>请求超时（秒）<input type="number" min="1" max="300" required value={editing.profile.timeout_seconds} onChange={e=>setProfile('timeout_seconds',Number(e.target.value))}/></label>
            <label>故障重试次数<input type="number" min="0" max="5" required value={editing.profile.retries} onChange={e=>setProfile('retries',Number(e.target.value))}/></label>
          </div>
          <h3><span>03</span> API Key（可选）</h3>
          <div className="settings-form-grid">
            <label className="span-two">API Key<input type="password" autoComplete="new-password" spellCheck="false" value={editing.api_key} onChange={e=>setEditing({...editing,api_key:e.target.value})} disabled={!canSaveKey} placeholder={!canSaveKey?'请在服务环境变量中配置 API Key':credentialMap[editing.profile.secret_ref]?.configured?'输入新 Key 以替换，留空保持原值':'粘贴 API Key，稍后保存也可'}/></label>
          </div>
          <details className="model-rate-details"><summary>计费速率（micro-USD / Token）</summary>
            <div className="settings-form-grid">
              <label>输入速率<input type="number" min="0" value={editing.profile.input_rate??1} onChange={e=>setProfile('input_rate',Number(e.target.value))}/></label>
              <label>输出速率<input type="number" min="0" value={editing.profile.output_rate??2} onChange={e=>setProfile('output_rate',Number(e.target.value))}/></label>
            </div>
          </details>
          {error&&<p className="settings-error" role="alert">{error}</p>}
        </fieldset>
      </div>
      <div className="agent-dialog-footer">
        <button type="button" className="secondary" disabled={busy} onClick={()=>setEditing(null)}>返回列表</button>
        <button type="submit" disabled={busy}>{busy?'保存中…':editing.is_new?'新增模型':'保存模型'}</button>
      </div>
    </form>}
  </dialog>;
}

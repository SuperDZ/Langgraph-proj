import React,{useMemo,useRef,useState} from 'react';
import Icon from './Icon';

/*
 * Skills 与 MCP —— 对标 Docker Hub / GitHub Marketplace / MCP Registry 的扩展治理表达：
 *   导入是带上限与校验的向导，目录是可检索可复制的清单，授权始终是显式人工动作。
 * 导入只做隔离存档，绝不执行包内脚本；批准与绑定各自留审计。
 */

const MAX_SKILL_BYTES = 600000;

const SKILL_STATUS_TEXT = {
  QUARANTINED:'已隔离',
  APPROVED:'已批准',
  DISABLED:'已停用',
  UNINSTALLED:'已卸载',
};

const MCP_STATUS_TEXT = {
  QUARANTINED:'已隔离',
  APPROVED:'已批准',
  DISABLED:'已停用',
  UNINSTALLED:'已卸载',
};

const RISK_TEXT = {
  CONTAINS_SCRIPTS_NEVER_EXECUTED:'包含脚本（永不执行）',
  LICENSE_UNDECLARED:'未声明许可证',
  POSSIBLE_PROMPT_INJECTION:'疑似提示注入',
};

const ROLES = ['frontend','backend','devops','qa','architecture','product','data','security','dev','qa-lead'];

function statusTone(status){
  if (status==='APPROVED') return 'tone-ok';
  if (status==='QUARANTINED') return 'tone-warn';
  return 'tone-bad';
}

function formatBytes(bytes){
  if (!bytes) return '0 B';
  if (bytes<1024) return bytes+' B';
  if (bytes<1024*1024) return (bytes/1024).toFixed(1)+' KB';
  return (bytes/1024/1024).toFixed(2)+' MB';
}

function formatMicroUsd(micro){
  const value=Number(micro)||0;
  if (value===0) return '$0';
  const usd=value/1000000;
  if (usd>=100) return '$'+usd.toFixed(0);
  if (usd>=1) return '$'+usd.toFixed(2);
  return '$'+usd.toFixed(4);
}

function HashChip({value,label,onCopy}){
  if(!value) return null;
  return <span className="hash-chip">
    <code>{value.length>18?value.slice(0,18)+'…':value}</code>
    <button type="button" className="icon-button visible" title={label||'复制哈希'} onClick={()=>onCopy&&onCopy(value,label)}>
      <Icon name="copy" size={12}/>
    </button>
  </span>;
}

function Dropzone({file,onFile,error}){
  const inputRef=useRef(null);
  const[over,setOver]=useState(false);
  const ratio=file?Math.min(1,file.size/MAX_SKILL_BYTES):0;
  const tone=ratio>=1?'bad':ratio>=0.8?'warn':'ok';
  const handle=(list)=>{
    const picked=list&&list[0];
    if(picked) onFile(picked);
  };
  return <div className="dropzone-wrap">
    <div
      className={'dropzone'+(over?' over':'')+(file?' filled':'')}
      onDragOver={e=>{e.preventDefault();setOver(true)}}
      onDragLeave={()=>setOver(false)}
      onDrop={e=>{e.preventDefault();setOver(false);handle(e.dataTransfer.files)}}
      onClick={()=>inputRef.current&&inputRef.current.click()}
      role="button" tabIndex={0}
      onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inputRef.current&&inputRef.current.click()}}}
    >
      <input ref={inputRef} type="file" accept=".zip" className="sr-only"
        onChange={e=>{handle(e.target.files);e.target.value=''}}/>
      <span className="dropzone-icon"><Icon name={file?'check-circle':'folder'} size={20}/></span>
      {file? <>
        <strong className="dropzone-name">{file.name}</strong>
        <span className="dropzone-size">{formatBytes(file.size)} · 上限 {formatBytes(MAX_SKILL_BYTES)}</span>
        <div className="usage-bar dropzone-meter"><i className={'tone-'+tone} style={{width:(ratio*100).toFixed(1)+'%'}}/></div>
      </> : <>
        <strong>拖入 Skill ZIP 包，或点击选择</strong>
        <span className="dropzone-hint">最大 600 KB · 仅做隔离存档，不执行任何脚本</span>
      </>}
    </div>
    {error&&<p className="field-error"><Icon name="alert-triangle" size={12}/>{error}</p>}
  </div>;
}

export default function SkillsMcp({run,busy,act,skills=[],mcp=[],policy,effective,onCopy}){
  const[file,setFile]=useState(null);
  const[fileError,setFileError]=useState('');
  const[mode,setMode]=useState('form');
  const[serverId,setServerId]=useState('local-tools');
  const[url,setUrl]=useState('http://127.0.0.1:8767/mcp');
  const[timeout,setTimeoutValue]=useState('20');
  const[toolsText,setToolsText]=useState('{}');
  const[rawText,setRawText]=useState('{"server_id":"local-tools","transport":"http","url":"http://127.0.0.1:8767/mcp","tools":{}}');
  const[registerError,setRegisterError]=useState('');
  const[role,setRole]=useState('backend');

  const toolsState=useMemo(()=>{
    try{
      const parsed=JSON.parse(toolsText||'{}');
      if(typeof parsed!=='object'||Array.isArray(parsed)||parsed===null) return {error:'工具策略必须是一个对象'};
      return {error:''};
    }catch(e){return {error:e.message};}
  },[toolsText]);

  const rawState=useMemo(()=>{
    if(mode!=='raw') return {error:''};
    try{
      const parsed=JSON.parse(rawText||'{}');
      if(typeof parsed!=='object'||Array.isArray(parsed)||parsed===null) return {error:'配置必须是 JSON 对象'};
      if(parsed.transport&&parsed.transport!=='http') return {error:'本控制台只接受 HTTP 传输；stdio 由受信主机 CLI 登记'};
      if(!parsed.server_id) return {error:'缺少 server_id'};
      return {error:''};
    }catch(e){return {error:'JSON 解析失败：'+e.message};}
  },[rawText,mode]);

  const buildConfig=()=>{
    if(mode==='raw') return JSON.parse(rawText);
    return {
      server_id:serverId.trim(),
      transport:'http',
      url:url.trim(),
      timeout:Number(timeout)||20,
      tools:JSON.parse(toolsText||'{}'),
    };
  };

  const pickFile=(picked)=>{
    setFileError('');
    if(!picked) return;
    if(picked.size>MAX_SKILL_BYTES){
      setFileError(`包体积 ${formatBytes(picked.size)} 超过 ${formatBytes(MAX_SKILL_BYTES)} 上限`);
      setFile(null);
      return;
    }
    if(!/\.zip$/i.test(picked.name)){
      setFileError('只接受 .zip 格式的 Skill 包');
      setFile(null);
      return;
    }
    setFile(picked);
  };

  const importSkill=async()=>{
    if(!file) return;
    try{
      const bytes=new Uint8Array(await file.arrayBuffer());
      let binary='';
      for(const byte of bytes) binary+=String.fromCharCode(byte);
      await act('skill-import',{content:btoa(binary)});
      setFile(null);
    }catch(e){setFileError(e.message||'导入失败');}
  };

  const registerMcp=async()=>{
    setRegisterError('');
    try{
      await act('mcp-register',{config:buildConfig()});
    }catch(e){setRegisterError(e.message||'登记失败');}
  };

  const quarantined=skills.filter(s=>s.status==='QUARANTINED').length;
  const pendingMcp=mcp.filter(m=>m.status==='QUARANTINED').length;

  return <>
    <section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="plug" size={16}/><h2>隔离导入 Skill / MCP</h2></div>
        <span className="settings-chip">SANDBOXED · NO EXECUTION</span>
      </div>
      <div className="import-grid">
        <div className="import-col">
          <div className="import-col-head">
            <span className="import-step">01</span>
            <div><strong>导入 Skill 包</strong><small>ZIP 归档，仅做隔离存档</small></div>
          </div>
          <Dropzone file={file} onFile={pickFile} error={fileError}/>
          {!run&&<p className="field-hint"><Icon name="lock" size={11}/>导入必须绑定一个具体运行</p>}
          <button type="button" className="primary-action import-submit" disabled={!file||!run||busy} onClick={importSkill}>
            <Icon name="upload" size={14}/>导入并隔离
          </button>
        </div>
        <div className="import-col">
          <div className="import-col-head">
            <span className="import-step">02</span>
            <div><strong>登记 MCP 服务</strong><small>仅 HTTP 传输，本机隔离</small></div>
            <div className="import-mode">
              <button type="button" className={mode==='form'?'active':''} onClick={()=>setMode('form')}>表单</button>
              <button type="button" className={mode==='raw'?'active':''} onClick={()=>setMode('raw')}>原始 JSON</button>
            </div>
          </div>
          {mode==='form'? <div className="mcp-form">
            <label className="field">
              <span className="field-label">Server ID</span>
              <span className="field-control"><Icon name="terminal" size={14}/><input value={serverId} onChange={e=>setServerId(e.target.value)} placeholder="local-tools"/></span>
            </label>
            <label className="field">
              <span className="field-label">服务地址</span>
              <span className="field-control"><Icon name="link" size={14}/><input value={url} onChange={e=>setUrl(e.target.value)} placeholder="http://127.0.0.1:8767/mcp"/></span>
            </label>
            <label className="field">
              <span className="field-label">超时（秒，1–120）</span>
              <span className="field-control"><Icon name="clock" size={14}/><input type="number" value={timeout} min="1" max="120" onChange={e=>setTimeoutValue(e.target.value)}/></span>
            </label>
            <label className="field full">
              <span className="field-label">工具能力策略</span>
              <span className={'field-control textarea'+(toolsState.error?' invalid':'')}>
                <textarea rows="4" value={toolsText} onChange={e=>setToolsText(e.target.value)} spellCheck="false"/>
                {toolsState.error&&<span className="field-error"><Icon name="alert-triangle" size={11}/>{toolsState.error}</span>}
              </span>
            </label>
          </div> : <div className="mcp-form">
            <label className="field full">
              <span className="field-label">ServerConfig JSON</span>
              <span className={'field-control textarea'+(rawState.error?' invalid':'')}>
                <textarea rows="9" value={rawText} onChange={e=>setRawText(e.target.value)} spellCheck="false"/>
                {rawState.error&&<span className="field-error"><Icon name="alert-triangle" size={11}/>{rawState.error}</span>}
              </span>
            </label>
          </div>}
          {registerError&&<p className="field-error"><Icon name="alert-triangle" size={12}/>{registerError}</p>}
          <button type="button" className="primary-action import-submit" disabled={!run||busy||!!toolsState.error||!!rawState.error} onClick={registerMcp}>
            <Icon name="plug" size={14}/>登记隔离版本
          </button>
        </div>
      </div>
      <p className="hint">受信主机使用 Phase 2 CLI 导入包与注册 MCP，页面不接收任意文件系统路径或可执行命令。登记不会启动服务，也不会授予角色工具权限。</p>
    </section>

    <section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="archive" size={16}/><h2>已隔离导入的 Skills</h2></div>
        <span className="settings-chip">{quarantined} QUARANTINED / {skills.length} TOTAL</span>
      </div>
      {skills.length? <div className="catalog-grid">
        {skills.map(s=>(
          <article key={s.hash} className="catalog-card">
            <div className="catalog-head">
              <span className="catalog-icon"><Icon name="folder" size={15}/></span>
              <strong>{s.name}</strong>
              <span className={'status-pill '+statusTone(s.status)}><i className="status-dot"/>{SKILL_STATUS_TEXT[s.status]||s.status}</span>
            </div>
            <p className="catalog-desc">{s.description||'未提供描述'}</p>
            <div className="catalog-hash"><span className="field-label">内容哈希</span><HashChip value={s.hash} label="复制 Skill 哈希" onCopy={onCopy}/></div>
            <div className="risk-list">
              <span className="field-label">已识别风险</span>
              {(s.risks&&s.risks.length? s.risks:[]).map(r=><span key={r} className="risk-chip"><Icon name="alert-triangle" size={10}/>{RISK_TEXT[r]||r}</span>)}
              {!(s.risks&&s.risks.length)&&<span className="risk-chip clean"><Icon name="check" size={10}/>无已识别项</span>}
            </div>
            {!!(s.dependencies&&s.dependencies.length)&&<div className="catalog-deps">
              <span className="field-label">依赖</span>
              {s.dependencies.map(d=><code key={d}>{d.slice(0,16)}</code>)}
            </div>}
            <div className="catalog-foot">
              <label className="role-select">
                <span className="field-label">绑定角色</span>
                <select value={role} onChange={e=>setRole(e.target.value)}>
                  {ROLES.map(r=><option key={r} value={r}>{r}</option>)}
                </select>
              </label>
              <button type="button" className="primary-action" disabled={!run||busy||s.status==='DISABLED'}
                onClick={()=>act('skill-approve',{hash:s.hash,role,risks:s.risks||[]})}>
                <Icon name="shield-check" size={14}/>确认全部风险并绑定
              </button>
            </div>
          </article>
        ))}
      </div> : <p className="empty">暂无已导入的 Skill。导入后需明确确认全部风险才能绑定角色。</p>}
    </section>

    <section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="link" size={16}/><h2>MCP 注册表</h2></div>
        <span className="settings-chip">{pendingMcp} PENDING / {mcp.length} TOTAL</span>
      </div>
      {mcp.length? <div className="catalog-grid">
        {mcp.map(m=>{
          const cfg=m.config||{};
          const tools=Object.keys(cfg.tools||{});
          return <article key={m.hash} className="catalog-card">
            <div className="catalog-head">
              <span className="catalog-icon"><Icon name="terminal" size={15}/></span>
              <strong>{cfg.server_id||'MCP SERVER'}</strong>
              <span className={'status-pill '+statusTone(m.status)}><i className="status-dot"/>{MCP_STATUS_TEXT[m.status]||m.status}</span>
            </div>
            <div className="mcp-facts">
              <div><span>传输</span><b>{String(cfg.transport||'—').toUpperCase()}</b></div>
              <div><span>地址</span><b title={cfg.url||''}>{cfg.url||'—'}</b></div>
              <div><span>工具数</span><b>{tools.length}</b></div>
              <div><span>超时</span><b>{cfg.timeout?cfg.timeout+'s':'—'}</b></div>
            </div>
            {!!tools.length&&<div className="mcp-tools">{tools.map(t=><span key={t} className="type-tag">{t}</span>)}</div>}
            <div className="catalog-hash"><span className="field-label">版本哈希</span><HashChip value={m.hash} label="复制 MCP 哈希" onCopy={onCopy}/></div>
            <div className="catalog-foot">
              <span className="hint">批准不会启动服务或授予角色工具权限</span>
              <div className="catalog-actions">
                <button type="button" className="primary-action" disabled={busy||m.status==='APPROVED'} onClick={()=>act('mcp-approve',{hash:m.hash})}>
                  <Icon name="shield-check" size={13}/>人工批准
                </button>
                <button type="button" className="secondary" disabled={busy||m.status==='DISABLED'} onClick={()=>act('mcp-disable',{hash:m.hash})}>
                  <Icon name="pause-circle" size={13}/>停用
                </button>
              </div>
            </div>
          </article>;
        })}
      </div> : <p className="empty">暂无 MCP 注册记录。登记后需人工批准才能进入运行时校验。</p>}
    </section>

    {policy&&<section className="panel">
      <div className="panel-head">
        <div className="panel-title"><Icon name="sliders" size={16}/><h2>角色工具策略</h2></div>
        <span className="settings-chip">EFFECTIVE · READ ONLY</span>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead><tr><th>角色</th><th>部门</th><th>主模型</th><th>令牌预算</th><th>成本预算</th><th>已绑定 Skill</th></tr></thead>
          <tbody>
            {Object.keys(effective||{}).map(role=>{
              const layer=effective[role]||{};
              const roleCfg=(policy.roles||{})[role]||{};
              const skillMap=layer.skills||{};
              const skillList=Object.entries(skillMap);
              return <tr key={role}>
                <td><span className="type-tag">{role}</span></td>
                <td className="phase-code">{roleCfg.department||'—'}</td>
                <td className="phase-code">{layer.primary||'—'}</td>
                <td className="mono-num">{layer.token_budget?layer.token_budget.toLocaleString('en-US'):'—'}</td>
                <td className="mono-num">{layer.cost_budget?formatMicroUsd(layer.cost_budget):'—'}</td>
                <td>{skillList.length
                  ? skillList.map(([name,hash])=><code key={name} className="policy-chip" title={hash}>{name}</code>)
                  : <span className="muted-text">未绑定</span>}</td>
              </tr>;
            })}
          </tbody>
        </table>
      </div>
      {policy.platform&&policy.platform.policy&&<div className="platform-policy">
        <span className="field-label">平台级策略 {policy.platform.policy.policy_id}</span>
        <div className="platform-policy-facts">
          <span><Icon name="lock" size={11}/>能力 {((policy.platform.policy.capabilities||[]).length)||'—'}</span>
          <span><Icon name="globe" size={11}/>网络 {(policy.platform.policy.network_hosts||[]).join('、')||'—'}</span>
          <span><Icon name="folder" size={11}/>工作区 {(policy.platform.policy.workspace_roots||[]).join('、')||'—'}</span>
          <span><Icon name="key" size={11}/>密钥 {(policy.platform.policy.secrets||[]).join('、')||'—'}</span>
          <span><Icon name="user-check" size={11}/>全部工具调用需人工审批</span>
        </div>
      </div>}
    </section>}
  </>;
}

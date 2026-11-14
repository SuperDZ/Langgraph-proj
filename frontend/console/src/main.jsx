import React, {useCallback, useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './console.css';
import './console-enhancements.css';
import './console-interactions.css';
import './workspace.css';
import ModelSettings from './ModelSettingsView';
import GlobalSettings from './GlobalSettings';
import WorkflowOverview from './WorkflowOverview';
import Icon from './Icon';
import ToastHost from './Toast';
import CommandPalette from './CommandPalette';
import RunTable from './RunTable';
import RunContext from './RunContext';
import Approvals from './Approvals';
import DeliveryForm from './DeliveryForm';
import CostAudit from './CostAudit';
import Knowledge from './Knowledge';
import SkillsMcp from './SkillsMcp';

const tabs = [
  ['runs', '交付与运行', 'play-circle', '查看交付进度、质量门禁与待处理事项。'],
  ['approvals', '门禁与发布', 'shield-check', '处理人工确认，查看预发许可与部署记录。'],
  ['knowledge', '复盘与记忆', 'archive', '复盘已交付的运行，审核候选记忆。'],
  ['config', '角色与模型', 'sliders', '配置各角色的模型、预算与凭据。'],
  ['skills', 'Skills 与 MCP', 'plug', '管理技能版本与工具连接。'],
  ['audit', '成本与审计', 'chart', '查看用量、运行事件与归档产物。'],
];
const groups = [['交付工作区', tabs.slice(0, 3)], ['平台管理', tabs.slice(3)]];
const shortcut = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl+';
const notifications = {
  start:'已提交运行', confirm_g1:'已提交方案确认', clarify:'已提交澄清答复',
  release:'已提交预发或恢复操作', retrospect:'复盘已生成',
  'memory-review':'记忆提案已处理', 'memory-revoke':'记忆已撤销', 'memory-rollback':'已回滚到目标版本',
  'evolution-review':'提案已审核', 'evolution-publish':'已发布已验证版本',
  'skill-import':'Skill 包已导入', 'skill-approve':'Skill 已批准并绑定',
  'mcp-register':'MCP 配置已登记', 'mcp-approve':'MCP 已批准', 'mcp-disable':'MCP 已停用',
};

async function request(path, body, token) {
  const response = await fetch(path, body ? {
    method:'POST', headers:{'Content-Type':'application/json', 'X-AgentLoop-CSRF':token},
    body:JSON.stringify(body),
  } : {});
  const data = await response.json();
  if (!response.ok || data.error) throw Error(data.error || response.status);
  return data;
}

function App() {
  const [page, setPage] = useState('runs'), [run, setRun] = useState(''), [snapshot, setSnapshot] = useState(null);
  const [connection, setConnection] = useState('connecting'), [pending, setPending] = useState(false);
  const [query, setQuery] = useState(''), [settingsOpen, setSettingsOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false), [toasts, setToasts] = useState([]);
  const [reviewReason, setReviewReason] = useState('');
  const [creating, setCreating] = useState(false), [startError, setStartError] = useState('');
  const [creationVersion, setCreationVersion] = useState(0);
  const requested = useRef(0), applied = useRef(0), activeRun = useRef('');
  const csrf = useRef(''), requestPending = useRef(false), lastJobError = useRef('');
  const creationForm = useRef(null), context = useRef(null), newButton = useRef(null), bringContextIntoView = useRef(false);
  const pushToast = (kind, title, detail) => setToasts([{id:Date.now()+Math.random(), kind, title, detail}]);
  const dismissToast = useCallback(id => setToasts(items => items.filter(item => item.id !== id)), []);

  function navigate(next) {
    setPage(next);
    setToasts([]);
    if (next !== page) window.scrollTo(0, 0);
  }

  function selectRun(id, reveal = false) {
    activeRun.current = id;
    bringContextIntoView.current = reveal;
    setRun(id);
    setReviewReason('');
    setQuery('');
    if (id === run && reveal) context.current?.focus();
  }

  async function copyText(value, label) {
    if (!value) {pushToast('info', '没有可复制的内容'); return;}
    try {await navigator.clipboard.writeText(value); pushToast('success', label || '已复制到剪贴板');}
    catch {pushToast('error', '复制失败', '浏览器拒绝了剪贴板访问');}
  }

  async function refresh(id = activeRun.current) {
    const seq = ++requested.current;
    try {
      const next = await request('/api/platform' + (id ? '?run_id=' + encodeURIComponent(id) : ''));
      if (seq < applied.current || id !== activeRun.current) return;
      applied.current = seq;
      csrf.current = next.csrf;
      setSnapshot({id, value:next});
      setConnection('online');
      if (next.job?.error && lastJobError.current !== next.job.error) pushToast('error', '运行异常', next.job.error);
      lastJobError.current = next.job?.error || '';
    } catch {
      if (seq >= applied.current && id === activeRun.current) {
        applied.current = seq;
        setConnection('offline');
      }
    }
  }

  useEffect(() => {
    refresh(run);
    const timer = setInterval(() => refresh(run), 2500);
    return () => clearInterval(timer);
  }, [run]);

  useEffect(() => {
    if (bringContextIntoView.current && page === 'runs' && context.current) {
      bringContextIntoView.current = false;
      context.current.focus();
    }
  }, [run, page]);

  useEffect(() => {
    function onKey(event) {
      if (!(event.metaKey || event.ctrlKey) || creating || settingsOpen) return;
      if (event.key.toLowerCase() === 'k') {event.preventDefault(); setPaletteOpen(value => !value);}
      else if (/^[1-6]$/.test(event.key) && !paletteOpen) {event.preventDefault(); navigate(tabs[Number(event.key)-1][0]);}
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [page, creating, settingsOpen, paletteOpen]);

  useEffect(() => {
    if (creating && page === 'runs') {
      creationForm.current?.querySelector('textarea')?.focus();
    }
  }, [creating, page]);

  async function act(action, body = {}, options = {}) {
    if (requestPending.current) return null;
    requestPending.current = true;
    setPending(true);
    try {
      const result = await request(options.path || '/api/platform/' + action, {run_id:run || 'console-config', ...body}, csrf.current);
      if (!options.silent) pushToast('success', notifications[action] || '操作已提交');
      if (action !== 'start') await refresh();
      return result;
    } catch (error) {
      if (!options.silent) pushToast('error', '操作失败', error.message);
      if (options.propagate) throw error;
      return null;
    } finally {
      requestPending.current = false;
      setPending(false);
    }
  }

  const globalData = snapshot?.value;
  const data = snapshot?.id === run ? globalData : null;
  const runs = globalData?.runs || [];
  const selected = data?.run || runs.find(item => item.run_id === run);
  const busy = pending || connection !== 'online' || globalData?.job?.busy;
  const selectedBusy = busy || !data?.run;
  const needsReview = runs.filter(item => ['WAITING_APPROVAL', 'PAUSED_FOR_HUMAN', 'NEEDS_RECONCILIATION'].includes(item.status)).length;
  const rootCount = runs.filter(item => !item.parent_run_id).length;
  const title = tabs.find(item => item[0] === page);
  const openNew = () => {setStartError(''); setCreating(true);};
  const openSettings = () => setSettingsOpen(true);
  const openApprovals = () => navigate('approvals'), openAudit = () => navigate('audit'), openRuns = () => navigate('runs');
  const copyId = id => copyText(id, '已复制运行标识');
  const save = (action, body) => act(action, body, {propagate:true, silent:true});
  const paletteCommands = [
    ...tabs.map(([id, label, icon], index) => ({id:'tab-'+id, label, icon, group:'页面', shortcut:shortcut+(index+1), run:() => navigate(id)})),
    {id:'new-delivery', label:'新建交付', icon:'plus', group:'操作', run:() => {openRuns(); openNew();}},
    {id:'settings', label:'打开全局模型设置', icon:'settings', group:'操作', run:openSettings},
    {id:'copy-run', label:'复制当前运行标识', hint:run || '尚未选择运行', icon:'copy', group:'操作', run:() => copyId(run)},
  ];

  return <div className="shell workspace">
    <aside className="workspace-sidebar">
      <a className="workspace-brand" href="/console/"><span><Icon name="layers" size={17}/></span>AgentLoop</a>
      <nav aria-label="主导航">
        {groups.map(([group, items]) => <div className="nav-group" key={group}>
          <span className="nav-group-title">{group}</span>
          {items.map(([id,label,icon]) => <button type="button" key={id} aria-label={label}
            aria-current={page === id ? 'page' : undefined} className={page === id ? 'active' : ''}
            onClick={() => navigate(id)} title={label}>
            <Icon name={icon} size={17}/><span className="nav-label">{label}</span>
          </button>)}
        </div>)}
      </nav>
      <div className="workspace-foot"><small>本地工作区 · 生产发布禁用</small></div>
    </aside>
    <div className="main">
      <header className="workspace-header">
        <nav className="area-switch" aria-label="切换工作区域">
          <a href="/console/" aria-current="page">工作空间</a>
          <a href="/workbench">工作台</a>
        </nav>
        <div className="breadcrumb"><strong>{title[1]}</strong></div>
        <div className="header-actions">
          <button type="button" className="command-trigger" onClick={() => setPaletteOpen(true)} aria-label="打开命令面板"><Icon name="search" size={15}/><span>搜索命令</span><kbd>{shortcut}K</kbd></button>
          <button type="button" className="secondary global-settings-button" disabled={busy || !globalData} onClick={openSettings} aria-label="打开全局模型设置"><Icon name="settings" size={16}/><span>设置</span></button>
          <span role="status" className={'connection-state '+connection}>{({online:'已连接', connecting:'连接中', offline:'连接中断'})[connection]}</span>
        </div>
      </header>
      <main>
        <div className="workspace-heading">
          <div><h1>{title[1]}</h1><p>{title[3]}</p></div>
          {page === 'runs' ? <button ref={newButton} type="button" className="new-run-button" onClick={openNew} aria-expanded={creating} aria-controls="new-delivery"><Icon name="plus" size={17}/>新建交付</button>
          : page !== 'config' && <label className="workspace-run-select">当前运行<select value={run} onChange={event => selectRun(event.target.value)}>
              <option value="">选择运行</option>
              {run && !runs.some(item => item.run_id === run) && <option value={run}>{run}</option>}
              {runs.map(item => <option key={item.run_id} value={item.run_id}>{item.parent_run_id ? '↳ ' : ''}{item.run_id}</option>)}
            </select></label>}
        </div>
        <ToastHost toasts={toasts} onDismiss={dismissToast}/>
        {connection === 'offline' && <p className="alert" role="alert">无法连接本机服务，操作已暂停。<button type="button" className="secondary" onClick={() => refresh()}>重试连接</button></p>}
        {page === 'approvals' && run && globalData?.job?.run_id === run && globalData.job.error &&
          <p className="alert" role="alert">{globalData.job.error}</p>}
        {page === 'runs' && <>
          <section ref={creationForm} id="new-delivery" className="panel delivery-inline" aria-labelledby="delivery-title" hidden={!creating}>
            <div className="delivery-dialog-head">
              <div><h2 id="delivery-title">新建交付</h2><p>先写清任务目标，再选择执行方式。</p></div>
              <button type="button" className="secondary" disabled={pending} onClick={() => {
                setCreating(false);
                newButton.current?.focus();
              }}>返回运行列表</button>
            </div>
            {startError && <p className="alert" role="alert">{startError}</p>}
            <DeliveryForm key={creationVersion} config={globalData?.config} effective={globalData?.effective_agents} credentials={globalData?.credentials}
              busy={busy} submitting={pending} shortcut={shortcut} onStart={async payload => {
                setStartError('');
                try {
                  const result = await act('start', {run_id:payload.runId, task:payload.task, use_models:payload.useModels, role_models:payload.roleModels}, {propagate:true, silent:true});
                  if (result) {
                    setCreating(false);
                    setCreationVersion(version => version + 1);
                    selectRun(payload.runId, true);
                    pushToast('success', '已提交运行', payload.runId);
                  }
                } catch (error) {setStartError(error.message);}
              }}/>
          </section>
          <div className="run-summary"><span><Icon name="layers" size={15}/><strong>{rootCount}</strong> 条主运行</span><span><Icon name="clock" size={15}/><strong>{needsReview}</strong> 条待人工处理</span></div>
          <div className="run-workspace">
            <section className="panel run-list-panel" aria-labelledby="run-list-title">
              <div className="run-list-title"><h2 id="run-list-title">运行列表</h2><span>{runs.length} 条记录</span></div>
              {!globalData && connection !== 'offline' ? <p className="empty" role="status">正在加载运行…</p>
                : <RunTable runs={runs} current={run} onSelect={item => selectRun(item.run_id, true)} onCopy={copyId}/>}
            </section>
            <div className="run-context-wrap" tabIndex={-1} ref={context}>
              <RunContext run={selected} gates={data?.gates} job={globalData?.job?.run_id === run ? globalData.job : null}
                selectRun={selectRun} openApprovals={openApprovals} openAudit={openAudit} openKnowledge={() => navigate('knowledge')}/>
              {run && !selected && (globalData?.job?.run_id === run && globalData.job.error
                ? <p className="alert" role="alert">{globalData.job.error}</p>
                : <p className="hint">正在等待运行记录写入…</p>)}
            </div>
          </div>
          <details className="workflow-help"><summary>了解交付流程</summary><WorkflowOverview compact/></details>
        </>}
        {page === 'approvals' && <Approvals key={run} run={selected} data={data} busy={selectedBusy} act={act} openAudit={openAudit} openRuns={openRuns}
          confirmG1={() => act('confirm_g1', {}, {path:'/api/confirm_g1'})}/>}
        {page === 'knowledge' && <Knowledge selected={selected} reports={data?.reports || []} proposals={data?.proposals || []} memories={data?.memories || []} evolutions={data?.evolutions || []} busy={selectedBusy} act={act} reason={reviewReason} setReason={setReviewReason} query={query} setQuery={setQuery}/>}
        {page === 'config' && <ModelSettings config={globalData?.config} effective={globalData?.effective_agents} credentials={globalData?.credentials} busy={busy} save={save} openGlobal={openSettings}/>}
        {page === 'skills' && <SkillsMcp run={run} busy={selectedBusy} act={act} skills={data?.skills || []} mcp={data?.mcp || []} policy={globalData?.config} effective={globalData?.effective_agents} onCopy={copyText}/>}
        {page === 'audit' && <CostAudit budgets={data?.budgets || []} budgetSummary={data?.budget_summary} events={data?.events || []} artifacts={data?.artifacts || []} onCopy={copyText}/>}
      </main>
    </div>
    {settingsOpen && globalData?.config && <GlobalSettings config={globalData.config} credentials={globalData.credentials} busy={busy} save={save} onClose={() => setSettingsOpen(false)}/>}
    <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={paletteCommands}/>
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);

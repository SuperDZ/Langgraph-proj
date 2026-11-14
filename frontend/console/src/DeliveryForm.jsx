import React, {useMemo, useState} from 'react';
import Icon from './Icon';
import RunModelSelector from './RunModelSelector';

/*
 * 新建交付表单：参考 Vercel Deploy / Linear 的「一张表单 + 分段选择 + 主次动作」结构。
 * 关键改进：模型来源用分段控件而非裸复选框；运行标识带格式校验与一键重生成；
 * 任务目标改为多行输入并带字数统计与写作提示。
 */

const ID_PATTERN = /^[A-Za-z0-9_-]{1,80}$/;

export default function DeliveryForm({config, effective, credentials, busy, submitting, shortcut, onStart}) {
  const [runId, setRunId] = useState(() => `delivery-${Date.now().toString(36)}`);
  const [task, setTask] = useState('');
  const [source, setSource] = useState('script');
  const [roleModels, setRoleModels] = useState({});
  const [touched, setTouched] = useState(false);

  const idError = useMemo(() => !runId ? '运行标识不能为空' : (ID_PATTERN.test(runId) ? '' : '只能使用字母、数字、下划线和连字符，且不超过 80 位'), [runId]);
  const taskMissing = task.trim().length < 4;
  const canSubmit = !idError && !taskMissing && !busy;
  const roleCount = Object.keys(config?.roles || {}).length;

  async function submit() {
    setTouched(true);
    if (!canSubmit) return;
    await onStart({runId, task: task.trim(), useModels: source === 'models', roleModels: source === 'models' ? roleModels : {}});
  }

  function onKeyDown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); submit(); }
  }

  return <div className="delivery-form" onKeyDown={onKeyDown}>
    <div className="delivery-fields">
      <div className="field full">
        <label htmlFor="delivery-task">任务目标</label>
        <div className={`field-control textarea ${touched && taskMissing ? 'invalid' : ''}`}>
          <textarea id="delivery-task" rows={3} value={task} maxLength={400}
            onChange={event => setTask(event.target.value)} onBlur={() => setTouched(true)}
            placeholder="描述要交付的结果、验收标准与约束条件，越具体越容易通过 G1 审核。"/>
          <span className="char-counter">{task.length}/400</span>
        </div>
        {touched && taskMissing ? <small className="field-error"><Icon name="alert-triangle" size={12}/>任务目标至少 4 个字符</small>
          : <small className="field-hint">写清交付物与验收标准；产品与架构专家会在 G1 前提出澄清。</small>}
      </div>

      <div className="field">
        <label htmlFor="delivery-run-id">运行标识</label>
        <div className={`field-control ${touched && idError ? 'invalid' : ''}`}>
          <Icon name="terminal" size={15}/>
          <input id="delivery-run-id" value={runId} spellCheck="false" autoComplete="off"
            onChange={event => setRunId(event.target.value)} onBlur={() => setTouched(true)}/>
          <button type="button" className="field-action" onClick={() => setRunId(`delivery-${Date.now().toString(36)}`)}>
            <Icon name="refresh" size={14}/><span>重新生成</span>
          </button>
        </div>
        {touched && idError ? <small className="field-error"><Icon name="alert-triangle" size={12}/>{idError}</small>
          : <small className="field-hint">用于证据、门禁与审计的引用键，创建后不可更改。</small>}
      </div>

      <div className="field full">
        <span className="field-label">执行角色来源</span>
        <div className="segmented" role="group" aria-label="执行角色来源">
          <button type="button" aria-pressed={source === 'script'} className={source === 'script' ? 'active' : ''}
            onClick={() => setSource('script')}>
            <Icon name="zap" size={14}/><span>脚本角色</span><small>内置流程，无需模型凭据</small>
          </button>
          <button type="button" aria-pressed={source === 'models'} className={source === 'models' ? 'active' : ''}
            onClick={() => setSource('models')}>
            <Icon name="cpu" size={14}/><span>已保存模型配置</span><small>{roleCount} 个角色各自选模型</small>
          </button>
        </div>
      </div>
    </div>

    {source === 'models' && <div className="delivery-models">
      <div className="delivery-models-head">
        <Icon name="sliders" size={14}/><strong>逐角色模型</strong>
        <span className="settings-chip">仅影响本次运行</span>
      </div>
      <RunModelSelector config={config} effective={effective} credentials={credentials}
        value={roleModels} onChange={setRoleModels} busy={busy}/>
    </div>}

    <div className="delivery-footer">
      <button type="button" className="secondary" onClick={() => {setTask('修复 hello 参数边界，交付页面和部署配置。'); document.getElementById('delivery-task')?.focus();}}>填入样例</button>
      <div className="delivery-actions">
        <span className="kbd-hint"><kbd>{shortcut}↵</kbd></span>
        <button type="button" className="primary-action" disabled={!canSubmit} onClick={submit}>
          {submitting ? <><Icon name="loader" size={14} className="spin"/>提交中…</> : <><Icon name="rocket" size={14}/>启动运行</>}
        </button>
      </div>
    </div>
  </div>;
}

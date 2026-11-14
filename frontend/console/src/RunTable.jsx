import React, {useMemo, useState} from 'react';
import Icon from './Icon';

/*
 * 运行数据表：参考 GitHub Actions / Datadog 的密集列表。
 * 提供搜索、状态筛选、列排序、当前运行高亮与一键复制，取代原来的纯按钮列表。
 */

const STATUS_TONE = {
  COMPLETED: 'ok', PASSED: 'ok', APPROVED: 'ok', ACTIVE: 'ok',
  RUNNING: 'live', STARTED: 'live',
  WAITING_APPROVAL: 'warn', PAUSED_FOR_HUMAN: 'warn', PENDING: 'warn',
  WAITING_GATE: 'warn', STALE: 'warn', BLOCKED:'warn', NEEDS_RECONCILIATION:'warn',
  FAILED: 'bad', CANCELLED: 'bad', REJECTED: 'bad',
};

const STATUS_TEXT = {
  COMPLETED: '已完成', RUNNING: '执行中', WAITING_APPROVAL: '待人工确认',
  PAUSED_FOR_HUMAN: '等待澄清', FAILED: '已失败', CANCELLED: '已取消',
  CREATED: '已创建', PENDING: '待处理', WAITING_GATE: '等待门禁',
  BLOCKED: '已阻塞', CANCEL_REQUESTED: '取消中', CANCELLING: '取消中',
  NEEDS_RECONCILIATION: '待对账',
  PASSED:'通过', APPROVED:'已批准', APPROVE:'已批准', REJECT:'已拒绝',
  REJECTED:'已拒绝', STALE:'已失效', REVOKED:'已撤销',
};

export function StatusPill({status}) {
  const tone = STATUS_TONE[status] || 'neutral';
  return <span className={`status-pill tone-${tone}`}>
    <i className="status-dot"/>{STATUS_TEXT[status] || status}
  </span>;
}

const COLUMNS = [
  {key: 'run_id', label: '运行标识'},
  {key: 'run_type', label: '类型', className:'col-type'},
  {key: 'phase', label: '阶段', className:'col-phase'},
  {key: 'status', label: '状态'},
];

export default function RunTable({runs = [], current, onSelect, onCopy, busy}) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('ALL');
  const [sort, setSort] = useState(null);

  const statuses = useMemo(() => {
    const counter = new Map();
    runs.forEach(run => counter.set(run.status, (counter.get(run.status) || 0) + 1));
    return [...counter.entries()].map(([status, count]) => ({status, count}));
  }, [runs]);

  const rows = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    let list = runs.filter(run => {
      if (filter !== 'ALL' && run.status !== filter) return false;
      if (!keyword) return true;
      return [run.run_id, run.phase, run.status, STATUS_TEXT[run.status], run.run_type, run.parent_run_id].join(' ').toLowerCase().includes(keyword);
    });
    if (!sort) return list.reverse();
    list.sort((a, b) => {
      const left = String(a[sort.key] || ''), right = String(b[sort.key] || '');
      if (left === right) return String(a.run_id).localeCompare(String(b.run_id));
      return sort.dir === 'asc' ? left.localeCompare(right) : right.localeCompare(left);
    });
    return list;
  }, [runs, query, filter, sort]);

  function toggleSort(key) {
    setSort(current => current?.key === key
      ? {key, dir: current.dir === 'asc' ? 'desc' : 'asc'}
      : {key, dir: 'asc'});
  }

  return <div className="run-table">
    <div className="run-table-toolbar">
      <label className="table-search">
        <Icon name="search" size={14}/>
        <input value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索运行标识、阶段或状态" aria-label="搜索运行"/>
      </label>
      <select aria-label="按状态筛选" value={filter} onChange={event => setFilter(event.target.value)}>
        <option value="ALL">全部状态</option>
        {filter !== 'ALL' && !statuses.some(item => item.status === filter) && <option value={filter}>{STATUS_TEXT[filter] || filter} (0)</option>}
        {statuses.map(item => <option key={item.status} value={item.status}>{STATUS_TEXT[item.status] || item.status} ({item.count})</option>)}
      </select>
    </div>

    {rows.length ? <div className="table-scroll">
      <table className="data-table">
        <thead><tr>
          {COLUMNS.map(column => <th key={column.key} className={column.className} aria-sort={sort?.key === column.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}>
            <button type="button" onClick={() => toggleSort(column.key)}
              className={sort?.key === column.key ? 'sorted' : ''}>
              {column.label}
              {sort?.key === column.key && <Icon name="chevron-down" size={12}
                className={sort.dir === 'asc' ? 'flip' : ''}/>}
            </button>
          </th>)}
          <th className="col-actions"><span className="sr-only">操作</span></th>
        </tr></thead>
        <tbody>
          {rows.map(run => {
            const isCurrent = run.run_id === current;
            const isChild = Boolean(run.parent_run_id);
            return <tr key={run.run_id} className={isCurrent ? 'current' : ''}
              onClick={() => onSelect && onSelect(run)}>
              <td className="col-id">
                <span className="id-cell">
                  {isChild && <Icon name="git-branch" size={13} className="branch-icon"/>}
                  <button type="button" className="run-id-button" aria-current={isCurrent ? 'true' : undefined} onClick={event => {event.stopPropagation(); onSelect?.(run);}}><code>{run.run_id}</code></button>
                </span>
                {isChild && <small className="parent-hint">父运行 {run.parent_run_id}</small>}
              </td>
              <td className="col-type"><span className="type-tag">{run.run_type}</span></td>
              <td className="col-phase"><code className="phase-code">{run.phase}</code></td>
              <td className="col-status"><StatusPill status={run.status}/></td>
              <td className="col-actions">
                <button type="button" className="icon-button" disabled={busy}
                  title="复制运行标识" aria-label={`复制运行标识 ${run.run_id}`}
                  onClick={event => { event.stopPropagation(); onCopy && onCopy(run.run_id); }}>
                  <Icon name="copy" size={14}/>
                </button>
              </td>
            </tr>;
          })}
        </tbody>
      </table>
    </div> : <div className="empty">{query || filter !== 'ALL' ? <>没有符合筛选条件的运行。<button type="button" className="secondary" onClick={() => {setQuery(''); setFilter('ALL');}}>清除筛选</button></> : '暂无运行。点击「新建交付」开始。'}</div>}
  </div>;
}

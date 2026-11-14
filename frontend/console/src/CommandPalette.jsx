import React, {useEffect, useMemo, useRef, useState} from 'react';
import Icon from './Icon';

/*
 * 命令面板（⌘K / Ctrl+K）：参考 Raycast、Linear 的键盘优先交互。
 * 所有页面切换、设置入口与高频操作都可以在这里直接触发。
 */

export default function CommandPalette({open, onClose, commands = []}) {
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);

  const results = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return commands;
    return commands.filter(item =>
      item.label.toLowerCase().includes(keyword) ||
      (item.hint || '').toLowerCase().includes(keyword) ||
      (item.group || '').toLowerCase().includes(keyword));
  }, [commands, query]);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setActive(0);
    const timer = setTimeout(() => inputRef.current?.focus(), 30);
    return () => clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(event) {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); return; }
      if (!results.length) return;
      if (event.key === 'ArrowDown') { event.preventDefault(); setActive(index => (index + 1) % results.length); }
      if (event.key === 'ArrowUp') { event.preventDefault(); setActive(index => (index - 1 + results.length) % results.length); }
      if (event.key === 'Enter') {
        event.preventDefault();
        const target = results[active];
        if (target) { onClose(); target.run(); }
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, results, active, onClose]);

  if (!open) return null;

  return <div className="palette-backdrop" onMouseDown={onClose}>
    <div className="palette" role="dialog" aria-modal="true" aria-label="命令面板" onMouseDown={event => event.stopPropagation()}>
      <div className="palette-search">
        <Icon name="search" size={16}/>
        <input ref={inputRef} value={query} onChange={event => { setQuery(event.target.value); setActive(0); }}
          placeholder="搜索命令、页面或操作…" aria-label="搜索命令" spellCheck="false"/>
        <kbd>ESC</kbd>
      </div>
      <div className="palette-list" role="listbox">
        {results.map((item, index) => <React.Fragment key={item.id}>
          {item.group && (index === 0 || results[index - 1].group !== item.group) &&
            <div className="palette-group">{item.group}</div>}
          <button type="button" role="option"
            aria-selected={index === active} className={`palette-item ${index === active ? 'active' : ''}`}
            onMouseEnter={() => setActive(index)} onClick={() => { onClose(); item.run(); }}>
            <span className="palette-item-icon"><Icon name={item.icon || 'zap'} size={15}/></span>
            <span className="palette-item-label">{item.label}</span>
            {item.hint && <span className="palette-item-hint">{item.hint}</span>}
            {item.shortcut && <kbd className="palette-item-key">{item.shortcut}</kbd>}
          </button>
        </React.Fragment>)}
        {!results.length && <p className="palette-empty">没有匹配的命令。试试“交付”“设置”或“密钥”。</p>}
      </div>
      <div className="palette-footer">
        <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
        <span><kbd>↵</kbd> 执行</span>
        <span><kbd>esc</kbd> 关闭</span>
      </div>
    </div>
  </div>;
}

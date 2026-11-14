import React, {useEffect, useRef} from 'react';
import Icon from './Icon';

/*
 * 页面内操作反馈。成功提示自动收起，错误保留供用户阅读。
 */

const KIND = {
  success: {icon: 'check-circle', tone: 'ok', label: '成功'},
  error: {icon: 'alert-triangle', tone: 'bad', label: '失败'},
  info: {icon: 'info', tone: 'info', label: '提示'},
};

function Toast({item, onDismiss}) {
  const meta = KIND[item.kind] || KIND.info;
  const timer = useRef(null);
  useEffect(() => {
    if (item.kind === 'error') return;
    timer.current = setTimeout(() => onDismiss(item.id), item.duration || 4600);
    return () => clearTimeout(timer.current);
  }, [item.id, item.kind, item.duration, onDismiss]);

  return <div className={`toast toast-${meta.tone}`} role="status" aria-live="polite">
    <span className="toast-icon"><Icon name={meta.icon} size={15}/></span>
    <span className="toast-body">
      <strong title={item.detail || item.title}>{item.title}</strong>
      {item.detail && <small>{item.detail}</small>}
    </span>
    <button type="button" className="toast-close" onClick={() => onDismiss(item.id)} aria-label="关闭通知">
      <Icon name="x" size={13}/>
    </button>
  </div>;
}

export default function ToastHost({toasts = [], onDismiss}) {
  return <div className="toast-host">
    {toasts.map(item => <Toast key={item.id} item={item} onDismiss={onDismiss}/>)}
  </div>;
}

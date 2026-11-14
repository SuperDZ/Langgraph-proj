import React from 'react';

/*
 * 图标系统：24×24 网格、1.75 描边、currentColor 描边。
 * 与 Lucide 保持一致的视觉语言，但全部手写内联 SVG，不引入任何外部依赖或网络请求。
 * 用法：<Icon name="search" size={16} />
 */
const PATHS = {
  'play-circle': <><circle cx="12" cy="12" r="9"/><path d="M10 8.6l6 3.4-6 3.4z"/></>,
  'shield-check': <><path d="M12 3l7.5 3v6.2c0 4.6-3.2 7.7-7.5 9.3-4.3-1.6-7.5-4.7-7.5-9.3V6z"/><path d="M9 12.2l2.2 2.2 4-4.4"/></>,
  'shield-alert': <><path d="M12 3l7.5 3v6.2c0 4.6-3.2 7.7-7.5 9.3-4.3-1.6-7.5-4.7-7.5-9.3V6z"/><path d="M12 8.5v4M12 15.8v.4"/></>,
  archive: <><rect x="3" y="4" width="18" height="4.5" rx="1"/><path d="M5 8.5V19a1.5 1.5 0 001.5 1.5h11A1.5 1.5 0 0019 19V8.5"/><path d="M10 13h4"/></>,
  sliders: <><path d="M4 7h9M17 7h3M4 12h3M11 12h9M4 17h9M17 17h3"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="15" cy="17" r="2"/></>,
  plug: <><path d="M9 3v5M15 3v5"/><path d="M7 8h10v3.5a5 5 0 01-10 0z"/><path d="M12 16.5V21"/></>,
  chart: <><path d="M3 21h18"/><rect x="5" y="11" width="3.2" height="7" rx="1"/><rect x="10.4" y="6" width="3.2" height="12" rx="1"/><rect x="15.8" y="9" width="3.2" height="9" rx="1"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.4M12 18.8v2.4M21.2 12h-2.4M5.2 12H2.8M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7M18.5 18.5l-1.7-1.7M7.2 7.2L5.5 5.5"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  trash: <><path d="M4 7h16M10 7V4.5h4V7M6.5 7l1 13h9l1-13"/></>,
  key: <><circle cx="8" cy="15.5" r="4"/><path d="M10.8 12.7L19 4.5M16.5 7l2 2M14 9.5l2 2"/></>,
  copy: <><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5.5 15H5a1 1 0 01-1-1V5a1 1 0 011-1h9a1 1 0 011 1v.5"/></>,
  check: <path d="M4.5 12.5l5 5 10-11"/>,
  x: <path d="M6 6l12 12M18 6L6 18"/>,
  'chevron-right': <path d="M9 5l7 7-7 7"/>,
  'chevron-down': <path d="M5 9l7 7 7-7"/>,
  'arrow-right': <><path d="M4 12h15M13.5 6.5l5.5 5.5-5.5 5.5"/></>,
  refresh: <><path d="M20 12a8 8 0 11-2.4-5.7"/><path d="M20 4v4.5h-4.5"/></>,
  external: <><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14.5V19a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 014 19V8a1.5 1.5 0 011.5-1.5H10"/></>,
  filter: <path d="M4 5h16l-6.2 7.3V19l-3.6 1.8v-8.5z"/>,
  command: <><path d="M9 6a3 3 0 10-3 3h12a3 3 0 10-3-3v12a3 3 0 103-3H6a3 3 0 103 3z"/></>,
  'alert-triangle': <><path d="M12 4l9 16H3z"/><path d="M12 10v4.2M12 17.4v.3"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5.2M12 7.8v.3"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5.3l3.2 1.9"/></>,
  terminal: <><rect x="3" y="4.5" width="18" height="15" rx="2"/><path d="M7.5 9.5l3 2.5-3 2.5M13 15h4"/></>,
  'git-branch': <><circle cx="6" cy="6" r="2.4"/><circle cx="6" cy="18" r="2.4"/><circle cx="18" cy="9" r="2.4"/><path d="M6 8.4v7.2M18 11.4c0 3-3.6 3.4-6 3.9"/></>,
  lock: <><rect x="4.5" y="10" width="15" height="10.5" rx="2"/><path d="M8 10V7.5a4 4 0 018 0V10"/></>,
  zap: <path d="M13 2.5L4.5 14H11l-1 7.5L19.5 10H13z"/>,
  rocket: <><path d="M12 3.2c3.4 2 5.3 5.5 5.3 8.9l3 3.3-3.4 3.4-3.3-3c-3.4 0-6.9-1.9-8.9-5.3z"/><circle cx="13.8" cy="9.2" r="1.5"/><path d="M9 15.4l-2.6 2.6M6.6 18.2l-2.4 2.4"/></>,
  cpu: <><rect x="5" y="5" width="14" height="14" rx="2.5"/><rect x="9.2" y="9.2" width="5.6" height="5.6" rx="1"/><path d="M9 2.5v2.5M15 2.5v2.5M9 19v2.5M15 19v2.5M2.5 9H5M2.5 15H5M19 9h2.5M19 15h2.5"/></>,
  layers: <><path d="M12 3l8.5 4.7L12 12.4 3.5 7.7z"/><path d="M3.5 12.3L12 17l8.5-4.7M3.5 16.6L12 21.3l8.5-4.7"/></>,
  link: <><path d="M10.2 13.8a4.2 4.2 0 006 .4l2.1-2.1a4.2 4.2 0 00-6-6l-1.2 1.2"/><path d="M13.8 10.2a4.2 4.2 0 00-6-.4l-2.1 2.1a4.2 4.2 0 006 6l1.2-1.2"/></>,
  more: <><circle cx="5.5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="18.5" cy="12" r="1.4"/></>,
  sparkles: <><path d="M11 3l1.5 4L16.5 8.5 12.5 10 11 14 9.5 10 5.5 8.5 9.5 7z"/><path d="M17.8 14.6l.8 2.1 2.1.8-2.1.8-.8 2.1-.8-2.1-2.1-.8 2.1-.8z"/></>,
  folder: <path d="M3 7a2 2 0 012-2h3.8l2 2H19a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>,
  eye: <><path d="M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12 18 17.5 12 17.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.6"/></>,
  pencil: <><path d="M4 20h4.2L19.5 8.7a2 2 0 000-2.8l-1.4-1.4a2 2 0 00-2.8 0L4 15.8z"/><path d="M14.5 5.5l4 4"/></>,
  download: <><path d="M12 4v10.5M8 11l4 4 4-4"/><path d="M5 19.5h14"/></>,
  activity: <path d="M3 12.5h3.6L10 5.5l4 13 3.4-6H21"/>,
  file: <><path d="M14 3H7.5A1.5 1.5 0 006 4.5v15A1.5 1.5 0 007.5 21h9a1.5 1.5 0 001.5-1.5V7z"/><path d="M14 3v4h4"/><path d="M9 13h6M9 16.5h4"/></>,
  'circle-dot': <><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2.6" fill="currentColor" stroke="none"/></>,
  database: <><ellipse cx="12" cy="6" rx="7.5" ry="3"/><path d="M4.5 6v12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V6"/><path d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3"/></>,
  'loader': <path d="M12 3.5a8.5 8.5 0 108.5 8.5"/>,
  'pause-circle': <><circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/></>,
  'check-circle': <><circle cx="12" cy="12" r="9"/><path d="M8 12.4l2.6 2.6L16 9.6"/></>,
  'x-circle': <><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5l5 5M14.5 9.5l-5 5"/></>,
  upload: <><path d="M12 16V4.5"/><path d="M7.5 9L12 4.5 16.5 9"/><path d="M4 16v2.5A1.5 1.5 0 005.5 20h13a1.5 1.5 0 001.5-1.5V16"/></>,
  'chevron-up': <path d="M5 15l7-7 7 7"/>,
  'shield-off': <><path d="M12 3l7.5 3v6.2c0 4.6-3.2 7.7-7.5 9.3-4.3-1.6-7.5-4.7-7.5-9.3V6z"/><path d="M9.5 9.5l5 5M14.5 9.5l-5 5"/></>,
  'user-check': <><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19.5c0-2.8 2.5-4.6 5.5-4.6 1 0 1.9.2 2.7.6"/><path d="M15 17.5l2 2 4-4.5"/></>,
  'rotate-ccw': <><path d="M4 12a8 8 0 108-8 8 8 0 00-6.6 3.5"/><path d="M3.5 4v4.5H8"/></>,
  globe: <><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/><path d="M12 3.5c2.2 2.4 3.3 5.4 3.3 8.5s-1.1 6.1-3.3 8.5c-2.2-2.4-3.3-5.4-3.3-8.5S9.8 5.9 12 3.5z"/></>,
};

export default function Icon({name, size = 16, className = '', strokeWidth = 1.75, title}) {
  const glyph = PATHS[name];
  if (!glyph) return null;
  return <svg className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
    aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}>
    {title && <title>{title}</title>}
    {glyph}
  </svg>;
}

export const ICON_NAMES = Object.keys(PATHS);

import React from 'react';

export const ROLE_NAMES = {
  'product-analyst': '产品分析师',
  'product-leader': '产品负责人',
  'ux-agent': '体验设计师',
  'product-expert': '产品专家',
  'architecture-expert': '架构专家',
  'expert-leader': '专家负责人',
  'engineering-leader': '研发负责人',
  backend: '后端开发',
  testing: '测试工程师',
  'code-review': '代码审查',
  'security-expert': '安全专家',
  frontend: '前端开发',
  devops: '部署运维',
};

export const DEPARTMENT_NAMES = {
  product: '产品团队',
  expert: '专家团队',
  engineering: '研发团队',
  security: '安全审查',
};

const PALETTES = {
  'product-analyst': ['#e8f2ff', '#246b9e'],
  'product-leader': ['#e9e7ff', '#6656b8'],
  'ux-agent': ['#fff0ed', '#bd654f'],
  'product-expert': ['#e5f4ef', '#28785f'],
  'architecture-expert': ['#eaf0f8', '#45647f'],
  'expert-leader': ['#f1ecff', '#7459a8'],
  'engineering-leader': ['#e6f2f1', '#27766f'],
  backend: ['#e7f0fb', '#356b9b'],
  testing: ['#edf5df', '#66803c'],
  'code-review': ['#fff4dc', '#98732e'],
  'security-expert': ['#f8e9ed', '#9a4d63'],
  frontend: ['#e9f3fa', '#367c99'],
  devops: ['#eceef8', '#586b9b'],
};

function Icon({role}) {
  const common = {fill: 'none', stroke: 'currentColor', strokeWidth: 2.2, strokeLinecap: 'round', strokeLinejoin: 'round'};
  const icons = {
    'product-analyst': <><path d="M17 43V30M25 43V22M33 43V27M41 43V17"/><path d="M14 46h31"/></>,
    'product-leader': <><path d="M19 48V15"/><path d="M20 17h23l-5 8 5 8H20"/><circle cx="19" cy="13" r="2"/></>,
    'ux-agent': <><path d="M17 43l4-12L39 13l6 6-18 18-10 6z"/><path d="M21 31l6 6M17 43l10-6"/></>,
    'product-expert': <><circle cx="32" cy="30" r="16"/><path d="M24 30l6 6 11-13"/></>,
    'architecture-expert': <><path d="M32 12l15 8v17l-15 9-15-9V20l15-8z"/><path d="M17 20l15 9 15-9M32 29v17"/></>,
    'expert-leader': <><circle cx="32" cy="30" r="17"/><path d="M38 21l-4 13-12 5 4-14 12-4z"/><circle cx="32" cy="30" r="2"/></>,
    'engineering-leader': <><circle cx="20" cy="18" r="4"/><circle cx="44" cy="18" r="4"/><circle cx="32" cy="44" r="4"/><path d="M20 22v7l12 9 12-9v-7"/></>,
    backend: <><rect x="15" y="14" width="34" height="13" rx="3"/><rect x="15" y="34" width="34" height="13" rx="3"/><path d="M21 20h2M21 40h2M28 20h13M28 40h13"/></>,
    testing: <><path d="M26 13h12M29 13v14L18 44c-1 3 1 4 4 4h20c3 0 5-2 3-5L35 27V13"/><path d="M24 36h16M28 32l4 4 7-8"/></>,
    'code-review': <><circle cx="28" cy="28" r="13"/><path d="M38 38l10 10M22 28l4 4 8-9"/></>,
    'security-expert': <><path d="M32 12l15 6v12c0 10-6 16-15 20-9-4-15-10-15-20V18l15-6z"/><path d="M25 31l5 5 10-12"/></>,
    frontend: <><rect x="12" y="14" width="40" height="29" rx="3"/><path d="M24 49h16M32 43v6M25 23l-6 6 6 6M39 23l6 6-6 6M35 21l-6 15"/></>,
    devops: <><path d="M25 22c-8-8-18 4-9 11s14 2 19-5 10-11 15-5-1 17-9 10-12-9-16-11z"/><path d="M27 25l5 5M37 34l5 5"/></>,
  };
  return <g {...common}>{icons[role] || icons['product-expert']}</g>;
}

export default function RoleAvatar({role, size = 'normal'}) {
  const [background, color] = PALETTES[role] || PALETTES['product-expert'];
  const name = ROLE_NAMES[role] || role;
  return <svg className={`role-avatar role-avatar-${size}`} viewBox="0 0 64 64" role="img" aria-label={name}>
    <title>{name}</title>
    <rect width="64" height="64" rx="18" fill={background}/>
    <circle cx="49" cy="13" r="9" fill={color} opacity=".08"/>
    <g style={{color}}><Icon role={role}/></g>
  </svg>;
}

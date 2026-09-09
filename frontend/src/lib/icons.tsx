/* eslint-disable react-refresh/only-export-components */
import type { ReactNode, SVGProps } from 'react';
import { NEED_ICONS, type NeedType } from './types';

const stroke: SVGProps<SVGSVGElement> = {
  fill: 'none',
  stroke: 'currentColor',
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

function Svg({ children, size = 16, sw = 1.9, ...rest }: SVGProps<SVGSVGElement> & { size?: number; sw?: number; children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...stroke} strokeWidth={sw} aria-hidden {...rest}>
      {children}
    </svg>
  );
}

export const Ico = {
  chev: (
    <Svg size={16} sw={2.2}>
      <polyline points="6 9 12 15 18 9" />
    </Svg>
  ),
  pencil: (
    <Svg size={15}>
      <path d="M15.2 4.6l4.2 4.2" />
      <path d="M17.4 2.4a2 2 0 0 1 2.8 0l1.4 1.4a2 2 0 0 1 0 2.8L8.4 20.8 3 21.6l.8-5.4z" />
    </Svg>
  ),
  eye: (
    <Svg size={16}>
      <path d="M2.5 12s3.4-6.5 9.5-6.5S21.5 12 21.5 12 18.1 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="2.6" />
    </Svg>
  ),
  check: (
    <Svg size={16} sw={2.4}>
      <polyline points="4 12.5 9.5 18 20 6.5" />
    </Svg>
  ),
  close: (
    <Svg size={15} sw={2.2} strokeLinejoin="miter">
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  ),
  play: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M8 5.5v13l11-6.5z" />
    </svg>
  ),
  pause: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <rect x="6" y="5" width="4.5" height="14" rx="1" />
      <rect x="13.5" y="5" width="4.5" height="14" rx="1" />
    </svg>
  ),
  print: (
    <Svg size={15}>
      <path d="M7 8V4h10v4" />
      <rect x="6" y="13" width="12" height="7" rx="1" />
      <path d="M6 12H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v1a2 2 0 0 1-2 2h-1" />
    </Svg>
  ),
  share: (
    <Svg size={16}>
      <circle cx="6" cy="12" r="2.4" fill="currentColor" stroke="none" />
      <circle cx="18" cy="5.5" r="2.4" fill="currentColor" stroke="none" />
      <circle cx="18" cy="18.5" r="2.4" fill="currentColor" stroke="none" />
      <path d="M8.2 10.8 15.8 6.7M8.2 13.2 15.8 17.3" />
    </Svg>
  ),
  info: (
    <Svg size={15} strokeLinejoin="miter">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5" strokeLinecap="round" />
      <circle cx="12" cy="7.6" r="1" fill="currentColor" stroke="none" />
    </Svg>
  ),
  up: (
    <Svg size={14} sw={2.4}>
      <path d="M12 19V5" />
      <polyline points="5.5 11.5 12 5 18.5 11.5" />
    </Svg>
  ),
  thumbUp: (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#12A150" strokeWidth="1.8" strokeLinejoin="round" aria-hidden>
      <path d="M7 10v10H4V10z" />
      <path d="M7 10l4-6a2 2 0 0 1 3 2l-.8 4H19a2 2 0 0 1 2 2.4l-1.3 5.2A2 2 0 0 1 17.8 20H7z" />
    </svg>
  ),
  thumbDn: (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#E5484D" strokeWidth="1.8" strokeLinejoin="round" aria-hidden>
      <path d="M17 14V4h3v10z" />
      <path d="M17 14l-4 6a2 2 0 0 1-3-2l.8-4H5a2 2 0 0 1-2-2.4l1.3-5.2A2 2 0 0 1 6.2 4H17z" />
    </svg>
  ),
  mic: (
    <Svg size={18}>
      <rect x="9" y="2.5" width="6" height="12" rx="3" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0" />
      <path d="M12 18v3.6" />
    </Svg>
  ),
  stop: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <rect x="6.5" y="6.5" width="11" height="11" rx="2.5" />
    </svg>
  ),
  upFile: (
    <Svg size={21} sw={1.8}>
      <path d="M12 16.5V4.5" />
      <polyline points="7 9.5 12 4.5 17 9.5" />
      <path d="M4.5 15.5v2.8a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-2.8" />
    </Svg>
  ),
  file: (
    <Svg size={21} sw={1.8}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <polyline points="14 3 14 8 19 8" />
      <path d="M8.5 13h7M8.5 16.5h4.5" />
    </Svg>
  ),
  wand: (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M11 2.5l1.5 3.8 3.8 1.5-3.8 1.5L11 13.1 9.5 9.3 5.7 7.8l3.8-1.5zM18.5 12l.9 2.2 2.2.9-2.2.9-.9 2.2-.9-2.2-2.2-.9 2.2-.9zM5 15l.8 1.9 1.9.8-1.9.8L5 20.4l-.8-1.9-1.9-.8 1.9-.8z" />
    </svg>
  ),
  chat: (
    <Svg size={17}>
      <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9.5 9.5 0 0 1-2.9-.4L3 21l1.6-4.6A8.3 8.3 0 0 1 3.6 11.5a8.4 8.4 0 0 1 9-8.4 8.4 8.4 0 0 1 8.4 8.4z" />
    </Svg>
  ),
  sliders: (
    <Svg size={17} strokeLinejoin="miter">
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
      <circle cx="16" cy="7" r="2.2" />
      <circle cx="10" cy="17" r="2.2" />
    </Svg>
  ),
};

const PATHS: Record<string, ReactNode> = {
  shield: <path d="M12 3.2 19.4 6v5.6c0 4.5-3.1 7.6-7.4 9.2C8 19.2 4.6 16.1 4.6 11.6V6z" />,
  heart: <path d="M12 20s-7.2-4.6-7.2-9.5A3.9 3.9 0 0 1 12 8.1a3.9 3.9 0 0 1 7.2 2.4C19.2 15.4 12 20 12 20z" />,
  beach: (
    <>
      <path d="M4.4 12.2c.4-4.2 3.6-7.4 7.6-7.4s7.2 3.2 7.6 7.4H4.4z" />
      <path d="M12 4.8 8.2 12.2M12 4.8l3.8 7.4M12 4.8V12.2" />
      <path d="M12 12.2v7.2" />
      <path d="M8.2 20.2c1.2-1.4 2.4-2 3.8-2s2.6.6 3.8 2" />
    </>
  ),
  target: (
    <>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="4.6" />
      <circle cx="12" cy="12" r="1.3" />
    </>
  ),
  money: (
    <>
      <path d="M12 3.6v16.8" />
      <path d="M16 8.2h-5.6a2.6 2.6 0 0 0 0 5.2h3.2a2.6 2.6 0 0 1 0 5.2H8" />
    </>
  ),
  house: (
    <>
      <path d="M3.8 11 12 4.2 20.2 11v9.2H3.8z" />
      <path d="M9.8 20.2v-5.6h4.4v5.6" />
    </>
  ),
  cap: (
    <>
      <path d="M2 8.4 12 4.2l10 4.2-10 4.2z" />
      <path d="M6.2 10.6v4.1c0 1.5 2.6 2.8 5.8 2.8s5.8-1.3 5.8-2.8v-4.1" />
    </>
  ),
  cross: <path d="M12 4.5v15M4.5 12h15" />,
  wheel: (
    <>
      <circle cx="11" cy="16" r="5" />
      <path d="M11 11V5.5M11 8h5.5M16 11l2.5 5.5h2" />
    </>
  ),
  hospital: (
    <>
      <path d="M5 21V7.6L12 3.4l7 4.2V21" />
      <path d="M9.4 21v-5.2h5.2V21" />
      <path d="M12 8.4v4M10 10.4h4" />
    </>
  ),
  bandage: (
    <>
      <path d="M8.1 15.9 15.9 8.1a2.5 2.5 0 0 1 3.5 3.5L11.6 19.4a2.5 2.5 0 1 1-3.5-3.5z" />
      <path d="M10.4 13.6h.02M12 12h.02M13.6 10.4h.02" />
    </>
  ),
  bolt: <path d="M13.5 3 5.5 13.5h5.2L10 21l8-10.5h-5.2z" />,
  care: (
    <>
      <path d="M12 16.6S7.4 13.8 7.4 11a2.6 2.6 0 0 1 4.6-1.6A2.6 2.6 0 0 1 16.6 11c0 2.8-4.6 5.6-4.6 5.6z" />
      <path d="M4.5 20.2h15" />
    </>
  ),
  rings: (
    <>
      <circle cx="9.2" cy="14" r="5" />
      <circle cx="15.4" cy="14" r="5" />
      <path d="M9.2 4.6h5.4" />
    </>
  ),
  baby: (
    <>
      <circle cx="12" cy="7.4" r="3.4" />
      <path d="M6.6 20.4c0-3.6 2.4-6 5.4-6s5.4 2.4 5.4 6" />
    </>
  ),
  cart: (
    <>
      <path d="M4 6.6h16v11.8H4z" />
      <path d="M4 10.8h16M12 10.8v7.6" />
    </>
  ),
  crash: (
    <>
      <path d="M3.4 6.6 9 13l3.2-3 4.6 5.2" />
      <path d="M20.6 10.4v5.2h-5.2" />
    </>
  ),
  flame: (
    <>
      <path d="M12 20.4V4.6" />
      <path d="M6.2 10.4 12 4.6l5.8 5.8" />
    </>
  ),
  wage: (
    <>
      <path d="M3.6 7.6h14.8a2 2 0 0 1 2 2v7.6a2 2 0 0 1-2 2H3.6z" />
      <path d="M16.4 13.4h3.6" />
    </>
  ),
};

export function ObjIcon({ name, size = 14 }: { name: string; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {PATHS[name] ?? PATHS.money}
    </svg>
  );
}

/** Same emoji as the plan chart markers — use this on score cards and plan tiles. */
export function NeedIcon({ type }: { type: NeedType }) {
  return (
    <span aria-hidden className={type === 'N_RET' ? 'need-ico need-ico-ret' : 'need-ico'}>
      {NEED_ICONS[type]}
    </span>
  );
}

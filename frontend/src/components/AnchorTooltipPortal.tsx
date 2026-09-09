import {
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from 'react';
import { createPortal } from 'react-dom';

const VIEWPORT_PAD = 8;
const GAP = 6;

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

export function AnchorTooltipPortal({
  anchorRef,
  open,
  children,
  className = '',
  role = 'tooltip',
}: {
  anchorRef: RefObject<HTMLElement | null>;
  open: boolean;
  children: ReactNode;
  className?: string;
  role?: string;
}) {
  const tipRef = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState<CSSProperties>({
    position: 'fixed',
    visibility: 'hidden',
    zIndex: 9999,
  });

  useLayoutEffect(() => {
    if (!open) return;

    const update = () => {
      const anchor = anchorRef.current;
      const tip = tipRef.current;
      if (!anchor || !tip) return;

      const ar = anchor.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const maxW = vw - VIEWPORT_PAD * 2;

      tip.style.maxWidth = `${maxW}px`;
      tip.style.left = '0px';
      tip.style.top = '0px';

      const tr = tip.getBoundingClientRect();
      const width = tr.width;
      const height = tr.height;

      let left = ar.left + ar.width / 2 - width / 2;
      left = clamp(left, VIEWPORT_PAD, Math.max(VIEWPORT_PAD, vw - VIEWPORT_PAD - width));

      let top = ar.bottom + GAP;
      if (top + height > vh - VIEWPORT_PAD) {
        const above = ar.top - GAP - height;
        if (above >= VIEWPORT_PAD) top = above;
        else top = clamp(top, VIEWPORT_PAD, vh - VIEWPORT_PAD - height);
      }

      setStyle({
        position: 'fixed',
        top,
        left,
        maxWidth: maxW,
        zIndex: 9999,
        visibility: 'visible',
      });
    };

    update();
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  }, [open, children, anchorRef]);

  if (!open) return null;

  return createPortal(
    <div ref={tipRef} role={role} className={className} style={style}>
      {children}
    </div>,
    document.body,
  );
}

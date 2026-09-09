import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type RefObject,
} from 'react';
import { createPortal } from 'react-dom';
import { Ico } from '../lib/icons';

const VIEWPORT_PAD = 12;
const GAP = 12;
const HOLE_PAD = 8;
const TIP_WIDTH = 320;

export type CoachStep = {
  title: string;
  body: string;
  anchorRef: RefObject<HTMLElement | null>;
};

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

export function CoachTour({
  steps,
  enabled,
  onComplete,
}: {
  steps: CoachStep[];
  enabled: boolean;
  onComplete: () => void;
}) {
  const [host, setHost] = useState<Element | null>(null);
  const [index, setIndex] = useState<number | null>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const indexRef = useRef(index);
  indexRef.current = index;
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;
  const [hole, setHole] = useState<CSSProperties>({ visibility: 'hidden' });
  const [tip, setTip] = useState<CSSProperties>({ visibility: 'hidden' });
  const [place, setPlace] = useState<'below' | 'above'>('below');

  useEffect(() => {
    setHost(document.querySelector('.x'));
  }, []);

  useEffect(() => {
    if (!enabled) {
      setIndex(null);
      return;
    }
    if (!host || !steps.length) return;
    const id = window.requestAnimationFrame(() => setIndex(0));
    return () => window.cancelAnimationFrame(id);
  }, [host, enabled, steps.length]);

  const step = index === null ? null : steps[index];

  const advance = () => {
    const cur = indexRef.current;
    if (cur === null) return;
    const next = cur + 1;
    if (next >= steps.length) {
      setIndex(null);
      onCompleteRef.current();
      return;
    }
    setHole({ visibility: 'hidden' });
    setTip({ visibility: 'hidden' });
    setIndex(next);
  };

  useLayoutEffect(() => {
    if (!step) return;
    const anchor = step.anchorRef.current;
    if (!anchor) return;

    const placeTip = () => {
      const ar = anchor.getBoundingClientRect();
      if (ar.width < 2 && ar.height < 2) return;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const left = clamp(ar.left - HOLE_PAD, VIEWPORT_PAD, vw - VIEWPORT_PAD);
      const top = clamp(ar.top - HOLE_PAD, VIEWPORT_PAD, vh - VIEWPORT_PAD);
      const width = Math.min(ar.width + HOLE_PAD * 2, vw - left - VIEWPORT_PAD);
      const height = Math.min(ar.height + HOLE_PAD * 2, vh - top - VIEWPORT_PAD);
      setHole({
        position: 'fixed',
        top,
        left,
        width,
        height,
        visibility: 'visible',
      });

      const bubble = tipRef.current;
      if (!bubble) return;
      const mobile = vw <= 700;
      if (mobile) {
        setPlace('above');
        setTip({
          position: 'fixed',
          left: VIEWPORT_PAD,
          right: VIEWPORT_PAD,
          bottom: VIEWPORT_PAD,
          top: 'auto',
          width: 'auto',
          maxWidth: 'none',
          visibility: 'visible',
        });
        return;
      }

      const maxW = Math.min(TIP_WIDTH, vw - VIEWPORT_PAD * 2);
      bubble.style.width = `${maxW}px`;
      const tr = bubble.getBoundingClientRect();
      const anchorMid = ar.left + ar.width / 2;
      let tipLeft = anchorMid - tr.width / 2;
      tipLeft = clamp(tipLeft, VIEWPORT_PAD, Math.max(VIEWPORT_PAD, vw - VIEWPORT_PAD - tr.width));
      const caretX = clamp(anchorMid - tipLeft, 16, Math.max(16, maxW - 16));

      const below = top + height + GAP;
      const above = top - GAP - tr.height;
      const useAbove = below + tr.height > vh - VIEWPORT_PAD && above >= VIEWPORT_PAD;
      setPlace(useAbove ? 'above' : 'below');
      setTip({
        position: 'fixed',
        top: useAbove ? Math.max(VIEWPORT_PAD, above) : below,
        left: tipLeft,
        width: maxW,
        visibility: 'visible',
        ['--coach-caret-x' as string]: `${caretX}px`,
      });
    };

    const rect = anchor.getBoundingClientRect();
    if (rect.bottom > window.innerHeight - 24 || rect.top < 72) {
      anchor.scrollIntoView({ block: 'center', inline: 'nearest' });
    }
    placeTip();
    const main = document.getElementById('main');
    const ro = new ResizeObserver(placeTip);
    ro.observe(anchor);
    window.addEventListener('resize', placeTip);
    main?.addEventListener('scroll', placeTip, { passive: true });
    window.addEventListener('scroll', placeTip, true);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', placeTip);
      main?.removeEventListener('scroll', placeTip);
      window.removeEventListener('scroll', placeTip, true);
    };
  }, [step]);

  useEffect(() => {
    if (index === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        advance();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [index]);

  if (index === null || !step || !host) return null;

  const last = index === steps.length - 1;

  return createPortal(
    <div className="x-coach" onClick={advance} role="presentation">
      <div className="x-coach-spot" style={hole} />
      <div
        ref={tipRef}
        className={`x-coach-tip ${place}`}
        style={tip}
        role="dialog"
        aria-modal="true"
        aria-labelledby="x-coach-title"
        aria-describedby="x-coach-body"
        onClick={e => e.stopPropagation()}
      >
        <button className="cl" type="button" aria-label="Close" onClick={advance}>
          {Ico.close}
        </button>
        <b id="x-coach-title">{step.title}</b>
        <p id="x-coach-body">{step.body}</p>
        <div className="x-coach-foot">
          <span className="x-coach-dots" aria-hidden>
            {steps.map((_, i) => (
              <i key={i} className={i === index ? 'on' : ''} />
            ))}
          </span>
          <span className="x-coach-n">
            {index + 1} of {steps.length}
          </span>
          <span className="sp" />
          <button className="x-btn p sm" type="button" onClick={advance}>
            {last ? 'Got it' : 'Next'}
          </button>
        </div>
      </div>
    </div>,
    host,
  );
}

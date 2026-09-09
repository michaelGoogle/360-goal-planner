import { useRef, useState } from 'react';
import { AnchorTooltipPortal } from './AnchorTooltipPortal';

/** Small (i) control with a dark hover/focus tooltip — same as Scenario Visualizer. */
export function InfoTip({
  text,
  className = '',
}: {
  text: string;
  className?: string;
}) {
  const anchorRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);

  return (
    <span
      ref={anchorRef}
      className={`relative inline-flex normal-case tracking-normal font-normal ${className}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={e => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      <button
        type="button"
        className="inline-flex items-center justify-center w-4 h-4 rounded-full border border-[#9aa6c4] text-xs leading-none text-[#6b78a0] bg-transparent cursor-help hover:border-orange-400 hover:text-orange-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400/60"
        aria-label={text}
        onClick={e => e.preventDefault()}
        onMouseDown={e => e.preventDefault()}
      >
        i
      </button>
      <AnchorTooltipPortal
        anchorRef={anchorRef}
        open={open}
        className="pointer-events-none w-72 rounded-md border border-[#26314f] bg-[#0a0f1f] px-2.5 py-2 text-sm leading-snug text-[#c5cce0] shadow-lg"
      >
        {text}
      </AnchorTooltipPortal>
    </span>
  );
}

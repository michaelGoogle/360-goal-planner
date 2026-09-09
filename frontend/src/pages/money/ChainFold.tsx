import type { KeyboardEvent, ReactNode, RefObject } from 'react';
import { Tip } from '../../components/ui';
import { Ico } from '../../lib/icons';
import { money } from '../../lib/types';

export function ChainFold({
  title,
  tag,
  unit,
  open,
  onToggle,
  chevronRef,
  children,
}: {
  title: string;
  tag: ReactNode;
  unit: string;
  open: boolean;
  onToggle: () => void;
  chevronRef?: RefObject<HTMLSpanElement | null>;
  children: ReactNode;
}) {
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onToggle();
    }
  };
  return (
    <div className={`x-chain fold ${open ? 'open' : ''}`}>
      <div
        className="sep"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-label={`${open ? 'Collapse' : 'Expand'} ${title}`}
        onClick={onToggle}
        onKeyDown={onKey}
      >
        <span>{title}</span>
        {tag}
        <em className="u">{unit}</em>
        <span ref={chevronRef} className="x-coach-hit">
          <span className="cv">{Ico.chev}</span>
        </span>
      </div>
      {children}
    </div>
  );
}

export function MoneyRow({
  label,
  value,
  tag,
  tipId,
  editId,
  tip,
  edit,
  open,
  onTip,
}: {
  label: string;
  value: number;
  tag: ReactNode;
  tipId: string;
  editId: string;
  tip: ReactNode;
  edit: ReactNode;
  open: string | null;
  onTip: (id: string) => void;
}) {
  return (
    <div className="t">
      <span>
        {label}
        <Tip id={tipId} open={open} onToggle={onTip} right>
          {tip}
        </Tip>
        {tag}
      </span>
      <b>{money(value)}</b>
      <Tip id={editId} open={open} onToggle={onTip} edit right wide>
        {edit}
      </Tip>
    </div>
  );
}

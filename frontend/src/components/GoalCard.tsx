import { useState, type ReactNode } from 'react';
import { Switch } from './ui';
import { Ico, NeedIcon } from '../lib/icons';
import { fillNeedEdit, needCardGap, needCardHave, patchNeedInputs } from '../lib/needEdit';
import {
  EXTRA_NEED_ICONS,
  EXTRA_NEEDS,
  money,
  NEED_META,
  NEED_TYPES,
  type ExtraNeed,
  type GpSession,
  type NeedRow,
  type NeedType,
} from '../lib/types';
import { bannerFor, GoalEditor } from './GoalEditor';

export const NEED_GROUPS: Record<'p' | 'w', { title: string; blurb: string }> = {
  p: { title: 'Wealth protection', blurb: 'Cover that absorbs the event it answers' },
  w: { title: 'Wealth growth', blurb: 'What builds the balance the goals are paid from' },
};

export function needsInGroup(session: GpSession, group: 'p' | 'w') {
  return session.needs
    .filter(n => n.enabled && NEED_META[n.type].group === group)
    .sort((a, b) => NEED_TYPES.indexOf(a.type) - NEED_TYPES.indexOf(b.type));
}

export function GoalCard({
  session,
  type,
  onToggle,
  onChange,
  startOpen = false,
  onAddPlan,
}: {
  session: GpSession;
  type: NeedType;
  onToggle: () => void;
  onChange: (p: Partial<GpSession>) => void;
  startOpen?: boolean;
  onAddPlan?: () => void;
}) {
  const [edit, setEdit] = useState(startOpen);
  const meta = NEED_META[type];
  const n = session.needs.find(x => x.type === type);
  if (!n) return null;
  const e = fillNeedEdit(session, n);
  const have = needCardHave(session, n);
  const req = n.needAmount || 0;
  const g = needCardGap(session, n);
  const pct = req ? Math.max(have > 0 ? 2 : 0, Math.min(100, (have / req) * 100)) : 100;
  const by =
    !edit && meta.group === 'w'
      ? type === 'N_RET'
        ? 'age ' + e.retAge
        : e.targetYear
          ? 'by ' + e.targetYear
          : ''
      : '';
  const why = edit ? bannerFor(session, type, e) : null;

  const patch = (p: Partial<NeedRow>) => {
    onChange(patchNeedInputs(session, type, p));
  };

  const toggleEdit = () => {
    if (!edit) patch({});
    setEdit(open => !open);
  };

  return (
    <div className={`gc on${edit ? ' open' : ''}`}>
      <div className="gc-h">
        <button
          className="gc-exp"
          type="button"
          aria-expanded={edit}
          aria-label={edit ? `Collapse ${meta.label}` : `Adjust ${meta.label}`}
          onClick={toggleEdit}
        >
          <span className="gc-ic" style={{ borderColor: meta.color }}>
            <NeedIcon type={type} />
          </span>
          <b>{meta.label}</b>
        </button>
        {by ? <span className="gc-by">{by}</span> : null}
        <button
          className="gc-x"
          type="button"
          title={edit ? 'Close' : 'Adjust'}
          aria-label={edit ? `Collapse ${meta.label}` : `Adjust ${meta.label}`}
          aria-expanded={edit}
          onClick={toggleEdit}
        >
          {edit ? Ico.chev : Ico.pencil}
        </button>
        <Switch on={n.enabled} label={meta.label} onClick={onToggle} />
      </div>
      {why ? (
        <div className="gc-why">
          {Ico.wand}
          <span>{why}</span>
        </div>
      ) : null}
      {edit ? (
        <div className="gc-e">
          <GoalEditor session={session} type={type} n={n} e={e} onPatch={patch} />
        </div>
      ) : null}
      <div className="gc-b">
        <div className="gc-l">
          <span>{meta.lo}</span>
          <b>{meta.hi}</b>
        </div>
        <div className="gc-bar">
          <i style={{ width: `${pct}%` }} />
        </div>
        <div className="gc-v">
          <span>{money(have)}</span>
          <b>{money(req)}</b>
        </div>
        <div className={`gc-row gc-sf ${g > 0 ? 'no' : 'ok'}`}>
          <span>{g > 0 ? 'Shortfall' : 'Status'}</span>
          <b>{g > 0 ? money(g) : 'Fully funded'}</b>
        </div>
        {g > 0 && onAddPlan ? (
          <div className="gc-add">
            <button
              className="x-addb"
              type="button"
              onClick={e => {
                e.stopPropagation();
                onAddPlan();
              }}
            >
              + Add a plan
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function NeedGroups({
  session,
  onChange,
  onToggleNeed,
  onToggleExtra,
  onAddPlan,
  protectLead,
  growthLead,
}: {
  session: GpSession;
  onChange: (p: Partial<GpSession>) => void;
  onToggleNeed: (t: NeedType) => void;
  onToggleExtra?: (k: ExtraNeed) => void;
  onAddPlan?: (t: NeedType) => void;
  protectLead?: ReactNode;
  growthLead?: ReactNode;
}) {
  const col = (group: 'p' | 'w', lead?: ReactNode) => {
    const meta = NEED_GROUPS[group];
    const extras =
      group === 'p' && onToggleExtra
        ? EXTRA_NEEDS.filter(x => session.extraNeeds.includes(x.k)).map(x => (
            <div key={x.k} className="gc on">
              <div className="gc-h">
                <span className="gc-ic" style={{ borderColor: x.color }}>
                  <span className="need-ico">{EXTRA_NEED_ICONS[x.k]}</span>
                </span>
                <b>{x.label}</b>
                <Switch on label={x.label} onClick={() => onToggleExtra(x.k)} />
              </div>
            </div>
          ))
        : [];
    return (
      <div className="x-prodg">
        <div className="x-prodh">
          <b>{meta.title}</b>
          <span>{meta.blurb}</span>
        </div>
        <div className="x-prodl">
          {lead}
          {extras}
          {needsInGroup(session, group).map(n => (
            <GoalCard
              key={n.type}
              session={session}
              type={n.type}
              onToggle={() => onToggleNeed(n.type)}
              onChange={onChange}
              onAddPlan={onAddPlan ? () => onAddPlan(n.type) : undefined}
            />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="x-need-cols">
      {col('p', protectLead)}
      {col('w', growthLead)}
    </div>
  );
}

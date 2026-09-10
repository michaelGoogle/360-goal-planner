import { Switch } from '../../components/ui';
import { Ico } from '../../lib/icons';
import { clampEvent, hydrateStressEvents, STRESS_BY_ID, type GpEvent } from '../../lib/stressEvents';
import {
  EXTRA_NEEDS,
  money,
  NEED_META,
  needGap,
  sessionAge,
  type ExtraNeed,
  type GpSession,
  type NeedType,
} from '../../lib/types';
import { AddPlanPanel } from './CoverCard';
import { EventCard } from './EventCard';
import { planIncluded, togglePlanPatch } from '../../lib/planProducts';

type Panel = 'goals' | 'events' | 'plans';

export function PlanModals({
  panel,
  focusId,
  planNeed,
  session,
  onChange,
  onToggleNeed,
  onToggleExtra,
  onToggleEvent,
  onEvents,
}: {
  panel: Panel | null;
  focusId: string | null;
  planNeed: NeedType | null;
  session: GpSession;
  onChange: (p: Partial<GpSession>) => void;
  onToggleNeed: (t: NeedType) => void;
  onToggleExtra: (k: ExtraNeed) => void;
  onToggleEvent: (id: string) => void;
  onEvents: (events: GpEvent[]) => void;
}) {
  if (!panel) return null;
  const title =
    panel === 'goals' ? 'Your goals' : panel === 'plans' ? 'Add a plan' : 'Unforeseen events';
  const blurb =
    panel === 'goals'
      ? 'Switch one off and watch the projection re-run — that is what the goal is costing you.'
      : panel === 'plans'
        ? planNeed
          ? `Sized to the ${NEED_META[planNeed].label} shortfall on Your score. Switch it on and it joins Suggested plan.`
          : 'Extra cover that can close a shortfall this plan does not yet answer.'
        : 'Apply a what-if and see how the plan holds up. It predicts nothing; it asks what if.';
  return (
    <div className="x-modal" role="dialog" aria-modal="true" aria-label={title}>
      <div className="x-modal-bd" onClick={() => onChange({ tip: null })} />
      <div className="x-modal-w">
        <div className="x-modal-h">
          <span className="t">
            <b>{title}</b>
            <span>{blurb}</span>
          </span>
          <button className="x-modal-x" type="button" aria-label="Close" onClick={() => onChange({ tip: null })}>
            {Ico.close}
          </button>
        </div>
        <div className="x-modal-b">
          {panel === 'goals' ? (
            <div className="card lp">
              <div className="lpb">
                {session.needs.map(n => (
                  <label
                    key={n.type}
                    className="flex"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '8px 0',
                      background: focusId === n.type ? '#edf2ff' : undefined,
                      borderRadius: 8,
                    }}
                  >
                    <Switch on={n.enabled} label={NEED_META[n.type].label} onClick={() => onToggleNeed(n.type)} />
                    <span style={{ flex: 1 }}>{NEED_META[n.type].label}</span>
                    <span className="x-sm">{money(needGap(session, n))} short</span>
                  </label>
                ))}
                {EXTRA_NEEDS.map(x => (
                  <label key={x.k} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0' }}>
                    <Switch
                      on={session.extraNeeds.includes(x.k)}
                      label={x.label}
                      onClick={() => onToggleExtra(x.k)}
                    />
                    <span>{x.label}</span>
                  </label>
                ))}
              </div>
            </div>
          ) : null}
          {panel === 'plans' ? (
            <div className="card lp">
              <div className="lpb">
                {planNeed ? (
                  <AddPlanPanel
                    session={session}
                    type={planNeed}
                    on={planIncluded(session, planNeed)}
                    onToggle={() => onChange(togglePlanPatch(session, planNeed))}
                  />
                ) : (
                  <p className="x-sm">No matching shortfall to close.</p>
                )}
              </div>
            </div>
          ) : null}
          {panel === 'events' ? (
            <EventsList
              session={session}
              focusId={focusId}
              onToggleEvent={onToggleEvent}
              onEvents={onEvents}
            />
          ) : null}
        </div>
        <div className="x-modal-f">
          <button className="x-btn p" type="button" onClick={() => onChange({ tip: null })}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

function EventsList({
  session,
  focusId,
  onToggleEvent,
  onEvents,
}: {
  session: GpSession;
  focusId: string | null;
  onToggleEvent: (id: string) => void;
  onEvents: (events: GpEvent[]) => void;
}) {
  const events = hydrateStressEvents(session.events);
  const startAge = sessionAge(session) || 40;
  const last = Math.max(1, (session.endAge || 85) - startAge);
  const startYear = new Date().getFullYear();
  const on = events.filter(e => e.on);
  const off = events.filter(e => !e.on);
  const patch = (id: string, p: Partial<GpEvent>) => {
    onEvents(events.map(e => (e.id === id ? clampEvent({ ...e, ...p }, last) : e)));
  };
  const group = (g: 'w' | 'p', title: string) => {
    const rows = off.filter(e => STRESS_BY_ID[e.id]?.group === g);
    if (!rows.length) return null;
    return (
      <div key={g}>
        <div className="lp-cat">
          {title}
          <span>{rows.length}</span>
        </div>
        {rows.map(ev => (
          <EventCard
            key={ev.id}
            ev={ev}
            startAge={startAge}
            last={last}
            startYear={startYear}
            startOpen={focusId === ev.id}
            onToggle={() => onToggleEvent(ev.id)}
            onPatch={p => patch(ev.id, p)}
          />
        ))}
      </div>
    );
  };
  return (
    <div className="card lp">
      <div className="lpb">
        {on.length ? (
          <>
            <div className="lp-on">
              {on.length} in your plan
            </div>
            {on.map(ev => (
              <EventCard
                key={ev.id}
                ev={ev}
                startAge={startAge}
                last={last}
                startYear={startYear}
                startOpen
                onToggle={() => onToggleEvent(ev.id)}
                onPatch={p => patch(ev.id, p)}
              />
            ))}
            {off.length ? <div className="lp-div" /> : null}
          </>
        ) : null}
        {group('w', 'Wealth accumulation')}
        {group('p', 'Wealth protection')}
      </div>
    </div>
  );
}

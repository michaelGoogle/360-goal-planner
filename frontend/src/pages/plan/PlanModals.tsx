import { RateSlider, Switch } from '../../components/ui';
import { Ico } from '../../lib/icons';
import { hydrateStressEvents, STRESS_BY_ID, type GpEvent } from '../../lib/stressEvents';
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

type Panel = 'goals' | 'events' | 'assume' | 'plans';

export function PlanModals({
  panel,
  focusId,
  planNeed,
  session,
  nAssume,
  onChange,
  onToggleNeed,
  onToggleExtra,
  onToggleEvent,
  onEvents,
  onAssume,
  onAssumeReset,
}: {
  panel: Panel | null;
  focusId: string | null;
  planNeed: NeedType | null;
  session: GpSession;
  nAssume: number;
  onChange: (p: Partial<GpSession>) => void;
  onToggleNeed: (t: NeedType) => void;
  onToggleExtra: (k: ExtraNeed) => void;
  onToggleEvent: (id: string) => void;
  onEvents: (events: GpEvent[]) => void;
  onAssume: (p: Partial<GpSession>) => void;
  onAssumeReset: () => void;
}) {
  if (!panel) return null;
  return (
    <div
      className="x-modal"
      role="dialog"
      aria-modal="true"
      aria-label={
        panel === 'goals'
          ? 'Your goals'
          : panel === 'events'
            ? 'Unforeseen events'
            : panel === 'plans'
              ? 'Add a plan'
              : 'Assumptions'
      }
    >
      <div className="x-modal-bd" onClick={() => onChange({ tip: null })} />
      <div className="x-modal-w">
        <div className="x-modal-h">
          <span className="t">
            <b>
              {panel === 'goals'
                ? 'Your goals'
                : panel === 'events'
                  ? 'Unforeseen events'
                  : panel === 'plans'
                    ? 'Add a plan'
                    : 'Assumptions'}
            </b>
            <span>
              {panel === 'goals'
                ? 'Switch one off and watch the projection re-run — that is what the goal is costing you.'
                : panel === 'events'
                  ? 'Apply a what-if and see how the plan holds up. It predicts nothing; it asks what if.'
                  : panel === 'plans'
                    ? planNeed
                      ? `Sized to the ${NEED_META[planNeed].label} shortfall on Your score. Switch it on and it joins Suggested plan.`
                      : 'Extra cover that can close a shortfall this plan does not yet answer.'
                    : 'The rates every figure on this page is worked out from. Move one and it all re-derives.'}
            </span>
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
          {panel === 'assume' ? (
            <div className="card lp">
              <div className="lpb">
              <div className="asg">
                <div className="asg-h">
                  <b>Economic Assumptions</b>
                </div>
                <div className="gc-e">
                  <RateSlider
                    label="Price inflation"
                    min={0}
                    max={0.1}
                    step={0.001}
                    value={session.inflationRate}
                    onChange={v => onAssume({ inflationRate: v })}
                  />
                  <RateSlider
                    label="Interest rate"
                    min={-0.03}
                    max={0.1}
                    step={0.001}
                    value={session.interestRate}
                    onChange={v => onAssume({ interestRate: v })}
                  />
                </div>
              </div>
              <div className="asg">
                <div className="asg-h">
                  <b>Growth and earnings</b>
                </div>
                <div className="gc-e">
                  <RateSlider
                    label="Income increment rate"
                    min={0}
                    max={0.1}
                    step={0.001}
                    value={session.incomeGrowthRate}
                    onChange={v => onAssume({ incomeGrowthRate: v })}
                  />
                  <RateSlider
                    label="Investment return"
                    min={0.022}
                    max={0.12}
                    step={0.001}
                    value={session.investmentReturn}
                    onChange={v => onAssume({ investmentReturn: v })}
                  />
                  <RateSlider
                    label="Return on other assets (e.g. Property)"
                    min={0.003}
                    max={0.08}
                    step={0.001}
                    value={session.assetReturn}
                    onChange={v => onAssume({ assetReturn: v })}
                  />
                </div>
              </div>
              <div className="lpfoot">
                <span>
                  {nAssume
                    ? `${nAssume} assumption${nAssume === 1 ? '' : 's'} changed`
                    : 'All assumptions at default'}
                </span>
                {nAssume ? (
                  <button className="x-btn g sm" type="button" onClick={onAssumeReset}>
                    Reset all
                  </button>
                ) : null}
              </div>
              </div>
            </div>
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

import { RateSlider } from './ui';
import { Ico } from '../lib/icons';
import type { GpSession } from '../lib/types';

export function AssumeModal({
  session,
  nAssume,
  onClose,
  onAssume,
  onAssumeReset,
}: {
  session: GpSession;
  nAssume: number;
  onClose: () => void;
  onAssume: (p: Partial<GpSession>) => void;
  onAssumeReset: () => void;
}) {
  return (
    <div className="x-modal" role="dialog" aria-modal="true" aria-label="Assumptions">
      <div className="x-modal-bd" onClick={onClose} />
      <div className="x-modal-w">
        <div className="x-modal-h">
          <span className="t">
            <b>Assumptions</b>
            <span>The rates every score and projection is worked out from. Move one and it all re-derives.</span>
          </span>
          <button className="x-modal-x" type="button" aria-label="Close" onClick={onClose}>
            {Ico.close}
          </button>
        </div>
        <div className="x-modal-b">
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
                    label="Cash / savings interest"
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
                    max={0.1}
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
        </div>
        <div className="x-modal-f">
          <button className="x-btn p" type="button" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

import { useEffect } from 'react';
import { RateSlider } from './ui';
import { Ico } from '../lib/icons';
import { NET_RETURN_PCT_MAX, NET_RETURN_PCT_MIN, NET_RETURN_TIP } from '../lib/assumptions';
import { ASSUME_CONFIG_FALLBACK, type AssumeConfig, type AssumeKey } from '../lib/config';
import { netReturnCeiling, netReturnCeilingNote } from '../lib/riskCapacity';
import type { GpSession } from '../lib/types';

/**
 * Where a rate's floor and ceiling are not the config bounds.
 *
 * Cash interest may be negative and the net-return slider is deliberately narrower
 * than the admin bound, because it is a net-of-costs rate. Everything else takes
 * its range from the published parameter version.
 */
const SLIDER_OVERRIDE: Partial<Record<AssumeKey, { min?: number; max?: number }>> = {
  interestRate: { min: -0.03, max: 0.1 },
  inflationRate: { max: 0.1 },
  loanRate: { max: 0.1 },
  incomeGrowthRate: { max: 0.1 },
  investmentReturn: { min: NET_RETURN_PCT_MIN / 100, max: NET_RETURN_PCT_MAX / 100 },
  assetReturn: { min: 0.003, max: 0.08 },
};

export function AssumeModal({
  session,
  nAssume,
  assumeConfig = ASSUME_CONFIG_FALLBACK,
  onClose,
  onAssume,
  onAssumeReset,
}: {
  session: GpSession;
  nAssume: number;
  assumeConfig?: AssumeConfig;
  onClose: () => void;
  onAssume: (p: Partial<GpSession>) => void;
  onAssumeReset: () => void;
}) {
  /** The published default unless the customer has moved this rate. */
  const rate = (k: AssumeKey): number => session[k] ?? assumeConfig[k].value;

  const range = (k: AssumeKey): { min: number; max: number } => {
    const override = SLIDER_OVERRIDE[k] ?? {};
    return {
      min: override.min ?? assumeConfig[k].min ?? 0,
      max: override.max ?? assumeConfig[k].max ?? 0.1,
    };
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

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
                    {...range('inflationRate')}
                    step={0.001}
                    value={rate('inflationRate')}
                    onChange={v => onAssume({ inflationRate: v })}
                  />
                  <RateSlider
                    label="Cash / savings interest"
                    {...range('interestRate')}
                    step={0.001}
                    value={rate('interestRate')}
                    onChange={v => onAssume({ interestRate: v })}
                  />
                  <RateSlider
                    label="Loan rate"
                    {...range('loanRate')}
                    step={0.001}
                    value={rate('loanRate')}
                    onChange={v => onAssume({ loanRate: v })}
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
                    {...range('incomeGrowthRate')}
                    step={0.001}
                    value={rate('incomeGrowthRate')}
                    onChange={v => onAssume({ incomeGrowthRate: v })}
                  />
                  <RateSlider
                    label="Net expected returns"
                    tip={NET_RETURN_TIP}
                    tipWide
                    tone="net-return"
                    {...range('investmentReturn')}
                    step={0.001}
                    value={rate('investmentReturn')}
                    ceiling={netReturnCeiling(session.riskProfile)}
                    note={netReturnCeilingNote(rate('investmentReturn'), session.riskProfile)}
                    onChange={v => onAssume({ investmentReturn: v })}
                  />
                  <RateSlider
                    label="Return on other assets (e.g. Property)"
                    {...range('assetReturn')}
                    step={0.001}
                    value={rate('assetReturn')}
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

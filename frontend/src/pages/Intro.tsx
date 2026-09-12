import { HappiUGauge } from '../components/HappiUGauge';
import { NarrBtn } from '../components/ui';

export function Intro({
  narrOn,
  narrPaused,
  onNarr,
  onStart,
}: {
  narrOn: boolean;
  narrPaused?: boolean;
  onNarr: () => void;
  onStart: () => void;
}) {
  return (
    <>
      <div className="x-band">
        <div className="k">FINPLAN360</div>
        <div className="t">Plan Your Financial Journey</div>
      </div>
      <div className="x-hero">
        <div className="x-hero-copy">
          <div className="x-h1">
            See how ready you are
            <br />
            for the life you want
          </div>
          <div className="x-lead">
            Tell us a little about yourself. FinPlan360 predicts where you stand today from people like you — unless you
            type the figures or add a statement. It then sizes the goals that actually matter — income if you could not
            work, retirement, family — and shows how far what you already have goes.
          </div>
          <div className="x-lead">
            You leave with a coverage score, the gaps behind it, and a year-by-year picture of your wealth you can
            test.
          </div>
          <div className="x-hero-cta">
            <div className="x-hero-act">
              <button className="x-cta" type="button" onClick={onStart}>
                Start my plan
              </button>
              <div className="x-hero-wow">
                <span>Your plan in 3 min.</span>
                <span className="x-hero-wow-rest">No sign up. No mobile number.</span>
              </div>
            </div>
            <NarrBtn label="Hear what you get" on={narrOn} paused={narrPaused} onClick={onNarr} />
          </div>
        </div>
        <div className="x-hero-visual">
          <div className="x-dev">
            <div className="x-phone">
              <div className="x-notch" />
              <div className="x-phone-s">
                <div className="x-phone-b">FINPLAN360</div>
                <div className="x-phone-g">
                  <HappiUGauge value={38} size={176} />
                </div>
                <div className="x-phone-h">Here is how ready you are</div>
                <div className="x-phone-p">
                  At your current rate of outgoings, an unexpected period out of work would leave you unable to keep up
                  with your expenses.
                </div>
                <div className="x-phone-cta">See what to fix first</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

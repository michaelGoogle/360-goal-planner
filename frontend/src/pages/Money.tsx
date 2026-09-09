import { useRef, useState } from 'react';
import { CoachTour } from '../components/CoachTour';
import { EDIT_HINT, TIPS } from '../lib/catalog';
import { MONEY_EDIT_TIP, MONEY_FIELD_SLIDER, moneyMax } from '../lib/needEdit';
import { assets, availableBudget, chartMoneyOut, employeeCpfMonthly, liquid, money, netWealth, takeHomeMonthly, type GpSession } from '../lib/types';
import { EqPie, Foot, GroupTag, NarrBtn, Tip } from '../components/ui';
import { Ico } from '../lib/icons';
import { ChainFold, MoneyRow } from './money/ChainFold';
import { CoverBlock } from './money/CoverBlock';
import { Explain } from './money/Explain';

export function Money({
  session,
  onChange,
  onBack,
  onReestimate,
  onScore,
  busy,
  predictError,
  narrOn,
  onNarr,
  gtTtOn,
  onGtTtComplete,
}: {
  session: GpSession;
  onChange: (p: Partial<GpSession>) => void;
  onBack: () => void;
  onReestimate: () => void;
  onScore: () => void;
  busy: boolean;
  predictError?: string | null;
  narrOn: boolean;
  onNarr: () => void;
  gtTtOn: boolean;
  onGtTtComplete: () => void;
}) {
  const [open, setOpen] = useState({ cash: false, wealth: false, cover: false });
  const toggle = (k: keyof typeof open) => setOpen(s => ({ ...s, [k]: !s[k] }));
  const sliderCap = useRef<{ key: string; max: number } | null>(null);
  const cashChevronRef = useRef<HTMLSpanElement>(null);
  const coverChevronRef = useRef<HTMLSpanElement>(null);
  const openEditKey = Object.entries(MONEY_EDIT_TIP).find(([, id]) => id === session.tip)?.[0];
  if (!openEditKey || sliderCap.current?.key !== openEditKey) sliderCap.current = null;
  const age = typeof session.age === 'number' ? session.age : 35;
  const mInc = session.incomeMonthly;
  const mExp = session.expenseMonthly;
  const cpf = employeeCpfMonthly(session);
  const takeHome = takeHomeMonthly(session);
  const sur = availableBudget(session);
  const outInclCpf = chartMoneyOut(session);
  const liq = liquid(session);
  const prop = session.property;
  const liab = session.mortgage;
  const net = netWealth(session);
  const P = session.provenance;

  const tag = (k: string) =>
    P[k] === 'doc' ? <em className="x-rtag doc">From your document</em> : P[k] === 'you' ? <em className="x-rtag you">You changed this</em> : null;

  const setMoney = (key: string, val: number) => {
    const v = Math.max(0, Math.round(val || 0));
    const moneyTouched = { ...session.moneyTouched, [key]: true as const };
    const provenance = { ...session.provenance, [key === 'budget' ? 'expense' : key]: 'you' as const };
    const patch: Partial<GpSession> = { moneyTouched, provenance };
    if (key === 'budget') patch.expenseMonthly = Math.max(0, takeHome - v);
    if (key === 'income') patch.incomeMonthly = v;
    if (key === 'expense') patch.expenseMonthly = v;
    if (key === 'savings') {
      const cur = liq;
      const r = cur > 0 ? session.cash / cur : 0.45;
      patch.cash = Math.round(v * r);
      patch.investments = v - Math.round(v * r);
    }
    if (key === 'property') patch.property = v;
    if (key === 'loans') patch.mortgage = v;
    onChange(patch);
  };

  const toggleTip = (id: string) => onChange({ tip: session.tip === id ? null : id });

  const editBody = (key: string, label: string, val: number) => {
    const spec = MONEY_FIELD_SLIDER[key];
    const computed = moneyMax(val, spec.floor);
    if (openEditKey === key && !sliderCap.current) sliderCap.current = { key, max: computed };
    const hi = openEditKey === key && sliderCap.current ? sliderCap.current.max : computed;
    const clamped = Math.min(hi, Math.max(0, val));
    const shown = spec.perMonth ? `${money(clamped)}/mo` : money(clamped);
    const capLabel = spec.perMonth ? `${money(hi)}/mo` : money(hi);
    return (
      <>
        <b>{label}</b>
        <div className="gsl" style={{ marginTop: 12 }}>
          <div className="gsl-h">
            <b>{shown}</b>
          </div>
          <input
            type="range"
            min={0}
            max={hi}
            step={spec.step}
            value={clamped}
            aria-label={label}
            onChange={e => setMoney(key, Number(e.target.value))}
          />
          <div className="gsl-ends">
            <span>{money(0)}</span>
            <span>{capLabel}</span>
          </div>
        </div>
        <p className="m">{EDIT_HINT[key]}</p>
      </>
    );
  };

  const tipBody = (key: string) => {
    const t = TIPS[key];
    if (!t) return null;
    return (
      <>
        <b>{t.title}</b>
        {t.body}
      </>
    );
  };

  if (busy && !mInc) {
    return (
      <>
        <div className="x-h1" style={{ whiteSpace: 'nowrap' }}>Working out where you stand</div>
        <div className="x-lead" style={{ maxWidth: 'none', marginBottom: 26 }}>
          Building a typical position for a {age}-year-old {String(session.occupation || '').toLowerCase()} in Singapore.
          You will be able to change every figure.
        </div>
        {[0, 1, 2].map(i => (
          <div key={i} className="x-card x-pad" style={{ marginBottom: 14 }}>
            <div className="x-sk" style={{ width: '34%', marginBottom: 16 }} />
            <div className="x-sk" style={{ height: 30, width: '64%', marginBottom: 12 }} />
            <div className="x-sk" style={{ width: '80%' }} />
          </div>
        ))}
      </>
    );
  }

  return (
    <>
      <div className="x-h1" style={{ whiteSpace: 'nowrap' }}>Where you stand today</div>
      <div className="x-lead" style={{ maxWidth: 'none', marginBottom: 20 }}>
        Three totals to start. Open a card to change a figure — the ⓘ says where it came from. Your CPF sits between
        money in and money out and is not editable.
      </div>

      {predictError ? <div className="x-qerr" style={{ marginBottom: 20 }}>{predictError}</div> : null}

      <div className="x-why">
        <div className="x-whyh x-narr-row">
          <span className="ic">{Ico.wand}</span>
          <div className="t">
            <b>Your financial position</b>
          </div>
          <NarrBtn label="Explain these figures" on={narrOn} onClick={onNarr} />
        </div>

        {session.explain ? <Explain session={session} onChange={onChange} /> : null}

        <ChainFold
          title="What comes in and goes out"
          tag={<GroupTag session={session} keys={['income', 'expense']} verb="earn and spend about this" />}
          unit="per month"
          open={open.cash}
          onToggle={() => toggle('cash')}
          chevronRef={cashChevronRef}
        >
          <EqPie
            rows={[
              { l: 'Money coming in', v: mInc, c: 'pos' },
              { l: 'Money going out', v: outInclCpf, c: 'neg' },
              { l: sur < 0 ? 'Short each month' : 'Available budget', v: sur, c: sur < 0 ? 'neg' : 'tot' },
            ]}
          />
          <div className="t">
            <span>
              Money coming in
              <Tip id="iinc" open={session.tip} onToggle={toggleTip} right>
                {tipBody('income')}
              </Tip>
              {tag('income')}
            </span>
            <b>{money(mInc)}</b>
            <Tip id="einc" open={session.tip} onToggle={toggleTip} edit right wide>
              {editBody('income', 'Money coming in each month', mInc)}
            </Tip>
          </div>
          <div className="t noedit">
            <span>
              Your CPF
              <Tip id="icpf" open={session.tip} onToggle={toggleTip} right>
                {tipBody('cpf')}
              </Tip>
            </span>
            <b>{money(cpf)}</b>
          </div>
          <div className="t">
            <span>
              Money going out
              <Tip id="iexp" open={session.tip} onToggle={toggleTip} right>
                {tipBody('expense')}
              </Tip>
              {tag('expense')}
            </span>
            <b>{money(mExp)}</b>
            <Tip id="eexp" open={session.tip} onToggle={toggleTip} edit right wide>
              {editBody('expense', 'Money going out each month', mExp)}
            </Tip>
          </div>
          <div className={`b noedit ${sur < 0 ? 'no' : ''}`}>
            <span>
              {sur < 0 ? 'Short each month' : 'Available budget'}
              <Tip id="bud" open={session.tip} onToggle={toggleTip} right>
                {tipBody('budget')}
              </Tip>
            </span>
            <b>{money(Math.abs(sur))}</b>
          </div>
        </ChainFold>

        <ChainFold
          title="What you own and owe"
          tag={<GroupTag session={session} keys={['savings', 'property', 'loans']} verb="own and owe about this" />}
          unit="today"
          open={open.wealth}
          onToggle={() => toggle('wealth')}
        >
          <EqPie
            rows={[
              { l: 'Assets', v: assets(session), c: 'pos' },
              { l: 'Loans outstanding', v: liab, c: 'neg' },
              { l: net < 0 ? 'Negative net wealth' : 'Net wealth', v: net, c: net < 0 ? 'neg' : 'tot' },
            ]}
          />
          <MoneyRow
            label="Savings & investments"
            value={liq}
            tag={tag('savings')}
            tipId="isav"
            editId="esav"
            tip={tipBody('savings')}
            edit={editBody('savings', 'Savings & investments', liq)}
            open={session.tip}
            onTip={toggleTip}
          />
          <MoneyRow
            label="Property"
            value={prop}
            tag={tag('property')}
            tipId="iprp"
            editId="eprp"
            tip={tipBody('property')}
            edit={editBody('property', 'Property', prop)}
            open={session.tip}
            onTip={toggleTip}
          />
          <MoneyRow
            label="Loans outstanding"
            value={liab}
            tag={tag('loans')}
            tipId="iloan"
            editId="eloan"
            tip={tipBody('loans')}
            edit={editBody('loans', 'Loans outstanding', liab)}
            open={session.tip}
            onTip={toggleTip}
          />
          <div className={`b noedit ${net < 0 ? 'no' : ''}`}>
            <span>
              Net wealth
              <Tip id="inet" open={session.tip} onToggle={toggleTip} right>
                {tipBody('net')}
              </Tip>
            </span>
            <b>{money(net)}</b>
          </div>
        </ChainFold>

        <ChainFold
          title="What cover you have"
          tag={<GroupTag session={session} keys={['cover']} verb="hold about this much cover" />}
          unit="sum assured"
          open={open.cover}
          onToggle={() => toggle('cover')}
          chevronRef={coverChevronRef}
        >
          <CoverBlock session={session} onChange={onChange} tipBody={tipBody('cover')} />
        </ChainFold>
      </div>

      <CoachTour
        enabled={gtTtOn}
        onComplete={onGtTtComplete}
        steps={[
          {
            title: 'What comes in and goes out',
            body: 'These figures are predicted from a demographic cohort like you. Click the arrow to open this card and customise any number.',
            anchorRef: cashChevronRef,
          },
          {
            title: 'What cover you have',
            body: 'Cover is also predicted from a cohort like you. Click the arrow to open this card and add or change the policies you actually hold.',
            anchorRef: coverChevronRef,
          },
        ]}
      />

      <Foot>
        <button className="x-btn g" type="button" onClick={onBack}>
          ← Back
        </button>
        <button className="x-btn sm" type="button" onClick={onReestimate} disabled={busy}>
          Re-estimate
        </button>
        <span className="sp" />
        <button className="x-btn p" type="button" onClick={onScore} disabled={busy}>
          {busy ? 'Scoring…' : 'Understand my goals and needs →'}
        </button>
      </Foot>
    </>
  );
}

import type { GpSession } from '../../lib/types';

export function Explain({ session, onChange }: { session: GpSession; onChange: (p: Partial<GpSession>) => void }) {
  const age = typeof session.age === 'number' ? session.age : null;
  const drivers = [
    {
      k: 'occ',
      v: session.occupation || 'Not set',
      on: true,
      e: 'People Like You uses this job to estimate a typical income',
    },
    {
      k: 'age',
      v: age ? age + ' years' : 'Not set',
      on: true,
      e: 'Shapes spending, savings, and how long the plan has to run',
    },
    {
      k: 'res',
      v: session.residency || 'Not set',
      on: true,
      e: 'Sets the market and currency for the estimate',
    },
    { k: 'deps', v: session.dependents + ' dependant' + (session.dependents === 1 ? '' : 's'), on: false, e: 'Shapes cover and family goals' },
    { k: 'gender', v: session.gender || 'Not set', on: false, e: 'Shapes retirement, not this estimate' },
  ];
  return (
    <div className="x-expl">
      <div className="x-explh">
        <b>What you told us</b>
        <button className="x-explx" type="button" onClick={() => onChange({ explain: false })}>
          Hide explanation
        </button>
      </div>
      <div className="x-whyg">
        {drivers.map(d => (
          <div key={d.k} className={`x-drv ${d.on ? 'on' : ''}`}>
            <span className="top">
              <span className="v">{d.v}</span>
            </span>
            <span className="e">{d.e}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

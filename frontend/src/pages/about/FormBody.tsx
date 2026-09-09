import { useState } from 'react';
import { D2C_DEPS, D2C_GEN, D2C_RES } from '../../lib/catalog';
import { cpfOn, depsFromChoice, sessionAge, type DepsChoice, type GpSession } from '../../lib/types';

export function FormBody({
  session,
  onTouch,
}: {
  session: GpSession;
  onTouch: (k: string, p: Partial<GpSession>) => void;
}) {
  const [ageDraft, setAgeDraft] = useState(session.age === '' ? '' : String(session.age));
  const [ageErr, setAgeErr] = useState('');
  const rq = <em className="rq">*</em>;

  const onAge = (raw: string) => {
    const digits = raw.replace(/\D/g, '').slice(0, 2);
    setAgeDraft(digits);
    if (digits === '') {
      setAgeErr('');
      onTouch('age', { age: '' });
      return;
    }
    if (digits.length < 2) {
      setAgeErr('');
      onTouch('age', { age: '' });
      return;
    }
    const n = Number(digits);
    if (n >= 18 && n <= 70) {
      setAgeErr('');
      onTouch('age', { age: n });
    } else {
      setAgeErr('Enter an age from 18 to 70');
      onTouch('age', { age: '' });
    }
  };

  return (
    <div className="x-form">
      <div className="x-2">
        <div className="x-f">
          <label>Your name {rq}</label>
          <input
            className="x-in"
            value={session.name}
            placeholder="What should we call you?"
            onChange={e => onTouch('name', { name: e.target.value })}
          />
        </div>
        <div className="x-f">
          <label>Your age {rq}</label>
          <input
            className={`x-in ${ageErr ? 'bad' : ''}`}
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={2}
            value={ageDraft}
            placeholder="18–70"
            aria-invalid={!!ageErr}
            onChange={e => onAge(e.target.value)}
            onBlur={() => {
              if (ageDraft !== '' && !sessionAge({ age: Number(ageDraft) || '' })) {
                setAgeErr('Enter an age from 18 to 70');
              }
            }}
          />
          {ageErr ? <span className="x-ferr">{ageErr}</span> : null}
        </div>
      </div>
      <div className="x-2">
        <div className="x-f">
          <label>Gender {rq}</label>
          <div className="x-pills sm">
            {D2C_GEN.map(o => (
              <button key={o} type="button" className={session.gender === o ? 'on' : ''} onClick={() => onTouch('gender', { gender: o })}>
                {o}
              </button>
            ))}
          </div>
        </div>
        <div className="x-f">
          <label>People who depend on your income {rq}</label>
          <div className="x-pills sm">
            {D2C_DEPS.map(o => (
              <button
                key={o}
                type="button"
                className={session.depsChoice === o ? 'on' : ''}
                onClick={() => onTouch('deps', { depsChoice: o as DepsChoice, dependents: depsFromChoice(o as DepsChoice) })}
              >
                {o}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="x-2">
        <div className="x-f">
          <label>Occupation {rq}</label>
          <input
            className="x-in"
            value={session.occupation}
            autoComplete="off"
            placeholder="e.g. software engineer, ICU nurse"
            onChange={e => onTouch('occ', { occupation: e.target.value })}
          />
        </div>
        <div className="x-f">
          <label>Residency status {rq}</label>
          <div className="x-pills sm col">
            {D2C_RES.map(o => (
              <button
                key={o}
                type="button"
                className={session.residency === o ? 'on' : ''}
                onClick={() => onTouch('res', { residency: o })}
              >
                {o}
              </button>
            ))}
          </div>
          <span className="hint">
            {cpfOn(session) ? 'CPF is projected for you.' : 'CPF is not projected — retirement is funded from savings alone.'}
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * Parameter admin screen, at `#parameters`.
 *
 * Lists the active version, lets an admin change values and save the result as the
 * next version, and shows the audit log. A version is never edited in place, so the
 * numbers an old session was calculated with stay readable forever.
 *
 * The gate is server-side: GP asks FM whether the bearer is a platform admin before
 * accepting a write. This screen is readable by anyone who can reach it, and Save
 * reports the 403 if they are not an admin.
 */

import { useEffect, useMemo, useState } from 'react';
import { loadAuthSession } from '../lib/auth';
import {
  fetchAudit,
  fetchParameters,
  fetchVersions,
  putParameters,
  type AuditEntry,
  type Parameter,
  type ParameterSet,
} from '../lib/config';

type Draft = Record<string, string>;

function displayValue(p: Parameter): string {
  return typeof p.value === 'number' ? String(p.value) : String(p.value);
}

function boundsNote(p: Parameter): string {
  if (p.min != null && p.max != null) return `${p.min} to ${p.max}`;
  if (p.min != null) return `at least ${p.min}`;
  if (p.max != null) return `at most ${p.max}`;
  return '';
}

/** Only rows the admin actually changed are sent; the rest are carried over. */
function changedRows(set: ParameterSet, draft: Draft): Record<string, number | string> {
  const out: Record<string, number | string> = {};
  for (const [name, raw] of Object.entries(draft)) {
    const original = set.parameters[name];
    if (!original) continue;
    const text = raw.trim();
    if (text === '' || text === displayValue(original)) continue;
    if (typeof original.value === 'number') {
      const n = Number(text);
      if (Number.isFinite(n)) out[name] = n;
    } else {
      out[name] = text;
    }
  }
  return out;
}

export function Parameters() {
  const [set, setSet] = useState<ParameterSet | null>(null);
  const [versions, setVersions] = useState<string[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [viewing, setViewing] = useState<string>('');
  const [draft, setDraft] = useState<Draft>({});
  const [note, setNote] = useState('');
  const [filter, setFilter] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [busy, setBusy] = useState(false);
  const token = loadAuthSession()?.access_token ?? null;

  const load = (version?: string) => {
    Promise.all([fetchParameters(version), fetchVersions(), fetchAudit()])
      .then(([params, vs, log]) => {
        setError('');
        setSet(params);
        setVersions(vs);
        setAudit(log);
        setViewing(params.version);
        setDraft({});
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load parameters'));
  };

  useEffect(() => load(), []);

  const changed = useMemo(() => (set ? changedRows(set, draft) : {}), [set, draft]);
  const nChanged = Object.keys(changed).length;
  const isLatest = !!set && versions.length > 0 && set.version === versions[versions.length - 1];

  const rows = useMemo(() => {
    if (!set) return [];
    const needle = filter.trim().toLowerCase();
    return Object.values(set.parameters)
      .filter(p => !needle || p.name.toLowerCase().includes(needle) || p.label.toLowerCase().includes(needle))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [set, filter]);

  const save = () => {
    if (!set || !nChanged) return;
    setBusy(true);
    setError('');
    setSaved('');
    putParameters(changed, note, token, set.version)
      .then(created => {
        setSaved(`Saved as ${created.version}`);
        setNote('');
        load();
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Could not save'))
      .finally(() => setBusy(false));
  };

  if (error && !set) {
    return (
      <div className="card lp" style={{ margin: 24 }}>
        <div className="lpb">
          <b>Parameters</b>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!set) {
    return (
      <div className="card lp" style={{ margin: 24 }}>
        <div className="lpb">Loading parameters…</div>
      </div>
    );
  }

  return (
    <div className="card lp" style={{ margin: 24 }}>
      <div className="lpb">
        <div className="asg-h">
          <b>
            Parameters {set.version} {set.model ? `(model ${set.model})` : null}
          </b>
          <span>
            {set.note || 'Values are read by every calculation. Saving creates the next version.'}
          </span>
        </div>

        <div className="gc-e" style={{ gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <label>
            Version{' '}
            <select
              value={viewing}
              onChange={e => load(e.target.value)}
              aria-label="Parameter version"
            >
              {versions.map(v => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <input
            type="search"
            placeholder="Filter by name"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            aria-label="Filter parameters"
          />
          {!isLatest ? <span>Viewing an old version; edits are based on it.</span> : null}
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 12 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>Name</th>
              <th style={{ textAlign: 'right' }}>Value</th>
              <th style={{ textAlign: 'left' }}>Unit</th>
              <th style={{ textAlign: 'left' }}>Level</th>
              <th style={{ textAlign: 'left' }}>New value</th>
              <th style={{ textAlign: 'left' }}>Where it is used</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(p => (
              <tr key={p.name}>
                <td title={p.label}>{p.name}</td>
                <td style={{ textAlign: 'right' }}>{displayValue(p)}</td>
                <td>
                  {p.currency ? `${p.currency} ` : ''}
                  {p.unit}
                </td>
                <td>{p.level}</td>
                <td>
                  <input
                    value={draft[p.name] ?? ''}
                    placeholder={boundsNote(p) || 'unchanged'}
                    onChange={e => setDraft(d => ({ ...d, [p.name]: e.target.value }))}
                    aria-label={`New value for ${p.name}`}
                    style={{ width: 120 }}
                  />
                </td>
                <td>{p.codeSource}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="lpfoot" style={{ gap: 12, flexWrap: 'wrap' }}>
          <input
            placeholder="Why this change"
            value={note}
            onChange={e => setNote(e.target.value)}
            aria-label="Change note"
            style={{ flex: 1, minWidth: 220 }}
          />
          <span>{nChanged ? `${nChanged} value${nChanged === 1 ? '' : 's'} changed` : 'No changes'}</span>
          <button className="x-btn p" type="button" disabled={!nChanged || busy} onClick={save}>
            {busy ? 'Saving…' : 'Save as new version'}
          </button>
        </div>

        {error ? <p role="alert">{error}</p> : null}
        {saved ? <p>{saved}</p> : null}

        <div className="asg-h" style={{ marginTop: 20 }}>
          <b>Change history</b>
        </div>
        {audit.length === 0 ? (
          <p>No changes yet; {set.version} came from the workbook.</p>
        ) : (
          <ul>
            {audit
              .slice()
              .reverse()
              .map((entry, i) => (
                <li key={`${entry.version}-${i}`}>
                  <b>{entry.version}</b> — {entry.createdAt} by {entry.createdBy || 'unknown'}
                  {entry.note ? ` — ${entry.note}` : ''}
                  <ul>
                    {Object.entries(entry.diff).map(([name, d]) => (
                      <li key={name}>
                        {name}: {String(d.from)} → {String(d.to)}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
          </ul>
        )}
      </div>
    </div>
  );
}

import { D2C_DOCF } from '../../lib/catalog';
import { Ico } from '../../lib/icons';
import type { DocKind, GpSession } from '../../lib/types';

export function DocTile({
  row,
  doc,
  onFile,
  onDel,
  onVal,
}: {
  row: [DocKind, string, string];
  doc?: GpSession['docs'][DocKind];
  onFile: (f: File | undefined) => void;
  onDel: () => void;
  onVal: (field: string, val: string | number) => void;
}) {
  const [k, title, sub] = row;
  if (doc?.state === 'reading') {
    return (
      <div className="x-doc busy">
        <span className="x-docic">{Ico.file}</span>
        <b>{title}</b>
        <span className="x-docsub">Reading {doc.name}…</span>
        <div className="x-docbar">
          <i />
        </div>
      </div>
    );
  }
  if (doc?.state === 'done') {
    return (
      <div className="x-doc done">
        <button className="x-docdel" type="button" aria-label={`Remove ${title}`} onClick={onDel}>
          {Ico.close}
        </button>
        <span className="x-docic ok">{Ico.check}</span>
        <b>{title}</b>
        <span className="x-docsub">{doc.name}</span>
        <div className="x-docv">
          {D2C_DOCF[k].map(f => (
            <label key={f[0]}>
              <span>{f[1]}</span>
              <input
                className="x-docin"
                inputMode={f[2] === 'n' ? 'numeric' : undefined}
                value={f[2] === 'n' ? Number(doc.v[f[0]] || 0).toLocaleString('en-SG') : String(doc.v[f[0]] || '')}
                onChange={e => onVal(f[0], f[2] === 'n' ? Number(String(e.target.value).replace(/,/g, '')) || 0 : e.target.value)}
              />
            </label>
          ))}
        </div>
        <span className={`x-docsrc ${doc.src === 'model' ? 'm' : ''}`}>
          {doc.src === 'model' ? 'Read from your document' : 'Simulated for this prototype'} · correct anything that is wrong
        </span>
      </div>
    );
  }
  return (
    <label className="x-doc">
      <input type="file" accept="image/*,application/pdf,.pdf" hidden onChange={e => onFile(e.target.files?.[0])} />
      <span className="x-docic">{Ico.upFile}</span>
      <b>{title}</b>
      <span className="x-docsub">{sub}</span>
      <span className="x-doccta">Choose a file or take a photo</span>
    </label>
  );
}

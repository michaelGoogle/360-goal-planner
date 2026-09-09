import { OCCUPATIONS } from './catalog';

const NUMW: Record<string, number> = {
  zero: 0,
  no: 0,
  none: 0,
  a: 1,
  an: 1,
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
};

const NOTOCC =
  /^(married|single|unmarried|divorced|widowed|separated|male|female|man|woman|lady|guy|citizen|singaporean|singapore citizen|sg citizen|local|permanent resident|pr|foreigner|foreign|expat|expatriate|employment pass|work permit|s pass|kids?|children|child|dependants?|no dependants|years? old|year old|none|no kids|nothing|myself|oh|zero|mail|kits|worse|maths|solution|actually)$/;

function jobOk(o: string): boolean {
  const low = o.toLowerCase().trim();
  if (low.length < 3 || NOTOCC.test(low) || /^[\d.]+$/.test(low)) return false;
  if (/\b(yeah|um|uh)\b/.test(low)) return false;
  if (/\b(kids?|kits|wife|husband|children|child|daughters?|sons?)\b/.test(low)) return false;
  if (/city zen|singapore sitting|see eo|account tent|no kits|pea are/.test(low)) return false;
  if (low === 'pre' || low === 'pr') return false;
  return true;
}

function num(w: string): number | null {
  if (NUMW[w] !== undefined) return NUMW[w];
  return /^\d+$/.test(w) ? Number(w) : null;
}

export interface ParsedSentence {
  age?: string;
  gender?: 'Male' | 'Female';
  res?: 'Singapore Citizen' | 'Permanent Resident' | 'Foreigner';
  deps?: string;
  occ?: string;
  name?: string;
}

export function parseSentence(text: string): ParsedSentence {
  const raw = String(text || '');
  const s = ' ' + raw.toLowerCase().replace(/[‘’]/g, "'").replace(/\s+/g, ' ') + ' ';
  const out: ParsedSentence = {};

  let m =
    raw.match(/\b(?:i'?m|i am|aged?|age of|age)\s*:?\s*(\d{2})\b/i) ||
    raw.match(/\b(\d{2})\s*(?:-|\s)?\s*(?:years?[- ]old|yrs?[- ]old|y\/?o)\b/i) ||
    raw.match(/(?:^|[,;(\s])(\d{2})(?=[,;)\s]|$)/);
  if (m && +m[1] >= 18 && +m[1] <= 70) out.age = String(+m[1]);

  if (/\b(female|woman|lady|girl|mrs|ms|miss|mother|mum|mom)\b/.test(s)) out.gender = 'Female';
  else if (/\b(male|man|guy|mr|father|dad)\b/.test(s)) out.gender = 'Male';

  if (/\b(permanent resident|spr|sg pr|s'pore pr)\b/.test(s) || /\bpr\b/.test(s)) out.res = 'Permanent Resident';
  else if (
    /\b(foreigner|foreign|expat|expatriate|employment pass|ep holder|s pass|work permit|not a resident|on a visa)\b/.test(
      s,
    )
  )
    out.res = 'Foreigner';
  else if (
    /\b(singaporean|singapore citizen|sg citizen|citizen|local|resident of singapore|singapore resident|living in singapore|live in singapore|resident in singapore)\b/.test(
      s,
    )
  )
    out.res = 'Singapore Citizen';

  let kids: number | null = null;
  m = s.match(/\b([a-z]+|\d+)\s+(?:young |small |little |grown )?(?:kids?|children|child|sons?|daughters?|boys?|girls?)\b/);
  if (m && num(m[1]) !== null) kids = num(m[1]);
  if (kids === null && /\b(no kids|no children|childless|without children)\b/.test(s)) kids = 0;
  m = s.match(/\b([a-z]+|\d+)\s+dependants?\b/);
  if (m && num(m[1]) !== null) kids = num(m[1]);
  const married = /\b(married|wife|husband|spouse|partner)\b/.test(s);
  const spouseDep =
    married &&
    /\b(housewife|homemaker|stay[- ]at[- ]home|not working|does not work|doesn't work|unemployed|full[- ]time (?:mum|mom|dad))\b/.test(
      s,
    );
  if (kids !== null || married) {
    const n = Math.max(0, (kids || 0) + (spouseDep ? 1 : 0));
    out.deps = n >= 4 ? '4+' : String(n);
  } else if (/\b(single|unmarried|nobody depends|no one depends|no dependants|on my own)\b/.test(s)) {
    out.deps = '0';
  }

  const cands: string[] = [];
  let m2 = s.match(/\b(?:i work as|working as|employed as|i work in)\s+an?\s+([a-z][a-z \-/&']{2,44})/);
  if (m2) cands.push(m2[1]);
  m2 = s.match(/\b(?:self[- ]employed|freelance)\s+([a-z][a-z \-/&']{2,44})/);
  if (m2) cands.push('self-employed ' + m2[1]);
  m2 = s.match(/\b(?:my job is|by profession|profession|occupation|job)\s*:?\s+([a-z][a-z \-/&']{2,44})/);
  if (m2) cands.push(m2[1]);
  m2 = s.match(/\b(?:i run|i own|i operate|running|i drive|i teach)\s+(?:an?\s+)?([a-z][a-z \-/&']{2,44})/);
  if (m2) cands.push(m2[1]);
  m2 = s.match(/\b(?:i am|i'm)\s+an?\s+(?:\d{1,2}[\s-]*(?:years?|yrs?)[\s-]*old\s+)?([a-z][a-z \-/&']{2,44})/);
  if (m2) cands.push(m2[1]);
  m2 = s.match(/,\s*([a-z][a-z \-/&']{2,44}?)\s*[.,!]?\s*$/);
  if (m2) cands.push(m2[1]);
  [
    'software engineer',
    'data scientist',
    'product manager',
    'business owner',
    'civil servant',
    'sales manager',
    'project manager',
    'operations manager',
    'financial adviser',
    'it consultant',
  ]
    .filter(k => s.includes(k))
    .forEach(k => cands.push(k));
  OCCUPATIONS.map(o => o.toLowerCase())
    .filter(o => o.length > 4 && !o.includes('/') && s.includes(o))
    .sort((a, b) => s.lastIndexOf(b) - s.lastIndexOf(a) || b.length - a.length)
    .slice(0, 2)
    .forEach(o => cands.push(o));
  [
    'engineer',
    'teacher',
    'nurse',
    'doctor',
    'lawyer',
    'accountant',
    'manager',
    'designer',
    'developer',
    'consultant',
    'analyst',
    'architect',
    'dentist',
    'pharmacist',
    'pilot',
    'chef',
    'driver',
    'banker',
    'entrepreneur',
    'freelancer',
    'student',
    'homemaker',
    'retired',
  ]
    .filter(k => s.includes(' ' + k))
    .forEach(k => cands.push(k));

  const clean = (c: string) => {
    let o = String(c || '')
      .replace(/\s+(?:earning|earn|making|make|with|and|who|based|living|salary|income|at|for|in|on|since|about)\b[\s\S]*$/, '')
      .replace(/^\s*(?:a|an|the|also|currently|now)\s+/, '')
      .replace(/^\s*\d{1,2}[\s-]*(?:years?|yrs?)[\s-]*old\s+/, '')
      .replace(
        /^(?:\s*(?:male|female|man|woman|married|single|young|singaporean|singapore citizen|sg citizen|permanent resident|pr|foreigner|expat|local|citizen)\b[, ]*)+/,
        '',
      )
      .replace(/[.,;!]+$/, '')
      .replace(/\s+(?:of|at|in|for|with|and|to|by|from|the|a|an)$/, '')
      .replace(/\s+/g, ' ')
      .trim();
        if (o.length < 3 || NOTOCC.test(o) || !jobOk(o)) return null;
    o = o.replace(/\b[a-z]/g, c2 => c2.toUpperCase());
    return o.replace(/\b[A-Za-z]{2,4}\b/g, w =>
      new RegExp('(^|[^A-Za-z])' + w.toUpperCase() + '([^A-Za-z]|$)').test(raw) ? w.toUpperCase() : w,
    );
  };
  for (const cand of cands) {
    const c = clean(cand);
    if (c) {
      out.occ = c;
      break;
    }
  }

  m = raw.match(/\b(?:my name is|i am called|call me|this is|name's)\s+([A-Za-z][a-zA-Z'-]{1,20})/i);
  if (m) out.name = m[1].charAt(0).toUpperCase() + m[1].slice(1);

  return out;
}

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { capEnabledNeeds, minExpenseMonthly, patchNeedInputs, toggleNeedEnabled } from './needEdit';
import { EMPTY_SESSION, NEED_TYPES, type NeedRow, type NeedType } from './types';

function row(type: NeedType, enabled: boolean, gap: number): NeedRow {
  return { type, enabled, needAmount: gap, gap };
}

function all(enabled: Partial<Record<NeedType, boolean>>, gaps: Partial<Record<NeedType, number>> = {}): NeedRow[] {
  return NEED_TYPES.map(type => row(type, enabled[type] ?? false, gaps[type] ?? 0));
}

function on(needs: NeedRow[]): NeedType[] {
  return needs.filter(n => n.enabled).map(n => n.type);
}

test('cap keeps two protection and two growth, retirement always on', () => {
  const needs = capEnabledNeeds(
    all(
      { N_CRI: true, N_TPD: true, N_INC: true, N_RET: true, N_EDU: true, N_SAV: true },
      { N_CRI: 100, N_TPD: 80, N_INC: 50, N_RET: 200, N_EDU: 90, N_SAV: 40 },
    ),
  );
  assert.deepEqual(on(needs).sort(), ['N_CRI', 'N_EDU', 'N_RET', 'N_TPD']);
});

test('owning a home does not swap savings for a home-purchase goal', () => {
  const needs = capEnabledNeeds(
    all({ N_CRI: true, N_TPD: true, N_RET: true, N_SAV: true }, { N_SAV: 80, N_PRP: 40 }),
  );
  assert.equal(needs.find(n => n.type === 'N_SAV')?.enabled, true);
  assert.equal(needs.find(n => n.type === 'N_PRP')?.enabled, false);
  assert.equal(needs.find(n => n.type === 'N_RET')?.enabled, true);
});

test('N_PRP stays off unless the customer already switched it on', () => {
  const needs = capEnabledNeeds(
    all({ N_CRI: true, N_TPD: true, N_RET: true, N_PRP: true }, { N_SAV: 80, N_PRP: 40 }),
  );
  assert.equal(needs.find(n => n.type === 'N_PRP')?.enabled, true);
  assert.equal(needs.find(n => n.type === 'N_SAV')?.enabled, false);
});

test('clicking a lower-gap need adds it without dropping the others', () => {
  const start = capEnabledNeeds(
    all(
      { N_CRI: true, N_TPD: true, N_RET: true, N_EDU: true },
      { N_CRI: 100, N_TPD: 80, N_INC: 20, N_HOS: 10, N_RET: 200, N_EDU: 90, N_SAV: 30 },
    ),
  );
  const next = toggleNeedEnabled(start, 'N_INC');
  assert.equal(next.find(n => n.type === 'N_INC')?.enabled, true);
  assert.equal(next.find(n => n.type === 'N_CRI')?.enabled, true);
  assert.equal(next.find(n => n.type === 'N_TPD')?.enabled, true);
});

test('clicking every remaining need turns the full catalog on', () => {
  let needs = all({});
  for (const t of NEED_TYPES) needs = toggleNeedEnabled(needs, t);
  assert.deepEqual(on(needs).sort(), [...NEED_TYPES].sort());
});

test('clicking a growth need keeps retirement and the existing growth card', () => {
  const start = capEnabledNeeds(
    all({ N_CRI: true, N_TPD: true, N_RET: true, N_EDU: true }, { N_EDU: 90, N_SAV: 20 }),
  );
  const next = toggleNeedEnabled(start, 'N_SAV');
  assert.deepEqual(on(next).filter(t => t === 'N_RET' || t === 'N_SAV' || t === 'N_EDU').sort(), [
    'N_EDU',
    'N_RET',
    'N_SAV',
  ]);
});

test('turning a need off does not immediately turn it back on', () => {
  const start = capEnabledNeeds(
    all({ N_CRI: true, N_TPD: true, N_RET: true, N_EDU: true }, { N_CRI: 100, N_TPD: 80 }),
  );
  const next = toggleNeedEnabled(start, 'N_CRI');
  assert.equal(next.find(n => n.type === 'N_CRI')?.enabled, false);
});

test('editing a need marks provenance as your own figures', () => {
  const s = {
    ...EMPTY_SESSION,
    needs: [row('N_RET', true, 100)],
  };
  const open = patchNeedInputs(s, 'N_RET', {});
  assert.equal(open.provenance, undefined);
  const edited = patchNeedInputs(s, 'N_RET', { retAge: 68 });
  assert.equal(edited.provenance?.needs, 'you');
});

test('spend floor is USD 100 converted at the session lock', () => {
  assert.equal(minExpenseMonthly(undefined), 100);
  assert.equal(minExpenseMonthly({ fx: { usdPerLocal: 1 } }), 100);
  assert.equal(minExpenseMonthly({ fx: { usdPerLocal: 0.7816 } }), 127.94);
});

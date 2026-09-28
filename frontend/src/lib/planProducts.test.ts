import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  FREE_BUDGET_SHARE,
  PLAN_FOR_NEED,
  coverPremiumFor,
  coverSumForPremium,
  defaultWealthMth,
  planAfford,
  refreshUntouchedCover,
  setPlanCoverPatch,
} from './planProducts';
import { EMPTY_SESSION, type GpSession, type NeedRow } from './types';

function session(partial: Partial<GpSession> = {}): GpSession {
  const nInc: NeedRow = {
    type: 'N_INC',
    enabled: true,
    needAmount: 500_000,
    have: 0,
    gap: 500_000,
  };
  const nRet: NeedRow = {
    type: 'N_RET',
    enabled: true,
    needAmount: 1_000_000,
    have: 200_000,
    gap: 800_000,
  };
  return {
    ...EMPTY_SESSION,
    age: 42,
    incomeMonthly: 10_000,
    expenseMonthly: 6_000,
    needs: [nInc, nRet],
    ...partial,
  };
}

test('FREE_BUDGET_SHARE is 50%', () => {
  assert.equal(FREE_BUDGET_SHARE, 0.5);
});

test('default monthly contribution is sized at the affordability share', () => {
  const s = session();
  const a = planAfford({ ...s, planMth: { N_RET: 0 }, planPrem: { N_INC: 0 }, planSum: { N_INC: 0 } });
  const mth = defaultWealthMth(s, 0);
  assert.ok(mth <= a.free + 50);
});

test('changing premium to 0 zeros sum assured', () => {
  const s = session({ planSum: { N_INC: 500_000 }, planPrem: { N_INC: coverPremiumFor(500_000) } });
  const p = setPlanCoverPatch(s, 'N_INC', { prem: 0 });
  assert.equal(p.planSum?.N_INC, 0);
  assert.equal(p.planPrem?.N_INC, 0);
  assert.equal(p.lifeSum, 0);
});

test('changing sum assured sets the matching premium', () => {
  const s = session();
  const p = setPlanCoverPatch(s, 'N_INC', { sum: 200_000 });
  assert.equal(p.planSum?.N_INC, 200_000);
  assert.equal(p.planPrem?.N_INC, coverPremiumFor(200_000));
});

test('untouched cover reseeds to the new gap', () => {
  const s = session({
    planSum: { N_INC: 100_000 },
    planPrem: { N_INC: coverPremiumFor(100_000) },
    needs: [
      { type: 'N_INC', enabled: true, needAmount: 800_000, have: 0, gap: 800_000 },
      { type: 'N_RET', enabled: true, needAmount: 1_000_000, have: 0, gap: 1_000_000 },
    ],
  });
  const p = refreshUntouchedCover(s);
  assert.equal(p.planSum?.N_INC, 800_000);
  assert.equal(p.planPrem?.N_INC, coverPremiumFor(800_000));
});

test('touched cover is kept when the gap changes', () => {
  const s = session({
    planSum: { N_INC: 100_000 },
    planPrem: { N_INC: coverPremiumFor(100_000) },
    planSumTouched: { N_INC: true },
    needs: [{ type: 'N_INC', enabled: true, needAmount: 800_000, have: 0, gap: 800_000 }],
  });
  const p = refreshUntouchedCover(s);
  assert.equal(p.planSum, undefined);
});

test('coverSumForPremium inverts coverPremiumFor at zero', () => {
  assert.equal(coverSumForPremium(0), 0);
});

test('every calculator need has a plan label including N_PAC and N_LTC', () => {
  assert.equal(PLAN_FOR_NEED.N_PAC, 'Personal accident cover');
  assert.equal(PLAN_FOR_NEED.N_LTC, 'Long-term care cover');
  assert.equal(PLAN_FOR_NEED.N_TPD, 'Disability cover');
  assert.equal(PLAN_FOR_NEED.N_PRP, 'Property plan');
});

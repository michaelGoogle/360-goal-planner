import assert from 'node:assert/strict';
import { test } from 'node:test';
import { applyPlanResponse } from './local';
import { EMPTY_SESSION, type GpSession, type NeedRow } from './types';

function session(partial: Partial<GpSession> = {}): GpSession {
  const nInc: NeedRow = { type: 'N_INC', enabled: true, needAmount: 500_000, have: 0, gap: 500_000 };
  const nRet: NeedRow = { type: 'N_RET', enabled: true, needAmount: 1_000_000, have: 200_000, gap: 800_000 };
  return { ...EMPTY_SESSION, age: 42, incomeMonthly: 10_000, expenseMonthly: 6_000, needs: [nInc, nRet], ...partial };
}

test('applyPlanResponse writes API plan fields onto the session', () => {
  const s = session();
  const patch = applyPlanResponse(s, {
    needs: [
      {
        type: 'N_INC',
        suggested: true,
        included: true,
        planSum: 500_000,
        planPrem: 390,
        planMth: 0,
        planLump: 0,
        capMth: 0,
        fv: 0,
        remain: 0,
      },
      {
        type: 'N_RET',
        suggested: true,
        included: true,
        planSum: 0,
        planPrem: 0,
        planMth: 1500,
        planLump: 0,
        capMth: 2000,
        fv: 400_000,
        remain: 400_000,
      },
    ],
    investMth: 1500,
    investLump: 0,
    protPremYear: 390,
    currency: 'SGD',
  });
  assert.equal(patch.prodSeeded, true);
  assert.equal(patch.planSum?.N_INC, 500_000);
  assert.equal(patch.planPrem?.N_INC, 390);
  assert.equal(patch.planMth?.N_RET, 1500);
  assert.equal(patch.investMth, 1500);
  assert.equal(patch.lifeSum, 500_000);
});

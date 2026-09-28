import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  debtServiceRatio,
  netReturnCeiling,
  riskCapacity,
  suitableRisk,
  suggestedNetReturn,
} from './riskCapacity';
import { monthlyLoanPayment } from './ratios';
import type { GpSession } from './types';

/** Risk.md §4.4 — 42, 2 dependants, retire 65, 55% LTV home. */
const EXAMPLE: Pick<
  GpSession,
  | 'age'
  | 'ageOfRetirement'
  | 'dependents'
  | 'incomeMonthly'
  | 'expenseMonthly'
  | 'cash'
  | 'investments'
  | 'property'
  | 'mortgage'
  | 'loanRate'
> = {
  age: 42,
  ageOfRetirement: 65,
  dependents: 2,
  incomeMonthly: 25_000,
  expenseMonthly: 17_485,
  cash: 142_000,
  investments: 805_000,
  property: 850_000,
  mortgage: 468_000,
  loanRate: 0,
};

test('Risk.md §4.4 example is Medium-High (4)', () => {
  const got = riskCapacity(EXAMPLE);
  assert.equal(got.factors.liquidityPts, 4);
  assert.equal(got.factors.dsrPts, 5);
  assert.equal(got.factors.darPts, 4);
  assert.equal(got.factors.savingsPts, 5);
  assert.equal(got.factors.horizonPts, 4);
  assert.equal(got.factors.dependantsPts, 3);
  assert.ok(Math.abs(got.raw - 4.25) < 1e-9);
  assert.equal(got.rounded, 4);
  assert.equal(got.capacity, 4);
  assert.equal(got.capReason, null);
});

test('cash below 3 months hard-caps at Low-Medium (2)', () => {
  const got = riskCapacity({ ...EXAMPLE, cash: 2 * 17_485 });
  assert.equal(got.factors.liquidityPts, 2);
  assert.equal(got.rounded, 4);
  assert.equal(got.capacity, 2);
  assert.match(got.capReason ?? '', /3 months/);
});

test('DSR above 50% hard-caps at Low-Medium (2)', () => {
  const got = riskCapacity({
    ...EXAMPLE,
    incomeMonthly: 5_000,
    expenseMonthly: 3_000,
    cash: 40_000,
    mortgage: 800_000,
  });
  assert.ok(got.factors.dsr > 0.5);
  assert.equal(got.capacity, 2);
  assert.match(got.capReason ?? '', /debt/i);
});

test('horizon under 10 years hard-caps at Medium (3)', () => {
  const got = riskCapacity({
    ...EXAMPLE,
    age: 58,
    cash: 200_000,
    mortgage: 50_000,
    dependents: 0,
  });
  assert.ok(got.factors.horizonYears < 10);
  assert.ok(got.rounded >= 3);
  assert.equal(got.capacity, 3);
  assert.match(got.capReason ?? '', /10 years/);
});

test('suitable band is min(capacity, tolerance)', () => {
  assert.equal(suitableRisk(4, 3), 3);
  assert.equal(suitableRisk(2, 5), 2);
  assert.equal(suitableRisk(5, 5), 5);
});

test('suggested net return and soft ceiling by band', () => {
  assert.equal(suggestedNetReturn(1), 0.03);
  assert.equal(suggestedNetReturn(3), 0.042);
  assert.equal(suggestedNetReturn(5), 0.055);
  assert.equal(netReturnCeiling(1), 0.042);
  assert.equal(netReturnCeiling(5), 0.065);
});

test('DSR at 0% is principal over 240 months; 3.5% is about 14.3% from 10.27%', () => {
  const mortgage = 246_480;
  const income = 10_000;
  const zero = debtServiceRatio(mortgage, income, 0);
  const priced = debtServiceRatio(mortgage, income, 0.035);
  assert.ok(Math.abs(zero * 100 - 10.27) < 0.01);
  assert.ok(Math.abs(priced * 100 - 14.32) < 0.05);
  assert.equal(monthlyLoanPayment(240_000, 0), 1000);
});

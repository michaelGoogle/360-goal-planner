import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  currencyForCountry,
  formatMoney,
  formatMoneyK,
  rateAsOfLabel,
  sessionCountry,
  sessionCurrency,
} from './currency';

test('Vietnam maps to VND and Singapore stays SGD', () => {
  assert.equal(currencyForCountry('Vietnam'), 'VND');
  assert.equal(currencyForCountry('Singapore'), 'SGD');
});

test('session currency falls back from nationality when currency is unset', () => {
  assert.equal(sessionCountry({ nationality: 'Vietnam' }), 'Vietnam');
  assert.equal(sessionCurrency({ nationality: 'Vietnam' }), 'VND');
  assert.equal(sessionCurrency({ currency: 'SGD', nationality: 'Vietnam' }), 'SGD');
});

test('formatMoney labels VND without converting', () => {
  assert.equal(formatMoney(1500, 'SGD'), 'S$1,500');
  assert.match(formatMoney(25_000_000, 'VND'), /₫/);
  assert.match(formatMoney(25_000_000, 'VND'), /25/);
});

test('formatMoneyK shortens large amounts in the same currency', () => {
  assert.equal(formatMoneyK(1_200_000, 'SGD'), 'S$1.2m');
  assert.match(formatMoneyK(25_000_000, 'VND'), /m/);
});

test('rate as-of uses the lock date when present', () => {
  assert.equal(rateAsOfLabel(undefined, 'SGD'), 'Amounts in SGD');
  assert.equal(
    rateAsOfLabel({ currency: 'VND', asOf: '2026-09-25T00:00:00Z' }, 'VND'),
    'Amounts in VND · rate as of 2026-09-25',
  );
});

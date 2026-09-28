/**
 * Session country / currency and display of user-currency amounts.
 *
 * Need amounts already arrive in the locked currency. This module only labels
 * them — it does not convert. The country list matches income_anchors.json.
 */

export const COUNTRY_CURRENCY: Record<string, string> = {
  singapore: 'SGD',
  vietnam: 'VND',
  malaysia: 'MYR',
  thailand: 'THB',
  philippines: 'PHP',
  australia: 'AUD',
  germany: 'EUR',
  'hong kong': 'HKD',
  usa: 'USD',
  'united states': 'USD',
};

const SYMBOL: Record<string, string> = {
  SGD: 'S$',
  USD: 'US$',
  VND: '₫',
  MYR: 'RM',
  THB: '฿',
  AUD: 'A$',
  HKD: 'HK$',
  PHP: '₱',
  EUR: '€',
};

export function currencyForCountry(country: string): string {
  const key = (country || 'Singapore').trim().toLowerCase();
  return COUNTRY_CURRENCY[key] || 'SGD';
}

export function sessionCountry(s: { country?: string; nationality?: string }): string {
  return s.country || s.nationality || 'Singapore';
}

export function sessionCurrency(s: { currency?: string; country?: string; nationality?: string }): string {
  return s.currency || currencyForCountry(sessionCountry(s));
}

export function currencySymbol(currency: string): string {
  const iso = (currency || 'SGD').toUpperCase();
  return SYMBOL[iso] || `${iso} `;
}

export function formatMoney(n: number, currency = 'SGD'): string {
  const v = Math.round(n);
  if (!Number.isFinite(v)) return '—';
  const loc = currency.toUpperCase() === 'VND' ? 'vi-VN' : 'en-SG';
  return (v < 0 ? '−' : '') + currencySymbol(currency) + Math.abs(v).toLocaleString(loc);
}

export function formatMoneyK(n: number, currency = 'SGD'): string {
  const v = Math.round(n);
  if (!Number.isFinite(v)) return '—';
  const sym = currencySymbol(currency);
  const sign = v < 0 ? '−' : '';
  if (Math.abs(v) >= 1e6) {
    const m = v / 1e6;
    const s = m.toFixed(1).replace(/\.0$/, '');
    return sign + sym + s + 'm';
  }
  if (Math.abs(v) >= 1000) return sign + sym + Math.round(Math.abs(v) / 1000) + 'k';
  return formatMoney(v, currency);
}

export function rateAsOfLabel(fx?: { currency?: string; asOf?: string } | null, currency?: string): string {
  const ccy = currency || fx?.currency || 'SGD';
  const day = fx?.asOf ? fx.asOf.slice(0, 10) : '';
  return day ? `Amounts in ${ccy} · rate as of ${day}` : `Amounts in ${ccy}`;
}

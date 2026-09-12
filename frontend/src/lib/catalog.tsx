import type { ReactNode } from 'react';
import { spendSharePct, type DocKind, type GpSession } from './types';

export const D2C_GEN = ['Male', 'Female'] as const;
export const D2C_RES = ['Singapore Citizen', 'Permanent Resident', 'Foreigner'] as const;
export const D2C_DEPS = ['0', '1', '2', '3', '4+'] as const;

export const D2C_RDLBL: Record<string, string> = {
  age: 'Age',
  gender: 'Gender',
  deps: 'Dependants',
  res: 'Residency',
  nat: 'Nationality',
  occ: 'Occupation',
  name: 'Name',
};

export const D2C_REQF = ['name', 'age', 'gender', 'deps', 'res', 'occ'] as const;
export const D2C_ORDF = ['name', 'age', 'gender', 'deps', 'res', 'occ'] as const;

export const D2C_DOCS: [DocKind, string, string][] = [
  ['cpf', 'CPF statement', 'Balances in your Ordinary, Special and Medisave accounts'],
  ['bank', 'Bank or CDP statement', 'Cash, savings and what you hold in investments'],
  ['pol', 'Insurance policy', 'Type of cover, sum assured and what you pay for it'],
];

export const D2C_DOCF: Record<DocKind, [string, string, 'n' | 't'][]> = {
  cpf: [
    ['oa', 'Ordinary Account', 'n'],
    ['sa', 'Special Account', 'n'],
    ['ma', 'Medisave Account', 'n'],
  ],
  bank: [
    ['cash', 'Cash and savings', 'n'],
    ['investments', 'Investments', 'n'],
  ],
  pol: [
    ['type', 'Type of cover', 't'],
    ['insurer', 'Insurer', 't'],
    ['sum', 'Sum assured', 'n'],
    ['premium', 'Annual premium', 'n'],
  ],
};

function depsPhrase(n: number): string {
  if (n <= 0) return 'no dependants';
  if (n === 1) return '1 dependant';
  return `${n} dependants`;
}

export const TIPS: Record<string, { title: string; body: ReactNode | ((s: GpSession) => ReactNode) }> = {
  income: {
    title: 'Money coming in · per month',
    body: (
      <>
        <p>
          <b>Gross, before your own CPF, including bonus.</b> The top of the payslip — salary plus one twelfth of any
          annual bonus, self-employed or business income, rental and any other regular income. Not after income tax.
          Your employer&apos;s CPF is not part of it.
        </p>
        <p>
          If this line is still a People like you estimate, it is a typical monthly figure for your occupation, age,
          and location, using public salary references such as Glassdoor-style market ranges and local pay scales. It
          is not your payslip.
        </p>
        <p className="m">
          Your CPF is taken off this figure on the next line. Money going out is a share of what is left after that.
        </p>
      </>
    ),
  },
  expense: {
    title: 'Money going out · per month',
    body: (s: GpSession) => (
      <>
        <p>
          After your own CPF, not from gross. With {depsPhrase(s.dependents)}, this is {spendSharePct(s.dependents)}% of
          take-home.
        </p>
        <p>
          Everything you actually spend from take-home: housing and loan repayments, food, transport, childcare,
          parents, and insurance premiums. Leave out your own CPF — that is the line above. Leave out what you
          save or invest; that is what the budget below measures.
        </p>
        <p className="m">
          The chart folds your CPF into money going out so the picture stays simple. This row does the same.
        </p>
        <p className="m">Spending is the figure people are most often wrong about. Three months of statements beats a guess.</p>
      </>
    ),
  },
  savings: {
    title: 'Cash & Savings · today',
    body: (
      <>
        <p>
          Short-term liquidity: cash at bank, deposits, and other money you could reach quickly. A balance, not a
          monthly amount. Grows more slowly than investments.
        </p>
        <p className="m">Not CPF: that is projected separately. Not property — that has its own line. Not funds or ETFs — those sit under Investments.</p>
      </>
    ),
  },
  investments: {
    title: 'Investments · today',
    body: (
      <>
        <p>Longer-term holdings — typically over five years: mutual funds, ETFs, shares, and similar. A balance, not a monthly amount.</p>
        <p className="m">Cash, deposits, and endowments sit under Cash &amp; Savings. CPF and property have their own lines.</p>
      </>
    ),
  },
  property: {
    title: 'Property · today',
    body: (
      <>
        <p>What your home, and any other property you own, would sell for today. Not what you paid for it, and not the amount left on the mortgage.</p>
      </>
    ),
  },
  loans: {
    title: 'Loans outstanding · today',
    body: (
      <>
        <p>What you still owe: the mortgage balance, car and renovation loans, study loans, and any card balance you carry rather than clear.</p>
        <p className="m">Your family would have to settle these, so they raise the protection you need.</p>
      </>
    ),
  },
  net: {
    title: 'Net wealth',
    body: <p>What you own less what you owe. It is the base your goals are funded from — the score cares more about it than about income.</p>,
  },
  cover: {
    title: 'What cover you have',
    body: (
      <>
        <p>The sum assured on policies you hold today. Every dollar here is subtracted from what you need, so cover you forget to add shows up as a bigger gap than you really have.</p>
        <p className="m">Add anything missing — the shortfalls above update as you do.</p>
      </>
    ),
  },
  cpf: {
    title: 'Your CPF · per month',
    body: (
      <>
        <p>
          <b>Your employee contribution only</b> — not what your employer adds. Citizens and PRs: 20% of ordinary wage
          to age 55, then 15% / 9.5% / 5%. Foreigners: none, so this line is S$0.
        </p>
        <p>
          Ordinary wage is capped at <b>S$8,000 a month</b> from 2026, so the most taken off pay is S$1,600 at the 20%
          rate. The older S$1,200 figure was 20% of the previous S$6,000 ceiling.
        </p>
        <p className="m">This line is calculated from money coming in, age, and residency. It cannot be edited here.</p>
      </>
    ),
  },
  budget: {
    title: 'Available budget · per month',
    body: (
      <>
        <p>Money coming in, less your CPF, less money going out. What is left to save, invest or put towards a goal.</p>
        <p className="m">
          The donut treats CPF as part of money going out so income splits into outgoings and leftover. Your CPF is
          not something you edit.
        </p>
      </>
    ),
  },
};

export const EDIT_HINT: Record<string, string> = {
  income: 'Gross, before your own CPF, including a twelfth of any bonus.',
  expense: 'Spend including your CPF contribution.',
  savings: 'Cash, deposits and other short-term liquidity. Not investments, CPF, or property.',
  investments: 'Funds, ETFs and other longer-term holdings. Not Cash & Savings, CPF, or property.',
  property: 'What it would sell for today, not what you paid.',
  loans: 'Everything still outstanding, mortgage included.',
};

export const X_RATIO_WHY: Record<string, [string, string]> = {
  liq: [
    'How long could you keep going with no income at all? We divide the cash you could reach tomorrow by what you spend in a month. Three to six months is the usual advice: enough to ride out a job loss or a hospital stay without selling something or borrowing.',
    'Cash and deposits ÷ monthly expenses',
  ],
  lnw: [
    'How much of what you own could you actually spend this week? Property and pensions count towards your wealth but cannot be turned into money quickly. If almost everything you own is locked up, you are wealthy on paper and stuck in practice.',
    'Cash and deposits ÷ net worth',
  ],
  dsr: [
    'What share of every pay cheque is already promised to a lender before you spend on anything else? Above roughly a third, a rate rise or a month out of work starts to hurt immediately, because the repayment does not shrink when your income does.',
    'Loan repayments ÷ monthly income',
  ],
  dar: [
    'How much of what you own is really the bank’s? A house bought mostly on a mortgage counts fully as an asset but is largely borrowed. Above half, a fall in property or market values wipes out net worth faster than most people expect.',
    'Total borrowing ÷ total assets',
  ],
  sav: [
    'What proportion of your income survives the month? This is the single figure that decides how fast every other goal on this page arrives — every projection here is driven by what you put away, not by what you earn.',
    '(Income − expenses) ÷ income',
  ],
  inw: [
    'How much of your wealth is working rather than sitting still? Cash is safe and loses to inflation every year. Over a horizon as long as the one on your plan screen, the split between invested and idle matters more than the return on either.',
    'Invested assets ÷ net worth',
  ],
};

export const COUNTRIES = [
  'Singapore',
  'Australia',
  'Bangladesh',
  'Canada',
  'China',
  'France',
  'Germany',
  'Hong Kong SAR',
  'India',
  'Indonesia',
  'Japan',
  'Malaysia',
  'Myanmar',
  'New Zealand',
  'Philippines',
  'South Korea',
  'Sri Lanka',
  'Taiwan',
  'Thailand',
  'United Arab Emirates',
  'United Kingdom',
  'United States of America',
  'Vietnam',
  'Other',
];

export const OCCUPATIONS = [
  'Accountant',
  'Actuary',
  'Architect',
  'Auditor',
  'Business Analyst',
  'Business Owner',
  'Chief Executive Officer',
  'Chief Financial Officer',
  'Chief Technology Officer',
  'Civil Engineer',
  'Consultant',
  'Data Scientist',
  'Dentist',
  'Doctor / General Practitioner',
  'Engineer',
  'Entrepreneur',
  'Financial Adviser',
  'Financial Analyst',
  'General Manager',
  'Homemaker',
  'Investment Banker',
  'Lawyer',
  'Lecturer',
  'Manager',
  'Medical Specialist',
  'Nurse',
  'Operations Manager',
  'Pharmacist',
  'Pilot',
  'Product Manager',
  'Project Manager',
  'Retired',
  'Risk Manager',
  'Sales Manager',
  'Software Developer',
  'Software Engineer',
  'Student',
  'Surgeon',
  'Teacher',
  'Web Developer',
];

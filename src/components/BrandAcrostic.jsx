import React from 'react';
import { Link } from 'react-router-dom';
import { useLanguage } from '../context/LanguageContext';

const LETTERS = [
  { letter: 'L', key: 'brandAcrosticL' },
  { letter: 'A', key: 'brandAcrosticA' },
  { letter: 'R', key: 'brandAcrosticR' },
  { letter: 'O', key: 'brandAcrosticO' },
];

export const BrandAcrostic = ({ className = '', testId = 'brand-acrostic' }) => {
  const { t } = useLanguage();
  return (
    <ul
      className={`flex flex-wrap justify-center gap-x-5 gap-y-1 ${className}`}
      data-testid={testId}
    >
      {LETTERS.map((row) => (
        <li key={row.letter} className="flex items-baseline gap-1.5">
          <span className="font-heading font-semibold text-laro-brand">
            {row.letter}
          </span>
          <span className="text-sm text-foreground/70 tracking-tight">
            {t(row.key)}
          </span>
        </li>
      ))}
    </ul>
  );
};

export const BrandLockup = ({ to = '/', imgClass = 'h-12', className = '' }) => {
  const { t } = useLanguage();
  return (
    <Link to={to} className={`flex flex-col items-center gap-2 ${className}`}>
      <img
        src="/laro-banner.png"
        alt={`${t('brandName')}: ${t('brandAcrosticLine')}`}
        className={imgClass}
      />
      <p className="text-xs text-muted-foreground text-center tracking-tight">
        {t('brandAcrosticLine')}
      </p>
    </Link>
  );
};

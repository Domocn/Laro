import React from 'react';
import { useLanguage } from '../context/LanguageContext';

export const MEASUREMENT_UNIT_VALUES = ['as_written', 'metric', 'imperial', 'both'];

export function MeasurementUnitPicker({
  value = 'metric',
  onChange,
  showBoth = true,
  compact = false,
  layout,
  testId = 'measurement-unit-picker',
}) {
  const { t } = useLanguage();
  const useGrid = layout === 'grid' || (!compact && layout !== 'wrap');
  const options = [
    {
      id: 'as_written',
      label: t('unitsAsWritten'),
      hint: t('unitsAsWrittenShort'),
    },
    {
      id: 'metric',
      label: t('metric'),
      hint: t('metricShort'),
    },
    {
      id: 'imperial',
      label: t('imperial'),
      hint: t('imperialShort'),
    },
  ];
  if (showBoth) {
    options.push({
      id: 'both',
      label: t('showBoth'),
      hint: t('unitsBothShort'),
    });
  }

  if (useGrid) {
    return (
      <div
        className="grid grid-cols-2 gap-2"
        role="radiogroup"
        aria-label={t('measurementUnits')}
        data-testid={testId}
      >
        {options.map((opt) => {
          const selected = value === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              aria-pressed={selected}
              data-testid={`units-${opt.id}`}
              onClick={() => onChange?.(opt.id)}
              className={`box-border w-full min-h-[3.25rem] h-auto rounded-xl px-3 py-2 text-left border-2 transition-colors appearance-none ${
                selected
                  ? 'border-laro bg-laro/10 text-laro'
                  : 'border-border/60 bg-background text-foreground hover:border-laro/50'
              }`}
            >
              <span className="block text-sm font-medium leading-tight">{opt.label}</span>
              <span
                className={`block text-xs leading-snug mt-0.5 ${
                  selected ? 'text-laro/80' : 'text-muted-foreground'
                }`}
              >
                {opt.hint}
              </span>
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      className="flex flex-wrap gap-2"
      role="radiogroup"
      aria-label={t('measurementUnits')}
      data-testid={testId}
    >
      {options.map((opt) => {
        const selected = value === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            aria-pressed={selected}
            data-testid={`units-${opt.id}`}
            onClick={() => onChange?.(opt.id)}
            className={`shrink-0 h-auto whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium border-2 transition-colors appearance-none ${
              selected
                ? 'border-laro bg-laro/10 text-laro'
                : 'bg-background border-border/60 text-foreground/80 hover:border-laro/40'
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

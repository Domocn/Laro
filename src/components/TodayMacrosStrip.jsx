import React from 'react';
import { useLanguage } from '../context/LanguageContext';
import { nutritionStatus } from '../lib/mealPlanNutrition';

const CHIP = ({ label, value, unit, highlight }) => (
  <div
    className={`rounded-full px-3 py-1 text-sm tabular-nums ${
      highlight ? 'bg-laro text-white' : 'bg-cream-subtle text-foreground'
    }`}
  >
    <span className="font-semibold">{value}</span>
    {unit ? <span className="text-xs ml-0.5 opacity-90">{unit}</span> : null}
    <span className="text-xs ml-1 opacity-80">{label}</span>
  </div>
);

export function TodayMacrosStrip({ totals, proteinTarget, calorieTarget }) {
  const { t } = useLanguage();
  const status = nutritionStatus(totals, { proteinTarget, calorieTarget });

  if (!totals?.hasAnyNutrition) {
    if (totals?.recipeMeals > 0) {
      return (
        <p className="text-sm text-muted-foreground" data-testid="today-macros-empty">
          {t('todayMacrosEmpty')}
        </p>
      );
    }
    return null;
  }

  const tone =
    status.overall === 'green'
      ? 'border-emerald-200 bg-emerald-50/60'
      : status.overall === 'amber'
        ? 'border-amber-200 bg-amber-50/60'
        : 'border-border/60 bg-cream-subtle/50';

  return (
    <div
      className={`rounded-xl border px-3 py-3 space-y-2 ${tone}`}
      data-testid="today-macros"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {t('todayMacrosTitle')}
      </p>
      <div className="flex flex-wrap gap-2 items-center">
        <CHIP
          label={t('protein')}
          value={
            proteinTarget != null
              ? `${totals.protein}/${Math.round(proteinTarget)}`
              : totals.protein
          }
          unit="g"
          highlight={status.protein === 'met'}
        />
        {calorieTarget != null && (
          <CHIP
            label={t('calories')}
            value={`${totals.calories}/${Math.round(calorieTarget)}`}
            unit=""
            highlight={status.calories === 'met'}
          />
        )}
        {calorieTarget == null && totals.calories > 0 && (
          <CHIP label={t('calories')} value={totals.calories} unit="kcal" />
        )}
        {totals.carbs > 0 && (
          <CHIP label={t('carbs')} value={totals.carbs} unit="g" />
        )}
        {totals.fat > 0 && <CHIP label={t('fat')} value={totals.fat} unit="g" />}
      </div>
      <p className="text-[10px] text-muted-foreground">{t('todayMacrosFromPlan')}</p>
    </div>
  );
}

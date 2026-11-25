import React, { useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import {
  DEFAULT_PROTEIN_MIN,
  MACRO_FIELDS,
  MACRO_PRESETS,
  PROTEIN_QUICK_PICKS,
  isMacroFilterActive,
} from '../lib/macroFilter';

const cap = (f) => f.charAt(0).toUpperCase() + f.slice(1);
const FIELD_KEYS = { calories: 'macroCaloriesKcal', protein: 'macroProteinG', carbs: 'macroCarbsG', fat: 'macroFatG' };

/** Per-serving macro chips (presets + Custom range) under the category chips. */
const PROTEIN_KEY = 'laro_protein_min';
const savedProtein = () => {
  try {
    return Number(localStorage.getItem(PROTEIN_KEY)) || DEFAULT_PROTEIN_MIN;
  } catch {
    return DEFAULT_PROTEIN_MIN;
  }
};

export function MacroFilterBar({ presetIds, custom, proteinMin, onProteinMinChange, onTogglePreset, onCustomChange, onClear }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(custom);
  const [proteinOpen, setProteinOpen] = useState(false);
  const [proteinDraft, setProteinDraft] = useState('');
  const customActive = isMacroFilterActive(custom);
  const anyActive = presetIds.length > 0 || customActive || !!proteinMin;
  const proteinGrams = Number(proteinDraft) > 0 && Number(proteinDraft) <= 300 ? Number(proteinDraft) : null;
  const applyProtein = () => {
    if (!proteinGrams) return;
    try {
      localStorage.setItem(PROTEIN_KEY, String(proteinGrams));
    } catch {
      /* private mode */
    }
    onProteinMinChange(proteinGrams);
    setProteinOpen(false);
  };

  const chip = (active) =>
    `px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
      active ? 'bg-laro text-white shadow-sm' : 'bg-white text-foreground border border-border/60 hover:bg-laro-light'
    }`;

  const setField = (key, value) => setDraft((d) => ({ ...d, [key]: value.replace(/[^0-9]/g, '').slice(0, 4) }));
  const clean = (d) =>
    Object.fromEntries(Object.entries(d).filter(([, v]) => v !== '' && v !== null && v !== undefined).map(([k, v]) => [k, Number(v)]));

  return (
    <div className="space-y-2" data-testid="macro-filter-bar">
      <div className="flex flex-wrap gap-2 items-center">
        <button
          type="button"
          onClick={() => {
            setProteinDraft(String(proteinMin || savedProtein()));
            setOpen(false);
            setProteinOpen((o) => !o);
          }}
          className={chip(!!proteinMin)}
          aria-expanded={proteinOpen}
          data-testid="macro-protein"
        >
          💪 {proteinMin ? t('macroProteinAtLeast', { grams: proteinMin }) : `${t('macroHighProtein')}…`}
        </button>
        {MACRO_PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => onTogglePreset(p.id)}
            className={chip(presetIds.includes(p.id))}
            aria-pressed={presetIds.includes(p.id)}
            data-testid={`macro-${p.id}`}
          >
            {p.emoji} {t(p.labelKey)}
          </button>
        ))}
        <button
          type="button"
          onClick={() => {
            setDraft(custom);
            setProteinOpen(false);
            setOpen((o) => !o);
          }}
          className={chip(customActive)}
          aria-expanded={open}
          data-testid="macro-custom"
        >
          ⚙️ {t('macroCustom')}
          {customActive ? ' ✓' : '…'}
        </button>
        {anyActive && (
          <Button variant="ghost" size="sm" className="rounded-full" onClick={onClear} data-testid="macro-clear">
            {t('macroClear')}
          </Button>
        )}
      </div>

      {proteinOpen && (
        <div className="bg-white rounded-2xl border border-border/60 p-4 space-y-3" data-testid="macro-protein-panel">
          <p className="text-sm text-muted-foreground">{t('macroProteinHint')}</p>
          <div className="flex flex-wrap gap-2">
            {PROTEIN_QUICK_PICKS.map((g) => (
              <button
                key={g}
                type="button"
                className={chip(proteinGrams === g)}
                onClick={() => setProteinDraft(String(g))}
                data-testid={`macro-protein-${g}`}
              >
                {g} g
              </button>
            ))}
          </div>
          <div className="flex gap-2 items-center max-w-xs">
            <Input
              inputMode="numeric"
              aria-label={t('macroProteinG')}
              value={proteinDraft}
              onChange={(e) => setProteinDraft(e.target.value.replace(/[^0-9]/g, '').slice(0, 3))}
              onKeyDown={(e) => e.key === 'Enter' && applyProtein()}
              data-testid="macro-protein-input"
            />
            <span className="text-sm text-muted-foreground">g</span>
          </div>
          <div className="flex gap-2 justify-end">
            {!!proteinMin && (
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => {
                  onProteinMinChange(null);
                  setProteinOpen(false);
                }}
              >
                {t('macroTurnOff')}
              </Button>
            )}
            <Button
              className="rounded-full bg-laro hover:bg-laro-dark"
              disabled={!proteinGrams}
              onClick={applyProtein}
              data-testid="macro-protein-apply"
            >
              {t('macroShowRecipes')}
            </Button>
          </div>
        </div>
      )}

      {open && (
        <div className="bg-white rounded-2xl border border-border/60 p-4 space-y-3" data-testid="macro-custom-panel">
          <p className="text-sm text-muted-foreground">{t('macroCustomHint')}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {MACRO_FIELDS.map((f) => (
              <div key={f}>
                <div className="text-sm font-medium mb-1">{t(FIELD_KEYS[f])}</div>
                <div className="flex gap-2">
                  <Input
                    inputMode="numeric"
                    placeholder={t('macroMin')}
                    aria-label={`${t(FIELD_KEYS[f])} ${t('macroMin')}`}
                    value={draft[`min${cap(f)}`] ?? ''}
                    onChange={(e) => setField(`min${cap(f)}`, e.target.value)}
                  />
                  <Input
                    inputMode="numeric"
                    placeholder={t('macroMax')}
                    aria-label={`${t(FIELD_KEYS[f])} ${t('macroMax')}`}
                    value={draft[`max${cap(f)}`] ?? ''}
                    onChange={(e) => setField(`max${cap(f)}`, e.target.value)}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              className="rounded-full"
              onClick={() => {
                setDraft({});
                onCustomChange({});
                setOpen(false);
              }}
            >
              {t('macroReset')}
            </Button>
            <Button
              className="rounded-full bg-laro hover:bg-laro-dark"
              onClick={() => {
                onCustomChange(clean(draft));
                setOpen(false);
              }}
              data-testid="macro-apply"
            >
              {t('macroApply')}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

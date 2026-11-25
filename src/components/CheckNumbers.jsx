import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, ChevronUp, Loader2, PencilLine, ScanBarcode, Tag, Undo2, X } from 'lucide-react';
import { toast } from 'sonner';
import { checkNumbersApi } from '../lib/api';
import {
  amountText,
  confirmedPayload,
  effectiveMacros,
  hasEdits,
  labelToMacros,
  overrideFrom,
  readSkipCheck,
  splitLines,
  totalsFor,
  writeSkipCheck,
} from '../lib/checkNumbers';
import { useLanguage } from '../context/LanguageContext';
import { Button } from './ui/button';

// "Check the numbers": before cooking (Cook Mode) or from the recipe page. One screen, short
// copy, big targets, no timers, no motion. Never blocks cooking: Skip is always there.

const UNITS = ['g', 'ml', 'tbsp', 'tsp', 'cup', 'whole'];

function useText() {
  const { t } = useLanguage();
  return useCallback(
    (key, fallback, params) => {
      let s = t(key, params);
      if (!s || s === key) {
        s = fallback;
        Object.entries(params || {}).forEach(([k, v]) => {
          s = s.replaceAll(`{${k}}`, String(v));
        });
      }
      return s;
    },
    [t],
  );
}

function errorText(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.length < 200) return detail;
  return fallback;
}

const CHIP_STYLES = {
  'AI estimate': 'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-900/40 dark:text-amber-100',
  'No estimate yet': 'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-900/40 dark:text-amber-100',
  'You checked': 'bg-laro/15 text-foreground border-laro/40',
  Barcode: 'bg-laro/15 text-foreground border-laro/40',
};

function SourceChip({ label }) {
  const style = CHIP_STYLES[label] || 'bg-emerald-50 text-emerald-900 border-emerald-300 dark:bg-emerald-900/40 dark:text-emerald-100';
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${style}`}>
      {label}
    </span>
  );
}

function MacroLine({ macros, tx }) {
  if (!macros) return <span className="text-muted-foreground">{tx('checkNoNumbers', 'No numbers yet')}</span>;
  return (
    <span className="tabular-nums">
      <strong className="font-semibold">{macros.cal} kcal</strong>
      <span className="text-muted-foreground">
        {' · '}P {macros.p} g · C {macros.c} g · F {macros.f} g
        {macros.g != null ? ` · ${macros.g} g used` : ''}
      </span>
    </span>
  );
}

function Field({ id, label, children, hint }) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  );
}

const inputClass =
  'h-12 w-full rounded-xl border border-input bg-background px-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function ResultPreview({ result, onUse, tx, food }) {
  if (!result) return null;
  return (
    <div className="mt-3 rounded-xl border border-laro/40 bg-laro/5 p-3 flex flex-col sm:flex-row sm:items-center gap-3">
      <div className="flex-1 min-w-0 text-sm">
        {result.product && <p className="font-medium truncate">{result.product}</p>}
        <MacroLine macros={result.macros} tx={tx} />
      </div>
      <Button type="button" className="h-12 rounded-full px-5 bg-laro hover:bg-laro-dark" onClick={onUse}
        aria-label={tx('checkUseFor', 'Use these numbers for {food}', { food })}>
        <Check className="w-4 h-4" aria-hidden="true" />
        {tx('checkUse', 'Use these numbers')}
      </Button>
    </div>
  );
}

function AmountPanel({ row, ctx, onApply, tx }) {
  const [amount, setAmount] = useState('');
  const [unit, setUnit] = useState('g');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const id = `cn-amount-${row.index}`;
  const work = async (e) => {
    e?.preventDefault();
    setError('');
    setResult(null);
    if (!amount.trim()) {
      setError(tx('checkTypeAmount', 'Type how much you used.'));
      return;
    }
    setBusy(true);
    try {
      const res = await ctx.api.estimate(ctx.recipeId, {
        version: ctx.version || null,
        low_fodmap: ctx.lowFodmap,
        index: row.index,
        mode: 'amount',
        amount: amount.trim(),
        unit: unit === 'whole' ? '' : unit,
      });
      setResult(res.data);
    } catch (err) {
      setError(errorText(err, tx('checkCouldntWorkOut', "Couldn't work that out. Try typing the label figures.")));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={work} className="mt-3 rounded-xl border bg-card p-3">
      <div className="grid grid-cols-[1fr_auto] gap-3 items-end">
        <Field id={`${id}-n`} label={tx('checkHowMuch', 'How much did you use?')}>
          <input id={`${id}-n`} className={inputClass} inputMode="decimal" autoComplete="off" value={amount}
            onChange={(e) => setAmount(e.target.value)} placeholder="15" />
        </Field>
        <Field id={`${id}-u`} label={tx('checkUnit', 'Unit')}>
          <select id={`${id}-u`} className={`${inputClass} pr-8`} value={unit} onChange={(e) => setUnit(e.target.value)}>
            {UNITS.map((u) => (
              <option key={u} value={u}>{u === 'whole' ? tx('checkUnitWhole', 'whole') : u}</option>
            ))}
          </select>
        </Field>
      </div>
      <Button type="submit" variant="outline" className="mt-3 h-12 rounded-full px-5" disabled={busy}>
        {busy && <Loader2 className="w-4 h-4 motion-safe:animate-spin" aria-hidden="true" />}
        {tx('checkWorkItOut', 'Work it out')}
      </Button>
      {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
      <ResultPreview result={result} tx={tx} food={row.name}
        onUse={() => onApply({ macros: result.macros, source: 'user', food: result.food })} />
    </form>
  );
}

export function useBarcodeCamera(onCode) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState('');
  const supported = typeof window !== 'undefined' && 'BarcodeDetector' in window && !!navigator.mediaDevices?.getUserMedia;
  const stop = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((tr) => tr.stop());
    streamRef.current = null;
    setActive(false);
  }, []);
  const start = useCallback(async () => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      streamRef.current = stream;
      setActive(true);
      const detector = new window.BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e'] });
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => {});
        }
      }, 50);
      timerRef.current = setInterval(async () => {
        try {
          if (!videoRef.current || videoRef.current.readyState < 2) return;
          const codes = await detector.detect(videoRef.current);
          const raw = codes?.[0]?.rawValue;
          if (raw) {
            stop();
            onCode(raw);
          }
        } catch {
          /* keep looking */
        }
      }, 600);
    } catch {
      setError('Camera not available. Type the barcode number instead.');
      stop();
    }
  }, [onCode, stop]);
  useEffect(() => stop, [stop]);
  return { videoRef, active, error, supported, start, stop };
}

function BarcodePanel({ row, ctx, onApply, tx }) {
  const [code, setCode] = useState('');
  const [grams, setGrams] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const id = `cn-barcode-${row.index}`;
  const camera = useBarcodeCamera(useCallback((raw) => setCode(raw), []));
  const lookUp = async (e) => {
    e?.preventDefault();
    setError('');
    setResult(null);
    if (!code.replace(/\D/g, '')) {
      setError(tx('checkNeedBarcode', 'Scan or type the barcode.'));
      return;
    }
    if (!(Number(grams) > 0)) {
      setError(tx('checkNeedGrams', 'How many grams (or ml) did you use?'));
      return;
    }
    setBusy(true);
    try {
      const res = await ctx.api.estimate(ctx.recipeId, {
        version: ctx.version || null,
        low_fodmap: ctx.lowFodmap,
        index: row.index,
        mode: 'barcode',
        barcode: code.replace(/\D/g, ''),
        used_g: Number(grams),
      });
      setResult(res.data);
    } catch (err) {
      setError(errorText(err, tx('checkProductNotFound', "We couldn't find that product. Type the label figures instead.")));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={lookUp} className="mt-3 rounded-xl border bg-card p-3">
      {camera.supported && (
        <div className="mb-3">
          {camera.active ? (
            <div className="flex flex-col gap-2">
              <video ref={camera.videoRef} className="w-full max-h-56 rounded-xl bg-black object-cover" muted playsInline
                aria-label={tx('checkCameraView', 'Camera view. Point it at the barcode.')} />
              <Button type="button" variant="outline" className="h-12 rounded-full" onClick={camera.stop}>
                {tx('checkStopCamera', 'Stop camera')}
              </Button>
            </div>
          ) : (
            <Button type="button" variant="outline" className="h-12 rounded-full px-5" onClick={camera.start}>
              <ScanBarcode className="w-4 h-4" aria-hidden="true" />
              {tx('checkUseCamera', 'Use camera')}
            </Button>
          )}
          {camera.error && <p role="alert" className="mt-2 text-sm text-destructive">{camera.error}</p>}
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field id={`${id}-code`} label={tx('checkBarcodeNumber', 'Barcode number')}>
          <input id={`${id}-code`} className={inputClass} inputMode="numeric" autoComplete="off" value={code}
            onChange={(e) => setCode(e.target.value)} placeholder="5000000000000" />
        </Field>
        <Field id={`${id}-g`} label={tx('checkGramsUsed', 'Grams (or ml) used')}>
          <input id={`${id}-g`} className={inputClass} inputMode="decimal" autoComplete="off" value={grams}
            onChange={(e) => setGrams(e.target.value)} placeholder="15" />
        </Field>
      </div>
      <Button type="submit" variant="outline" className="mt-3 h-12 rounded-full px-5" disabled={busy}>
        {busy && <Loader2 className="w-4 h-4 motion-safe:animate-spin" aria-hidden="true" />}
        {tx('checkLookUp', 'Look up')}
      </Button>
      {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
      <ResultPreview result={result} tx={tx} food={row.name}
        onUse={() => onApply({ macros: result.macros, source: 'barcode', barcode: result.barcode, product: result.product })} />
    </form>
  );
}

function LabelPanel({ row, onApply, tx }) {
  const [basis, setBasis] = useState('100g');
  const [label, setLabel] = useState({ kcal: '', protein: '', carbs: '', fat: '' });
  const [usedG, setUsedG] = useState('');
  const [packs, setPacks] = useState('1');
  const [packG, setPackG] = useState('');
  const [touched, setTouched] = useState(false);
  const id = `cn-label-${row.index}`;
  const computed = useMemo(() => labelToMacros(label, { basis, usedG, packs, packG }), [label, basis, usedG, packs, packG]);
  const set = (k) => (e) => setLabel((prev) => ({ ...prev, [k]: e.target.value }));
  const submit = (e) => {
    e.preventDefault();
    setTouched(true);
    if (computed.macros) onApply({ macros: computed.macros, source: 'user' });
  };
  return (
    <form onSubmit={submit} className="mt-3 rounded-xl border bg-card p-3">
      <fieldset>
        <legend className="text-sm font-medium mb-2">{tx('checkLabelBasis', 'The label figures are')}</legend>
        <div className="flex flex-wrap gap-2">
          {[['100g', tx('checkPer100', 'Per 100 g / ml')], ['pack', tx('checkPerPack', 'Per pack')]].map(([value, text]) => (
            <label key={value}
              className={`inline-flex items-center gap-2 h-12 px-4 rounded-full border cursor-pointer ${basis === value ? 'border-laro bg-laro/10 font-semibold' : ''}`}>
              <input type="radio" name={`${id}-basis`} value={value} checked={basis === value}
                onChange={() => setBasis(value)} className="w-4 h-4 accent-[rgb(var(--laro-accent-rgb))]" />
              {text}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[['kcal', 'kcal'], ['protein', tx('checkProtein', 'Protein g')], ['carbs', tx('checkCarbs', 'Carbs g')], ['fat', tx('checkFat', 'Fat g')]].map(([k, text]) => (
          <Field key={k} id={`${id}-${k}`} label={text}>
            <input id={`${id}-${k}`} className={inputClass} inputMode="decimal" autoComplete="off" value={label[k]} onChange={set(k)} />
          </Field>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        {basis === '100g' ? (
          <Field id={`${id}-used`} label={tx('checkGramsUsed', 'Grams (or ml) used')}>
            <input id={`${id}-used`} className={inputClass} inputMode="decimal" autoComplete="off" value={usedG}
              onChange={(e) => setUsedG(e.target.value)} placeholder="15" />
          </Field>
        ) : (
          <>
            <Field id={`${id}-packs`} label={tx('checkPacksUsed', 'Packs used')}>
              <input id={`${id}-packs`} className={inputClass} inputMode="decimal" autoComplete="off" value={packs}
                onChange={(e) => setPacks(e.target.value)} />
            </Field>
            <Field id={`${id}-packg`} label={tx('checkPackWeight', 'Pack weight g (optional)')}>
              <input id={`${id}-packg`} className={inputClass} inputMode="decimal" autoComplete="off" value={packG}
                onChange={(e) => setPackG(e.target.value)} />
            </Field>
          </>
        )}
      </div>
      <div className="mt-3 text-sm" aria-live="polite">
        {computed.macros ? <MacroLine macros={computed.macros} tx={tx} /> : touched && (
          <p role="alert" className="text-destructive">{computed.error}</p>
        )}
      </div>
      <Button type="submit" className="mt-3 h-12 rounded-full px-5 bg-laro hover:bg-laro-dark"
        aria-label={tx('checkUseFor', 'Use these numbers for {food}', { food: row.name })}>
        <Check className="w-4 h-4" aria-hidden="true" />
        {tx('checkUse', 'Use these numbers')}
      </Button>
    </form>
  );
}

const PANELS = [
  ['amount', PencilLine, 'checkEnterUsed', 'Enter what I used'],
  ['barcode', ScanBarcode, 'checkScan', 'Scan barcode'],
  ['label', Tag, 'checkTypeLabel', 'Type label'],
];

function LineRow({ row, edit, openPanel, onToggle, onApply, onUndo, ctx, tx }) {
  const macros = effectiveMacros(row, edit ? { [row.index]: edit } : {});
  const checked = !!edit?.macros;
  const label = checked ? (edit.source === 'barcode' ? 'Barcode' : 'You checked') : row.source_label;
  const amount = amountText(row);
  return (
    <li className={`rounded-2xl border p-4 bg-card ${checked ? 'border-laro/50' : ''}`} data-testid={`check-line-${row.index}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 text-base">
          {amount && <span className="font-semibold mr-1.5">{amount}</span>}
          <span>{row.name}</span>
        </p>
        <SourceChip label={label} />
      </div>
      <p className="mt-1 text-sm">
        <MacroLine macros={macros} tx={tx} />
      </p>
      {!checked && row.reasons?.some((r) => r !== row.source_label) && (
        <p className="mt-1 text-xs text-muted-foreground">
          {row.reasons.filter((r) => r !== row.source_label).join(' · ')}
        </p>
      )}
      {edit?.product && <p className="mt-1 text-xs text-muted-foreground truncate">{edit.product}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {checked ? (
          <Button type="button" variant="outline" className="h-12 rounded-full px-5" onClick={() => onUndo(row.index)}
            aria-label={tx('checkUndoFor', 'Undo check for {food}', { food: row.name })}>
            <Undo2 className="w-4 h-4" aria-hidden="true" />
            {tx('checkUndo', 'Undo')}
          </Button>
        ) : (
          <>
            {row.macros && (
              <Button type="button" className="h-12 rounded-full px-5 bg-laro hover:bg-laro-dark"
                onClick={() => onApply(row.index, { macros: row.macros, source: 'user' })}
                aria-label={tx('checkLooksRightFor', 'Looks right: {food}', { food: row.name })}>
                <Check className="w-4 h-4" aria-hidden="true" />
                {tx('checkLooksRight', 'Looks right')}
              </Button>
            )}
            {PANELS.map(([panel, Icon, key, text]) => (
              <Button key={panel} type="button" variant={openPanel === panel ? 'secondary' : 'outline'}
                className="h-12 rounded-full px-4" aria-expanded={openPanel === panel}
                aria-controls={`cn-panel-${row.index}`} onClick={() => onToggle(row.index, panel)}
                aria-label={`${tx(key, text)}: ${row.name}`}>
                <Icon className="w-4 h-4" aria-hidden="true" />
                {tx(key, text)}
              </Button>
            ))}
          </>
        )}
      </div>
      {!checked && openPanel && (
        <div id={`cn-panel-${row.index}`}>
          {openPanel === 'amount' && <AmountPanel row={row} ctx={ctx} tx={tx} onApply={(e) => onApply(row.index, e)} />}
          {openPanel === 'barcode' && <BarcodePanel row={row} ctx={ctx} tx={tx} onApply={(e) => onApply(row.index, e)} />}
          {openPanel === 'label' && <LabelPanel row={row} tx={tx} onApply={(e) => onApply(row.index, e)} />}
        </div>
      )}
    </li>
  );
}

/**
 * mode "cook": shown at the start of Cook Mode; onStart(override) / onSkip().
 * mode "page": opened from the recipe page; onClose(override, { saved }).
 * `initialData` renders without fetching (previews / tests).
 */
export function CheckNumbers({
  recipe,
  versionName = '',
  lowFodmap = false,
  mode = 'cook',
  onStart,
  onSkip,
  onClose,
  api = checkNumbersApi,
  initialData = null,
}) {
  const tx = useText();
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(!initialData);
  const [loadError, setLoadError] = useState('');
  const [edits, setEdits] = useState({});
  const [open, setOpen] = useState(null); // { index, panel }
  const [showAll, setShowAll] = useState(false);
  const [saveForNext, setSaveForNext] = useState(true);
  const [dontAsk, setDontAsk] = useState(() => readSkipCheck(recipe?.id));
  const [saving, setSaving] = useState(false);
  const headingRef = useRef(null);
  const recipeId = recipe?.id;

  useEffect(() => {
    if (initialData) return undefined;
    let cancelled = false;
    setLoading(true);
    api
      .get(recipeId, { version: versionName, lowFodmap })
      .then((res) => {
        if (!cancelled) setData(res.data);
      })
      .catch(() => {
        if (!cancelled) setLoadError(tx('checkLoadFailed', "Couldn't load the numbers. You can still cook."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // tx changes identity every render (LanguageContext): only refetch when the choice changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, recipeId, versionName, lowFodmap, initialData]);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const lines = data?.lines || [];
  const { uncertain, trusted } = useMemo(() => splitLines(lines), [lines]);
  const totals = useMemo(() => totalsFor(lines, edits, data?.servings || recipe?.servings || 1), [lines, edits, data, recipe]);
  const canEdit = data?.can_edit !== false;

  // Nothing uncertain at the start of a cook: don't stop the cook to ask.
  const autoSkipped = useRef(false);
  useEffect(() => {
    if (mode === 'cook' && data && !loading && uncertain.length === 0 && !autoSkipped.current) {
      autoSkipped.current = true;
      onSkip?.();
    }
  }, [mode, data, loading, uncertain.length, onSkip]);

  const ctx = { api, recipeId, version: data?.version ?? versionName, lowFodmap: data?.low_fodmap ?? lowFodmap };

  const applyEdit = (index, edit) => {
    setEdits((prev) => ({ ...prev, [index]: edit }));
    setOpen(null);
  };
  const undoEdit = (index) =>
    setEdits((prev) => {
      const next = { ...prev };
      delete next[index];
      return next;
    });
  const togglePanel = (index, panel) =>
    setOpen((prev) => (prev && prev.index === index && prev.panel === panel ? null : { index, panel }));

  const finish = async () => {
    writeSkipCheck(recipeId, dontAsk);
    const override = overrideFrom(totals, edits);
    let saved = false;
    if (hasEdits(edits) && saveForNext && canEdit) {
      setSaving(true);
      try {
        await api.save(recipeId, {
          version: ctx.version || null,
          low_fodmap: !!ctx.lowFodmap,
          lines: confirmedPayload(lines, edits),
        });
        saved = true;
        toast.success(tx('checkSaved', 'Saved for next time'));
      } catch (err) {
        toast.error(errorText(err, tx('checkSaveFailed', "Couldn't save. Using your numbers for this cook only.")));
      } finally {
        setSaving(false);
      }
    }
    if (mode === 'cook') onStart?.(override, { saved });
    else onClose?.(override, { saved });
  };
  const skip = () => {
    writeSkipCheck(recipeId, dontAsk);
    if (mode === 'cook') onSkip?.();
    else onClose?.(null, { saved: false });
  };

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      skip();
    }
  };

  const choiceLabel = [ctx.version, ctx.lowFodmap ? 'Low FODMAP' : null].filter(Boolean).join(' · ');
  const renderRow = (row) => (
    <LineRow key={row.index} row={row} edit={edits[row.index]} ctx={ctx} tx={tx}
      openPanel={open?.index === row.index ? open.panel : null}
      onToggle={togglePanel} onApply={applyEdit} onUndo={undoEdit} />
  );

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-background text-foreground" role="dialog" aria-modal="true"
      aria-labelledby="check-numbers-title" onKeyDown={onKeyDown} data-testid="check-numbers">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-2xl px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-6">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 id="check-numbers-title" ref={headingRef} tabIndex={-1} className="font-heading text-2xl font-bold outline-none">
                {tx('checkTitle', 'Check the numbers')}
              </h2>
              <p className="mt-1 text-muted-foreground">
                {recipe?.title}
                {choiceLabel ? ` · ${choiceLabel}` : ''}
              </p>
            </div>
            <Button type="button" variant="ghost" size="icon" className="h-12 w-12 rounded-full shrink-0" onClick={skip}
              aria-label={mode === 'cook' ? tx('checkSkip', 'Skip') : tx('close', 'Close')}>
              <X className="w-5 h-5" aria-hidden="true" />
            </Button>
          </div>

          {loading && (
            <p className="mt-8 flex items-center gap-2 text-muted-foreground" role="status">
              <Loader2 className="w-5 h-5 motion-safe:animate-spin" aria-hidden="true" />
              {tx('checkLoading', 'Getting the numbers…')}
            </p>
          )}
          {loadError && <p className="mt-8 text-base" role="alert">{loadError}</p>}

          {data && !loading && (
            <>
              <p className="mt-4 text-base">
                {uncertain.length > 0
                  ? tx('checkIntro', '{n} of these are guesses. Check them if you like. It only takes a moment.', { n: uncertain.length })
                  : tx('checkAllGood', 'Every line comes from a food label or database.')}
              </p>
              {!canEdit && (
                <p className="mt-2 text-sm text-muted-foreground">
                  {tx('checkReadOnly', "You can't change this recipe, so fixes count for this cook only.")}
                </p>
              )}
              {uncertain.length > 0 && <ul className="mt-4 flex flex-col gap-3">{uncertain.map(renderRow)}</ul>}
              {trusted.length > 0 && (
                <div className="mt-5">
                  <Button type="button" variant="ghost" className="h-12 rounded-full px-4" aria-expanded={showAll}
                    aria-controls="check-numbers-trusted" onClick={() => setShowAll((v) => !v)}>
                    {showAll ? <ChevronUp className="w-4 h-4" aria-hidden="true" /> : <ChevronDown className="w-4 h-4" aria-hidden="true" />}
                    {showAll
                      ? tx('checkHideAll', 'Hide the other ingredients')
                      : tx('checkShowAll', 'Show all ingredients ({n} more)', { n: trusted.length })}
                  </Button>
                  {showAll && <ul id="check-numbers-trusted" className="mt-3 flex flex-col gap-3">{trusted.map(renderRow)}</ul>}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="border-t bg-card/95 backdrop-blur px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <div className="mx-auto w-full max-w-2xl">
          {data && (
            <p className="text-base tabular-nums" aria-live="polite" data-testid="check-numbers-totals">
              <span className="text-muted-foreground">{tx('checkPerServing', 'Per serving')}: </span>
              <strong>{totals.calories} kcal</strong>
              <span className="text-muted-foreground"> · P {totals.protein} g · C {totals.carbs} g · F {totals.fat} g</span>
              {!totals.complete && (
                <span className="block text-xs text-muted-foreground">
                  {tx('checkIncomplete', 'Some lines have no numbers yet, so this is low.')}
                </span>
              )}
            </p>
          )}
          <div className="mt-2 flex flex-col sm:flex-row sm:flex-wrap gap-x-5 gap-y-1">
            {canEdit && (
              <label className="inline-flex items-center gap-3 min-h-11 cursor-pointer">
                <input type="checkbox" className="w-5 h-5 accent-[rgb(var(--laro-accent-rgb))]" checked={saveForNext}
                  onChange={(e) => setSaveForNext(e.target.checked)} />
                {tx('checkSaveForNext', 'Save for next time')}
              </label>
            )}
            {mode === 'cook' && (
              <label className="inline-flex items-center gap-3 min-h-11 cursor-pointer">
                <input type="checkbox" className="w-5 h-5 accent-[rgb(var(--laro-accent-rgb))]" checked={dontAsk}
                  onChange={(e) => setDontAsk(e.target.checked)} />
                {tx('checkDontAsk', "Don't ask again for this recipe")}
              </label>
            )}
          </div>
          <div className="mt-2 flex gap-3">
            <Button type="button" className="h-14 flex-1 rounded-full text-base bg-laro hover:bg-laro-dark" onClick={finish}
              disabled={saving} data-testid="check-numbers-start">
              {saving && <Loader2 className="w-4 h-4 motion-safe:animate-spin" aria-hidden="true" />}
              {mode === 'cook' ? tx('checkStartCooking', 'Start cooking') : tx('checkDone', 'Done')}
            </Button>
            <Button type="button" variant="outline" className="h-14 rounded-full px-6 text-base" onClick={skip}
              data-testid="check-numbers-skip">
              {mode === 'cook' ? tx('checkSkip', 'Skip') : tx('close', 'Close')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CheckNumbers;

import React, { useState } from 'react';
import { toast } from 'sonner';
import { Store, Copy } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { Button } from './ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { SHOP_STORES, shopSearchTerm, shopUrl } from '../lib/shopLinks';

/**
 * "Shop this list": pick a shop once, then step through unticked items (one tap each).
 * Supermarkets have no "add a whole list" link, so Laro opens each item's search in turn.
 * rows: [{ item, index }] in aisle order; onGotIt(index) ticks the item.
 */
export function ShopListRun({ rows, amazonTag, onGotIt }) {
  const { t } = useLanguage();
  const [run, setRun] = useState(null); // { store, queue: [{item,index}], pos }

  const open = (store, entry) => {
    if (entry) window.open(shopUrl(store.id, entry.item.name, amazonTag), '_blank', 'noopener,noreferrer');
  };
  const start = (store) => {
    const queue = rows.filter((r) => !r.item.checked);
    if (!queue.length) return;
    setRun({ store, queue, pos: 0 });
    open(store, queue[0]);
  };
  const advance = (tick) => {
    if (!run) return;
    const entry = run.queue[run.pos];
    if (tick && entry) onGotIt(entry.index);
    const next = { ...run, pos: run.pos + 1 };
    setRun(next);
    open(next.store, next.queue[next.pos]);
  };
  const copyList = async () => {
    const text = rows.filter((r) => !r.item.checked).map((r) => shopSearchTerm(r.item.name)).join('\n');
    try {
      await navigator.clipboard.writeText(text);
      toast.success(t('shopListCopied'));
    } catch {
      toast.error(t('shopListCopyFailed'));
    }
  };

  const remaining = rows.filter((r) => !r.item.checked).length;
  if (!remaining && !run) return null;

  if (run) {
    const entry = run.queue[run.pos];
    return (
      <div className="rounded-2xl bg-laro-light p-4 space-y-2" data-testid="shop-run-bar">
        {entry ? (
          <>
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                {run.store.label} · {t('shopRunProgress', { n: run.pos + 1, total: run.queue.length })}
              </span>
              <Button variant="ghost" size="sm" onClick={() => setRun(null)}>
                {t('shopRunStop')}
              </Button>
            </div>
            <button type="button" className="font-heading text-lg font-semibold text-left" onClick={() => open(run.store, entry)}>
              {shopSearchTerm(entry.item.name)}
            </button>
            <p className="text-xs text-muted-foreground">{t('shopRunHint', { store: run.store.label })}</p>
            <div className="flex gap-2">
              <Button className="rounded-full bg-laro hover:bg-laro-dark flex-1" onClick={() => advance(true)} data-testid="shop-run-got-it">
                {t('shopRunGotIt')}
              </Button>
              <Button variant="outline" className="rounded-full flex-1" onClick={() => advance(false)}>
                {t('shopRunSkip')}
              </Button>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-between">
            <span className="font-medium">{t('shopRunDone', { store: run.store.label })}</span>
            <Button variant="ghost" size="sm" onClick={() => setRun(null)}>
              {t('shopRunFinish')}
            </Button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="rounded-full" data-testid="shop-list-btn">
            <Store className="w-4 h-4 mr-2" />
            {t('shopThisList')}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-64">
          <DropdownMenuLabel className="font-normal">{t('shopThisListAt')}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {SHOP_STORES.map((store) => (
            <DropdownMenuItem key={store.id} onSelect={() => start(store)}>
              {store.label}
            </DropdownMenuItem>
          ))}
          {amazonTag && <p className="px-2 py-1.5 text-[11px] text-muted-foreground">{t('amazonAssociateNote')}</p>}
        </DropdownMenuContent>
      </DropdownMenu>
      <Button variant="ghost" className="rounded-full" onClick={copyList} data-testid="copy-list-btn">
        <Copy className="w-4 h-4 mr-2" />
        {t('copyList')}
      </Button>
    </div>
  );
}

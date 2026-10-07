import React, { useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { orderedRetailerEntries, retailerLabel } from '../lib/ukRetailers';
import { ChevronDown, ChevronUp } from 'lucide-react';

const COLLAPSED_MAX = 6;

/**
 * Compact chips linking to each UK online supermarket search for an ingredient.
 */
export function RetailerSearchLinks({
  retailerLinks,
  preferredRetailerId,
  productHint,
  compact = false,
}) {
  const { t } = useLanguage();
  const [expanded, setExpanded] = useState(false);

  if (!retailerLinks || !Object.keys(retailerLinks).length) return null;

  const entries = orderedRetailerEntries(retailerLinks);
  const visible = expanded ? entries : entries.slice(0, COLLAPSED_MAX);
  const hiddenCount = entries.length - visible.length;

  return (
    <div className="mt-2 space-y-1.5" data-testid="retailer-search-links">
      {productHint ? (
        <p className="text-[10px] text-muted-foreground line-clamp-1" title={productHint}>
          {productHint}
        </p>
      ) : null}
      <div
        className={`flex flex-wrap gap-1 ${compact ? 'max-h-24 overflow-y-auto' : ''}`}
        role="list"
      >
        {visible.map(([id, url]) => {
          const isPreferred = preferredRetailerId && id === preferredRetailerId;
          return (
            <a
              key={id}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              role="listitem"
              className={`text-[10px] font-medium px-2 py-0.5 rounded-full border transition-colors ${
                isPreferred
                  ? 'bg-laro text-white border-laro'
                  : 'bg-white border-border/60 hover:border-laro/50 text-foreground'
              }`}
              onClick={(e) => e.stopPropagation()}
            >
              {retailerLabel(id)}
            </a>
          );
        })}
      </div>
      {hiddenCount > 0 && (
        <button
          type="button"
          className="inline-flex items-center gap-0.5 text-[10px] font-medium text-laro hover:underline"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded((v) => !v);
          }}
        >
          {expanded ? (
            <>
              <ChevronUp className="w-3 h-3" />
              {t('showFewerStores')}
            </>
          ) : (
            <>
              <ChevronDown className="w-3 h-3" />
              {t('showAllStores', { count: entries.length })}
            </>
          )}
        </button>
      )}
    </div>
  );
}

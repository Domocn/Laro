import React, { useMemo, useState } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from './ui/command';
import { countryFlag, countryName, countryOptions, normalizeCountry } from '../lib/locales';
import { useLanguage } from '../context/LanguageContext';

/**
 * Searchable country picker: common countries first (UK, Ireland, US, Canada, Australia,
 * New Zealand), then every other country A–Z. Type to filter by name or code.
 */
export function CountryPicker({ value, onChange, id, testId = 'country-picker', className = '', ariaLabelledBy }) {
  const { t } = useLanguage();
  const tr = (key, fallback) => {
    const s = t(key);
    return s && s !== key ? s : fallback;
  };
  const [open, setOpen] = useState(false);
  const code = normalizeCountry(value);
  const { common, rest } = useMemo(() => countryOptions(), []);

  const item = (c) => (
    <CommandItem
      key={c.code}
      value={`${c.name} ${c.code}`}
      onSelect={() => {
        onChange?.(c.code);
        setOpen(false);
      }}
      data-testid={`${testId}-option-${c.code}`}
      className="flex items-center gap-2"
    >
      <span aria-hidden="true">{c.flag}</span>
      <span className="flex-1">{c.name}</span>
      {c.code === code && <Check className="h-4 w-4 text-laro" aria-hidden="true" />}
    </CommandItem>
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          id={id}
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-haspopup="listbox"
          aria-labelledby={ariaLabelledBy}
          data-testid={testId}
          className={`flex h-10 w-full items-center justify-between gap-2 rounded-xl bg-cream-subtle border border-transparent px-3 text-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-laro ${className}`}
        >
          <span className="flex items-center gap-2 truncate">
            <span aria-hidden="true">{countryFlag(code)}</span>
            <span className="truncate">{countryName(code)}</span>
          </span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] min-w-[16rem] p-0" align="start">
        <Command>
          <CommandInput placeholder={tr('countrySearchPlaceholder', 'Search countries…')} data-testid={`${testId}-search`} />
          <CommandList className="max-h-72">
            <CommandEmpty>{tr('countryNoMatch', 'No country matches that.')}</CommandEmpty>
            <CommandGroup heading={tr('countryCommon', 'Common')}>{common.map(item)}</CommandGroup>
            <CommandSeparator />
            <CommandGroup heading={tr('countryAll', 'All countries')}>{rest.map(item)}</CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export default CountryPicker;

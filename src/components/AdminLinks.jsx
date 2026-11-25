import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Copy, Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

const RANGES = [1, 7, 30, 90];
const PLACES = ['whatsapp', 'instagram', 'facebook', 'tiktok', 'email', 'poster'];

const LABELS = {
  direct: 'Typed in or no link info',
  unknown: 'Not recorded (before tracking)',
  'android-app': 'Android app',
  'google-app': 'Google app',
  'play-store': 'Play Store page',
};

function label(source) {
  if (LABELS[source]) return LABELS[source];
  if (source.startsWith('code:')) return `Code ${source.slice(5)}`;
  return source.charAt(0).toUpperCase() + source.slice(1);
}

function when(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

// Admin → Links: where visits and sign-ups come from, plus trackable links to share.
export function AdminLinks() {
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [place, setPlace] = useState('whatsapp');
  const [campaign, setCampaign] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminApi.getLinks(days);
      setData(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not load links');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  const slug = campaign.trim().toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-|-$/g, '');
  const link = `${window.location.origin}/?s=${place}${slug ? `&c=${slug}` : ''}`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      toast.success('Link copied');
    } catch {
      toast.error('Could not copy. Select the link and copy it.');
    }
  };

  return (
    <div className="space-y-4" data-testid="admin-links">
      <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-4 space-y-3">
        <p className="font-medium">Make a link to share</p>
        <div className="flex flex-wrap gap-2">
          {PLACES.map((p) => (
            <Button
              key={p}
              size="sm"
              variant={place === p ? 'default' : 'outline'}
              className="rounded-full"
              onClick={() => setPlace(p)}
            >
              {label(p)}
            </Button>
          ))}
        </div>
        <Input
          value={campaign}
          onChange={(e) => setCampaign(e.target.value)}
          placeholder="Optional name, for example circleup-walk"
          maxLength={60}
        />
        <div className="flex gap-2 items-center">
          <code className="flex-1 min-w-0 truncate bg-muted rounded-lg px-3 py-2 text-sm">{link}</code>
          <Button size="sm" className="rounded-full" onClick={copy}>
            <Copy className="w-4 h-4 mr-1" /> Copy
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Promo links (register?ref=CODE) are tracked too. Visits from Instagram, Facebook and TikTok are
          spotted even without a special link.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 items-center justify-between">
        <div className="flex flex-wrap gap-2">
          {RANGES.map((d) => (
            <Button
              key={d}
              size="sm"
              variant={days === d ? 'default' : 'outline'}
              className="rounded-full"
              onClick={() => setDays(d)}
            >
              {d === 1 ? 'Last 24 hours' : `Last ${d} days`}
            </Button>
          ))}
        </div>
        <Button variant="outline" size="sm" className="rounded-full" onClick={load}>
          <RefreshCw className="w-4 h-4 mr-1" /> Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      ) : !data?.sources?.length ? (
        <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-8 text-center text-muted-foreground">
          No visits in this period yet.
        </div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {data.total_visits} {data.total_visits === 1 ? 'visit' : 'visits'} and {data.total_signups}{' '}
            {data.total_signups === 1 ? 'sign-up' : 'sign-ups'}. Visits count people who were not signed in.
          </p>
          <div className="bg-white dark:bg-card rounded-2xl border border-border/60 divide-y divide-border/60">
            {data.sources.map((s) => (
              <div key={s.source} className="p-4 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium">{label(s.source)}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {[
                      s.iphone ? `${s.iphone} iPhone` : null,
                      s.android ? `${s.android} Android` : null,
                      s.desktop ? `${s.desktop} computer` : null,
                      s.last_visit ? `last ${when(s.last_visit)}` : null,
                    ].filter(Boolean).join(' · ')}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-semibold">{s.visits} {s.visits === 1 ? 'visit' : 'visits'}</p>
                  <p className="text-xs text-muted-foreground">
                    {s.signups} {s.signups === 1 ? 'sign-up' : 'sign-ups'}
                  </p>
                </div>
              </div>
            ))}
          </div>
          {data.campaigns?.length > 0 && (
            <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-4 space-y-1">
              <p className="font-medium mb-2">Named links</p>
              {data.campaigns.map((c) => (
                <p key={`${c.source}-${c.campaign}`} className="text-sm flex justify-between gap-3">
                  <span>{label(c.source)} · {c.campaign}</span>
                  <span className="text-muted-foreground">{c.visits}</span>
                </p>
              ))}
            </div>
          )}
          {data.referrers?.length > 0 && (
            <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-4 space-y-1">
              <p className="font-medium mb-2">Websites that linked here</p>
              {data.referrers.map((r) => (
                <p key={r.referrer_host} className="text-sm flex justify-between gap-3">
                  <span className="truncate">{r.referrer_host}</span>
                  <span className="text-muted-foreground">{r.visits}</span>
                </p>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default AdminLinks;

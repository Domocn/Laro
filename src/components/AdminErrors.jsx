import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { Button } from './ui/button';
import { Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

const RANGES = [1, 7, 30];

function when(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

// Admin → Errors: server 500s and web crashes, grouped, most people affected first.
export function AdminErrors() {
  const [days, setDays] = useState(7);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);
  const [samples, setSamples] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminApi.listErrors(days);
      setGroups(res.data?.groups || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not load errors');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = async (fp) => {
    if (open === fp) {
      setOpen(null);
      return;
    }
    setOpen(fp);
    if (!samples[fp]) {
      try {
        const res = await adminApi.getErrorSamples(fp);
        setSamples((s) => ({ ...s, [fp]: res.data?.events || [] }));
      } catch {
        setSamples((s) => ({ ...s, [fp]: [] }));
      }
    }
  };

  return (
    <div className="space-y-4" data-testid="admin-errors">
      <div className="flex flex-wrap gap-2 items-center justify-between">
        <div className="flex gap-2">
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
          <Loader2 className="w-4 h-4 animate-spin" /> Loading errors…
        </div>
      ) : groups.length === 0 ? (
        <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-8 text-center text-muted-foreground">
          No errors in this period.
        </div>
      ) : (
        <div className="space-y-2">
          {groups.map((g) => (
            <div key={g.fingerprint} className="bg-white dark:bg-card rounded-2xl border border-border/60">
              <button
                type="button"
                className="w-full text-left p-4 flex items-start justify-between gap-3"
                onClick={() => toggle(g.fingerprint)}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    {g.is_new && (
                      <span className="rounded-full bg-red-100 text-red-700 px-2 py-0.5 text-xs font-semibold">New</span>
                    )}
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{g.source}</span>
                    <span className="font-medium">{g.error_type}</span>
                    <code className="text-xs text-muted-foreground">{g.method} {g.path}</code>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1 truncate">{g.message}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Last seen {when(g.last_seen)} · first seen {when(g.first_ever)}
                    {g.location ? ` · ${g.location}` : ''}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-semibold">{g.count}×</p>
                  <p className="text-xs text-muted-foreground">
                    {g.users} {g.users === 1 ? 'person' : 'people'}
                  </p>
                </div>
              </button>
              {open === g.fingerprint && (
                <div className="border-t border-border/60 p-4 space-y-3">
                  {!samples[g.fingerprint] ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    samples[g.fingerprint].slice(0, 5).map((ev, i) => (
                      <div key={i} className="text-xs space-y-1">
                        <p className="text-muted-foreground">
                          {when(ev.created_at)} · {ev.user_id ? 'signed-in user' : 'signed out'}
                          {ev.app_version ? ` · v${ev.app_version}` : ''} · {(ev.user_agent || '').slice(0, 60)}
                        </p>
                        {ev.detail && (
                          <pre className="bg-muted rounded-lg p-2 overflow-x-auto max-h-56 whitespace-pre-wrap">
                            {ev.detail}
                          </pre>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default AdminErrors;

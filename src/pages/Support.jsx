import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { supportApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  LifeBuoy,
  Loader2,
  Plus,
  ArrowLeft,
  Send,
  Ticket,
} from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../context/LanguageContext';

const STATUS_LABEL_KEYS = {
  open: 'statusOpen',
  in_progress: 'statusInProgress',
  waiting_on_user: 'statusWaitingOnUser',
  resolved: 'statusResolved',
  closed: 'statusClosed',
};

const CATEGORY_LABEL_KEYS = {
  bug: 'categoryBug',
  feature: 'categoryFeature',
  support: 'categorySupport',
  other: 'other',
};

const statusClass = (status) => {
  switch (status) {
    case 'open':
      return 'bg-amber-100 text-amber-800';
    case 'in_progress':
      return 'bg-sky-100 text-sky-800';
    case 'waiting_on_user':
      return 'bg-violet-100 text-violet-800';
    case 'resolved':
      return 'bg-emerald-100 text-emerald-800';
    case 'closed':
      return 'bg-muted text-muted-foreground';
    default:
      return 'bg-muted text-muted-foreground';
  }
};

export const Support = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [creating, setCreating] = useState(false);
  const [reply, setReply] = useState('');
  const [sendingReply, setSendingReply] = useState(false);
  const [form, setForm] = useState({
    subject: '',
    description: '',
    category: 'support',
  });

  const loadTickets = useCallback(async () => {
    try {
      const res = await supportApi.list();
      setTickets(res.data?.tickets || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastTicketsLoadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  useEffect(() => {
    if (searchParams.get('new') === '1') {
      setShowNew(true);
      const cat = searchParams.get('category');
      if (cat && CATEGORY_LABEL_KEYS[cat]) {
        setForm((f) => ({ ...f, category: cat }));
      }
    }
  }, [searchParams]);

  const openTicket = async (id) => {
    setSelectedId(id);
    setShowNew(false);
    setDetailLoading(true);
    setReply('');
    try {
      const res = await supportApi.get(id);
      setDetail(res.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastTicketOpenFailed'));
      setSelectedId(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCreate = async () => {
    if (form.subject.trim().length < 3 || form.description.trim().length < 10) {
      toast.error(t('toastTicketFormIncomplete'));
      return;
    }
    setCreating(true);
    try {
      const res = await supportApi.create({
        subject: form.subject.trim(),
        description: form.description.trim(),
        category: form.category,
        platform: 'web',
        app_version: undefined,
        device_info: navigator.userAgent?.slice(0, 500),
      });
      toast.success(t('ticketNumberCreated', { number: res.data.ticket_number }));
      setForm({ subject: '', description: '', category: 'support' });
      setShowNew(false);
      setSearchParams({});
      await loadTickets();
      await openTicket(res.data.id);
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastTicketCreateFailed'));
    } finally {
      setCreating(false);
    }
  };

  const handleReply = async () => {
    if (!selectedId || !reply.trim()) return;
    setSendingReply(true);
    try {
      await supportApi.addMessage(selectedId, reply.trim());
      setReply('');
      const res = await supportApi.get(selectedId);
      setDetail(res.data);
      await loadTickets();
      toast.success(t('toastReplySent'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastReplyFailed'));
    } finally {
      setSendingReply(false);
    }
  };

  const handleClose = async () => {
    if (!selectedId) return;
    try {
      await supportApi.update(selectedId, { status: 'closed' });
      toast.success(t('toastTicketClosed'));
      const res = await supportApi.get(selectedId);
      setDetail(res.data);
      await loadTickets();
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastTicketCloseFailed'));
    }
  };

  const listTitle = useMemo(() => {
    if (showNew) return t('newTicket');
    if (selectedId) return detail?.ticket_number || t('ticket');
    return t('helpSupport');
  }, [showNew, selectedId, detail, t]);

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-6" data-testid="support-page">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-start justify-between gap-3">
            <div>
              {(showNew || selectedId) && (
                <button
                  type="button"
                  className="text-sm text-muted-foreground hover:text-foreground mb-2 inline-flex items-center gap-1"
                  onClick={() => {
                    setShowNew(false);
                    setSelectedId(null);
                    setDetail(null);
                    setSearchParams({});
                  }}
                >
                  <ArrowLeft className="w-4 h-4" />
                  {t('allTickets')}
                </button>
              )}
              <h1 className="font-heading text-3xl font-bold flex items-center gap-2">
                <LifeBuoy className="w-8 h-8 text-laro" />
                {listTitle}
              </h1>
              <p className="text-muted-foreground mt-1">
                {t('supportPageDesc')}
              </p>
            </div>
            {!showNew && !selectedId && (
              <Button
                className="rounded-full bg-laro hover:bg-laro-dark shrink-0"
                onClick={() => setShowNew(true)}
                data-testid="new-ticket-btn"
              >
                <Plus className="w-4 h-4 mr-2" />
                {t('newTicket')}
              </Button>
            )}
          </div>
        </motion.div>

        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-laro" />
          </div>
        ) : showNew ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-white dark:bg-card rounded-2xl border border-border/60 p-6 space-y-4"
          >
            <div>
              <Label>{t('category')}</Label>
              <select
                className="w-full mt-1 p-2 rounded-xl border border-border/60 bg-background text-sm"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                {Object.entries(CATEGORY_LABEL_KEYS).map(([value, key]) => (
                  <option key={value} value={value}>
                    {t(key)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="ticket-subject">{t('subject')}</Label>
              <Input
                id="ticket-subject"
                className="mt-1 rounded-xl"
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                placeholder={t('ticketSubjectPlaceholder')}
                data-testid="ticket-subject"
              />
            </div>
            <div>
              <Label htmlFor="ticket-description">{t('details')}</Label>
              <textarea
                id="ticket-description"
                className="w-full mt-1 min-h-[140px] rounded-xl border border-border/60 bg-background p-3 text-sm"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder={t('ticketDescriptionPlaceholder')}
                data-testid="ticket-description"
              />
            </div>
            <Button
              className="rounded-full bg-laro hover:bg-laro-dark w-full"
              onClick={handleCreate}
              disabled={creating}
              data-testid="submit-ticket-btn"
            >
              {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Ticket className="w-4 h-4 mr-2" />}
              {t('submitTicket')}
            </Button>
          </motion.div>
        ) : selectedId ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
            {detailLoading || !detail ? (
              <div className="flex justify-center py-16">
                <Loader2 className="w-8 h-8 animate-spin text-laro" />
              </div>
            ) : (
              <>
                <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-6 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${statusClass(detail.status)}`}>
                      {STATUS_LABEL_KEYS[detail.status] ? t(STATUS_LABEL_KEYS[detail.status]) : detail.status}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {CATEGORY_LABEL_KEYS[detail.category] ? t(CATEGORY_LABEL_KEYS[detail.category]) : detail.category}
                    </span>
                  </div>
                  <h2 className="font-heading text-xl font-semibold">{detail.subject}</h2>
                  {detail.resolution && (
                    <div className="rounded-xl bg-emerald-50 dark:bg-emerald-950/30 p-3 text-sm">
                      <p className="font-medium text-emerald-800 dark:text-emerald-200 mb-1">{t('resolution')}</p>
                      <p>{detail.resolution}</p>
                    </div>
                  )}
                  {!['resolved', 'closed'].includes(detail.status) && (
                    <Button variant="outline" className="rounded-full" onClick={handleClose}>
                      {t('closeTicket')}
                    </Button>
                  )}
                </div>

                <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-6 space-y-4">
                  <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wide">{t('conversation')}</h3>
                  <ul className="space-y-3">
                    {(detail.messages || []).map((msg) => (
                      <li
                        key={msg.id}
                        className={`rounded-xl p-3 text-sm ${
                          msg.is_staff ? 'bg-laro/10' : 'bg-cream-subtle dark:bg-muted'
                        }`}
                      >
                        <p className="text-xs text-muted-foreground mb-1">
                          {msg.is_staff ? t('laroSupport') : t('you')}
                          {msg.created_at ? ` · ${new Date(msg.created_at).toLocaleString()}` : ''}
                        </p>
                        <p className="whitespace-pre-wrap">{msg.body}</p>
                      </li>
                    ))}
                  </ul>

                  {!['resolved', 'closed'].includes(detail.status) && (
                    <div className="space-y-2 pt-2 border-t border-border/60">
                      <textarea
                        className="w-full min-h-[80px] rounded-xl border border-border/60 bg-background p-3 text-sm"
                        placeholder={t('addAReplyPlaceholder')}
                        value={reply}
                        onChange={(e) => setReply(e.target.value)}
                        data-testid="ticket-reply"
                      />
                      <Button
                        className="rounded-full bg-laro hover:bg-laro-dark"
                        onClick={handleReply}
                        disabled={sendingReply || !reply.trim()}
                      >
                        {sendingReply ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        ) : (
                          <Send className="w-4 h-4 mr-2" />
                        )}
                        {t('sendReply')}
                      </Button>
                    </div>
                  )}
                </div>
              </>
            )}
          </motion.div>
        ) : tickets.length === 0 ? (
          <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-10 text-center">
            <Ticket className="w-10 h-10 text-laro mx-auto mb-3" />
            <h3 className="font-heading text-lg font-semibold mb-1">{t('noTicketsYet')}</h3>
            <p className="text-sm text-muted-foreground mb-4">
              {t('noTicketsDesc')}
            </p>
            <Button className="rounded-full bg-laro hover:bg-laro-dark" onClick={() => setShowNew(true)}>
              <Plus className="w-4 h-4 mr-2" />
              {t('newTicket')}
            </Button>
          </div>
        ) : (
          <ul className="space-y-3" data-testid="tickets-list">
            {tickets.map((ticketItem) => (
              <li key={ticketItem.id}>
                <button
                  type="button"
                  onClick={() => openTicket(ticketItem.id)}
                  className="w-full text-left bg-white dark:bg-card rounded-2xl border border-border/60 p-4 hover:border-laro/40 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="font-mono text-xs text-laro">{ticketItem.ticket_number}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusClass(ticketItem.status)}`}>
                      {STATUS_LABEL_KEYS[ticketItem.status] ? t(STATUS_LABEL_KEYS[ticketItem.status]) : ticketItem.status}
                    </span>
                  </div>
                  <p className="font-medium truncate">{ticketItem.subject}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {CATEGORY_LABEL_KEYS[ticketItem.category] ? t(CATEGORY_LABEL_KEYS[ticketItem.category]) : ticketItem.category}
                    {ticketItem.updated_at ? ` · ${t('updatedPrefix')} ${new Date(ticketItem.updated_at).toLocaleDateString()}` : ''}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}

        {!showNew && !selectedId && (
          <p className="text-center text-xs text-muted-foreground">
            {t('preferEmail')}{' '}
            <button type="button" className="text-laro hover:underline" onClick={() => navigate('/settings')}>
              {t('settingsAppLink')}
            </button>{' '}
            {t('stillHasBasics')}
          </p>
        )}
      </div>
    </Layout>
  );
};

export default Support;

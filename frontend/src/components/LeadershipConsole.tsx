'use client';

import { useEffect, useRef, useState } from 'react';
import { Loader2, LogOut, Radio, Sparkles } from 'lucide-react';

import {
  Announcement,
  AnnouncementStats,
  ApiError,
  LoginResponse,
  approveAnnouncement,
  createAnnouncement,
  getAnnouncementStats,
  requestAIDraft,
  sendAnnouncement,
} from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SelectNative } from '@/components/ui/select-native';
import { Textarea } from '@/components/ui/textarea';

const CLASSIFICATIONS = ['', 'journeyman', 'apprentice', 'foreman', 'retiree'];
const STATS_POLL_INTERVAL_MS = 3000;

const STATUS_LABEL: Record<Announcement['status'], string> = {
  draft: 'Draft',
  approved: 'Approved',
  sending: 'Sending',
  sent: 'Sent',
  cancelled: 'Cancelled',
};

const STATUS_VARIANT: Record<
  Announcement['status'],
  'secondary' | 'default' | 'outline'
> = {
  draft: 'secondary',
  approved: 'outline',
  sending: 'default',
  sent: 'default',
  cancelled: 'secondary',
};

interface LeadershipConsoleProps {
  session: LoginResponse;
  onLogout: () => void;
}

export function LeadershipConsole({ session, onLogout }: LeadershipConsoleProps) {
  const [rawText, setRawText] = useState('');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [classification, setClassification] = useState('');
  const [needsAck, setNeedsAck] = useState(true);

  const [announcement, setAnnouncement] = useState<Announcement | null>(null);
  const [stats, setStats] = useState<AnnouncementStats | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const idempotencyKeyRef = useRef(crypto.randomUUID());

  useEffect(() => {
    if (!announcement || (announcement.status !== 'sending' && announcement.status !== 'sent')) {
      return;
    }

    let cancelled = false;
    const poll = async () => {
      try {
        const nextStats = await getAnnouncementStats(session.access, announcement.id);
        if (!cancelled) setStats(nextStats);
      } catch {
        // Transient polling errors are not surfaced; the next tick retries.
      }
    };

    poll();
    const interval = setInterval(poll, STATS_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [announcement, session.access]);

  async function handleCreateOrUpdateDraft() {
    setActionError(null);
    setIsBusy(true);
    try {
      const created = await createAnnouncement(session.access, {
        title,
        body,
        audience_classification: classification,
        needs_ack: needsAck,
      });
      setAnnouncement(created);
      setStats(null);
      idempotencyKeyRef.current = crypto.randomUUID();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Failed to create draft.');
    } finally {
      setIsBusy(false);
    }
  }

  async function handleImproveWithAI() {
    if (!announcement) {
      setAiError('Create a draft before requesting an AI rewrite.');
      return;
    }
    setAiError(null);
    setIsBusy(true);
    try {
      const updated = await requestAIDraft(session.access, announcement.id, rawText);
      setAnnouncement(updated);
      setTitle(updated.title);
      setBody(updated.body);
    } catch (err) {
      setAiError(
        err instanceof ApiError
          ? err.message
          : 'AI draft assistance is unavailable right now. You can keep editing manually.',
      );
    } finally {
      setIsBusy(false);
    }
  }

  async function handleApprove() {
    if (!announcement) return;
    setActionError(null);
    setIsBusy(true);
    try {
      const approved = await approveAnnouncement(session.access, announcement.id);
      setAnnouncement(approved);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Failed to approve.');
    } finally {
      setIsBusy(false);
    }
  }

  async function handleSend() {
    if (!announcement) return;
    setActionError(null);
    setIsBusy(true);
    try {
      const sent = await sendAnnouncement(session.access, announcement.id, idempotencyKeyRef.current);
      setAnnouncement(sent);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Failed to send.');
    } finally {
      setIsBusy(false);
    }
  }

  const canApprove = announcement?.status === 'draft';
  const canSend = announcement?.status === 'approved';
  const isSent = announcement?.status === 'sending' || announcement?.status === 'sent';

  return (
    <div className="min-h-screen bg-muted/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Radio className="size-4" />
            </div>
            <div>
              <h1 className="text-sm font-semibold leading-none">CrewLink</h1>
              <p className="mt-1 text-xs text-muted-foreground">Local #{session.local_id}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={onLogout}>
            <LogOut />
            Sign out
          </Button>
        </div>
      </header>

      <main className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-8">
        <Card>
          <CardHeader>
            <CardTitle>1. Compose</CardTitle>
            <CardDescription>
              Write manually, or paste rough notes and improve them with AI.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="raw-text">Messy source text (optional)</Label>
              <Textarea
                id="raw-text"
                value={rawText}
                onChange={(event) => setRawText(event.target.value)}
                placeholder="e.g. meeting thursday 6pm everyone needs to come re contract talks"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="self-start"
                onClick={handleImproveWithAI}
                disabled={isBusy || !rawText.trim()}
              >
                <Sparkles />
                Improve with AI
              </Button>
              {aiError && <p className="text-sm text-amber-600">{aiError}</p>}
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" value={title} onChange={(event) => setTitle(event.target.value)} />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="body">Body</Label>
              <Textarea
                id="body"
                className="min-h-24"
                value={body}
                onChange={(event) => setBody(event.target.value)}
              />
            </div>

            {announcement?.push_preview && (
              <p className="text-sm text-muted-foreground">
                Push preview: “{announcement.push_preview}”
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>2. Audience</CardTitle>
            <CardDescription>Local #{session.local_id} — your local only.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="classification">Classification (optional)</Label>
              <SelectNative
                id="classification"
                value={classification}
                onChange={(event) => setClassification(event.target.value)}
              >
                {CLASSIFICATIONS.map((value) => (
                  <option key={value} value={value}>
                    {value ? value[0].toUpperCase() + value.slice(1) : 'All active members'}
                  </option>
                ))}
              </SelectNative>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="size-4 rounded border-input"
                checked={needsAck}
                onChange={(event) => setNeedsAck(event.target.checked)}
              />
              Require acknowledgement
            </label>

            <Button
              type="button"
              variant="outline"
              className="self-start"
              onClick={handleCreateOrUpdateDraft}
              disabled={isBusy || !title.trim() || !body.trim()}
            >
              {announcement ? 'Save as new draft' : 'Create draft'}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>3. Approve and send</CardTitle>
            {announcement && (
              <CardDescription className="flex items-center gap-2">
                Announcement #{announcement.id}
                <Badge variant={STATUS_VARIANT[announcement.status]}>
                  {STATUS_LABEL[announcement.status]}
                </Badge>
              </CardDescription>
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {actionError && <p className="text-sm text-destructive">{actionError}</p>}

            <div className="flex gap-3">
              <Button variant="outline" onClick={handleApprove} disabled={isBusy || !canApprove}>
                Approve draft
              </Button>
              <Button onClick={handleSend} disabled={isBusy || !canSend}>
                {isBusy && <Loader2 className="animate-spin" />}
                Send
              </Button>
            </div>
          </CardContent>
        </Card>

        {isSent && (
          <Card>
            <CardHeader>
              <CardTitle>Delivery status</CardTitle>
            </CardHeader>
            <CardContent>
              {stats ? (
                <dl className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">Sent</dt>
                    <dd className="text-2xl font-semibold">{stats.sent}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">Read</dt>
                    <dd className="text-2xl font-semibold">{stats.read}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                      Acknowledged
                    </dt>
                    <dd className="text-2xl font-semibold">{stats.acknowledged}</dd>
                  </div>
                </dl>
              ) : (
                <p className="text-sm text-muted-foreground">Loading counts…</p>
              )}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

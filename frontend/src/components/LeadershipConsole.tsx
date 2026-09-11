'use client';

import { useEffect, useRef, useState } from 'react';
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

const CLASSIFICATIONS = ['', 'journeyman', 'apprentice', 'foreman', 'retiree'];
const STATS_POLL_INTERVAL_MS = 3000;

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
    if (!announcement || announcement.status !== 'sending' && announcement.status !== 'sent') {
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
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-8 py-12">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">CrewLink callout console</h1>
          <p className="text-sm text-zinc-500">Local #{session.local_id}</p>
        </div>
        <button onClick={onLogout} className="text-sm text-zinc-500 underline">
          Sign out
        </button>
      </header>

      <section className="flex flex-col gap-3 rounded border border-zinc-200 p-4">
        <h2 className="font-medium">1. Compose</h2>

        <label className="flex flex-col gap-1 text-sm">
          Messy source text (optional - improve with AI below)
          <textarea
            className="min-h-20 rounded border border-zinc-300 px-3 py-2"
            value={rawText}
            onChange={(event) => setRawText(event.target.value)}
            placeholder="e.g. meeting thursday 6pm everyone needs to come re contract talks"
          />
        </label>

        <button
          onClick={handleImproveWithAI}
          disabled={isBusy || !rawText.trim()}
          className="self-start rounded border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-50"
        >
          Improve with AI
        </button>
        {aiError && <p className="text-sm text-amber-700">{aiError}</p>}

        <label className="flex flex-col gap-1 text-sm">
          Title
          <input
            className="rounded border border-zinc-300 px-3 py-2"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Body
          <textarea
            className="min-h-24 rounded border border-zinc-300 px-3 py-2"
            value={body}
            onChange={(event) => setBody(event.target.value)}
          />
        </label>

        {announcement?.push_preview && (
          <p className="text-sm text-zinc-500">Push preview: “{announcement.push_preview}”</p>
        )}
      </section>

      <section className="flex flex-col gap-3 rounded border border-zinc-200 p-4">
        <h2 className="font-medium">2. Audience</h2>
        <p className="text-sm text-zinc-500">Local #{session.local_id} (your local only)</p>

        <label className="flex flex-col gap-1 text-sm">
          Classification (optional)
          <select
            className="rounded border border-zinc-300 px-3 py-2"
            value={classification}
            onChange={(event) => setClassification(event.target.value)}
          >
            {CLASSIFICATIONS.map((value) => (
              <option key={value} value={value}>
                {value || 'All active members'}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={needsAck}
            onChange={(event) => setNeedsAck(event.target.checked)}
          />
          Require acknowledgement
        </label>

        <button
          onClick={handleCreateOrUpdateDraft}
          disabled={isBusy || !title.trim() || !body.trim()}
          className="self-start rounded border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-50"
        >
          {announcement ? 'Save as new draft' : 'Create draft'}
        </button>
      </section>

      <section className="flex flex-col gap-3 rounded border border-zinc-200 p-4">
        <h2 className="font-medium">3. Approve and send</h2>
        {actionError && <p className="text-sm text-red-600">{actionError}</p>}

        <div className="flex gap-3">
          <button
            onClick={handleApprove}
            disabled={isBusy || !canApprove}
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-50"
          >
            Approve draft
          </button>
          <button
            onClick={handleSend}
            disabled={isBusy || !canSend}
            className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            Send
          </button>
        </div>

        {announcement && (
          <p className="text-sm text-zinc-500">
            Announcement #{announcement.id} - status: <strong>{announcement.status}</strong>
          </p>
        )}
      </section>

      {isSent && (
        <section className="flex flex-col gap-2 rounded border border-zinc-200 p-4">
          <h2 className="font-medium">Delivery status</h2>
          {stats ? (
            <dl className="grid grid-cols-3 gap-4 text-center">
              <div>
                <dt className="text-xs uppercase text-zinc-500">Sent</dt>
                <dd className="text-2xl font-semibold">{stats.sent}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-zinc-500">Read</dt>
                <dd className="text-2xl font-semibold">{stats.read}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-zinc-500">Acknowledged</dt>
                <dd className="text-2xl font-semibold">{stats.acknowledged}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-zinc-500">Loading counts...</p>
          )}
        </section>
      )}
    </div>
  );
}

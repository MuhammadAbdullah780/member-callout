const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface LoginResponse {
  access: string;
  refresh: string;
  role: string;
  local_id: number;
}

export interface Announcement {
  id: number;
  title: string;
  body: string;
  push_preview: string;
  audience_classification: string;
  needs_ack: boolean;
  status: 'draft' | 'approved' | 'sending' | 'sent' | 'cancelled';
  approved_by: number | null;
  approved_at: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface AnnouncementStats {
  sent: number;
  read: number;
  acknowledged: number;
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, headers, ...rest } = options;

  const response = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      body.detail ?? (Array.isArray(body) ? body[0] : null) ?? response.statusText;
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function login(username: string, password: string) {
  return request<LoginResponse>('/api/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export function createAnnouncement(
  token: string,
  data: { title: string; body: string; audience_classification: string; needs_ack: boolean },
) {
  return request<Announcement>('/api/announcements/', {
    method: 'POST',
    token,
    body: JSON.stringify(data),
  });
}

export function requestAIDraft(token: string, announcementId: number, rawText: string) {
  return request<Announcement>(`/api/announcements/${announcementId}/ai-draft/`, {
    method: 'POST',
    token,
    body: JSON.stringify({ raw_text: rawText }),
  });
}

export function approveAnnouncement(token: string, announcementId: number) {
  return request<Announcement>(`/api/announcements/${announcementId}/approve/`, {
    method: 'POST',
    token,
  });
}

export function sendAnnouncement(token: string, announcementId: number, idempotencyKey: string) {
  return request<Announcement>(`/api/announcements/${announcementId}/send/`, {
    method: 'POST',
    token,
    headers: { 'Idempotency-Key': idempotencyKey },
  });
}

export function getAnnouncementStats(token: string, announcementId: number) {
  return request<AnnouncementStats>(`/api/announcements/${announcementId}/stats/`, {
    token,
  });
}

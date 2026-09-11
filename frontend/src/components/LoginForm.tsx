'use client';

import { FormEvent, useState } from 'react';
import { ApiError, LoginResponse, login } from '@/lib/api';

interface LoginFormProps {
  onLogin: (session: LoginResponse) => void;
}

export function LoginForm({ onLogin }: LoginFormProps) {
  const [username, setUsername] = useState('leader27');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const session = await login(username, password);
      if (session.role !== 'leadership') {
        setError('This screen is for leadership accounts only.');
        return;
      }
      onLogin(session);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto mt-24 flex w-full max-w-sm flex-col gap-4">
      <h1 className="text-xl font-semibold">CrewLink leadership login</h1>

      <label className="flex flex-col gap-1 text-sm">
        Username
        <input
          className="rounded border border-zinc-300 px-3 py-2"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          required
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        Password
        <input
          className="rounded border border-zinc-300 px-3 py-2"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </label>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
      >
        {isSubmitting ? 'Signing in...' : 'Sign in'}
      </button>
    </form>
  );
}

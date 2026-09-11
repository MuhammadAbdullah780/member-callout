'use client';

import { useState } from 'react';
import { LeadershipConsole } from '@/components/LeadershipConsole';
import { LoginForm } from '@/components/LoginForm';
import { LoginResponse } from '@/lib/api';

export default function Home() {
  const [session, setSession] = useState<LoginResponse | null>(null);

  return (
    <div className="min-h-full bg-zinc-50 px-4">
      {session ? (
        <LeadershipConsole session={session} onLogout={() => setSession(null)} />
      ) : (
        <LoginForm onLogin={setSession} />
      )}
    </div>
  );
}

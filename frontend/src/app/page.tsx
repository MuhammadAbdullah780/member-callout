'use client';

import { useState } from 'react';
import { LeadershipConsole } from '@/components/LeadershipConsole';
import { LoginForm } from '@/components/LoginForm';
import { LoginResponse } from '@/lib/api';

export default function Home() {
  const [session, setSession] = useState<LoginResponse | null>(null);

  if (!session) {
    return <LoginForm onLogin={setSession} />;
  }

  return <LeadershipConsole session={session} onLogout={() => setSession(null)} />;
}

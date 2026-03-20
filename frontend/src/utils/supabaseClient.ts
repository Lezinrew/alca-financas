import { createClient } from '@supabase/supabase-js';

const supabaseUrl = (import.meta.env.VITE_SUPABASE_URL as string | undefined)?.trim();
const supabaseAnonKey = (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined)?.trim();

const isTest = import.meta.env.MODE === 'test';
const resolvedUrl = supabaseUrl || (isTest ? 'http://localhost:54321' : undefined);
const resolvedAnonKey = supabaseAnonKey || (isTest ? 'test-anon-key' : undefined);

if (!resolvedUrl || !resolvedAnonKey) {
  throw new Error(
    'Supabase não configurado: o bundle foi gerado sem VITE_SUPABASE_URL e VITE_SUPABASE_ANON_KEY. ' +
      'O Vite só inclui essas variáveis na hora do `npm run build` (ex.: docker run -e VITE_SUPABASE_URL=... -e VITE_SUPABASE_ANON_KEY=...). ' +
      'No servidor: scripts/rebuild-frontend-prod-on-server.sh ou veja SUPABASE-SECRETS-SETUP.md.'
  );
}

export const supabase = createClient(resolvedUrl, resolvedAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});


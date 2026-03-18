import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

const isTest = import.meta.env.MODE === 'test';
const resolvedUrl = supabaseUrl || (isTest ? 'http://localhost:54321' : undefined);
const resolvedAnonKey = supabaseAnonKey || (isTest ? 'test-anon-key' : undefined);

if (!resolvedUrl || !resolvedAnonKey) {
  throw new Error(
    'Supabase não configurado. Defina VITE_SUPABASE_URL e VITE_SUPABASE_ANON_KEY no ambiente do frontend.'
  );
}

export const supabase = createClient(resolvedUrl, resolvedAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});


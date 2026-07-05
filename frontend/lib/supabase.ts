/**
 * Browser-side Supabase client, used only for email/password auth (sign
 * up, sign in, session persistence/refresh) — see context/AuthContext.tsx.
 * All document/chat data still goes through the FastAPI backend (lib/api.ts),
 * never queried directly from the browser with this client.
 */
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

if (!supabaseUrl || !supabaseAnonKey) {
  // A misconfigured deployment shouldn't crash the whole app at import
  // time (that would take down every page, not just auth) — sign-in/
  // sign-up will simply fail with a clear Supabase error until these are
  // set in .env.local.
  console.warn(
    "NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY are not set — " +
      "sign-in and sign-up will fail until they're configured in .env.local."
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

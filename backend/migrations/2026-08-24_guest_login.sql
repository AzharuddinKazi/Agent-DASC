-- Name-only "guest" login, alongside Google sign-in (see TASKS.md).
--
-- Office laptops have Gmail deactivated, so colleagues can't complete Google sign-in there.
-- This adds a second, much weaker login path — just a name, no verification — good enough
-- for "how many people actually opened and tried the app", not for anything security-
-- sensitive. Google accounts stay the only path to admin (ADMIN_EMAILS still keys off
-- verified Google email; guest rows never have one, so a guest can never become admin).
--
-- Idempotent (IF NOT EXISTS / DROP IF EXISTS everywhere) so re-running it is harmless.

ALTER TABLE public.users ALTER COLUMN google_sub DROP NOT NULL;
ALTER TABLE public.users ALTER COLUMN email DROP NOT NULL;

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS auth_provider text NOT NULL DEFAULT 'google';

ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_auth_provider_check;
ALTER TABLE public.users
    ADD CONSTRAINT users_auth_provider_check CHECK (auth_provider IN ('google', 'guest'));

-- A guest row is only ever identified by its name, so it must have one.
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_guest_name_check;
ALTER TABLE public.users
    ADD CONSTRAINT users_guest_name_check CHECK (auth_provider <> 'guest' OR name IS NOT NULL);

-- De-dupes guests by name (case-insensitive) so re-registering the same name on a cleared
-- cookie reuses the same account instead of inflating the headcount. Google accounts already
-- de-dupe on google_sub/email; this is the guest-only equivalent. Postgres UNIQUE constraints
-- treat every NULL as distinct, so this doesn't need to be a partial index to coexist with
-- google rows (which have auth_provider='google', never matching this index's predicate).
DROP INDEX IF EXISTS users_guest_name_unique;
CREATE UNIQUE INDEX users_guest_name_unique ON public.users (lower(name)) WHERE auth_provider = 'guest';

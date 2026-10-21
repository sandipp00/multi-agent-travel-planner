-- Database setup for the travel planner website.
-- Run once in Supabase: Dashboard -> SQL Editor -> New query -> paste -> Run.

create table if not exists public.conversations (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  title       text not null default '',
  messages    jsonb not null default '[]'::jsonb,   -- full model history, for follow-ups
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table if not exists public.plans (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users (id) on delete cascade,
  user_email       text not null default '',
  conversation_id  uuid references public.conversations (id) on delete cascade,
  request          text not null,          -- what the traveler typed
  reply            text not null,          -- the planner's answer
  tool_data        jsonb not null default '[]'::jsonb,   -- specialist results behind the answer
  issues           jsonb not null default '[]'::jsonb,   -- fact-check mismatches left in the answer
  used_tools       boolean not null default false,       -- a full plan (counts toward daily limits)
  duration_ms      integer not null default 0,
  rating           smallint check (rating in (-1, 1)),   -- thumbs down / up
  comment          text not null default '',
  flags            text[] not null default '{}',         -- e.g. {prices_wrong, itinerary_confusing}
  feedback_at      timestamptz,
  created_at       timestamptz not null default now()
);

create index if not exists plans_user_created_idx on public.plans (user_id, created_at desc);
create index if not exists plans_created_idx on public.plans (created_at desc);
create index if not exists conversations_user_updated_idx on public.conversations (user_id, updated_at desc);

-- Only the server (secret key) may read or write these tables: row-level
-- security on, with no policies, blocks the public/browser keys entirely.
alter table public.conversations enable row level security;
alter table public.plans enable row level security;

-- Newer Supabase projects require explicit grants for API access.
grant usage on schema public to service_role;
grant select, insert, update, delete on public.conversations, public.plans to service_role;

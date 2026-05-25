drop table if exists public.device_access cascade;
drop table if exists public.device_slots cascade;
drop table if exists public.devices cascade;

create extension if not exists pgcrypto;

create table public.devices (
  device_id uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique references auth.users(id) on delete set null,
  display_name text,
  install_id text unique,
  status text not null default 'active' check (status in ('active','offline','destroyed')),
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  destroyed_at timestamptz
);

create table public.device_slots (
  slot_number bigint generated always as identity primary key,
  device_id uuid unique references public.devices(device_id) on delete set null,
  assigned_at timestamptz not null default now(),
  released_at timestamptz
);

create table public.device_access (
  user_id uuid not null references auth.users(id) on delete cascade,
  topic text not null,
  can_read boolean not null default false,
  can_write boolean not null default false,
  created_at timestamptz not null default now(),
  primary key (user_id, topic)
);

alter table public.devices enable row level security;
alter table public.device_slots enable row level security;
alter table public.device_access enable row level security;

drop policy if exists devices_select_allowed on public.devices;
create policy devices_select_allowed
on public.devices
for select
to authenticated
using (
  auth.uid() = auth_user_id
  or exists (
    select 1
    from public.device_access da
    where da.user_id = auth.uid()
      and da.topic = ('device:' || devices.device_id::text)
      and da.can_read = true
  )
);

drop policy if exists slots_select_allowed on public.device_slots;
create policy slots_select_allowed
on public.device_slots
for select
to authenticated
using (
  exists (
    select 1
    from public.devices d
    where d.device_id = device_slots.device_id
      and (
        d.auth_user_id = auth.uid()
        or exists (
          select 1
          from public.device_access da
          where da.user_id = auth.uid()
            and da.topic = ('device:' || d.device_id::text)
            and da.can_read = true
        )
      )
  )
);

drop policy if exists access_self_select on public.device_access;
create policy access_self_select
on public.device_access
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists realtime_read_allowed_topics on realtime.messages;
create policy realtime_read_allowed_topics
on realtime.messages
for select
to authenticated
using (
  realtime.messages.extension = 'broadcast'
  and exists (
    select 1
    from public.device_access da
    where da.user_id = auth.uid()
      and da.topic = realtime.topic()
      and da.can_read = true
  )
);

drop policy if exists realtime_write_allowed_topics on realtime.messages;
create policy realtime_write_allowed_topics
on realtime.messages
for insert
to authenticated
with check (
  realtime.messages.extension = 'broadcast'
  and exists (
    select 1
    from public.device_access da
    where da.user_id = auth.uid()
      and da.topic = realtime.topic()
      and da.can_write = true
  )
);

create or replace function public.allocate_free_slot(p_device_id uuid)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_slot bigint;
begin
  select slot_number into v_slot
  from public.device_slots
  where device_id = p_device_id
  limit 1;

  if v_slot is not null then
    return v_slot;
  end if;

  insert into public.device_slots (device_id)
  values (p_device_id)
  returning slot_number into v_slot;

  return v_slot;
end;
$$;

create or replace function public.touch_device_last_seen(p_device_id uuid)
returns void
language sql
security definer
set search_path = public
as $$
  update public.devices
  set last_seen_at = now(),
      status = 'active'
  where device_id = p_device_id
    and auth_user_id = auth.uid();
$$;

comment on table public.device_access is
'Authorization matrix used by private Realtime broadcast channels.';

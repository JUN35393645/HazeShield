create extension if not exists pgcrypto;

create table public.zones (
  id text primary key,
  name text not null unique,
  state text not null
);

create table public.plans (
  id text primary key,
  name text not null,
  plan_type text not null check (plan_type in ('monthly', 'seasonal', 'group')),
  price numeric(10, 2) not null check (price >= 0),
  description text not null
);

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  name text not null,
  email text not null unique,
  role text not null check (role in ('customer', 'employer', 'admin')),
  zone_id text references public.zones(id) on delete set null,
  wallet text default 'Touch n Go',
  account_status text not null default 'active' check (account_status in ('active', 'deleted')),
  occupation text,
  occupation_other text,
  company_name text,
  referral_code text not null unique default ('HS-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 10))),
  created_at timestamptz not null default now()
);

create table public.employer_memberships (
  id uuid primary key default gen_random_uuid(),
  employer_id uuid not null references public.profiles(id) on delete cascade,
  customer_id uuid not null references public.profiles(id) on delete cascade,
  status text not null default 'active' check (status in ('active', 'removed')),
  created_at timestamptz not null default now(),
  unique (employer_id, customer_id)
);

create table public.policies (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete set null,
  plan_id text not null references public.plans(id),
  zone_id text not null references public.zones(id),
  status text not null check (status in ('active', 'cancelled')),
  start_date date not null,
  end_date date not null,
  sponsor_user_id uuid references public.profiles(id) on delete set null,
  sponsor_policy_id uuid references public.policies(id) on delete set null,
  auto_renew boolean not null default true,
  created_at timestamptz not null default now(),
  check (end_date >= start_date)
);

create table public.readings (
  id uuid primary key default gen_random_uuid(),
  zone_id text not null references public.zones(id),
  reading_date date not null,
  api_value integer not null check (api_value between 0 and 1000),
  source text not null default 'SIMULATED',
  unique (zone_id, reading_date)
);

create table public.trigger_events (
  id uuid primary key default gen_random_uuid(),
  zone_id text not null references public.zones(id),
  start_date date not null,
  end_date date not null,
  days_above_threshold integer not null check (days_above_threshold >= 2),
  unique (zone_id, start_date)
);

create table public.payouts (
  id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.policies(id) on delete cascade,
  trigger_event_id uuid not null references public.trigger_events(id),
  payout_date date not null,
  amount numeric(10, 2) not null check (amount >= 0),
  wallet text not null,
  status text not null default 'paid',
  created_at timestamptz not null default now(),
  unique (policy_id, payout_date)
);

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  message text not null,
  created_at timestamptz not null default now()
);

create table public.payments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete set null,
  policy_id uuid not null references public.policies(id) on delete cascade,
  amount numeric(10, 2) not null check (amount >= 0),
  method text not null,
  status text not null default 'paid',
  created_at timestamptz not null default now()
);

create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid references public.profiles(id) on delete set null,
  action text not null,
  details text not null default '',
  created_at timestamptz not null default now()
);

create index policies_user_status_idx on public.policies(user_id, status);
create index policies_zone_status_idx on public.policies(zone_id, status);
create unique index policies_sponsor_member_unique_idx on public.policies(sponsor_policy_id, user_id) where sponsor_policy_id is not null;
create index readings_zone_date_idx on public.readings(zone_id, reading_date desc);
create index payouts_date_idx on public.payouts(payout_date desc);

insert into public.zones (id, name, state) values
  ('klang-valley', 'Klang Valley', 'Selangor'),
  ('kuching', 'Kuching', 'Sarawak'),
  ('sri-aman', 'Sri Aman', 'Sarawak'),
  ('johor-bahru', 'Johor Bahru', 'Johor'),
  ('penang', 'Penang', 'Penang'),
  ('ipoh', 'Ipoh', 'Perak'),
  ('kota-kinabalu', 'Kota Kinabalu', 'Sabah')
on conflict (id) do nothing;

insert into public.plans (id, name, plan_type, price, description) values
  ('monthly', 'Monthly', 'monthly', 15.00, 'Flexible cover, billed monthly'),
  ('seasonal', 'Haze season', 'seasonal', 60.00, 'July to September coverage'),
  ('worker-group', 'Worker group', 'group', 250.00, '20 workers, RM12.50 per worker')
on conflict (id) do nothing;

insert into public.readings(zone_id, reading_date, api_value, source)
select z.id, d.reading_date,
  case
    when z.id = 'ipoh' and d.reading_date = current_date then 160
    when z.id = 'klang-valley' and d.reading_date between current_date - 10 and current_date - 8 then 160
    else 25 + (('x' || substr(md5(z.id || d.reading_date::text), 1, 8))::bit(32)::bigint % 91)::integer
  end,
  'SIMULATED'
from public.zones z
cross join lateral (select generate_series(current_date - 59, current_date, interval '1 day')::date as reading_date) d
on conflict (zone_id, reading_date) do nothing;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  account_type text := new.raw_user_meta_data ->> 'account_type';
  account_name text := trim(coalesce(new.raw_user_meta_data ->> 'name', ''));
  account_zone text := new.raw_user_meta_data ->> 'zone_id';
  account_occupation text := new.raw_user_meta_data ->> 'occupation';
begin
  if lower(coalesce(new.email, '')) !~ '^[a-z0-9.!#$%&''*+/=?^_`{|}~-]+@gmail[.]com$' then
    raise exception 'Use a Gmail address ending in @gmail.com';
  end if;
  if account_type is null or account_type not in ('individual', 'employer') then raise exception 'Choose a valid account type'; end if;
  if length(account_name) not between 2 and 80 then raise exception 'Name must contain 2 to 80 characters'; end if;
  if not exists (select 1 from public.zones where id = account_zone) then raise exception 'Choose a valid primary zone'; end if;
  if account_type = 'individual' and (
    account_occupation is null or account_occupation not in ('Delivery rider', 'E-hailing driver', 'Food vendor', 'Market trader',
      'Construction worker', 'Outdoor service worker', 'Other')
    or (account_occupation = 'Other' and length(trim(coalesce(new.raw_user_meta_data ->> 'occupation_other', ''))) not between 1 and 80)
  ) then raise exception 'Choose a listed occupation and describe Other';
  end if;
  if account_type = 'employer' and length(trim(coalesce(new.raw_user_meta_data ->> 'company_name', ''))) not between 1 and 120 then
    raise exception 'Business name must contain 1 to 120 characters';
  end if;
  insert into public.profiles (
    id, name, email, role, zone_id, occupation, occupation_other, company_name
  )
  values (
    new.id,
    account_name,
    lower(new.email),
    case when account_type = 'employer' then 'employer' else 'customer' end,
    account_zone,
    case when account_type = 'employer' then null else account_occupation end,
    case when account_type = 'employer' then null else new.raw_user_meta_data ->> 'occupation_other' end,
    case when account_type = 'employer' then new.raw_user_meta_data ->> 'company_name' else null end
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.profiles
    where id = (select auth.uid()) and role = 'admin' and account_status = 'active'
  );
$$;

alter table public.zones enable row level security;
alter table public.plans enable row level security;
alter table public.profiles enable row level security;
alter table public.employer_memberships enable row level security;
alter table public.policies enable row level security;
alter table public.readings enable row level security;
alter table public.trigger_events enable row level security;
alter table public.payouts enable row level security;
alter table public.notifications enable row level security;
alter table public.payments enable row level security;
alter table public.audit_logs enable row level security;

grant usage on schema public to anon, authenticated;
grant select on public.zones, public.plans, public.readings to anon, authenticated;
grant select on public.profiles, public.employer_memberships, public.policies,
  public.trigger_events, public.payouts, public.notifications, public.payments,
  public.audit_logs to authenticated;

create policy "Zones are publicly readable" on public.zones for select to anon, authenticated using (true);
create policy "Plans are publicly readable" on public.plans for select to anon, authenticated using (true);
create policy "Readings are publicly readable" on public.readings for select to anon, authenticated using (true);
create policy "Profiles visible to owner, team and admin" on public.profiles for select to authenticated
using (
  id = (select auth.uid())
  or (select public.is_admin())
  or exists (
    select 1 from public.employer_memberships m
    where m.status = 'active'
      and ((m.employer_id = (select auth.uid()) and m.customer_id = profiles.id)
        or (m.customer_id = (select auth.uid()) and m.employer_id = profiles.id))
  )
);
create policy "Memberships visible to related accounts or admin" on public.employer_memberships for select to authenticated
using (employer_id = (select auth.uid()) or customer_id = (select auth.uid()) or (select public.is_admin()));
create policy "Policies visible to owner, sponsor or admin" on public.policies for select to authenticated
using (user_id = (select auth.uid()) or sponsor_user_id = (select auth.uid()) or (select public.is_admin()));
create policy "Trigger events visible to authenticated users" on public.trigger_events for select to authenticated using (true);
create policy "Payouts visible to policy owner or admin" on public.payouts for select to authenticated
using (
  (select public.is_admin())
  or exists (select 1 from public.policies p where p.id = payouts.policy_id and p.user_id = (select auth.uid()))
);
create policy "Notifications visible to owner or admin" on public.notifications for select to authenticated
using (user_id = (select auth.uid()) or (select public.is_admin()));
create policy "Payments visible to owner or admin" on public.payments for select to authenticated
using (user_id = (select auth.uid()) or (select public.is_admin()));
create policy "Audit logs visible to admins" on public.audit_logs for select to authenticated using ((select public.is_admin()));

create or replace function public.purchase_policy(p_plan_id text, p_zone_id text, p_wallet text)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller uuid := auth.uid();
  profile public.profiles%rowtype;
  selected_plan public.plans%rowtype;
  parent_id uuid;
  new_policy_id uuid;
  begin_date date := current_date;
  finish_date date;
  member_total integer;
begin
  select * into profile from public.profiles where id = caller and account_status = 'active' for update;
  if not found then raise exception 'Active account required'; end if;
  if profile.role not in ('customer', 'employer') then raise exception 'This account cannot purchase a plan'; end if;
  select * into selected_plan from public.plans where id = p_plan_id;
  if not found or not exists (select 1 from public.zones where id = p_zone_id) then raise exception 'Plan or zone not found'; end if;
  if profile.role = 'customer' and selected_plan.plan_type = 'group' then raise exception 'Group plans require an employer account'; end if;
  if profile.role = 'employer' and selected_plan.plan_type <> 'group' then raise exception 'Employers must choose a group plan'; end if;
  if p_wallet not in ('Touch n Go', 'GrabPay', 'Boost') then raise exception 'Choose a supported payout wallet'; end if;
  if selected_plan.plan_type = 'group' then
    select count(*) into member_total from public.employer_memberships where employer_id = caller and status = 'active';
    if member_total = 0 then raise exception 'Add at least one existing individual account before buying group cover'; end if;
    if member_total > 20 then raise exception 'The group plan covers up to 20 individual accounts'; end if;
    if exists (
      select 1 from public.policies p where p.user_id = caller and p.sponsor_policy_id is null
        and p.status = 'active' and p.start_date <= current_date and p.end_date >= current_date
        and exists (select 1 from public.plans pl where pl.id = p.plan_id and pl.plan_type = 'group')
    ) then raise exception 'An active group plan already covers this roster'; end if;
  end if;
  if selected_plan.plan_type = 'seasonal' then
    if begin_date > make_date(extract(year from begin_date)::int, 9, 30) then
      begin_date := make_date(extract(year from begin_date)::int + 1, 7, 1);
      finish_date := make_date(extract(year from begin_date)::int, 9, 30);
    else
      begin_date := greatest(begin_date, make_date(extract(year from begin_date)::int, 7, 1));
      finish_date := make_date(extract(year from begin_date)::int, 9, 30);
    end if;
  else
    finish_date := begin_date + 30;
  end if;
  update public.profiles set wallet = p_wallet where id = caller;
  insert into public.policies(user_id, plan_id, zone_id, status, start_date, end_date)
    values (caller, p_plan_id, p_zone_id, 'active', begin_date, finish_date)
    returning id into new_policy_id;
  insert into public.payments(user_id, policy_id, amount, method, status)
    values (caller, new_policy_id, selected_plan.price, p_wallet, 'paid');
  if selected_plan.plan_type = 'group' then
    parent_id := new_policy_id;
    insert into public.policies(user_id, plan_id, zone_id, status, start_date, end_date, sponsor_user_id, sponsor_policy_id)
      select m.customer_id, p_plan_id, coalesce(c.zone_id, p_zone_id), 'active', begin_date, finish_date, caller, parent_id
      from public.employer_memberships m
      join public.profiles c on c.id = m.customer_id
      where m.employer_id = caller and m.status = 'active'
      on conflict (sponsor_policy_id, user_id) where sponsor_policy_id is not null
      do update set status = 'active', start_date = excluded.start_date, end_date = excluded.end_date, zone_id = excluded.zone_id;
  end if;
  return new_policy_id;
end;
$$;

create or replace function public.add_employer_member(p_customer_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller uuid := auth.uid();
  active_count integer;
  plan_row record;
begin
  perform 1 from public.profiles where id = caller and role = 'employer' and account_status = 'active' for update;
  if not found then
    raise exception 'Employer account required';
  end if;
  if not exists (select 1 from public.profiles where id = p_customer_id and role = 'customer' and account_status = 'active') then
    raise exception 'No existing individual account has that Gmail address';
  end if;
  if exists (select 1 from public.employer_memberships where employer_id = caller and customer_id = p_customer_id and status = 'active') then
    raise exception 'This account is already on the employer roster';
  end if;
  select count(*) into active_count from public.employer_memberships where employer_id = caller and status = 'active';
  if active_count >= 20 then raise exception 'The demo group plan supports up to 20 people'; end if;
  insert into public.employer_memberships(employer_id, customer_id, status)
    values (caller, p_customer_id, 'active')
    on conflict (employer_id, customer_id) do update set status = 'active', created_at = now();
  select p.id, p.start_date, p.end_date, p.plan_id, p.zone_id into plan_row
    from public.policies p join public.plans pl on pl.id = p.plan_id
    where p.user_id = caller and p.sponsor_policy_id is null and p.status = 'active'
      and p.start_date <= current_date and p.end_date >= current_date and pl.plan_type = 'group'
    order by p.created_at desc limit 1;
  if found then
    insert into public.policies(user_id, plan_id, zone_id, status, start_date, end_date, sponsor_user_id, sponsor_policy_id)
      select p_customer_id, plan_row.plan_id, coalesce(c.zone_id, plan_row.zone_id), 'active',
        plan_row.start_date, plan_row.end_date, caller, plan_row.id
      from public.profiles c where c.id = p_customer_id
      on conflict (sponsor_policy_id, user_id) where sponsor_policy_id is not null
      do update set status = 'active', start_date = excluded.start_date, end_date = excluded.end_date, zone_id = excluded.zone_id;
  end if;
end;
$$;

create or replace function public.remove_employer_member(p_customer_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare caller uuid := auth.uid();
begin
  perform 1 from public.profiles where id = caller and role = 'employer' and account_status = 'active' for update;
  if not found then raise exception 'Employer account required'; end if;
  update public.employer_memberships set status = 'removed'
    where employer_id = caller and customer_id = p_customer_id and status = 'active';
  if not found then raise exception 'Active team member not found'; end if;
  update public.policies set status = 'cancelled'
    where sponsor_user_id = caller and user_id = p_customer_id and sponsor_policy_id is not null and status <> 'cancelled';
end;
$$;

create or replace function public.admin_set_policy_status(p_policy_id uuid, p_status text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not public.is_admin() then raise exception 'Admin access required'; end if;
  if p_status not in ('active', 'cancelled') then raise exception 'Invalid policy status'; end if;
  update public.policies set status = p_status where id = p_policy_id;
  if not found then raise exception 'Policy not found'; end if;
  if p_status = 'cancelled' then
    update public.policies set status = 'cancelled' where sponsor_policy_id = p_policy_id;
  else
    update public.policies child set status = 'active'
      where child.sponsor_policy_id = p_policy_id and exists (
        select 1 from public.employer_memberships m
        where m.employer_id = (select p.user_id from public.policies p where p.id = p_policy_id)
          and m.customer_id = child.user_id and m.status = 'active'
      );
  end if;
  insert into public.audit_logs(actor_id, action, details)
    values (auth.uid(), 'policy_status_changed', 'policy_id=' || p_policy_id || '; status=' || p_status);
end;
$$;

create or replace function public.admin_record_reading(p_zone_id text, p_reading_date date, p_api_value integer)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  first_day date := p_reading_date - 1;
  payout_from date;
  event_id uuid;
  payout_total integer := 0;
  payout_day date;
  policy_row record;
  event_start date;
begin
  if not public.is_admin() then raise exception 'Admin access required'; end if;
  if p_api_value < 0 or p_api_value > 1000 then raise exception 'API value must be from 0 to 1000'; end if;
  perform 1 from public.zones where id = p_zone_id for update;
  if not found then raise exception 'Zone not found'; end if;
  insert into public.readings(zone_id, reading_date, api_value, source)
    values (p_zone_id, p_reading_date, p_api_value, 'MANUAL')
    on conflict (zone_id, reading_date) do update set api_value = excluded.api_value, source = excluded.source;
  if not exists (select 1 from public.readings where zone_id = p_zone_id and reading_date = first_day and api_value > 150)
     or p_api_value <= 150 then
    insert into public.audit_logs(actor_id, action, details)
      values (auth.uid(), 'reading_recorded', 'zone=' || p_zone_id || '; date=' || p_reading_date || '; API=' || p_api_value);
    return jsonb_build_object('triggered', false, 'missing', not exists (
      select 1 from public.readings where zone_id = p_zone_id and reading_date = first_day
    ), 'payouts', 0);
  end if;
  select id into event_id from public.trigger_events
    where zone_id = p_zone_id and end_date = p_reading_date;
  if found then
    insert into public.audit_logs(actor_id, action, details)
      values (auth.uid(), 'reading_recorded', 'zone=' || p_zone_id || '; date=' || p_reading_date || '; API=' || p_api_value || '; trigger=' || event_id);
    return jsonb_build_object('triggered', true, 'missing', false, 'event_id', event_id, 'payouts', 0);
  end if;
  select id, start_date into event_id, event_start
    from public.trigger_events where zone_id = p_zone_id and end_date = first_day;
  if found then
    update public.trigger_events set end_date = p_reading_date, days_above_threshold = days_above_threshold + 1
      where id = event_id;
    payout_from := p_reading_date;
  else
    event_start := first_day;
    insert into public.trigger_events(zone_id, start_date, end_date, days_above_threshold)
      values (p_zone_id, event_start, p_reading_date, 2)
      returning id into event_id;
    payout_from := first_day;
  end if;
  for payout_day in select generate_series(payout_from, p_reading_date, interval '1 day')::date loop
    if extract(month from payout_day) not between 7 and 9 then continue; end if;
    for policy_row in
        select p.id, p.user_id, coalesce(owner.wallet, 'Anonymized') as wallet
        from public.policies p
        join public.profiles owner on owner.id = p.user_id and owner.role = 'customer'
        where p.zone_id = p_zone_id and p.status = 'active'
          and p.start_date <= payout_day and p.end_date >= payout_day
    loop
      if (select count(*) from public.payouts pa where pa.policy_id = policy_row.id
        and date_part('year', pa.payout_date) = date_part('year', payout_day)) >= 5 then
        continue;
      end if;
      insert into public.payouts(policy_id, trigger_event_id, payout_date, amount, wallet, status)
        values (policy_row.id, event_id, payout_day, 30, policy_row.wallet, 'paid')
        on conflict (policy_id, payout_date) do nothing;
      if found then payout_total := payout_total + 1; end if;
      if found then
        insert into public.notifications(user_id, message)
          values (policy_row.user_id, 'Haze trigger confirmed. Your simulated RM30 payout was recorded.');
      end if;
    end loop;
  end loop;
  insert into public.audit_logs(actor_id, action, details)
    values (auth.uid(), 'reading_recorded', 'zone=' || p_zone_id || '; date=' || p_reading_date || '; API=' || p_api_value || '; trigger=' || event_id);
  return jsonb_build_object('triggered', true, 'missing', false, 'event_id', event_id, 'payouts', payout_total);
end;
$$;

create or replace function public.admin_anonymize_account(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare target_role text;
begin
  if not public.is_admin() then raise exception 'Admin access required'; end if;
  select role into target_role from public.profiles where id = p_user_id and account_status = 'active';
  if not found then raise exception 'Active account not found'; end if;
  if target_role = 'admin' then raise exception 'Admin accounts cannot be deleted here'; end if;
  update public.policies set status = 'cancelled'
    where (user_id = p_user_id or sponsor_user_id = p_user_id
      or sponsor_policy_id in (select id from public.policies where user_id = p_user_id or sponsor_user_id = p_user_id))
      and status <> 'cancelled';
  update public.payouts set wallet = 'Anonymized'
    where policy_id in (select id from public.policies where user_id = p_user_id or sponsor_user_id = p_user_id);
  update public.payments set method = 'Anonymized'
    where policy_id in (select id from public.policies where user_id = p_user_id or sponsor_user_id = p_user_id);
  update public.employer_memberships set status = 'removed' where employer_id = p_user_id or customer_id = p_user_id;
  delete from public.notifications where user_id = p_user_id;
  insert into public.audit_logs(actor_id, action, details)
    values (auth.uid(), 'account_anonymized', 'account_id=' || p_user_id || '; role=' || target_role);
  update public.profiles set
    account_status = 'deleted',
    name = 'Deleted account ' || p_user_id::text,
    email = 'deleted+' || p_user_id::text || '@invalid.invalid',
    zone_id = null,
    wallet = null,
    occupation = null,
    occupation_other = null,
    company_name = null
    where id = p_user_id;
end;
$$;

create or replace function public.admin_reset_demo_activity()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not public.is_admin() then raise exception 'Admin access required'; end if;
  delete from public.payouts;
  delete from public.payments;
  delete from public.notifications;
  delete from public.policies;
  delete from public.employer_memberships;
  delete from public.trigger_events;
  delete from public.readings;
  insert into public.readings(zone_id, reading_date, api_value, source)
    select z.id, d.reading_date,
      case
        when z.id = 'ipoh' and d.reading_date = current_date then 160
        when z.id = 'klang-valley' and d.reading_date between current_date - 10 and current_date - 8 then 160
        else 25 + (('x' || substr(md5(z.id || d.reading_date::text), 1, 8))::bit(32)::bigint % 91)::integer
      end,
      'SIMULATED'
    from public.zones z
    cross join lateral (select generate_series(current_date - 59, current_date, interval '1 day')::date as reading_date) d;
  insert into public.audit_logs(actor_id, action, details)
    values (auth.uid(), 'demo_activity_reset', 'Policies, payments, payouts, memberships and readings reset; profiles retained');
end;
$$;

revoke all on function public.handle_new_user() from public, anon, authenticated;
revoke all on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;
revoke all on function public.purchase_policy(text, text, text) from public, anon;
grant execute on function public.purchase_policy(text, text, text) to authenticated;
revoke all on function public.add_employer_member(uuid) from public, anon;
grant execute on function public.add_employer_member(uuid) to authenticated;
revoke all on function public.remove_employer_member(uuid) from public, anon;
grant execute on function public.remove_employer_member(uuid) to authenticated;
revoke all on function public.admin_set_policy_status(uuid, text) from public, anon;
grant execute on function public.admin_set_policy_status(uuid, text) to authenticated;
revoke all on function public.admin_record_reading(text, date, integer) from public, anon;
grant execute on function public.admin_record_reading(text, date, integer) to authenticated;
revoke all on function public.admin_anonymize_account(uuid) from public, anon;
grant execute on function public.admin_anonymize_account(uuid) to authenticated;
revoke all on function public.admin_reset_demo_activity() from public, anon;
grant execute on function public.admin_reset_demo_activity() to authenticated;

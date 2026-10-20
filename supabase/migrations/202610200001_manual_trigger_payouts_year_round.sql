create or replace function public.admin_record_reading(p_zone_id text, p_reading_date date, p_api_value integer)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  first_day date := p_reading_date - 1;
  previous_api integer;
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

  select api_value into previous_api from public.readings
    where zone_id = p_zone_id and reading_date = first_day;
  if p_api_value <= 150 then
    insert into public.audit_logs(actor_id, action, details)
      values (auth.uid(), 'reading_recorded', 'zone=' || p_zone_id || '; date=' || p_reading_date || '; API=' || p_api_value);
    return jsonb_build_object('triggered', false, 'missing', false, 'reason', 'current_reading_below_threshold', 'payouts', 0);
  end if;
  if previous_api is null then
    insert into public.audit_logs(actor_id, action, details)
      values (auth.uid(), 'reading_recorded', 'zone=' || p_zone_id || '; date=' || p_reading_date || '; API=' || p_api_value);
    return jsonb_build_object('triggered', false, 'missing', true, 'reason', 'previous_reading_missing', 'payouts', 0);
  end if;
  if previous_api <= 150 then
    insert into public.audit_logs(actor_id, action, details)
      values (auth.uid(), 'reading_recorded', 'zone=' || p_zone_id || '; date=' || p_reading_date || '; API=' || p_api_value);
    return jsonb_build_object('triggered', false, 'missing', false, 'reason', 'previous_reading_below_threshold', 'payouts', 0);
  end if;

  select id into event_id from public.trigger_events
    where zone_id = p_zone_id and end_date = p_reading_date;
  if found then
    payout_from := p_reading_date;
  else
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
  end if;

  for payout_day in select generate_series(payout_from, p_reading_date, interval '1 day')::date loop
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
      if found then
        payout_total := payout_total + 1;
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

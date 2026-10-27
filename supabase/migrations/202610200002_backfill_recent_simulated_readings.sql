insert into public.readings(zone_id, reading_date, api_value, source)
select
  z.id,
  days.reading_date,
  25 + (('x' || substr(md5(z.id || days.reading_date::text), 1, 8))::bit(32)::bigint % 91)::integer,
  'SIMULATED'
from public.zones z
cross join lateral (
  select generate_series(
    (now() at time zone 'Asia/Kuala_Lumpur')::date - 6,
    (now() at time zone 'Asia/Kuala_Lumpur')::date,
    interval '1 day'
  )::date as reading_date
) days
on conflict (zone_id, reading_date) do nothing;

select
  z.name as zone,
  count(r.id) as readings_in_latest_seven_days,
  min(r.reading_date) as first_date,
  max(r.reading_date) as last_date
from public.zones z
left join public.readings r
  on r.zone_id = z.id
  and r.reading_date between
    (now() at time zone 'Asia/Kuala_Lumpur')::date - 6
    and (now() at time zone 'Asia/Kuala_Lumpur')::date
group by z.id, z.name
order by z.name;

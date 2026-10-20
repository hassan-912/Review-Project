-- Shared maintenance controls and immutable token-rate snapshots. No documents/prompts stored.
alter table public.app_controls add column if not exists maintenance_enabled boolean not null default false;
alter table public.app_controls add column if not exists billing_mode text not null default 'free' check(billing_mode in ('free','paid'));
alter table public.app_controls add column if not exists monthly_budget_usd numeric(12,2) not null default 25 check(monthly_budget_usd>0);
alter table public.model_usage_events add column if not exists review_id uuid;
alter table public.model_usage_events add column if not exists billing_mode text not null default 'unknown' check(billing_mode in ('free','paid','unknown'));
alter table public.model_usage_events add column if not exists cached_input_tokens integer check(cached_input_tokens>=0);
alter table public.model_usage_events add column if not exists input_usd_per_million numeric(12,6);
alter table public.model_usage_events add column if not exists cached_usd_per_million numeric(12,6);
alter table public.model_usage_events add column if not exists output_usd_per_million numeric(12,6);
create index if not exists model_usage_created on public.model_usage_events(created_at,id);
create index if not exists model_usage_review on public.model_usage_events(review_id);

create table public.model_token_prices (
  model text not null references public.model_catalog(model), effective_at timestamptz not null,
  input_usd numeric(12,6) not null check(input_usd>=0), cached_usd numeric(12,6) not null check(cached_usd>=0),
  output_usd numeric(12,6) not null check(output_usd>=0), source text not null,
  primary key(model,effective_at)
);
alter table public.model_token_prices enable row level security;
revoke all on public.model_token_prices from public,anon,authenticated;
grant all on public.model_token_prices to service_role;
-- Standard text/image/PDF rates verified 2026-10-19. Future changes do not reprice old events.
insert into public.model_token_prices values
 ('gemini-3.8-flash','2026-10-18T21:00:00Z',0.75,0.075,3.75,'https://ai.google.dev/gemini-api/docs/pricing'),
 ('gemini-3.6-flash','2026-10-18T21:00:00Z',0.75,0.075,3.75,'https://ai.google.dev/gemini-api/docs/pricing'),
 ('gemini-3.5-flash-lite','2026-10-18T21:00:00Z',0.30,0.03,2.50,'https://ai.google.dev/gemini-api/docs/pricing'),
 ('gemini-3.1-flash-lite','2026-10-18T21:00:00Z',0.25,0.025,1.50,'https://ai.google.dev/gemini-api/docs/pricing'),
 ('gemini-3.8-flash','2027-01-01T08:00:00Z',1.50,0.15,7.50,'https://ai.google.dev/gemini-api/docs/pricing'),
 ('gemini-3.6-flash','2027-01-01T08:00:00Z',1.50,0.15,7.50,'https://ai.google.dev/gemini-api/docs/pricing');

create or replace function public.set_maintenance_mode(p_actor uuid,p_enabled boolean) returns void
language plpgsql security invoker set search_path='' as $$
begin
  if not exists(select 1 from public.profiles where id=p_actor and is_approved and role='super_admin') then raise exception 'access_revoked'; end if;
  update public.app_controls set maintenance_enabled=p_enabled where id;
  insert into public.admin_audit(actor_id,target,action) values(p_actor,'maintenance','Maintenance enabled: '||p_enabled::text);
end $$;

create or replace function public.set_billing_tracking(p_actor uuid,p_mode text,p_budget numeric) returns void
language plpgsql security invoker set search_path='' as $$
begin
  if not exists(select 1 from public.profiles where id=p_actor and is_approved and role='super_admin') then raise exception 'access_revoked'; end if;
  if p_mode is null or p_mode not in ('free','paid') or p_budget is null or p_budget<=0 or p_budget>100000 then raise exception 'invalid_settings'; end if;
  update public.app_controls set billing_mode=p_mode,monthly_budget_usd=p_budget where id;
  insert into public.admin_audit(actor_id,target,action) values(p_actor,'billing','Billing tracking: '||p_mode||'; monthly alert USD '||p_budget::text);
end $$;

create or replace function public.reserve_model_review_request(p_user_id uuid,p_model text,p_tokens integer,p_review_id uuid) returns uuid
language plpgsql security invoker set search_path='' as $$
declare event_id uuid; prices public.model_token_prices; mode text;
begin
  if p_review_id is not null and not exists(select 1 from public.review_attempts where request_id=p_review_id and user_id=p_user_id and status='running') then
    raise exception 'invalid_review';
  end if;
  event_id := public.reserve_model_request(p_user_id,p_model,p_tokens);
  if event_id is null then return null; end if;
  select * into prices from public.model_token_prices where model=p_model and effective_at<=now() order by effective_at desc limit 1;
  select billing_mode into mode from public.app_controls where id;
  update public.model_usage_events set review_id=p_review_id,billing_mode=mode,
    input_usd_per_million=prices.input_usd,cached_usd_per_million=prices.cached_usd,output_usd_per_million=prices.output_usd
    where id=event_id;
  return event_id;
end $$;

create or replace function public.finish_model_usage(p_event uuid,p_user_id uuid,p_status text,p_input integer,p_output integer,p_cached_input integer,p_latency integer,p_cooldown integer) returns void
language plpgsql security invoker set search_path='' as $$
declare model_name text;
begin
  update public.model_usage_events set status=p_status,
    input_tokens=case when p_input>=0 then p_input end, output_tokens=case when p_output>=0 then p_output end,
    cached_input_tokens=case when p_cached_input>=0 and p_cached_input<=p_input then p_cached_input when p_input is not null then 0 end,
    latency_ms=greatest(p_latency,0)
    where id=p_event and user_id=p_user_id and status='reserved' returning model into model_name;
  if model_name is not null and p_cooldown>0 then
    update public.model_catalog set cooldown_until=greatest(coalesce(cooldown_until,now()),now()+make_interval(secs=>least(p_cooldown,90000))) where model=model_name;
  end if;
end $$;

revoke all on function public.set_maintenance_mode(uuid,boolean),public.set_billing_tracking(uuid,text,numeric),
 public.reserve_model_review_request(uuid,text,integer,uuid),public.finish_model_usage(uuid,uuid,text,integer,integer,integer,integer,integer) from public,anon,authenticated;
grant execute on function public.set_maintenance_mode(uuid,boolean),public.set_billing_tracking(uuid,text,numeric),
 public.reserve_model_review_request(uuid,text,integer,uuid),public.finish_model_usage(uuid,uuid,text,integer,integer,integer,integer,integer) to service_role;

-- Append the new stable category without disturbing the team's existing order.
update public.app_controls set upload_category_order=array_append(upload_category_order,'appointment') where not ('appointment'=any(upload_category_order));
alter table public.app_controls alter column upload_category_order set default array['passport','visa_form','cover_letter','hotel','flight','insurance','employment','travel_plan','bank_statement','appointment','supporting'];
create or replace function public.set_upload_category_order(p_actor uuid,p_order text[]) returns void
language plpgsql security invoker set search_path='' as $$
declare expected text[]:=array['passport','visa_form','cover_letter','hotel','flight','insurance','employment','travel_plan','bank_statement','appointment','supporting'];
begin
  if not exists(select 1 from public.profiles where id=p_actor and is_approved and role='super_admin') then raise exception 'access_revoked'; end if;
  if p_order is null or cardinality(p_order)<>11 or not (p_order @> expected and p_order <@ expected)
    or array_position(p_order,null) is not null then raise exception 'invalid_categories'; end if;
  update public.app_controls set upload_category_order=p_order where id;
  insert into public.admin_audit(actor_id,target,action) values(p_actor,'upload_categories','Upload category order updated');
end $$;

create or replace function public.reserve_model_request(p_user_id uuid,p_model text,p_tokens integer) returns uuid
language plpgsql security invoker set search_path = '' as $$
declare c public.model_catalog; event_id uuid; minute_count integer; day_count integer; minute_tokens bigint;
  day_start timestamptz := date_trunc('day',now() at time zone 'America/Los_Angeles') at time zone 'America/Los_Angeles';
begin
  if not exists(select 1 from public.profiles where id=p_user_id and is_approved)
    or not (select reviews_enabled and not maintenance_enabled from public.app_controls where id) then return null; end if;
  perform pg_advisory_xact_lock(hashtextextended(p_model,0));
  select * into c from public.model_catalog where model=p_model;
  if c.model is null or not c.enabled or c.cooldown_until > now() or p_tokens < 1 or p_tokens > c.tpm then return null; end if;
  select count(*) filter(where created_at > now()-interval '60 seconds'),count(*),
    coalesce(sum(greatest(reserved_tokens,coalesce(input_tokens,0))) filter(where created_at > now()-interval '60 seconds'),0)
    into minute_count,day_count,minute_tokens from public.model_usage_events where model=p_model and created_at >= least(day_start,now()-interval '60 seconds');
  -- Rolling minute may cross midnight: count the calendar-day quota separately.
  select count(*) into day_count from public.model_usage_events where model=p_model and created_at>=day_start;
  if minute_count>=c.rpm or day_count>=c.rpd or minute_tokens+p_tokens>c.tpm then return null; end if;
  insert into public.model_usage_events(model,user_id,reserved_tokens) values(p_model,p_user_id,p_tokens) returning id into event_id;
  -- Keep token-only cost history across billing months.
  delete from public.admin_audit where created_at < now()-interval '90 days';
  return event_id;
end $$;

create or replace function public.reserve_review_attempt(p_user_id uuid,p_request_id uuid,p_hourly_limit integer,p_daily_limit integer) returns boolean
language plpgsql security invoker set search_path='' as $$
declare hourly_count integer; daily_count integer; limits public.profiles;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_user_id::text,0));
  select * into limits from public.profiles where id=p_user_id and is_approved;
  if limits.id is null or not (select reviews_enabled and not maintenance_enabled from public.app_controls where id) then return false; end if;
  if exists(select 1 from public.review_attempts where request_id=p_request_id) then return false; end if;
  delete from public.review_attempts where user_id=p_user_id and requested_at<now()-interval '32 days';
  select count(*) filter(where requested_at>now()-interval '1 hour'),count(*) into hourly_count,daily_count
    from public.review_attempts where user_id=p_user_id and requested_at>now()-interval '24 hours';
  if hourly_count>=limits.hourly_limit or daily_count>=limits.daily_limit then return false; end if;
  insert into public.review_attempts(request_id,user_id) values(p_request_id,p_user_id);
  return true;
end $$;

notify pgrst,'reload schema';

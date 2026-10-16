-- Apply through Supabase apply_migration. No applicant documents are persisted.
alter table public.profiles add column if not exists hourly_limit integer not null default 5 check (hourly_limit between 1 and 100);
alter table public.profiles add column if not exists daily_limit integer not null default 20 check (daily_limit between 1 and 1000);

create table public.model_catalog (
  model text primary key check (model in ('gemini-3.8-flash','gemini-3.6-flash','gemini-3.5-flash-lite','gemini-3.1-flash-lite')),
  priority integer not null check (priority between 1 and 100), enabled boolean not null default true,
  rpm integer not null check (rpm between 1 and 15), tpm integer not null check (tpm between 1 and 250000),
  rpd integer not null check (rpd between 1 and 500), cooldown_until timestamptz,
  quota_checked_at timestamptz not null, quota_source text not null,
  check (model like '%flash-lite' or (rpm <= 5 and rpd <= 20))
);
insert into public.model_catalog(model,priority,rpm,tpm,rpd,quota_checked_at,quota_source) values
 ('gemini-3.8-flash',1,5,250000,20,'2026-10-16T00:00:00Z','AI Studio project rate-limit page; Free tier'),
 ('gemini-3.6-flash',2,5,250000,20,'2026-10-16T00:00:00Z','AI Studio project rate-limit page; Free tier'),
 ('gemini-3.5-flash-lite',3,15,250000,500,'2026-10-16T00:00:00Z','AI Studio project rate-limit page; Free tier'),
 ('gemini-3.1-flash-lite',4,15,250000,500,'2026-10-16T00:00:00Z','AI Studio project rate-limit page; Free tier');
create table public.model_usage_events (
  id uuid primary key default gen_random_uuid(), model text not null references public.model_catalog(model),
  user_id uuid references public.profiles(id) on delete set null, created_at timestamptz not null default now(),
  status text not null default 'reserved' check (status in ('reserved','success','rate_limited','unavailable','invalid_response','failed')),
  reserved_tokens integer not null check (reserved_tokens > 0), input_tokens integer, output_tokens integer, latency_ms integer
);
create index model_usage_window on public.model_usage_events(model,created_at desc);
create index model_usage_user on public.model_usage_events(user_id);
create table public.app_controls (id boolean primary key default true check(id), reviews_enabled boolean not null default true);
insert into public.app_controls default values;
create table public.admin_audit (id bigint generated always as identity primary key, actor_id uuid references public.profiles(id) on delete set null,
  target text not null, action text not null, created_at timestamptz not null default now());
create index admin_audit_actor on public.admin_audit(actor_id);
alter table public.model_catalog enable row level security;
alter table public.model_usage_events enable row level security;
alter table public.app_controls enable row level security;
alter table public.admin_audit enable row level security;
revoke all on public.model_catalog, public.model_usage_events, public.app_controls, public.admin_audit from public,anon,authenticated;
grant all on public.model_catalog, public.model_usage_events, public.app_controls, public.admin_audit to service_role;
grant usage,select on sequence public.admin_audit_id_seq to service_role;

create function public.reserve_model_request(p_user_id uuid,p_model text,p_tokens integer) returns uuid
language plpgsql security invoker set search_path = '' as $$
declare c public.model_catalog; event_id uuid; minute_count integer; day_count integer; minute_tokens bigint;
  day_start timestamptz := date_trunc('day',now() at time zone 'America/Los_Angeles') at time zone 'America/Los_Angeles';
begin
  if not exists(select 1 from public.profiles where id=p_user_id and is_approved)
    or not (select reviews_enabled from public.app_controls where id) then return null; end if;
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
  delete from public.model_usage_events where created_at < now()-interval '32 days';
  delete from public.admin_audit where created_at < now()-interval '90 days';
  return event_id;
end $$;

create function public.finish_model_request(p_event uuid,p_user_id uuid,p_status text,p_input integer,p_output integer,p_latency integer,p_cooldown integer) returns void
language plpgsql security invoker set search_path = '' as $$
declare model_name text;
begin
  update public.model_usage_events set status=p_status,input_tokens=greatest(p_input,0),output_tokens=greatest(p_output,0),latency_ms=greatest(p_latency,0)
    where id=p_event and user_id=p_user_id and status='reserved' returning model into model_name;
  if model_name is not null and p_cooldown>0 then
    update public.model_catalog set cooldown_until=greatest(coalesce(cooldown_until,now()),now()+make_interval(secs=>least(p_cooldown,90000))) where model=model_name;
  end if;
end $$;

create function public.super_admin_update(p_actor uuid,p_target uuid,p_role text,p_approved boolean,p_hourly integer,p_daily integer) returns void
language plpgsql security invoker set search_path = '' as $$
declare previous public.profiles;
begin
  perform pg_advisory_xact_lock(hashtextextended('super_admin_configuration',0));
  if not exists(select 1 from public.profiles where id=p_actor and is_approved and role='super_admin') then raise exception 'access_revoked'; end if;
  if p_role not in ('user','admin','super_admin') or p_hourly not between 1 and 100 or p_daily not between 1 and 1000 then raise exception 'invalid_settings'; end if;
  select * into previous from public.profiles where id=p_target for update;
  if previous.id is null then raise exception 'unknown_user'; end if;
  if p_actor=p_target and not p_approved then raise exception 'cannot_revoke_self'; end if;
  if previous.role='super_admin' and previous.is_approved and (p_role<>'super_admin' or not p_approved)
    and not exists(select 1 from public.profiles where role='super_admin' and is_approved and id<>p_target) then raise exception 'last_super_admin'; end if;
  update public.profiles set role=p_role,is_approved=p_approved,hourly_limit=p_hourly,daily_limit=p_daily where id=p_target;
  insert into public.admin_audit(actor_id,target,action) values(p_actor,p_target::text,'Profile permissions and review limits updated');
end $$;

create function public.set_team_approval(p_actor uuid,p_target uuid,p_approved boolean) returns void
language plpgsql security invoker set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(hashtextextended('super_admin_configuration',0));
  if p_actor=p_target or not exists(select 1 from public.profiles where id=p_actor and is_approved and role in ('admin','super_admin')) then raise exception 'access_revoked'; end if;
  if not exists(select 1 from public.profiles where id=p_target and role='user') then raise exception 'super_admin_required'; end if;
  update public.profiles set is_approved=p_approved where id=p_target;
  insert into public.admin_audit(actor_id,target,action) values(p_actor,p_target::text,case when p_approved then 'Approved' else 'Revoked' end);
end $$;

create function public.configure_free_model(p_actor uuid,p_model text,p_enabled boolean,p_priority integer,p_rpm integer,p_tpm integer,p_rpd integer) returns void
language plpgsql security invoker set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(hashtextextended(p_model,0));
  if not exists(select 1 from public.profiles where id=p_actor and is_approved and role='super_admin') then raise exception 'access_revoked'; end if;
  update public.model_catalog set enabled=p_enabled,priority=p_priority,rpm=p_rpm,tpm=p_tpm,rpd=p_rpd where model=p_model;
  if not found then raise exception 'unknown_model'; end if;
  insert into public.admin_audit(actor_id,target,action) values(p_actor,p_model,'Free-model routing and application caps updated');
end $$;

create function public.set_reviews_enabled(p_actor uuid,p_enabled boolean) returns void
language plpgsql security invoker set search_path = '' as $$
begin
  if not exists(select 1 from public.profiles where id=p_actor and is_approved and role='super_admin') then raise exception 'access_revoked'; end if;
  update public.app_controls set reviews_enabled=p_enabled where id;
  insert into public.admin_audit(actor_id,target,action) values(p_actor,'reviews','Reviews enabled: '||p_enabled::text);
end $$;

-- PUBLIC has execute by default; explicitly remove it from every privileged RPC.
revoke all on function public.reserve_model_request(uuid,text,integer),public.finish_model_request(uuid,uuid,text,integer,integer,integer,integer),
 public.super_admin_update(uuid,uuid,text,boolean,integer,integer),public.set_team_approval(uuid,uuid,boolean),
 public.configure_free_model(uuid,text,boolean,integer,integer,integer,integer),public.set_reviews_enabled(uuid,boolean) from public,anon,authenticated;
grant execute on function public.reserve_model_request(uuid,text,integer),public.finish_model_request(uuid,uuid,text,integer,integer,integer,integer),
 public.super_admin_update(uuid,uuid,text,boolean,integer,integer),public.set_team_approval(uuid,uuid,boolean),
 public.configure_free_model(uuid,text,boolean,integer,integer,integer,integer),public.set_reviews_enabled(uuid,boolean) to service_role;

create function public.model_usage_overview(p_actor uuid) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare result jsonb; day_start timestamptz:=date_trunc('day',now() at time zone 'America/Los_Angeles') at time zone 'America/Los_Angeles';
begin
  if not exists(select 1 from public.profiles where id=p_actor and is_approved and role='super_admin') then raise exception 'access_revoked'; end if;
  select jsonb_build_object('checked_at',now(),'day_resets_at',(date_trunc('day',now() at time zone 'America/Los_Angeles')+interval '1 day') at time zone 'America/Los_Angeles',
    'reviews_enabled',(select reviews_enabled from public.app_controls where id),
    'models',coalesce((select jsonb_agg(to_jsonb(s) order by priority,model) from (
      select c.*,count(e.id) filter(where e.created_at>=day_start) as requests_today,
        count(e.id) filter(where e.created_at>now()-interval '60 seconds') as requests_minute,
        coalesce(sum(greatest(e.reserved_tokens,coalesce(e.input_tokens,0))) filter(where e.created_at>now()-interval '60 seconds'),0) as tokens_minute,
        coalesce(sum(e.input_tokens) filter(where e.created_at>=day_start),0) as input_tokens_today,
        coalesce(sum(e.output_tokens) filter(where e.created_at>=day_start),0) as output_tokens_today,
        count(e.id) filter(where e.created_at>=day_start and e.status not in ('success','reserved')) as errors_today,
        count(e.id) filter(where e.created_at>=day_start and e.status='reserved') as pending_today
      from public.model_catalog c left join public.model_usage_events e on e.model=c.model and e.created_at>=least(day_start,now()-interval '60 seconds') group by c.model
    ) s),'[]'::jsonb),
    'audit',coalesce((select jsonb_agg(to_jsonb(a)) from (select actor_id,target,action,created_at from public.admin_audit order by created_at desc limit 100) a),'[]'::jsonb)) into result;
  return result;
end $$;
revoke all on function public.model_usage_overview(uuid) from public,anon,authenticated;
grant execute on function public.model_usage_overview(uuid) to service_role;

create or replace function public.reserve_review_attempt(p_user_id uuid,p_request_id uuid,p_hourly_limit integer,p_daily_limit integer) returns boolean
language plpgsql security invoker set search_path='' as $$
declare hourly_count integer; daily_count integer; limits public.profiles;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_user_id::text,0));
  select * into limits from public.profiles where id=p_user_id and is_approved;
  if limits.id is null or not (select reviews_enabled from public.app_controls where id) then return false; end if;
  if exists(select 1 from public.review_attempts where request_id=p_request_id) then return false; end if;
  delete from public.review_attempts where user_id=p_user_id and requested_at<now()-interval '32 days';
  select count(*) filter(where requested_at>now()-interval '1 hour'),count(*) into hourly_count,daily_count
    from public.review_attempts where user_id=p_user_id and requested_at>now()-interval '24 hours';
  if hourly_count>=limits.hourly_limit or daily_count>=limits.daily_limit then return false; end if;
  insert into public.review_attempts(request_id,user_id) values(p_request_id,p_user_id);
  return true;
end $$;

drop policy if exists "Admins can read all logs" on public.review_logs;
create policy "Admins can read all logs" on public.review_logs for select to authenticated
using (exists(select 1 from public.profiles where id=(select auth.uid()) and is_approved and role in ('admin','super_admin')));
notify pgrst,'reload schema';

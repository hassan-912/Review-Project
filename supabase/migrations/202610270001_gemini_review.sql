-- Gemini accounting contains metadata only, never document text or model output.
begin;
alter table public.profiles alter column daily_limit set default 5;
update public.profiles set daily_limit=least(daily_limit,5);
alter table public.profiles add constraint profiles_daily_limit_max_five check(daily_limit between 1 and 5);

create or replace function public.reserve_review_attempt(
 p_user_id uuid,p_request_id uuid,p_hourly_limit integer,p_daily_limit integer
) returns boolean language plpgsql security invoker set search_path='' as $$
declare limits public.profiles; hourly_count integer; daily_count integer;
 day_start timestamptz:=date_trunc('day',now() at time zone 'Africa/Cairo') at time zone 'Africa/Cairo';
begin
 perform pg_advisory_xact_lock(hashtextextended(p_user_id::text,0));
 select * into limits from public.profiles where id=p_user_id and is_approved;
 if limits.id is null or not coalesce((select reviews_enabled and not maintenance_enabled from public.app_controls where id),false) then return false; end if;
 if exists(select 1 from public.review_attempts where request_id=p_request_id) then return false; end if;
 select count(*) filter(where requested_at>now()-interval '1 hour'),
        count(*) filter(where requested_at>=day_start) into hourly_count,daily_count
 from public.review_attempts where user_id=p_user_id and requested_at>=least(day_start,now()-interval '1 hour');
 if hourly_count>=limits.hourly_limit or daily_count>=least(limits.daily_limit,5) then return false; end if;
 insert into public.review_attempts(request_id,user_id) values(p_request_id,p_user_id);
 return true;
end $$;
revoke all on function public.reserve_review_attempt(uuid,uuid,integer,integer) from public,anon,authenticated;
grant execute on function public.reserve_review_attempt(uuid,uuid,integer,integer) to service_role;

create table public.gemini_review_usage (
 id uuid primary key,
 review_id uuid not null unique references public.review_attempts(request_id),
 user_id uuid not null references public.profiles(id) on delete cascade,
 username text not null,
 created_at timestamptz not null default now(),
 model text not null,
 status text not null default 'reserved' check(status in ('reserved','completed','failed')),
 input_tokens integer check(input_tokens>=0),
 output_tokens integer check(output_tokens>=0),
 thinking_tokens integer check(thinking_tokens>=0),
 billable_output_tokens integer check(billable_output_tokens>=0),
 cached_input_tokens integer check(cached_input_tokens>=0),
 usage_known boolean not null default false,
 input_rate numeric not null check(input_rate>=0),
 cached_rate numeric not null check(cached_rate>=0),
 output_rate numeric not null check(output_rate>=0),
 price_source text not null,
 usd_egp numeric check(usd_egp>0),
 fx_date date,
 fx_source text not null,
 cost_usd numeric check(cost_usd>=0),
 cost_egp numeric check(cost_egp>=0),
 files jsonb not null default '[]'::jsonb,
 latency_ms integer check(latency_ms>=0)
);
create index gemini_usage_created on public.gemini_review_usage(created_at,id);
create index gemini_usage_user_created on public.gemini_review_usage(user_id,created_at);
alter table public.gemini_review_usage enable row level security;
revoke all on public.gemini_review_usage from public,anon,authenticated;
grant select,insert,update on public.gemini_review_usage to service_role;

create function public.reserve_gemini_usage(p_user_id uuid,p_review_id uuid,p_event jsonb)
returns boolean language plpgsql security invoker set search_path='' as $$
declare reviewer public.profiles;
begin
 perform pg_advisory_xact_lock(hashtextextended(p_user_id::text,0));
 select * into reviewer from public.profiles where id=p_user_id and is_approved;
 if reviewer.id is null or not coalesce((select reviews_enabled and not maintenance_enabled from public.app_controls where id),false) then return false; end if;
 if not exists(select 1 from public.review_attempts where request_id=p_review_id and user_id=p_user_id and status='running') then return false; end if;
 if exists(select 1 from public.gemini_review_usage where review_id=p_review_id) then return false; end if;
 insert into public.gemini_review_usage(id,review_id,user_id,username,model,input_rate,cached_rate,output_rate,
 price_source,usd_egp,fx_date,fx_source,files)
 values((p_event->>'id')::uuid,p_review_id,p_user_id,coalesce(reviewer.username,''),p_event->>'model',
 (p_event->>'input_rate')::numeric,(p_event->>'cached_rate')::numeric,(p_event->>'output_rate')::numeric,
 p_event->>'price_source',(p_event->>'usd_egp')::numeric,(p_event->>'fx_date')::date,p_event->>'fx_source',p_event->'files');
 return true;
end $$;
revoke all on function public.reserve_gemini_usage(uuid,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.reserve_gemini_usage(uuid,uuid,jsonb) to service_role;
notify pgrst,'reload schema';
commit;

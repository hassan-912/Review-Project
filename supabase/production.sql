-- Server-only guardrails. Existing profiles and review_logs schemas are preserved.
begin;
alter table public.profiles enable row level security;
alter table public.review_logs enable row level security;

-- Signup triggers require definer privileges, but must not be callable through the API.
alter function public.handle_new_user() set search_path = '';
revoke execute on function public.handle_new_user() from public, anon, authenticated;

create table if not exists public.review_attempts (
    request_id uuid primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    requested_at timestamptz not null default now()
);
alter table public.review_attempts enable row level security;
revoke all on public.review_attempts from anon, authenticated;
grant select, insert, delete on public.review_attempts to service_role;
create index if not exists review_attempts_user_time_idx
    on public.review_attempts(user_id, requested_at);

create or replace function public.reserve_review_attempt(
    p_user_id uuid, p_request_id uuid, p_hourly_limit integer, p_daily_limit integer
) returns boolean
language plpgsql security invoker set search_path = '' as $$
declare hourly_count integer; daily_count integer;
begin
    if p_hourly_limit <= 0 or p_daily_limit <= 0 then
        raise exception 'Invalid review allowance';
    end if;
    -- Serialize concurrent requests from the same user across every app worker.
    perform pg_advisory_xact_lock(hashtextextended(p_user_id::text, 0));
    if not exists (select 1 from public.profiles where id=p_user_id and is_approved=true) then
        return false;
    end if;
    -- A request ID can only reserve once; failed reviews also consume an attempt.
    if exists (select 1 from public.review_attempts where request_id=p_request_id) then
        return false;
    end if;
    delete from public.review_attempts where user_id=p_user_id and requested_at < now()-interval '32 days';
    select count(*) filter (where requested_at > now()-interval '1 hour'), count(*)
        into hourly_count, daily_count from public.review_attempts
        where user_id=p_user_id and requested_at > now()-interval '24 hours';
    if hourly_count >= p_hourly_limit or daily_count >= p_daily_limit then
        return false;
    end if;
    insert into public.review_attempts(request_id,user_id) values (p_request_id,p_user_id);
    return true;
end;
$$;
revoke all on function public.reserve_review_attempt(uuid,uuid,integer,integer) from public,anon,authenticated;
grant execute on function public.reserve_review_attempt(uuid,uuid,integer,integer) to service_role;
create index if not exists review_logs_user_timestamp_idx on public.review_logs(user_id,timestamp desc);
notify pgrst, 'reload schema';
commit;

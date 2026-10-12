-- Additive production change. Authorization remains in protected profile columns.
alter table public.profiles add column if not exists username text;
with bases as (
  select id, case when lower(split_part(email,'@',1)) ~ '^[a-z0-9]'
    then left(regexp_replace(lower(split_part(email,'@',1)), '[^a-z0-9_.-]', '_', 'g'),24)
    else 'user' end as base from public.profiles where username is null
), numbered as (
  select id,base,row_number() over(partition by base order by id) as n from bases
)
update public.profiles p set username = case when length(b.base)<3 then 'user_'||b.base else b.base end
  || case when b.n>1 then '_'||b.n::text else '' end
from numbered b where p.id=b.id;
alter table public.profiles alter column username set not null;
alter table public.profiles add constraint profiles_username_format check (username ~ '^[a-z0-9][a-z0-9_.-]{2,31}$');
create unique index if not exists profiles_username_unique on public.profiles(lower(username));
create or replace function public.handle_new_user() returns trigger language plpgsql
security definer set search_path='' as $$
declare chosen text;
begin
  chosen := lower(trim(new.raw_user_meta_data->>'username'));
  if chosen is null or chosen !~ '^[a-z0-9][a-z0-9_.-]{2,31}$' then
    raise exception 'Valid username required';
  end if;
  insert into public.profiles(id,email,username,is_approved,role)
  values(new.id,new.email,chosen,false,'user');
  return new;
end;
$$;
revoke execute on function public.handle_new_user() from public,anon,authenticated;
alter table public.review_logs add column if not exists submitted_username text;
update public.review_logs l set submitted_username=p.username from public.profiles p where l.user_id=p.id and l.submitted_username is null;
-- Reviews are written by the verified server only, so users cannot spoof attribution/score.
drop policy if exists "Users can insert own logs" on public.review_logs;
revoke insert,update,delete on public.review_logs from anon,authenticated;
alter table public.review_attempts add column if not exists client_name text;
alter table public.review_attempts add column if not exists submitted_username text;
alter table public.review_attempts add column if not exists submitted_by text;
alter table public.review_attempts add column if not exists score numeric;
alter table public.review_attempts add column if not exists status text not null default 'legacy';
alter table public.review_attempts add constraint review_attempts_status check(status in ('legacy','running','completed','failed'));
update public.review_attempts a set submitted_username=p.username,submitted_by=p.email from public.profiles p where a.user_id=p.id and a.submitted_username is null;
alter table public.profiles enable row level security;
alter table public.review_logs enable row level security;
alter table public.review_attempts enable row level security;

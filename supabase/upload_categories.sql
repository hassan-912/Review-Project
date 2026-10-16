-- No documents or balances are stored. This setting is shared by all approved users.
alter table public.app_controls add column if not exists upload_category_order text[] not null
default array['passport','visa_form','cover_letter','hotel','flight','insurance','employment','travel_plan','bank_statement','supporting'];

create or replace function public.set_upload_category_order(p_actor uuid,p_order text[]) returns void
language plpgsql security invoker set search_path='' as $$
declare expected text[]:=array['passport','visa_form','cover_letter','hotel','flight','insurance','employment','travel_plan','bank_statement','supporting'];
begin
  if not exists(select 1 from public.profiles where id=p_actor and is_approved and role='super_admin') then
    raise exception 'access_revoked';
  end if;
  if p_order is null or cardinality(p_order)<>10 or not (p_order @> expected and p_order <@ expected)
    or array_position(p_order,null) is not null then raise exception 'invalid_categories'; end if;
  update public.app_controls set upload_category_order=p_order where id;
  insert into public.admin_audit(actor_id,target,action) values(p_actor,'upload_categories','Upload category order updated');
end $$;
revoke all on function public.set_upload_category_order(uuid,text[]) from public,anon,authenticated;
grant execute on function public.set_upload_category_order(uuid,text[]) to service_role;

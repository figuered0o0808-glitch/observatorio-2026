-- Perfil de quem se cadastra no mural, e as preferências que a pessoa quiser levar de um
-- navegador para outro. Só isso: email e senha ficam com o Supabase, em auth.users.
--
-- Regra de acesso por linha ligada em tudo: cada pessoa lê e escreve a própria linha e mais
-- nada. Sem isso, qualquer usuário logado leria a tabela inteira com a chave anon.

create table if not exists public.perfil (
  id           uuid primary key references auth.users(id) on delete cascade,
  nome         text,
  area         text,
  preferencias jsonb not null default '{}'::jsonb,
  criado_em    timestamptz not null default now(),
  visto_em     timestamptz
);

alter table public.perfil enable row level security;

create policy "cada um lê o próprio perfil"    on public.perfil for select using (auth.uid() = id);
create policy "cada um cria o próprio perfil"  on public.perfil for insert with check (auth.uid() = id);
create policy "cada um edita o próprio perfil" on public.perfil for update using (auth.uid() = id) with check (auth.uid() = id);
create policy "cada um apaga o próprio perfil" on public.perfil for delete using (auth.uid() = id);

-- a linha do perfil nasce junto com a conta, para o app nunca ter de criar depois
create or replace function public.ao_criar_usuario()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.perfil (id, nome, area)
  values (new.id, new.raw_user_meta_data->>'nome', coalesce(new.raw_user_meta_data->>'area',''))
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists ao_criar_usuario on auth.users;
create trigger ao_criar_usuario after insert on auth.users
  for each row execute function public.ao_criar_usuario();

-- Storage: o bucket 'mural' é privado, e só quem está logado pode pedir link assinado da carga.
insert into storage.buckets (id, name, public) values ('mural', 'mural', false)
on conflict (id) do nothing;

create policy "logado lê a carga do mural" on storage.objects for select
  using (bucket_id = 'mural' and auth.role() = 'authenticated');

-- Direito de exclusão (LGPD art. 18, VI): a pessoa apaga a própria conta de dentro do mural,
-- sem precisar pedir por email. Só isso justifica security definer aqui: apagar de auth.users
-- exige privilégio que a chave pública do aplicativo não tem, e a função apaga exclusivamente
-- a linha de quem chamou. O perfil vai junto pelo on delete cascade.
create or replace function public.apagar_minha_conta()
returns void language plpgsql security definer set search_path = public, auth as $$
declare eu uuid := auth.uid();
begin
  if eu is null then raise exception 'sem sessão'; end if;
  delete from public.perfil where id = eu;
  delete from auth.users where id = eu;
end $$;

revoke all on function public.apagar_minha_conta() from public, anon;
grant execute on function public.apagar_minha_conta() to authenticated;

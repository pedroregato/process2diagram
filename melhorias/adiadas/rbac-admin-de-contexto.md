# Ideia registrada: RBAC — admin restrito a um contexto

## Origem

Levantado durante o planejamento de `templates-ata-por-contexto.md` (2026-07-08): a permissão de configurar o template de ata de um contexto foi definida como "admin ou master" — mas isso são papéis **globais** (`modules/auth.py`, `master > admin > user`, `is_admin()` cobre os dois). Não existe hoje uma role "admin só daquele contexto específico".

## Estado atual (verificado)

- `modules/auth.py::is_admin()` — `True` para `"admin"` e `"master"`, sem distinção de contexto. Um admin vê/administra **todos** os contextos, não um subconjunto.
- Não há tabela de papel por contexto (ex: `context_roles` ou similar) — `contexts` não tem nenhuma coluna de "dono"/"responsável".

## Por que pode valer a pena

Em uma instalação multi-tenant/multi-contexto (vários domínios, cada um com vários contextos), um admin global enxerga e administra tudo — pode não ser o desejado quando diferentes equipes/clientes compartilham a mesma instância e cada um deveria só mexer no próprio contexto (ex: alguém do SDEA não deveria conseguir configurar o template de outro contexto do mesmo domínio, mesmo sendo "admin" nominalmente).

## O que precisa ser decidido antes de virar um plano de verdade

1. Quem concede a role de "admin do contexto" — só master global, ou o próprio admin global pode delegar?
2. Um usuário pode ser admin de múltiplos contextos, ou só um?
3. Isso substitui `is_admin()` nos pontos já existentes que checam admin (ex: `_ADMIN_TOOLS` do Assistente, várias telas de manutenção), ou é uma camada **adicional** só para ações escopadas a contexto (como o template de ata), deixando `is_admin()` global intacto para o resto?
4. Vale a pena agora, ou só quando o projeto realmente tiver múltiplos domínios/contextos com equipes que não deveriam se ver?

## Status

Ideia registrada, sem plano detalhado ainda — decisão do usuário foi seguir com admin/master global no plano de templates de ata por enquanto, e tratar isto separadamente quando houver prioridade. Retomar como um `melhorias/*.md` completo (mesmo formato do plano de templates de ata) quando as perguntas acima tiverem resposta.

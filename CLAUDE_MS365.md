# CLAUDE_MS365.md — Integração Microsoft 365 (Outlook + Teams) no Process2Diagram

> Status: **PENDENTE** — aguardando App Registration no Azure AD pelo TI corporativo.
> Bloqueio: fluxo client_credentials exige admin consent. Sem isso, a implementação não pode ser concluída.

## Contexto

- **App**: Streamlit + `AssistantToolExecutor` (`core/assistant_tools.py`)
- **Padrão a seguir**: `modules/calendar_client.py` (Google Calendar)
- **Objetivo**:
  1. Enviar ata (minutes_md) e relatório executivo (HTML) via Outlook
  2. Agendar reunião no Teams com lista de participantes

## Bloqueio atual

O fluxo `client_credentials` (app-only, sem usuário) exige que um administrador
do Azure AD / Microsoft Entra ID conceda consentimento administrativo para as
permissões de aplicativo. A organização usa contas corporativas mas não há
administradores disponíveis no projeto.

**Ação necessária:** abrir chamado de TI com o texto em `docs/ms365_ti_request.md`
(ou equivalente), solicitando a criação do App Registration e entrega de
`client_id`, `client_secret` e `tenant_id`.

## Arquitetura planejada

```
Assistente P2D
    └── AssistantToolExecutor
            ├── outlook_send_email      (admin-only)
            └── teams_schedule_meeting  (admin-only)
                        │
                        ▼
              modules/office_client.py
                        │
                        ▼
              MSAL ConfidentialClientApplication
                        │
                        ▼
              Microsoft Graph API v1.0
                  /users/{sender}/sendMail
                  /users/{sender}/events  (isOnlineMeeting=true)
```

## Permissões Graph API necessárias

| Permissão | Tipo | Para que serve |
|---|---|---|
| `Mail.Send` | Application | Enviar e-mail em nome de uma caixa |
| `Calendars.ReadWrite` | Application | Criar eventos no calendário |
| `OnlineMeetings.ReadWrite` | Application | Criar reuniões Teams com link |

## Secrets necessários (após setup do TI)

```toml
# .streamlit/secrets.toml
[microsoft_365]
client_id      = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
client_secret  = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
tenant_id      = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
default_sender = "usuario@dominio.com.br"   # caixa que envia os e-mails
```

## Dependências a adicionar em requirements.txt

```
msal==1.31.0
```
(`requests` já disponível via supabase/google-auth)

## Implementação planejada

### modules/office_client.py (novo)

Funções públicas:
- `ms365_configured() -> bool`
- `send_outlook_email(to, subject, body, body_type, attachments) -> str`
- `schedule_teams_meeting(subject, start_time, end_time, attendees, body) -> str`
- `diagnose_ms365() -> str`  — diagnóstico passo a passo (padrão do calendar_client)

### core/assistant_tools.py (extensão)

Novas ferramentas (admin-only):
- `outlook_send_email` — envia ata/relatório por e-mail com anexos opcionais
- `teams_schedule_meeting` — cria reunião Teams com convite para lista de participantes

Adicionar a `_TOOL_CATEGORIES` (categoria "admin") e `_ADMIN_TOOLS`.

### agents/agent_assistant.py

Adicionar bloco "CAPACIDADES MICROSOFT 365" no `_SYSTEM_TOOLS_TEMPLATE`,
seguindo o mesmo padrão do bloco "CAPACIDADES GOOGLE CALENDAR".

## Alternativa parcial (sem admin TI)

Caso o TI negue ou demore: implementar `outlook_send_email` via **SMTP**
com senha de aplicativo — cobre envio de ata sem Graph API.
Teams scheduling não tem alternativa sem Graph API.

## Referências

- Microsoft Graph API: https://learn.microsoft.com/en-us/graph/api/overview
- MSAL Python: https://learn.microsoft.com/en-us/entra/identity-platform/msal-python
- Padrão interno: `modules/calendar_client.py`

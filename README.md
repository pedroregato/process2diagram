# Process2Diagram — Arquitetura v2

## Visão Geral

Pipeline multi-provedor de LLM que converte transcrições de reuniões em diagramas de processo.
Suporta DeepSeek, Claude, OpenAI, Groq e Gemini por meio de uma interface unificada.

---

## Estrutura do Projeto

```
process2diagram/
│
├── app.py                    # Interface Streamlit + orquestração
├── requirements.txt
│
└── modules/
    ├── config.py             # ★ Registro de provedores — adicione novos LLMs aqui
    ├── session_security.py   # ★ Segurança da chave de API (armazenamento apenas na sessão)
    ├── schema.py             # Modelo de dados do processo (Etapas, Arestas, Decisões)
    ├── ingest.py             # Leitura da transcrição
    ├── preprocess.py         # Limpeza do texto
    ├── extract_llm.py        # ★ Roteamento multi-LLM + extração
    ├── diagram_mermaid.py    # Gerador de fluxograma Mermaid
    ├── diagram_drawio.py     # Gerador de XML Draw.io
    └── utils.py              # Exportação JSON
```

---

## Como Adicionar um Novo Provedor de LLM

Edite apenas o arquivo `modules/config.py`. Adicione uma entrada:

```python
"Meu Provedor": {
    "default_model": "nome-do-modelo",
    "base_url": "https://api.meuprovedor.com/v1",   # None para Anthropic
    "api_key_label": "Chave de API — Meu Provedor",
    "api_key_help": "Obtenha sua chave em meuprovedor.com",
    "api_key_prefix": "sk-",
    "client_type": "openai_compatible",  # ou "anthropic"
    "cost_hint": "$X / $Y por 1M tokens",
    "supports_json_mode": True,
    "supports_system_prompt": True,
},
```

Se o provedor expõe uma API compatível com o formato OpenAI → funciona automaticamente.
Se utiliza um SDK próprio → adicione um handler em `extract_llm.py → call_llm()`.

---

## Modelo de Segurança da Chave de API

### Estratégia: isolamento por sessão

As chaves são armazenadas **exclusivamente** em `st.session_state`, que é:

- Memória RAM do servidor, isolada por sessão de navegador
- Destruída ao fechar a aba ou quando a sessão expira
- Nunca gravada em disco, banco de dados, logs ou variáveis de ambiente

### O que isso garante na prática

| Ameaça | Protegido? |
|---|---|
| Outro usuário no Streamlit Cloud ver sua chave | ✅ Sim — sessões são completamente isoladas |
| Chave persistir após fechar a aba | ✅ Não há persistência |
| Chave aparecer nos logs do servidor | ✅ Nunca registrada |
| Chave enviada a terceiros | ✅ Enviada apenas ao provedor de LLM escolhido |
| Servidor Streamlit Cloud comprometido | ❌ Não protegido (use `st.secrets` neste caso) |

### Para implantações com maior nível de segurança

Utilize o padrão de proxy backend:

```
Usuário → Seu Backend (chave armazenada em st.secrets) → Provedor de LLM
```

Nesse modelo, o frontend nunca tem acesso à chave.

---

## Executando Localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Implantando no Streamlit Cloud

1. Faça o push do repositório para o GitHub
2. Acesse share.streamlit.io → New app
3. Selecione o repositório e defina `Main file: app.py`
4. Clique em Deploy — nenhuma configuração de secrets é necessária (cada usuário insere sua própria chave)

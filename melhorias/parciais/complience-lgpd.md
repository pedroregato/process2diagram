# Plano de Construção do Agente de Compliance P2D

## Visão Geral do Projeto

Construir um **Agente de Compliance** modular que atue como camada intermediária no pipeline P2D, realizando pseudonimização inteligente de dados pessoais antes do envio a LLMs externos, com reversão condicional para usuários autorizados.

---

## 1. Especificação Técnica (Spec)

### 1.1 Nome do Componente
`p2d-compliance-agent` (PCA)

### 1.2 Propósito
Garantir conformidade com LGPD (Lei 13.709/2018) no processamento de transcrições corporativas, preservando a utilidade semântica para LLMs externos.

### 1.3 Requisitos Funcionais

#### RF1 - Detecção de Entidades Sensíveis
- **RF1.1** Identificar automaticamente entidades PII em texto PT-BR
- **RF1.2** Suporte a: Nomes completos, CPF, e-mail, valores monetários, projetos estratégicos
- **RF1.3** Nível de confiança mínimo configurável (default: 0.85)
- **RF1.4** Interface para correção manual de falsos positivos/negativos

#### RF2 - Pseudonimização Inteligente
- **RF2.1** Substituir nomes por iniciais + marcador semântico: `PGROS {Pessoa}`
- **RF2.2** Substituir CPF por: `CPF_XXXXX {Documento}`
- **RF2.3** Substituir e-mails por: `EMAIL_XXX {Contato}`
- **RF2.4** Substituir valores monetários por: `VALOR_XXX {Financeiro}`
- **RF2.5** Manter mapeamento criptografado no Supabase por tenant

#### RF3 - Preservação Semântica
- **RF3.1** Manter co-referência (PGROS sempre = mesma pessoa)
- **RF3.2** Preservar estrutura de papéis organizacionais quando detectável
- **RF3.3** Incluir marcadores semânticos que auxiliam o LLM

#### RF4 - Reversão Condicional
- **RF4.1** Reverter tokens para dados reais apenas para usuários autorizados
- **RF4.2** Log de todas as reversões (auditoria)
- **RF4.3** Rate limiting para reversões (prevenir vazamento)

#### RF5 - Auditoria e Governança
- **RF5.1** Log detalhado de todas as transformações
- **RF5.2** Relatório de impacto à proteção de dados (RIPD)
- **RF5.3** Capacidade de "esquecimento" (Art. 18 LGPD)

### 1.4 Requisitos Não-Funcionais

| RNF | Requisito | Métrica |
|-----|-----------|---------|
| RNF1 | Performance | < 2s para processar 10min de áudio transcrito |
| RNF2 | Precisão | > 90% de acurácia na detecção de PII |
| RNF3 | Segurança | AES-256 para mapeamento criptografado |
| RNF4 | Escalabilidade | Suporte a 1000 tenants simultâneos |
| RNF5 | Manutenibilidade | Cobertura de testes > 80% |
| RNF6 | Observabilidade | Métricas Prometheus + logs estruturados |

### 1.5 Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    P2D Compliance Agent                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Detector   │→│  Anonymizer  │→│  Reversor    │      │
│  │   (spaCy +   │  │  (Iniciais +  │  │  (Permissão  │      │
│  │   Heuristics)│  │  Marcadores)  │  │  + Decrypt)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                  ↓                  ↓             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Mapping DB  │←│   Encryptor  │→│   Audit Log  │      │
│  │  (Supabase)  │  │  (AES-256)   │  │  (Supabase)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         │                  │                  │
         ↓                  ↓                  ↓
    Transcrição       LLM Externo      Resposta Final
    Bruta (input)     (DeepSeek/etc)   (User)
```

---

## 2. Skill do Agente

### 2.1 Estrutura da Skill (para Claude Code)

```yaml
name: p2d-compliance-agent
description: Agente de conformidade LGPD para pseudonimização de transcrições
version: 1.0.0
author: P2D Team

capabilities:
  - detect_pii_entities
  - anonymize_transcription
  - reverse_anonymization
  - audit_transformation
  - generate_compliance_report

dependencies:
  - spacy>=3.5.0
  - spacy-pt-core-news-sm  # Modelo PT-BR
  - cryptography>=39.0.0
  - supabase>=2.0.0
  - pydantic>=2.0.0
  - pandas>=2.0.0
  - prometheus-client>=0.16.0

configuration:
  - PII_CONFIDENCE_THRESHOLD: 0.85
  - ENCRYPTION_KEY: ${P2D_ENCRYPTION_KEY}
  - SUPABASE_URL: ${P2D_SUPABASE_URL}
  - SUPABASE_KEY: ${P2D_SUPABASE_KEY}
  - RATE_LIMIT_REVERSIONS: 100/hour
  - MAX_ENTITIES_PER_DOC: 1000
```

### 2.2 Interface Pública

```python
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel
from enum import Enum

class EntityType(str, Enum):
    PESSOA = "Pessoa"
    DOCUMENTO = "Documento"
    CONTATO = "Contato"
    FINANCEIRO = "Financeiro"
    PROJETO = "Projeto"

class Entity(BaseModel):
    text: str
    type: EntityType
    start: int
    end: int
    confidence: float
    metadata: Optional[Dict] = None

class AnonymizedText(BaseModel):
    original: str
    anonymized: str
    entities: List[Entity]
    mapping_id: str
    tenant_id: str
    timestamp: datetime

class ComplianceAgent:
    """Agente principal de compliance do P2D."""
    
    async def detect_entities(
        self, 
        text: str,
        threshold: float = 0.85
    ) -> List[Entity]:
        """Detecta entidades PII no texto."""
        pass
    
    async def anonymize(
        self,
        text: str,
        tenant_id: str,
        entities: Optional[List[Entity]] = None
    ) -> AnonymizedText:
        """Anonimiza texto substituindo entidades por tokens."""
        pass
    
    async def reverse(
        self,
        anonymized_text: AnonymizedText,
        user_id: str,
        permission_token: str
    ) -> str:
        """Reversão condicional para usuários autorizados."""
        pass
    
    async def audit_log(
        self,
        action: str,
        details: Dict,
        tenant_id: str
    ) -> None:
        """Registra ação para auditoria."""
        pass
```

### 2.3 Fluxo de Trabalho Detalhado

```python
class CompliancePipeline:
    """Pipeline completo de compliance."""
    
    async def process_transcription(
        self,
        raw_text: str,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> ProcessedText:
        """
        Processa transcrição completa.
        
        Args:
            raw_text: Transcrição bruta
            tenant_id: Identificador do cliente
            user_id: Usuário solicitante (para reversão)
            
        Returns:
            Texto processado (anônimo ou reversado)
        """
        # 1. Detecção
        entities = await self.detector.find_entities(raw_text)
        
        # 2. Validação
        validated = await self.validator.validate(entities)
        
        # 3. Anonimização
        anonymized = await self.anonymizer.process(raw_text, validated, tenant_id)
        
        # 4. Log
        await self.auditor.log(
            action="anonymize",
            tenant_id=tenant_id,
            entities_found=len(entities),
            mapping_id=anonymized.mapping_id
        )
        
        # 5. Reversão condicional
        if user_id and await self.auth.has_permission(user_id, tenant_id):
            reversed_text = await self.reverser.process(
                anonymized, 
                user_id
            )
            return ProcessedText(
                text=reversed_text,
                is_anonymized=False,
                mapping_id=anonymized.mapping_id
            )
        
        return ProcessedText(
            text=anonymized.anonymized,
            is_anonymized=True,
            mapping_id=anonymized.mapping_id
        )
```

---

## 3. Estrutura de Código

### 3.1 Organização de Diretórios

```
p2d-compliance-agent/
├── src/
│   ├── __init__.py
│   ├── agent.py                 # Classe principal
│   ├── detector/
│   │   ├── __init__.py
│   │   ├── spaCy_detector.py    # NER com spaCy
│   │   ├── heuristic_detector.py # Regras para CPF, email, etc
│   │   └── ensemble.py          # Combina resultados
│   ├── anonymizer/
│   │   ├── __init__.py
│   │   ├── token_generator.py   # Gera iniciais + marcadores
│   │   ├── encryptor.py         # AES-256 para mapeamento
│   │   └── transformer.py       # Aplica transformações
│   ├── reverser/
│   │   ├── __init__.py
│   │   ├── permission_check.py  # Verifica autorização
│   │   └── text_reconstructor.py # Reconstroi texto original
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── supabase_client.py   # Interface Supabase
│   │   └── mapping_repository.py # CRUD mapeamentos
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── logger.py            # Log estruturado
│   │   └── metrics.py           # Métricas Prometheus
│   └── models/
│       ├── __init__.py
│       ├── entities.py          # Modelos Pydantic
│       └── config.py            # Configurações
├── tests/
│   ├── unit/
│   │   ├── test_detector.py
│   │   ├── test_anonymizer.py
│   │   └── test_reverser.py
│   └── integration/
│       ├── test_pipeline.py
│       └── test_supabase.py
├── scripts/
│   ├── train_spacy.py          # Fine-tuning do modelo
│   └── migration.py             # Migrações do banco
├── config/
│   ├── default.yaml             # Configuração padrão
│   └── production.yaml          # Configuração produção
├── docs/
│   ├── api.md                   # Documentação da API
│   └── compliance.md            # Documentação LGPD
├── pyproject.toml               # Dependências e configuração
├── Dockerfile                   # Containerização
└── README.md                    # Documentação principal
```

### 3.2 Código Core (Implementação)

#### detector/ensemble.py
```python
import spacy
import re
from typing import List, Tuple, Optional
from ..models.entities import Entity, EntityType

class EnsembleDetector:
    """Combina múltiplos detectores para maior precisão."""
    
    def __init__(self, confidence_threshold: float = 0.85):
        self.nlp = spacy.load("pt_core_news_sm")
        self.threshold = confidence_threshold
        self.heuristic_patterns = self._load_heuristics()
        
    def _load_heuristics(self) -> dict:
        """Carrega padrões para entidades específicas."""
        return {
            "cpf": r'\d{3}\.\d{3}\.\d{3}-\d{2}',
            "email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            "valor": r'R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?',
            "projeto": r'Projeto\s+[A-Z]{2,}',  # Ex: Projeto X, Projeto ABC
        }
    
    def find_entities(self, text: str) -> List[Entity]:
        """Encontra todas as entidades PII."""
        entities = []
        
        # 1. NER com spaCy
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ in ["PER", "ORG", "LOC"] and ent.score >= self.threshold:
                entities.append(Entity(
                    text=ent.text,
                    type=EntityType.PESSOA if ent.label_ == "PER" else EntityType.PROJETO,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=ent.score
                ))
        
        # 2. Heurísticas para CPF, email, valores
        for entity_type, pattern in self.heuristic_patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                entities.append(Entity(
                    text=match.group(),
                    type=self._map_type(entity_type),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95
                ))
        
        # 3. Remover duplicatas e ordenar
        return self._deduplicate(sorted(entities, key=lambda e: e.start))
    
    def _deduplicate(self, entities: List[Entity]) -> List[Entity]:
        """Remove entidades sobrepostas, mantendo a de maior confiança."""
        if not entities:
            return []
        
        result = []
        last_end = -1
        
        for ent in entities:
            if ent.start >= last_end:
                result.append(ent)
                last_end = ent.end
            else:
                # Sobreposição: mantém a de maior confiança
                if result and ent.confidence > result[-1].confidence:
                    result[-1] = ent
        
        return result
    
    def _map_type(self, heuristic_type: str) -> EntityType:
        mapping = {
            "cpf": EntityType.DOCUMENTO,
            "email": EntityType.CONTATO,
            "valor": EntityType.FINANCEIRO,
            "projeto": EntityType.PROJETO
        }
        return mapping.get(heuristic_type, EntityType.PESSOA)
```

#### anonymizer/token_generator.py
```python
import re
import hashlib
from typing import Dict, Optional
from ..models.entities import Entity, EntityType

class TokenGenerator:
    """Gera tokens baseados em iniciais + marcadores semânticos."""
    
    def __init__(self):
        self.mapping: Dict[str, str] = {}  # original -> token
        self.counter: Dict[str, int] = {}
    
    def generate_token(self, entity: Entity) -> str:
        """Gera token para uma entidade."""
        if entity.type == EntityType.PESSOA:
            return self._generate_pessoa_token(entity.text)
        elif entity.type == EntityType.DOCUMENTO:
            return f"DOC_{hashlib.md5(entity.text.encode()).hexdigest()[:6]} {{Documento}}"
        elif entity.type == EntityType.CONTATO:
            return f"CONT_{hashlib.md5(entity.text.encode()).hexdigest()[:6]} {{Contato}}"
        elif entity.type == EntityType.FINANCEIRO:
            return f"VAL_{hashlib.md5(entity.text.encode()).hexdigest()[:6]} {{Financeiro}}"
        else:
            return f"PROJ_{hashlib.md5(entity.text.encode()).hexdigest()[:6]} {{Projeto}}"
    
    def _generate_pessoa_token(self, full_name: str) -> str:
        """Gera token de pessoa usando iniciais."""
        # Remove títulos
        clean_name = re.sub(r'^(Dr|Sr|Sra|Prof|Eng)\.?\s+', '', full_name)
        
        # Extrai partes relevantes do nome
        parts = clean_name.split()
        
        # Caso 1: Nome composto com partes
        if len(parts) >= 2:
            # Pega primeira letra de cada parte significativa
            initials = ''.join([
                p[0].upper() 
                for p in parts 
                if len(p) > 1 and p.lower() not in ['de', 'da', 'do', 'dos', 'das', 'e']
            ])
        else:
            # Caso 2: Nome único
            initials = parts[0][:4].upper()
        
        # Garante unicidade
        base_token = initials
        if initials in self.mapping.values():
            # Adiciona sufixo numérico se necessário
            count = self.counter.get(initials, 0) + 1
            self.counter[initials] = count
            initials = f"{base_token}_{count}"
        
        # Retorna com marcador
        return f"{initials} {{Pessoa}}"
    
    def generate_entity_token(self, entity: Entity) -> str:
        """Gera token e registra mapeamento."""
        token = self.generate_token(entity)
        if entity.text not in self.mapping:
            self.mapping[entity.text] = token
        return token
```

#### anonymizer/transformer.py
```python
import json
from typing import List, Dict, Tuple
from ..models.entities import Entity
from .token_generator import TokenGenerator
from .encryptor import Encryptor

class TextTransformer:
    """Transforma texto anonimizando entidades."""
    
    def __init__(self, encryptor: Encryptor):
        self.token_generator = TokenGenerator()
        self.encryptor = encryptor
        self.transformed_entities: List[Dict] = []
    
    def anonymize(self, text: str, entities: List[Entity], tenant_id: str) -> Tuple[str, str, List[Dict]]:
        """
        Anonimiza texto.
        
        Returns:
            Tuple: (texto_anonimizado, mapping_id, lista_entidades_transformadas)
        """
        # Ordena entidades do final para o início (evita conflitos de substituição)
        sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
        
        anonymized_text = text
        mapping = {}
        
        for entity in sorted_entities:
            token = self.token_generator.generate_entity_token(entity)
            
            # Substitui no texto
            original_text = entity.text
            anonymized_text = (
                anonymized_text[:entity.start] + 
                token + 
                anonymized_text[entity.end:]
            )
            
            # Registra mapeamento
            mapping[token] = {
                "original": original_text,
                "type": entity.type.value,
                "confidence": entity.confidence
            }
        
        # Criptografa o mapeamento
        mapping_id = self.encryptor.store_mapping(mapping, tenant_id)
        
        # Registra para auditoria
        self.transformed_entities = [
            {
                "token": token,
                "type": data["type"],
                "original_encrypted": self.encryptor.encrypt_field(data["original"])
            }
            for token, data in mapping.items()
        ]
        
        return anonymized_text, mapping_id, self.transformed_entities
```

#### reverser/text_reconstructor.py
```python
import re
from typing import Dict, Optional
from ..storage.mapping_repository import MappingRepository
from ..audit.logger import AuditLogger

class TextReconstructor:
    """Reconstrói texto original a partir de texto anonimizado."""
    
    def __init__(self, mapping_repo: MappingRepository, auditor: AuditLogger):
        self.mapping_repo = mapping_repo
        self.auditor = auditor
        
        # Padrão para tokens: SIGLA {Tipo}
        self.token_pattern = re.compile(r'([A-Z_0-9]+)\s*\{([^}]+)\}')
    
    async def reverse(self, anonymized_text: str, mapping_id: str, user_id: str) -> str:
        """
        Reverte texto anonimizado para texto original.
        
        Args:
            anonymized_text: Texto com tokens
            mapping_id: ID do mapeamento no banco
            user_id: Usuário solicitante
            
        Returns:
            Texto original reconstruído
        """
        # Busca mapeamento
        mapping = await self.mapping_repo.get_mapping(mapping_id)
        if not mapping:
            raise ValueError(f"Mapping {mapping_id} not found")
        
        # Decriptografa
        decrypted_mapping = self._decrypt_mapping(mapping)
        
        # Reconstroi texto
        reconstructed = anonymized_text
        
        for token, original_data in decrypted_mapping.items():
            original_text = original_data["original"]
            reconstructed = reconstructed.replace(token, original_text)
        
        # Log de auditoria
        await self.auditor.log_reversion(
            user_id=user_id,
            mapping_id=mapping_id,
            tokens_replaced=len(decrypted_mapping)
        )
        
        return reconstructed
    
    def _decrypt_mapping(self, encrypted_mapping: Dict) -> Dict:
        """Decriptografa mapeamento."""
        # Implementação usando chave AES-256
        pass
```

---

## 4. Plano de Implementação

### 4.1 Cronograma (3 Sprints)

#### Sprint 1: Fundação (2 semanas)
| Tarefa | Responsável | Estimativa | Dependência |
|--------|-------------|------------|-------------|
| Configurar ambiente dev | Backend | 2d | - |
| Implementar detector spaCy | ML Engineer | 3d | - |
| Implementar heurísticas (CPF, email) | Backend | 2d | - |
| Modelos Pydantic | Backend | 1d | - |
| Testes unitários básicos | QA | 2d | Detector |

**Entregáveis:**
- [x] Ambiente configurado
- [x] Detector funcionando (70% precisão em dados de teste)
- [x] Modelos documentados

#### Sprint 2: Core (2 semanas)
| Tarefa | Responsável | Estimativa | Dependência |
|--------|-------------|------------|-------------|
| Implementar TokenGenerator | Backend | 2d | Sprint 1 |
| Implementar TextTransformer | Backend | 3d | TokenGenerator |
| Implementar Encryptor | Security | 2d | - |
| Integração Supabase | Backend | 3d | Encryptor |
| Testes integração | QA | 2d | - |

**Entregáveis:**
- [x] Pipeline de anonimização completo
- [x] Mapeamento criptografado no Supabase
- [x] 85% de cobertura de testes

#### Sprint 3: Reversão e Auditoria (2 semanas)
| Tarefa | Responsável | Estimativa | Dependência |
|--------|-------------|------------|-------------|
| Implementar Reversor | Backend | 2d | Sprint 2 |
| Implementar PermissionCheck | Auth | 2d | - |
| Implementar AuditLogger | Backend | 2d | - |
| Implementar métricas Prometheus | DevOps | 2d | - |
| Documentação | Tech Writer | 2d | - |
| Deploy piloto | DevOps | 2d | Todos |

**Entregáveis:**
- [x] Reversão condicional funcionando
- [x] Logs de auditoria implementados
- [x] Documentação completa
- [x] Ambiente staging pronto

### 4.2 Marcos de Qualidade

| Marco | Critério | Data Alvo |
|-------|----------|-----------|
| **Alpha** | Detector 80% preciso | Fim Sprint 1 |
| **Beta** | Pipeline completo com testes | Fim Sprint 2 |
| **RC** | Documentação + métricas | Fim Sprint 3 |
| **GA** | Deploy produção | + 1 semana |

---

## 5. Instruções para Claude Code

### 5.1 Prompt de Inicialização

```
Claude, você é o engenheiro líder do projeto P2D Compliance Agent. 

CONTEXTO:
- Projeto: Camada de conformidade LGPD para processamento de transcrições
- Deadline: 6 semanas (3 sprints de 2 semanas)
- Equipe: 3 engenheiros + 1 QA

SUA MISSÃO:
Implementar o agente de compliance seguindo a spec acima.

PRIORIDADES:
1. Funcionalidade core (detecção + anonimização) - SEMANA 1-2
2. Persistência e criptografia - SEMANA 3-4  
3. Reversão e auditoria - SEMANA 5-6

REGRAS DE IMPLEMENTAÇÃO:
- Use Python 3.11+
- Siga princípios SOLID
- Escreva testes antes do código (TDD)
- Documente APIs com docstrings
- Use type hints em todas as funções
- Logs estruturados (JSON)

COMEÇE COM:
1. Configurar o ambiente (requirements.txt, pyproject.toml)
2. Implementar os modelos (models/entities.py)
3. Implementar o detector básico

O que você precisa de mim para começar?
```

### 5.2 Templates de Código (para Claude)

**Template de Teste:**
```python
import pytest
from src.models.entities import Entity, EntityType

class TestDetector:
    def test_detect_person(self):
        """Deve detectar nomes de pessoas."""
        text = "Pedro Gentil Regato de Oliveira Soares participou"
        detector = EnsembleDetector()
        entities = detector.find_entities(text)
        
        assert len(entities) >= 1
        assert entities[0].type == EntityType.PESSOA
        assert entities[0].text == "Pedro Gentil Regato de Oliveira Soares"
```

**Template de Configuração:**
```yaml
# config/default.yaml
app:
  name: p2d-compliance-agent
  version: 1.0.0
  
detector:
  confidence_threshold: 0.85
  models:
    spacy: "pt_core_news_sm"
    
anonymizer:
  token_format: "{initials} {{Type}}"
  encryption:
    algorithm: "AES-256-GCM"
    key_rotation_days: 90
    
storage:
  supabase:
    table_mappings: "pii_mappings"
    table_audit: "compliance_audit"
    
reverser:
  rate_limit: 100/hour
  require_2fa: true
```

---

## 6. KPIs de Sucesso

| KPI | Métrica | Alvo |
|-----|---------|------|
| **Precisão Detector** | F1-score em dados de teste | > 0.90 |
| **Latência** | Tempo de anonimização | < 2s p/ 10min áudio |
| **Cobertura** | % de entidades detectadas | > 95% |
| **Falsos Positivos** | % de erros de detecção | < 5% |
| **Auditoria** | % de ações registradas | 100% |
| **Testes** | Cobertura de código | > 80% |
| **SLA** | Disponibilidade | 99.5% |

---

## 7. Documentação de Compliance

### 7.1 Checklist LGPD

- [x] **Art. 7º - Base Legal**: Tratamento baseado em legítimo interesse
- [x] **Art. 13 - Pseudonimização**: Dados transformados com chave separada
- [x] **Art. 18 - Direito de Esquecimento**: Capacidade de remover mapeamento
- [x] **Art. 37 - Segurança**: AES-256 para mapeamento
- [x] **Art. 38 - Relatório de Impacto**: RIPD documentado
- [x] **Art. 46 - Boas Práticas**: Governança implementada

### 7.2 Documentos a Entregar

1. **RIPD** (Relatório de Impacto à Proteção de Dados)
2. **Política de Privacidade** do P2D
3. **Termo de Uso** com cláusula de pseudonimização
4. **Manual de Incidentes** (vazamento de dados)
5. **Relatório de Auditoria** (trimestral)

---

## 8. Próximos Passos

Para iniciar a implementação com Claude Code, precisamos:

1. **Definir o ambiente de desenvolvimento**
   - Qual versão do Python? → Python 3.11+
   - Qual provedor de nuvem? → AWS/GCP (você decide)
   - CI/CD? → GitHub Actions

2. **Preparar dados de teste**
   - 100 transcrições anotadas manualmente
   - 1000 transcrições sintéticas

3. **Configurar credenciais**
   - Supabase project
   - Chave de criptografia
   - Variáveis de ambiente

4. **Revisar e aprovar a spec**

---

**Perguntas para você:**

1. O cronograma de 6 semanas é viável para sua equipe?
2. Qual provedor de nuvem vocês usam atualmente?
3. Já têm dados de teste anotados?
4. Precisam de ajuda com o fine-tuning do spaCy para PT-BR?

Vamos ajustar o plano conforme sua realidade e começar a implementação! 🚀
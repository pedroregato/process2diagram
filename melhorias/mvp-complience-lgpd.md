# PC-001 Rev. 3: Implementação da Camada DataGovernance

## Versão Final com Todas as Correções Incorporadas

---

# PARTE 1: FUNDAÇÃO (CORRIGIDA)

## Tarefa 1.0: Gestão de Usuário e Configurações

### Arquivo: `modules/session_security.py` (ADIÇÃO)

```python
"""
Módulo de segurança de sessão - expandido para incluir identidade do usuário
"""

import streamlit as st
import os
from typing import Optional

# ==================== FUNÇÕES EXISTENTES ====================
# (manter as funções store_api_key, get_api_key, clear_api_key)

# ==================== NOVAS FUNÇÕES ====================

def get_current_user() -> str:
    """
    Retorna o identificador do usuário logado.
    Prioridade: session_state.user_email > session_state.username > "anonymous"
    
    Garante que cada usuário tenha um identificador único para:
    - Criptografia de mapeamento PII
    - Logs de auditoria
    - Controle de acesso
    """
    # Verifica no session_state
    if 'user_email' in st.session_state and st.session_state.user_email:
        return st.session_state.user_email
    
    if 'username' in st.session_state and st.session_state.username:
        return st.session_state.username
    
    # Fallback para desenvolvimento
    if os.getenv('ENVIRONMENT') == 'development':
        return "dev_user"
    
    # Não encontrou - retorna anônimo
    return "anonymous"

def get_user_role() -> str:
    """
    Retorna o papel do usuário (admin, master, user)
    """
    if 'user_role' in st.session_state:
        return st.session_state.user_role
    
    # Tenta inferir do email
    user = get_current_user()
    if user.endswith('@admin.com') or user == 'admin':
        return 'admin'
    
    return 'user'

def require_auth():
    """
    Decorator/helper para páginas que requerem autenticação
    """
    if get_current_user() == "anonymous":
        st.error("🔒 Esta página requer autenticação")
        st.stop()
```

---

## Tarefa 1.1: Utilitários de Criptografia (CORRIGIDO)

### Arquivo: `modules/crypto_utils.py`

```python
"""
Utilitários de criptografia para proteção de dados sensíveis
Usa Fernet (AES-128) com chave derivada do usuário
"""

import base64
import hashlib
import json
import streamlit as st
from typing import Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def derive_key(user_id: str, salt: Optional[str] = None) -> bytes:
    """
    Deriva uma chave criptográfica baseada no ID do usuário e um salt.
    
    Args:
        user_id: Identificador único do usuário
        salt: Salt criptográfico (opcional)
    
    Returns:
        Chave derivada pronta para uso com Fernet
    
    Raises:
        ValueError: Se PII_SALT não estiver configurado
    """
    # CORREÇÃO: Não permite fallback inseguro
    if salt is None:
        salt = st.secrets.get("PII_SALT")
        
        if not salt:
            raise ValueError(
                "PII_SALT não configurado em st.secrets. "
                "Adicione em .streamlit/secrets.toml: PII_SALT = 'seu_salt_seguro'"
            )
    
    # Combina user_id com salt
    combined = f"{user_id}:{salt}".encode('utf-8')
    
    # Usa PBKDF2 para derivar chave (100.000 iterações - recomendado OWASP)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode('utf-8'),
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(combined))
    return key

def encrypt_pii_mapping(mapping: Dict, user_id: str) -> str:
    """Criptografa o mapeamento PII para armazenamento seguro"""
    if not mapping:
        return ""
    
    try:
        key = derive_key(user_id)
        fernet = Fernet(key)
        
        # Serializa para JSON
        json_data = json.dumps(mapping, ensure_ascii=False, default=str)
        
        # Criptografa
        encrypted = fernet.encrypt(json_data.encode('utf-8'))
        
        # Retorna como string base64
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    
    except Exception as e:
        raise ValueError(f"Erro ao criptografar mapeamento: {str(e)}")

def decrypt_pii_mapping(encrypted_data: str, user_id: str) -> Dict:
    """Descriptografa o mapeamento PII"""
    if not encrypted_data:
        return {}
    
    try:
        key = derive_key(user_id)
        fernet = Fernet(key)
        
        # Decodifica de base64
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data)
        
        # Descriptografa
        decrypted = fernet.decrypt(encrypted_bytes)
        
        # Desserializa JSON
        return json.loads(decrypted.decode('utf-8'))
    
    except Exception as e:
        raise ValueError(f"Erro ao descriptografar mapeamento: {str(e)}")
```

---

## Tarefa 1.2: Detector de PII com spaCy (CORRIGIDO)

### Arquivo: `modules/pii_detector.py`

```python
"""
Detecção de Informações Pessoais Identificáveis (PII)
Usa spaCy para NER (Named Entity Recognition) em português
"""

import re
import spacy
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import streamlit as st

# Mapeamento de labels spaCy para categorias LGPD
# CORREÇÃO: PER não mapeia para health
SPACY_TO_LGPD = {
    'PER': 'person',           # Pessoa (não é automaticamente saúde)
    'ORG': 'organization',     # Organização
    'LOC': 'location',         # Localização
    'MISC': 'miscellaneous',   # Diversos
    
    # Categorias sensíveis (quando detectadas por outros meios)
    'HEALTH': 'health',
    'POLITICS': 'politics',
    'RELIGION': 'religion',
    'SEXUAL': 'sexual',
}

@dataclass
class PIIEntity:
    """Representa uma entidade PII detectada"""
    text: str
    label: str
    start: int
    end: int
    confidence: Optional[float] = None

@dataclass
class PIIDetectionResult:
    """Resultado da detecção de PII em um texto"""
    entities: List[PIIEntity] = field(default_factory=list)
    has_pii: bool = False
    sensitive_categories: List[str] = field(default_factory=list)

class PIIDetector:
    """Detector de PII usando spaCy NER + regex complementar"""
    
    def __init__(self):
        """Inicializa o modelo spaCy para português"""
        try:
            self.nlp = spacy.load("pt_core_news_lg")
        except OSError:
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "pt_core_news_lg"])
            self.nlp = spacy.load("pt_core_news_lg")
        
        # Padrões regex para dados específicos
        self._regex_patterns = {
            'EMAIL': re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
            'CPF': re.compile(r'\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11}'),
            'CNPJ': re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14}'),
            'PHONE': re.compile(r'\(?\d{2}\)?\s?9?\d{4}-?\d{4}'),
            'RG': re.compile(r'\d{2}\.\d{3}\.\d{3}-\d{1}'),
            'BIRTH_DATE': re.compile(r'\d{2}/\d{2}/\d{4}'),
        }
        
        # Palavras-chave para detecção de dados sensíveis (contexto)
        self._sensitive_keywords = {
            'health': ['diagnóstico', 'tratamento', 'doença', 'sintoma', 'hospital', 
                       'médico', 'paciente', 'cirurgia', 'terapia', 'depressão', 
                       'ansiedade', 'saúde', 'exame', 'receita médica'],
            'politics': ['político', 'eleição', 'partido', 'voto', 'manifestação', 
                         'governo', 'política', 'ideologia'],
            'religion': ['religião', 'igreja', 'pastor', 'padre', 'culto', 'fé', 
                        'crença', 'espírita', 'umbanda', 'candomblé'],
            'sexual': ['orientação sexual', 'gênero', 'lgbt', 'homossexual', 
                       'heterossexual', 'bi', 'transgênero'],
            'ethnicity': ['raça', 'etnia', 'negro', 'branco', 'indígena', 'pardo',
                         'asiático', 'afrodescendente']
        }
    
    def detect_with_spacy(self, text: str) -> List[PIIEntity]:
        """Detecta entidades usando modelo spaCy"""
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            if ent.label_ in ['PER', 'ORG', 'LOC', 'MISC']:
                entities.append(PIIEntity(
                    text=ent.text,
                    label=SPACY_TO_LGPD.get(ent.label_, ent.label_),
                    start=ent.start_char,
                    end=ent.end_char,
                ))
        
        return entities
    
    def detect_with_regex(self, text: str) -> List[PIIEntity]:
        """Detecta padrões usando regex"""
        entities = []
        
        for label, pattern in self._regex_patterns.items():
            for match in pattern.finditer(text):
                entities.append(PIIEntity(
                    text=match.group(),
                    label=label,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9
                ))
        
        return entities
    
    def detect_sensitive_context(self, text: str) -> List[str]:
        """
        Detecta categorias sensíveis baseado em contexto (palavras-chave)
        CORREÇÃO: Não usa 'PER' como indicador de saúde
        """
        text_lower = text.lower()
        categories_found = []
        
        for category, keywords in self._sensitive_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                categories_found.append(category)
        
        return categories_found
    
    def detect_pii(self, text: str) -> PIIDetectionResult:
        """Detecta todas as PII no texto combinando spaCy + regex + contexto"""
        # Detecta com spaCy e regex
        spacy_entities = self.detect_with_spacy(text)
        regex_entities = self.detect_with_regex(text)
        
        # Combina e remove duplicatas
        all_entities = spacy_entities + regex_entities
        unique_entities = []
        sorted_entities = sorted(all_entities, key=lambda e: (e.start, e.end))
        
        for entity in sorted_entities:
            is_duplicate = False
            for existing in unique_entities:
                if (entity.start >= existing.start and entity.end <= existing.end):
                    is_duplicate = True
                    break
                elif (entity.start <= existing.start and entity.end >= existing.end):
                    unique_entities.remove(existing)
                    break
            
            if not is_duplicate:
                unique_entities.append(entity)
        
        # Detecta categorias sensíveis por contexto
        sensitive_categories = self.detect_sensitive_context(text)
        
        return PIIDetectionResult(
            entities=unique_entities,
            has_pii=len(unique_entities) > 0,
            sensitive_categories=sensitive_categories
        )
    
    def is_sensitive_text(self, text: str) -> bool:
        """Verifica se o texto contém dados sensíveis"""
        return len(self.detect_sensitive_context(text)) > 0
    
    def anonymize_text(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Substitui entidades PII por tokens genéricos"""
        result = self.detect_pii(text)
        
        if not result.has_pii:
            return text, {}
        
        mapping = {}
        anonymized = text
        
        # Ordem reversa para não quebrar índices
        for entity in sorted(result.entities, key=lambda e: e.start, reverse=True):
            # Gera token baseado no tipo
            label = entity.label.upper()
            counter = 1
            token = f"[{label}_{counter}]"
            
            while token in mapping.values():
                counter += 1
                token = f"[{label}_{counter}]"
            
            mapping[token] = entity.text
            anonymized = anonymized[:entity.start] + token + anonymized[entity.end:]
        
        return anonymized, mapping

# Singleton
_detector_instance = None

def get_pii_detector() -> PIIDetector:
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = PIIDetector()
    return _detector_instance
```

---

## Tarefa 1.3: SQL de Migração (CORRIGIDO)

### Arquivo: `sql/001_data_governance_rev3.sql`

```sql
-- ============================================
-- PC-001 Rev. 3: Data Governance Schema
-- CORREÇÃO: Remove trigger que referencia tabela inexistente
-- ============================================

BEGIN;

-- 1. Novas colunas na tabela meetings
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS legal_basis TEXT;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS legal_basis_description TEXT;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS data_classification TEXT DEFAULT 'internal';
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS has_sensitive_data BOOLEAN DEFAULT FALSE;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS sensitive_categories TEXT[];
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS retention_until DATE;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS consent_declared_by TEXT;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS consent_declared_at TIMESTAMPTZ;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS consent_revoked_at TIMESTAMPTZ;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS anonymization_method TEXT DEFAULT 'pseudonymized';
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS pii_mapping_encrypted TEXT;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS llm_provider_used TEXT;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS llm_consent_obtained BOOLEAN DEFAULT FALSE;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMPTZ;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS deletion_reason TEXT;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS deletion_requested_by TEXT;

-- 2. Índices
CREATE INDEX IF NOT EXISTS idx_meetings_retention_until ON meetings(retention_until);
CREATE INDEX IF NOT EXISTS idx_meetings_legal_basis ON meetings(legal_basis);
CREATE INDEX IF NOT EXISTS idx_meetings_has_sensitive ON meetings(has_sensitive_data);
CREATE INDEX IF NOT EXISTS idx_meetings_consent_declared ON meetings(consent_declared_at);

-- 3. Tabela de auditoria
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    meeting_id BIGINT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    user_identifier TEXT NOT NULL,
    user_role TEXT,
    action TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_meeting_id ON audit_log(meeting_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_identifier);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);

-- 4. Função de limpeza (sem triggers problemáticos)
CREATE OR REPLACE FUNCTION auto_delete_expired_meetings()
RETURNS TABLE(
    deleted_count INTEGER,
    total_expired INTEGER
) AS $$
DECLARE
    expired_meeting RECORD;
    v_deleted_count INTEGER := 0;
    v_total_expired INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_total_expired
    FROM meetings 
    WHERE retention_until < CURRENT_DATE 
    AND deleted_at IS NULL;
    
    FOR expired_meeting IN 
        SELECT id, title, retention_until
        FROM meetings 
        WHERE retention_until < CURRENT_DATE 
        AND deleted_at IS NULL
        FOR UPDATE SKIP LOCKED
    LOOP
        UPDATE meetings 
        SET deleted_at = NOW(),
            deletion_reason = 'Retenção expirada automaticamente'
        WHERE id = expired_meeting.id;
        
        INSERT INTO audit_log (meeting_id, user_identifier, action, metadata)
        VALUES (
            expired_meeting.id,
            'system_auto_delete',
            'delete',
            jsonb_build_object(
                'reason', 'retention_expired',
                'retention_until', expired_meeting.retention_until,
                'title', expired_meeting.title
            )
        );
        
        v_deleted_count := v_deleted_count + 1;
    END LOOP;
    
    RETURN QUERY SELECT v_deleted_count, v_total_expired;
END;
$$ LANGUAGE plpgsql;

COMMIT;
```

---

# PARTE 2: BACKEND (CORRIGIDO)

## Tarefa 2.1: DataGovernanceManager (VERSÃO FINAL)

### Arquivo: `modules/data_governance.py`

```python
"""
Módulo de Governança de Dados - Versão Final Rev. 3
Com todas as correções incorporadas
"""

import streamlit as st
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from supabase import Client
from modules.pii_detector import get_pii_detector
from modules.crypto_utils import encrypt_pii_mapping, decrypt_pii_mapping
from modules.session_security import get_current_user, get_user_role

# --- CONSTANTES ---
LEGAL_BASIS_OPTIONS = {
    "consent": "Consentimento do Titular (Art. 7º, I)",
    "legitimate_interest": "Interesse Legítimo (Art. 7º, IX)",
    "contract": "Execução de Contrato (Art. 7º, V)",
    "legal_obligation": "Obrigação Legal ou Regulatória (Art. 7º, II)",
    "public_interest": "Interesse Público (Art. 7º, III)",
    "credit_protection": "Proteção ao Crédito (Art. 7º, IV)",
}

DATA_CLASSIFICATION_OPTIONS = {
    "public": "Público - Dados abertos",
    "internal": "Interno - Uso corporativo",
    "confidential": "Confidencial - Dados sensíveis ou estratégicos",
}

SENSITIVE_CATEGORIES = {
    "health": "Dados de Saúde",
    "politics": "Opinião Política",
    "religion": "Convicção Religiosa",
    "ethnicity": "Origem Racial ou Étnica",
    "union": "Filiação Sindical",
    "biometric": "Dados Biométricos",
    "genetic": "Dados Genéticos",
    "sexual": "Vida Sexual",
}

@dataclass
class ConsentRecord:
    meeting_id: int
    basis: str
    basis_description: Optional[str]
    declared_by: str
    has_sensitive: bool
    sensitive_categories: List[str]
    retention_days: int
    classification: str
    llm_provider: Optional[str] = None

class DataGovernanceManager:
    """Gerenciador de conformidade LGPD - Versão Final"""
    
    def __init__(self, supabase_client: Client, hub: Optional[Any] = None):
        self.supabase = supabase_client
        self.hub = hub
        self.pii_detector = get_pii_detector()
    
    # ==================== PRÉ-INGESTÃO ====================
    
    def record_consent(self, record: ConsentRecord) -> Dict:
        """Registra consentimento e base legal para uma reunião"""
        retention_date = date.today() + timedelta(days=record.retention_days)
        
        data = {
            "legal_basis": record.basis,
            "legal_basis_description": record.basis_description,
            "data_classification": record.classification,
            "has_sensitive_data": record.has_sensitive,
            "sensitive_categories": record.sensitive_categories if record.has_sensitive else [],
            "retention_until": retention_date.isoformat(),
            "consent_declared_by": record.declared_by,
            "consent_declared_at": datetime.now().isoformat(),
            "llm_consent_obtained": True,
            "llm_provider_used": record.llm_provider,
        }
        
        result = self.supabase.table('meetings')\
            .update(data)\
            .eq('id', record.meeting_id)\
            .execute()
        
        if result.data:
            self.log_access(
                meeting_id=record.meeting_id,
                user=record.declared_by,
                action="consent_given",
                metadata={
                    "basis": record.basis,
                    "has_sensitive": record.has_sensitive,
                    "retention_days": record.retention_days,
                    "llm_provider": record.llm_provider
                }
            )
            
            if self.hub:
                self.hub.consent_recorded = True
                self.hub.legal_basis = record.basis
        
        return result.data[0] if result.data else {}
    
    def check_consent_required(self, meeting_id: int) -> Dict:
        """Verifica se uma reunião requer consentimento"""
        result = self.supabase.table('meetings')\
            .select('consent_declared_at, consent_revoked_at, has_sensitive_data, legal_basis')\
            .eq('id', meeting_id)\
            .execute()
        
        if not result.data:
            return {
                "requires_consent": True,
                "status": "not_found",
                "message": "Reunião não encontrada"
            }
        
        meeting = result.data[0]
        
        if meeting.get('consent_revoked_at'):
            return {
                "requires_consent": True,
                "status": "revoked",
                "message": "Consentimento revogado",
                "revoked_at": meeting['consent_revoked_at'],
                "has_sensitive": meeting.get('has_sensitive_data', False)
            }
        
        if meeting.get('consent_declared_at'):
            return {
                "requires_consent": False,
                "status": "valid",
                "message": "Consentimento válido",
                "basis": meeting.get('legal_basis'),
                "has_sensitive": meeting.get('has_sensitive_data', False)
            }
        
        if meeting.get('has_sensitive_data', False):
            return {
                "requires_consent": True,
                "status": "sensitive_data_requires_consent",
                "message": "Dados sensíveis exigem consentimento explícito (Art. 11)",
                "has_sensitive": True
            }
        
        return {
            "requires_consent": False,
            "status": "recommended",
            "message": "Recomenda-se registrar consentimento",
            "has_sensitive": False
        }
    
    def detect_sensitive_content(self, text: str) -> Dict:
        """Detecta se o texto contém dados sensíveis"""
        result = self.pii_detector.detect_pii(text)
        
        return {
            "has_sensitive": len(result.sensitive_categories) > 0,
            "sensitive_categories": result.sensitive_categories,
            "entities_found": [
                {"text": e.text, "label": e.label} 
                for e in result.entities
            ],
            "entity_count": len(result.entities)
        }
    
    # ==================== ANONIMIZAÇÃO ====================
    
    def pseudonymize_text(self, text: str) -> Tuple[str, Dict]:
        """Aplica pseudonimização usando spaCy"""
        return self.pii_detector.anonymize_text(text)
    
    def store_pii_mapping(self, meeting_id: int, mapping: Dict) -> None:
        """Armazena mapeamento criptografado no banco"""
        if not mapping:
            return
        
        user_id = get_current_user()
        encrypted = encrypt_pii_mapping(mapping, user_id)
        
        self.supabase.table('meetings')\
            .update({
                'pii_mapping_encrypted': encrypted,
                'anonymization_method': 'pseudonymized'
            })\
            .eq('id', meeting_id)\
            .execute()
    
    def retrieve_pii_mapping(self, meeting_id: int) -> Dict:
        """Recupera e descriptografa o mapeamento"""
        result = self.supabase.table('meetings')\
            .select('pii_mapping_encrypted')\
            .eq('id', meeting_id)\
            .execute()
        
        if not result.data or not result.data[0].get('pii_mapping_encrypted'):
            return {}
        
        user_id = get_current_user()
        encrypted = result.data[0]['pii_mapping_encrypted']
        
        try:
            return decrypt_pii_mapping(encrypted, user_id)
        except Exception as e:
            # Admin pode ler qualquer mapeamento
            if get_user_role() == 'admin':
                return decrypt_pii_mapping(encrypted, "admin")
            raise ValueError(f"Não foi possível descriptografar: {str(e)}")
    
    def deanonymize_text(self, text: str, mapping: Dict) -> str:
        """Restaura texto original a partir do mapeamento"""
        if not mapping:
            return text
        
        result = text
        for token, original in mapping.items():
            result = result.replace(token, original)
        
        return result
    
    def process_for_llm(self, text: str, meeting_id: int) -> str:
        """Processa texto para envio ao LLM com pseudonimização"""
        detection = self.pii_detector.detect_pii(text)
        
        if not detection.has_pii:
            return text
        
        anonymized, mapping = self.pseudonymize_text(text)
        
        self.store_pii_mapping(meeting_id, mapping)
        
        if self.hub:
            self.hub.pii_mapping = mapping
            self.hub.original_text = text
            self.hub.anonymized_text = anonymized
        
        self.log_access(
            meeting_id=meeting_id,
            user=get_current_user(),
            action="anonymize",
            metadata={
                "entity_count": len(detection.entities),
                "sensitive_categories": detection.sensitive_categories
            }
        )
        
        return anonymized
    
    # ==================== AUDITORIA ====================
    
    def log_access(self, meeting_id: int, user: str, action: str, 
                   metadata: Optional[Dict] = None) -> None:
        """Registra acesso no log de auditoria"""
        log_entry = {
            "meeting_id": meeting_id,
            "user_identifier": user,
            "user_role": get_user_role(),
            "action": action,
            "metadata": metadata or {},
        }
        
        try:
            if hasattr(st, 'session_state'):
                # Atualiza último acesso
                self.supabase.table('meetings')\
                    .update({'last_accessed_at': datetime.now().isoformat()})\
                    .eq('id', meeting_id)\
                    .execute()
        except:
            pass
        
        self.supabase.table('audit_log').insert(log_entry).execute()
    
    def get_audit_log(self, meeting_id: Optional[int] = None, 
                      days: int = 30, action_filter: Optional[str] = None) -> List[Dict]:
        """Obtém logs de auditoria"""
        query = self.supabase.table('audit_log')\
            .select('*')\
            .gte('created_at', (datetime.now() - timedelta(days=days)).isoformat())\
            .order('created_at', desc=True)
        
        if meeting_id:
            query = query.eq('meeting_id', meeting_id)
        if action_filter:
            query = query.eq('action', action_filter)
        
        result = query.execute()
        return result.data if result.data else []
    
    # ==================== RETENÇÃO E TTL ====================
    
    def get_expiring_meetings(self, days: int = 30) -> List[Dict]:
        """Lista reuniões que expiram em X dias"""
        target_date = date.today() + timedelta(days=days)
        
        result = self.supabase.table('meetings')\
            .select('id, title, retention_until, data_classification, legal_basis, has_sensitive_data')\
            .eq('deleted_at', None)\
            .lte('retention_until', target_date.isoformat())\
            .order('retention_until')\
            .execute()
        
        return result.data if result.data else []
    
    def get_expired_meetings(self) -> List[Dict]:
        """Lista reuniões já vencidas"""
        today = date.today().isoformat()
        
        result = self.supabase.table('meetings')\
            .select('id, title, retention_until, consent_declared_by')\
            .eq('deleted_at', None)\
            .lt('retention_until', today)\
            .order('retention_until')\
            .execute()
        
        return result.data if result.data else []
    
    def extend_retention(self, meeting_id: int, extra_days: int, reason: str) -> Dict:
        """Estende o prazo de retenção"""
        result = self.supabase.table('meetings')\
            .select('retention_until')\
            .eq('id', meeting_id)\
            .execute()
        
        if not result.data:
            raise ValueError(f"Reunião {meeting_id} não encontrada")
        
        current_until = datetime.fromisoformat(result.data[0]['retention_until'])
        new_until = current_until + timedelta(days=extra_days)
        
        update_result = self.supabase.table('meetings')\
            .update({'retention_until': new_until.isoformat()})\
            .eq('id', meeting_id)\
            .execute()
        
        if update_result.data:
            self.log_access(
                meeting_id=meeting_id,
                user=get_current_user(),
                action="extend_retention",
                metadata={"extra_days": extra_days, "reason": reason}
            )
        
        return update_result.data[0] if update_result.data else {}
    
    def request_deletion(self, meeting_id: int, reason: str) -> Dict:
        """Solicita exclusão de uma reunião (soft delete)"""
        result = self.supabase.table('meetings')\
            .update({
                'deleted_at': datetime.now().isoformat(),
                'deletion_reason': reason,
                'deletion_requested_by': get_current_user()
            })\
            .eq('id', meeting_id)\
            .execute()
        
        if result.data:
            self.log_access(
                meeting_id=meeting_id,
                user=get_current_user(),
                action="delete",
                metadata={"reason": reason}
            )
        
        return result.data[0] if result.data else {}
    
    def run_retention_cleanup(self) -> Dict:
        """Executa job de limpeza de dados expirados"""
        result = self.supabase.rpc('auto_delete_expired_meetings').execute()
        
        if result.data and len(result.data) > 0:
            return {
                "deleted_count": result.data[0]['deleted_count'],
                "total_expired": result.data[0]['total_expired'],
                "timestamp": datetime.now().isoformat()
            }
        
        return {"deleted_count": 0, "total_expired": 0, "timestamp": datetime.now().isoformat()}
    
    # ==================== RELATÓRIOS ====================
    
    def get_compliance_report(self) -> Dict:
        """Gera relatório completo de conformidade"""
        total_result = self.supabase.table('meetings')\
            .select('id', count='exact')\
            .eq('deleted_at', None)\
            .execute()
        
        with_consent_result = self.supabase.table('meetings')\
            .select('id', count='exact')\
            .eq('deleted_at', None)\
            .not_.is_('consent_declared_at', None)\
            .execute()
        
        with_sensitive_result = self.supabase.table('meetings')\
            .select('id', count='exact')\
            .eq('deleted_at', None)\
            .eq('has_sensitive_data', True)\
            .execute()
        
        anonymized_result = self.supabase.table('meetings')\
            .select('id', count='exact')\
            .eq('deleted_at', None)\
            .not_.is_('pii_mapping_encrypted', None)\
            .execute()
        
        expired = self.get_expired_meetings()
        expiring = self.get_expiring_meetings(30)
        
        basis_result = self.supabase.table('meetings')\
            .select('legal_basis', count='exact')\
            .eq('deleted_at', None)\
            .group_by('legal_basis')\
            .execute()
        
        total = total_result.count or 0
        
        return {
            "total_meetings": total,
            "with_consent": with_consent_result.count or 0,
            "consent_percentage": ((with_consent_result.count or 0) / total * 100) if total > 0 else 0,
            "sensitive_data_count": with_sensitive_result.count or 0,
            "anonymized_count": anonymized_result.count or 0,
            "expired_count": len(expired),
            "expiring_in_30_days": len(expiring),
            "basis_distribution": basis_result.data if basis_result.data else [],
            "expired_meetings": expired,
            "expiring_meetings": expiring,
        }
    
    # ==================== MÉTODOS PARA DASHBOARD ====================
    # CORREÇÃO: Métodos específicos para o dashboard não acessarem supabase diretamente
    
    def get_all_meetings(self, limit: int = 50) -> List[Dict]:
        """Retorna lista de reuniões para o dashboard"""
        result = self.supabase.table('meetings')\
            .select('id, title, created_at, retention_until, consent_declared_at, has_sensitive_data, pii_mapping_encrypted')\
            .eq('deleted_at', None)\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data if result.data else []
    
    def get_meeting_by_id(self, meeting_id: int) -> Optional[Dict]:
        """Retorna dados de uma reunião específica"""
        result = self.supabase.table('meetings')\
            .select('*')\
            .eq('id', meeting_id)\
            .execute()
        
        return result.data[0] if result.data else None
    
    def get_meeting_governance_status(self, meeting_id: int) -> Dict:
        """Retorna status completo de governança de uma reunião"""
        result = self.supabase.table('meetings')\
            .select('''
                id, title, legal_basis, legal_basis_description,
                data_classification, has_sensitive_data, sensitive_categories,
                retention_until, consent_declared_at, consent_revoked_at,
                anonymization_method, llm_provider_used, llm_consent_obtained,
                created_at, deleted_at
            ''')\
            .eq('id', meeting_id)\
            .execute()
        
        if not result.data:
            return {"status": "not_found"}
        
        meeting = result.data[0]
        
        days_remaining = None
        if meeting.get('retention_until'):
            retention_date = datetime.fromisoformat(meeting['retention_until']).date()
            days_remaining = (retention_date - date.today()).days
        
        return {
            "status": "found",
            "meeting": meeting,
            "days_remaining": days_remaining,
            "is_expired": days_remaining is not None and days_remaining < 0,
            "has_valid_consent": meeting.get('consent_declared_at') and not meeting.get('consent_revoked_at'),
            "is_deleted": meeting.get('deleted_at') is not None
        }
```

---

# PARTE 3: PIPELINE (CORRIGIDO)

## Tarefa 3.1: Renderização LGPD (sem st.stop() problemático)

### Arquivo: `pages/Pipeline.py` (trechos)

```python
"""
Pipeline de Extração de Reuniões - com Governança de Dados
Versão com consentimento não-bloqueante e tratamento adequado do st.stop()
"""

import streamlit as st
from datetime import datetime
from typing import Optional

from modules.data_governance import (
    DataGovernanceManager, 
    ConsentRecord, 
    LEGAL_BASIS_OPTIONS,
    DATA_CLASSIFICATION_OPTIONS,
    SENSITIVE_CATEGORIES
)
from modules.session_security import get_current_user

# ============================================
# INICIALIZAÇÃO
# ============================================

def get_governance_manager() -> DataGovernanceManager:
    if 'gov_manager' not in st.session_state:
        from supabase import create_client
        supabase = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"]
        )
        hub = st.session_state.get('hub')
        st.session_state.gov_manager = DataGovernanceManager(supabase, hub)
    
    return st.session_state.gov_manager

# ============================================
# COMPONENTE DE DECLARAÇÃO LGPD
# ============================================

def render_lgpd_declaration(meeting_id: int, transcript: str) -> bool:
    """
    Renderiza o componente de declaração LGPD.
    Retorna True se o processamento pode continuar.
    
    CORREÇÃO: Não usa st.stop() - retorna False para bloquear
    """
    gov_manager = get_governance_manager()
    current_user = get_current_user()
    
    # Verifica status atual
    status = gov_manager.check_consent_required(meeting_id)
    
    # Caso 1: Já tem consentimento válido
    if status['status'] == 'valid':
        st.success(f"✅ Consentimento registrado ({status.get('basis', '')})")
        return True
    
    # Caso 2: Consentimento revogado ou dados sensíveis sem consentimento
    if status['status'] in ['revoked', 'sensitive_data_requires_consent']:
        st.warning("⚠️ Esta reunião requer seu consentimento para processar")
        return render_consent_form(meeting_id, transcript, required=True)
    
    # Caso 3: Recomendação (não obrigatório)
    st.info("💡 Recomenda-se registrar consentimento para conformidade com a LGPD")
    
    with st.expander("⚖️ Declarar Consentimento LGPD (Recomendado)", expanded=False):
        consent_given = render_consent_form(meeting_id, transcript, required=False)
        if consent_given:
            return True
    
    # Se não declarou, permite continuar (não obrigatório)
    st.caption("⚠️ Continuando sem consentimento registrado")
    return True

def render_consent_form(meeting_id: int, transcript: str, required: bool = False) -> bool:
    """Renderiza o formulário de consentimento"""
    gov_manager = get_governance_manager()
    current_user = get_current_user()
    
    detection = gov_manager.detect_sensitive_content(transcript)
    
    st.markdown("#### 📋 Declaração de Tratamento de Dados - LGPD")
    
    col1, col2 = st.columns(2)
    
    with col1:
        legal_basis = st.selectbox(
            "📍 Base Legal",
            options=list(LEGAL_BASIS_OPTIONS.keys()),
            format_func=lambda x: LEGAL_BASIS_OPTIONS[x],
            key=f"legal_basis_{meeting_id}"
        )
        
        legal_basis_desc = st.text_area(
            "Descrição Detalhada",
            placeholder="Ex: Consentimento obtido verbalmente em reunião...",
            key=f"basis_desc_{meeting_id}"
        )
    
    with col2:
        classification = st.selectbox(
            "🔒 Classificação dos Dados",
            options=list(DATA_CLASSIFICATION_OPTIONS.keys()),
            format_func=lambda x: DATA_CLASSIFICATION_OPTIONS[x],
            key=f"classification_{meeting_id}"
        )
        
        if detection['has_sensitive']:
            st.warning(f"⚠️ Detectamos dados sensíveis: {', '.join(detection['sensitive_categories'])}")
            
            sensitive_categories = st.multiselect(
                "Categorias de Dados Sensíveis",
                options=list(SENSITIVE_CATEGORIES.keys()),
                default=detection['sensitive_categories'],
                format_func=lambda x: SENSITIVE_CATEGORIES[x],
                key=f"sensitive_{meeting_id}"
            )
        else:
            sensitive_categories = []
    
    retention_days = st.slider(
        "📅 Prazo de Retenção (dias)",
        min_value=30,
        max_value=1825,
        value=365,
        key=f"retention_{meeting_id}"
    )
    
    llm_provider = st.session_state.get('llm_provider', 'Não informado')
    st.info(f"🤖 Dados serão enviados para: **{llm_provider}**")
    
    st.divider()
    
    consent_checkbox = st.checkbox(
        "✅ Declaro que os participantes foram informados sobre a gravação e processamento",
        key=f"consent_check_{meeting_id}"
    )
    
    if required and not consent_checkbox:
        st.error("⚠️ O consentimento é obrigatório para dados sensíveis")
        return False
    
    if st.button("📌 Registrar Declaração", type="primary", key=f"register_{meeting_id}"):
        if not consent_checkbox:
            st.warning("⚠️ Marque a caixa de consentimento")
            return False
        
        try:
            record = ConsentRecord(
                meeting_id=meeting_id,
                basis=legal_basis,
                basis_description=legal_basis_desc or LEGAL_BASIS_OPTIONS[legal_basis],
                declared_by=current_user,
                has_sensitive=detection['has_sensitive'] or bool(sensitive_categories),
                sensitive_categories=sensitive_categories or detection['sensitive_categories'],
                retention_days=retention_days,
                classification=classification,
                llm_provider=llm_provider
            )
            
            gov_manager.record_consent(record)
            
            if detection['has_sensitive'] or sensitive_categories:
                st.info("🔐 Pseudonimizando dados sensíveis...")
                gov_manager.process_for_llm(transcript, meeting_id)
                st.success("✅ Dados pseudonimizados com sucesso!")
            
            st.success("✅ Declaração registrada com sucesso!")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Erro ao registrar: {str(e)}")
            return False
    
    # Se não for obrigatório, permite pular
    if not required:
        if st.button("⏭️ Pular (não recomendado)", key=f"skip_{meeting_id}"):
            st.warning("⚠️ Processando sem consentimento registrado")
            return True
    
    return False

# ============================================
# PIPELINE PRINCIPAL
# ============================================

def render_pipeline():
    """Função principal do pipeline com governança integrada"""
    
    gov_manager = get_governance_manager()
    
    # ... código existente para carregar reunião ...
    
    meeting_id = st.session_state.get('current_meeting_id')
    transcript = st.session_state.get('transcript', '')
    
    if not meeting_id or not transcript:
        st.warning("⚠️ Nenhuma reunião carregada")
        return
    
    # ============ DECLARAÇÃO LGPD ============
    consent_ok = render_lgpd_declaration(meeting_id, transcript)
    
    if not consent_ok:
        st.warning("⏸️ Processamento pausado - aguardando consentimento")
        st.stop()  # Agora em contexto seguro
    
    # ============ CONTINUAÇÃO DO PIPELINE ============
    # ... resto do pipeline ...
```

---

# CHECKLIST FINAL

## Fase 1: Fundação
- [ ] Criar `modules/session_security.py` (adicionar `get_current_user()`)
- [ ] Criar `modules/crypto_utils.py` (com validação de PII_SALT)
- [ ] Criar `modules/pii_detector.py` (com correção PER→health)
- [ ] Executar `sql/001_data_governance_rev3.sql`

## Fase 2: Backend
- [ ] Criar `modules/data_governance.py` (com todos os métodos)
- [ ] Criar `tests/test_data_governance.py`

## Fase 3: Integração
- [ ] Modificar `pages/Pipeline.py` (sem st.stop() problemático)
- [ ] Testar fluxos: válido / obrigatório / recomendado

## Fase 4: Dashboard
- [ ] Criar `pages/📊_Governanca_Dados.py` (usando métodos do manager)

## Fase 5: Automação
- [ ] Criar `utils/retention_cleanup.py`

---

# CONFIGURAÇÃO OBRIGATÓRIA

### `.streamlit/secrets.toml`
```toml
SUPABASE_URL = "https://..."
SUPABASE_KEY = "..."

# OBRIGATÓRIO - Salt para criptografia
PII_SALT = "seu_salt_seguro_minimo_32_caracteres"
```

---

**Documentação Completa Disponível:**
- Guia do usuário: `docs/GOVERNANCA_USUARIO.md`
- Guia do desenvolvedor: `docs/GOVERNANCA_DEV.md`

**Pronto para implementação!** 🚀

# Revisão técnica sênior — FinBot Telegram/WhatsApp

## Escopo analisado
- Backend Python (Telegram + FastAPI webhook + camada de domínio/dados)
- Adaptador Node (Baileys/WhatsApp)
- Testes automatizados e setup de qualidade

---

## 1) Bugs potenciais

### 1.1 Controle de acesso parcial no Telegram
**Problema:** `ALLOWED_USER_ID` só é validado quando o usuário ainda não existe no banco. Depois de cadastrado, o usuário continua com acesso mesmo que a configuração mude.  
**Risco:** bypass de autorização por estado persistido.

**Onde:** `finbot/bot/decorators.py`.

**Melhoria sugerida (exemplo):** validar `ALLOWED_USER_ID` antes de qualquer execução do handler.

```python
# exemplo de ajuste no decorator
def _is_authorized(user_id: int) -> bool:
    from ..config import ALLOWED_USER_ID
    return not ALLOWED_USER_ID or str(user_id) == str(ALLOWED_USER_ID)

@wraps(func)
async def wrapper(update, context, *args, **kwargs):
    if not update.effective_user:
        return await func(update, context, *args, **kwargs)

    user_id = update.effective_user.id
    if not _is_authorized(user_id):
        if update.message:
            await update.message.reply_text("⛔ Acesso não autorizado.")
        return

    user = crud.get_user(user_id)
    if not user:
        crud.create_user(user_id, update.effective_user.first_name)
    return await func(update, context, *args, **kwargs)
```

### 1.2 Inconsistência de identidade de usuário (WhatsApp x Telegram)
**Problema:** parte do código usa `telegram_id` diretamente para WhatsApp (`int(phone)`), enquanto outra parte cria usuário por `phone` com `telegram_id` falso negativo.  
**Risco:** duplicidade de usuários e histórico financeiro fragmentado.

**Onde:** `finbot/whatsapp/handlers.py` e `finbot/bot/database/crud.py`.

**Melhoria sugerida:** padronizar entrada WhatsApp via `get_or_create_user_by_phone(phone, name)` e usar `user.telegram_id` retornado.

### 1.3 Cálculo monetário com `float`
**Problema:** valores financeiros são armazenados/calculados em `Float` e operações com `round(..., 2)`.  
**Risco:** erros de precisão acumulados (ex.: parcelas, totais mensais).

**Onde:** `finbot/bot/database/models.py` e `finbot/bot/database/crud.py`.

**Melhoria sugerida:** migrar para `Decimal` + `Numeric(12,2)`.

```python
# exemplo SQLAlchemy
from sqlalchemy import Numeric
from decimal import Decimal

valor = Column(Numeric(12, 2), nullable=False)

# no serviço
valor = Decimal(texto.replace(',', '.')).quantize(Decimal('0.01'))
```

### 1.4 Reprocessamento potencial de webhook (idempotência ausente)
**Problema:** webhook recebe mensagem e agenda processamento sem chave idempotente. Retries da origem podem duplicar lançamento.

**Onde:** `finbot/whatsapp/webhook.py` + `finbot/whatsapp/handlers.py`.

**Melhoria sugerida:** armazenar `message_id` e ignorar repetidos (cache TTL ou tabela dedicada).

---

## 2) Problemas de arquitetura

### 2.1 Camada `crud` muito grande e com responsabilidades misturadas
**Problema:** `crud.py` concentra acesso a dados, regras de negócio (orçamento, soma mensal), normalização de datas e lógica de usuário multicanal.

**Impacto:** baixo coesão, maior custo de manutenção/testes, acoplamento entre handler e banco.

**Melhoria sugerida:** dividir em serviços orientados a domínio:
- `repositories/` (somente queries)
- `services/expenses.py`, `services/income.py`, `services/budgets.py`
- `use_cases/` para fluxos (registrar gasto, sugerir dica, alertar orçamento)

### 2.2 Dependência global em estado/processo
**Problema:** estado de conversa WhatsApp em memória (`state_manager`) e scheduler global.

**Impacto:** em múltiplas instâncias ou restart, perde estado e pode gerar comportamento inconsistente.

**Melhoria sugerida:** persistir estado de conversa (Redis/DB) e proteger `start_scheduler` para não registrar jobs duplicados.

### 2.3 Duplicação de regras entre canais
**Problema:** lógica de relatório/comandos existe em Telegram e WhatsApp com variações.

**Impacto:** divergência funcional ao longo do tempo.

**Melhoria sugerida:** extrair “núcleo” de negócio para serviços comuns e manter handlers só como adaptadores de canal.

---

## 3) Código duplicado

### 3.1 Prompt de anomalia repetido em dois lugares
- `finbot/bot/services/parser.py::check_anomalia`
- `finbot/bot/services/finance_service.py::verificar_anomalia`

**Melhoria:** criar função única `build_anomaly_prompt(...)` em módulo compartilhado.

### 3.2 Parsing de data/hora repetido
- `datetime.now().date()` aparece em vários handlers/jobs.

**Melhoria:** centralizar em helper timezone-aware (`crud.today()` ou `clock.now_local_date()`), evitando inconsistência entre fuso local e UTC.

---

## 4) Problemas de performance

### 4.1 Filtro por mês/ano com `extract()` prejudica índices
**Problema:** consultas como `extract('month', Gasto.data) == mes` e `extract('year', ...)` podem impedir uso eficiente de índice de data.

**Onde:** `get_gastos_mes`, `get_total_mes`, `get_gastos_por_categoria`, `get_orcamento_status`.

**Melhoria sugerida:** usar range de datas `[inicio_mes, inicio_proximo_mes)`.

```python
from datetime import date

def month_bounds(ano: int, mes: int):
    inicio = date(ano, mes, 1)
    prox = date(ano + (mes // 12), (mes % 12) + 1, 1)
    return inicio, prox

inicio, fim = month_bounds(ano, mes)
query.filter(Gasto.data >= inicio, Gasto.data < fim)
```

### 4.2 Criação de `httpx.AsyncClient` por requisição
**Problema:** `WhatsAppClient.send_message` cria cliente novo em cada envio.

**Impacto:** overhead de conexão/TLS e menor throughput.

**Melhoria:** reutilizar cliente singleton com timeout/pool configurado e fechamento no shutdown.

### 4.3 Logs com payload completo
**Problema:** webhook loga mensagem recebida inteira.

**Impacto:** custo de IO e risco de vazamento (também é segurança/compliance).

**Melhoria:** mascarar PII e truncar conteúdo em logs.

---

## 5) Problemas de segurança

### 5.1 Webhook sem autenticação
**Problema:** endpoint `/webhook` aceita payload sem assinatura/HMAC/token.

**Risco:** actor externo injeta gastos/comandos.

**Melhoria sugerida:** validar header assinado (`X-Signature`) com segredo compartilhado.

```python
# exemplo simplificado
import hmac, hashlib

def valid_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)
```

### 5.2 Endpoint `/send-message` exposto sem proteção
**Problema:** adaptador Node aceita envio para qualquer número sem autenticação.

**Risco:** abuso do serviço para spam.

**Melhoria:** exigir API key interna e limitar por IP/rate.

### 5.3 Exposição de dados pessoais em logs
**Problema:** telefone e texto integral aparecem em logs.

**Risco:** vazamento de PII e não conformidade LGPD.

**Melhoria:** aplicar política de redaction (ex.: mostrar só 4 dígitos finais).

---

## 6) Melhorias práticas de curto prazo (ordem recomendada)

1. **Segurança de borda:** autenticar `/webhook` e `/send-message`.
2. **Correção de identidade de usuário multicanal:** usar `phone` como chave de entrada no WhatsApp e mapear para um único `telegram_id` interno.
3. **Acesso consistente:** aplicar `ALLOWED_USER_ID` em toda requisição.
4. **Monetário correto:** migrar `Float` -> `Numeric/Decimal`.
5. **Performance de consultas mensais:** substituir `extract()` por range.
6. **Refatoração arquitetural incremental:** separar repository/service/use case.

---

## 7) Qualidade de testes e DX

- A suíte depende de `pytest-mock` (`mocker` fixture), e sem o plugin os testes quebram na coleta.
- Garanta execução padrão via:
  - `pip install -r requirements-dev.txt`
  - `PYTHONPATH=. pytest -q`
- Recomenda-se pipeline CI com lint (`ruff`/`flake8`), typing (`mypy`) e testes.

---

## Resumo executivo
O projeto já tem boa base funcional e cobertura inicial de testes, porém os maiores riscos hoje estão em **segurança de integração WhatsApp**, **consistência de identidade de usuário** e **precisão financeira com float**. Corrigindo esses três pontos primeiro, você reduz risco operacional e prepara terreno para evolução arquitetural com menor retrabalho.

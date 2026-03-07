import asyncio
import json
import logging
import re

import httpx

from finbot.core.config import AI_PROVIDER, GEMINI_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)

_MODEL_NAME = "gemini-2.5-flash"

try:
    from google import genai
    from google.genai.types import HttpOptions
except Exception:
    genai = None
    HttpOptions = None


try:
    _gemini_client = (
        genai.Client(api_key=GEMINI_API_KEY, http_options=HttpOptions(api_version="v1"))
        if genai and HttpOptions and GEMINI_API_KEY
        else None
    )
except Exception as exc:
    logger.error("Failed to configure Gemini: %s", exc)
    _gemini_client = None


def _provider_order() -> list[str]:
    provider = (AI_PROVIDER or "gemini").lower()
    if provider == "auto":
        return ["ollama", "gemini"]
    if provider in {"ollama", "gemini"}:
        return [provider]
    return ["gemini"]


async def _generate_content_gemini(prompt: str, retries: int) -> str:
    if _gemini_client is None:
        return ""

    for attempt in range(retries):
        try:
            response = await _gemini_client.aio.models.generate_content(
                model=_MODEL_NAME,
                contents=prompt,
            )
            return (getattr(response, "text", "") or "").strip()
        except Exception as exc:
            logger.warning(
                "Error calling Gemini (%s) - Attempt %s/%s: %s",
                _MODEL_NAME,
                attempt + 1,
                retries,
                exc,
            )
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                logger.error("Final failure calling Gemini after %s attempts: %s", retries, exc)
    return ""


async def _generate_content_ollama(prompt: str, retries: int) -> str:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                text = (data.get("response") or "").strip()
                if text:
                    return text
        except Exception as exc:
            logger.warning(
                "Error calling Ollama (%s at %s) - Attempt %s/%s: %s",
                OLLAMA_MODEL,
                OLLAMA_BASE_URL,
                attempt + 1,
                retries,
                exc,
            )
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                logger.error("Final failure calling Ollama after %s attempts: %s", retries, exc)
    return ""


async def generate_content(prompt: str, retries: int = 3) -> str:
    for provider in _provider_order():
        if provider == "ollama":
            result = await _generate_content_ollama(prompt, retries)
        else:
            result = await _generate_content_gemini(prompt, retries)

        if result:
            return result

    return ""


PROMPT_INSTALLMENT_TIP = """
Voce e um consultor financeiro pessoal. Um usuario registrou uma nova parcela.
Gere UMA dica curta (maximo 2 frases), pratica e especifica para o contexto abaixo.

Dados:
- Compra: {description}
- Parcela mensal: R$ {installment_amount:.2f}
- Duracao: {total_installments}x ({remaining_installments} restantes)
- Termino previsto: {end_date}
- Total de parcelas ativas do usuario: R$ {active_monthly_total:.2f}/mes

Regras:
- Seja especifico: mencione valores ou datas reais
- Foque em: impacto no orcamento, prazo real ou estrategia de reserva
- NUNCA seja generico ("economize mais", "planeje-se" sao proibidos)
- Tom: direto, sem rodeios, como um amigo que entende de financas
- Retorne apenas a dica, sem prefixo ou explicacao
"""


async def generate_installment_tip(data: dict) -> str:
    try:
        prompt = PROMPT_INSTALLMENT_TIP.format(**data)
        return await generate_content(prompt)
    except Exception as exc:
        logger.error("Error generating tip: %s", exc)
        return "Reserve o valor da parcela alguns dias antes do vencimento para evitar imprevistos."


async def answer_natural(message: str, context: dict) -> str:
    data_str = ""
    if context:
        data_str = f"\nDados do usuario este mes: {json.dumps(context, ensure_ascii=False)}"

    prompt = f"""
Voce e o FinBot, assistente financeiro pessoal via WhatsApp/Telegram.
Responda de forma curta, direta e amigavel em portugues.
Maximo 3 frases. Use emojis com moderacao.
{data_str}

Mensagem do usuario: {message}
"""
    return await generate_content(prompt)


PROMPT_INTERPRET = """
Analise a mensagem financeira do usuario e extraia os dados em formato JSON.
Considere o historico da conversa para inferir contexto (ex: correcoes de valores, categorias).

Tipos possiveis:
- 'expense': gasto, compra, pagamento
- 'income': ganho, salario, recebimento
- 'installment': parcelamento (cartao de credito)
- 'balance': consultar saldo/gastos (hoje, semana, mes)
- 'report': pedir relatorio ou resumo
- 'question': duvida financeira generica
- 'confirmation': confirmar acao anterior (sim, ok, confirma)
- 'cancellation': cancelar acao anterior (nao, cancela, esquece)
- 'unknown': nao entendi

Campos JSON:
- type: (obrigatorio) um dos tipos acima
- value: (number, opcional) valor monetario
- category: (string, opcional) categoria (ex: Alimentacao, Transporte, Casa, Lazer)
- date: (string, opcional) data mencionada (YYYY-MM-DD, ou 'hoje', 'ontem')
- description: (string, opcional) descricao curta
- installment_count: (number, opcional) numero de parcelas se for installment
- question_text: (string, opcional) se for 'question', o texto da pergunta

Exemplos:
"Gastei 45 no mercado" -> {{"type": "expense", "value": 45, "category": "Mercado", "description": "Mercado", "date": "hoje"}}
"Uber 18 reais" -> {{"type": "expense", "value": 18, "category": "Transporte", "description": "Uber", "date": "hoje"}}
"Sim" (apos pergunta de confirmacao) -> {{"type": "confirmation"}}
"Nao, foi 50 reais" -> {{"type": "expense", "value": 50}}

Historico:
{history}

Mensagem atual: "{message}"

Responda APENAS o JSON, sem markdown ou explicacoes.
"""


async def interpret_message(message: str, history: list = None) -> dict:
    history_str = ""
    if history:
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])

    prompt = PROMPT_INTERPRET.format(message=message, history=history_str)
    response_text = await generate_content(prompt)
    response_text = response_text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from AI: %s", response_text)
        return _fallback_interpret_message(message)


def _fallback_interpret_message(message: str) -> dict:
    text = (message or "").strip()
    lowered = text.lower()

    if not text:
        return {"type": "unknown"}

    greetings = {"oi", "ola", "bom dia", "boa tarde", "boa noite", "/start", "/menu", "menu", "ajuda", "/help"}
    if lowered in greetings:
        return {"type": "question", "question_text": text}

    if any(token in lowered for token in ["relatorio", "resumo", "/mes", "/semana", "/hoje"]):
        return {"type": "report"}

    if any(token in lowered for token in ["saldo", "balanco", "quanto gastei"]):
        return {"type": "balance"}

    if lowered in {"sim", "s", "ok", "confirmar", "confirma", "yes"}:
        return {"type": "confirmation"}

    if lowered in {"nao", "n", "cancelar", "cancela", "parar"}:
        return {"type": "cancellation"}

    amount_match = re.search(r"(\d+[\.,]\d+|\d+)", lowered)
    if amount_match:
        value = float(amount_match.group(1).replace(",", "."))
        category = "Outros"
        category_map = {
            "Transporte": ["uber", "taxi", "99", "metro", "onibus"],
            "Alimentacao": ["almoco", "jantar", "lanche", "ifood", "restaurante", "mercado"],
            "Casa": ["aluguel", "condominio", "luz", "agua", "internet"],
            "Lazer": ["cinema", "netflix", "spotify", "bar", "show"],
            "Saude": ["farmacia", "remedio", "medico"],
        }
        for cat_name, keywords in category_map.items():
            if any(keyword in lowered for keyword in keywords):
                category = cat_name
                break

        return {
            "type": "expense",
            "value": value,
            "category": category,
            "description": text,
            "date": "hoje",
        }

    return {"type": "unknown"}

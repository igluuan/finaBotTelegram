from google import genai
from google.genai.types import HttpOptions
import logging
try:
    from ...config import GEMINI_API_KEY
except ImportError:
    from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

_MODEL_NAME = "gemini-2.5-flash"

try:
    _client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=HttpOptions(api_version="v1"),
    ) if GEMINI_API_KEY else None
except Exception as _e:
    logger.error(f"Falha ao configurar Gemini: {_e}")
    _client = None

async def generate_content(prompt: str) -> str:
    if _client is None:
        return ""
    try:
        response = await _client.aio.models.generate_content(
            model=_MODEL_NAME,
            contents=prompt,
        )
        return getattr(response, "text", "") or ""
    except Exception as e:
        logger.error(f"Erro ao chamar Gemini ({_MODEL_NAME}): {e}")
        return ""

PROMPT_DICA_PARCELA = """
Você é um consultor financeiro pessoal. Um usuário registrou uma nova parcela.
Gere UMA dica curta (máximo 2 frases), prática e específica para o contexto abaixo.

Dados:
- Compra: {descricao}
- Parcela mensal: R$ {valor_parcela:.2f}
- Duração: {total_parcelas}x ({parcelas_restantes} restantes)
- Término previsto: {data_termino}
- Total de parcelas ativas do usuário: R$ {total_mensal_ativo:.2f}/mês

Regras:
- Seja específico: mencione valores ou datas reais
- Foque em: impacto no orçamento, prazo real ou estratégia de reserva
- NUNCA seja genérico ("economize mais", "planeje-se" são proibidos)
- Tom: direto, sem rodeios, como um amigo que entende de finanças
- Retorne apenas a dica, sem prefixo ou explicação
"""

async def gerar_dica_parcela(dados: dict) -> str:
    try:
        prompt = PROMPT_DICA_PARCELA.format(**dados)
        return await generate_content(prompt)
    except Exception:
        return "Reserve o valor da parcela alguns dias antes do vencimento para evitar imprevistos."

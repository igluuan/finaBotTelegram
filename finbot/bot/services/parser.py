import json
import logging
import re
from datetime import date, datetime, timedelta
from .ai_service import generate_content

logger = logging.getLogger(__name__)

def parse_user_date(texto: str, hoje: date | None = None) -> date:
    if hoje is None:
        hoje = date.today()
    t = texto.lower()
    if "ontem" in t:
        return hoje - timedelta(days=1)
    m = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', t)
    if not m:
        return hoje
    dia = int(m.group(1))
    mes = int(m.group(2))
    ano_str = m.group(3)
    if ano_str:
        ano = int(ano_str)
        if ano < 100:
            ano = 2000 + ano if ano < 70 else 1900 + ano
    else:
        ano = hoje.year
    try:
        data_base = date(ano, mes, dia)
    except ValueError:
        return hoje
    if not ano_str and data_base > hoje + timedelta(days=1):
        try:
            data_base = date(ano - 1, mes, dia)
        except ValueError:
            return hoje
    return data_base

def _local_parse_gasto(mensagem: str) -> dict:
    """
    Fallback local para extrair valor, categoria e descrição de mensagens simples,
    como '7,94 uber' ou 'almoço 20'.
    """
    msg = mensagem.strip().lower()
    # Extrair primeiro número (aceita vírgula ou ponto)
    m = re.search(r'(?P<valor>\d+[\.,]\d+|\d+)', msg)
    if not m:
        return {"erro": "nao_reconhecido"}
    raw_valor = m.group("valor").replace(',', '.')
    try:
        valor = float(raw_valor)
    except Exception:
        return {"erro": "nao_reconhecido"}

    # Remover o número para analisar palavras
    texto_sem_num = (msg[:m.start()] + msg[m.end():]).strip()
    descricao = texto_sem_num.strip() if texto_sem_num else ""

    # Heurística de categorias por palavras-chave
    cat = "outros"
    mappings = {
        "transporte": ["uber", "99", "taxi", "ônibus", "onibus", "metro", "combustivel", "combustível"],
        "alimentacao": ["almoço", "almoco", "jantar", "lanche", "café", "cafe", "restaurante", "pizza", "burger"],
        "mercado": ["mercado", "supermercado", "carrefour", "assai", "atacad", "extra"],
        "moradia": ["aluguel", "condominio", "condomínio", "luz", "energia", "agua", "água", "internet"],
        "lazer": ["cinema", "netflix", "spotify", "lazer", "jogo", "game", "bar"],
        "saude": ["farmacia", "farmácia", "remedio", "remédio", "medico", "médico", "plano"],
        "educacao": ["curso", "faculdade", "escola", "ebook", "livro"],
        "assinaturas": ["assinatura", "prime", "disney", "hbo", "max"]
    }
    for k, kws in mappings.items():
        if any(kw in texto_sem_num for kw in kws):
            cat = k
            break

    return {
        "valor": valor,
        "categoria": cat,
        "descricao": descricao.strip().title() if descricao else "",
        "confianca": 0.9
    }

async def parse_gasto(mensagem: str) -> dict:
    prompt = f"""
SYSTEM:
Você é um parser de gastos financeiros. Extraia dados da mensagem e retorne
APENAS JSON válido, sem markdown, sem explicações.

Categorias disponíveis:
alimentacao, transporte, moradia, saude, lazer, educacao,
vestuario, mercado, assinaturas, outros

Retorne:
{{
  "valor": 35.00,
  "categoria": "transporte",
  "descricao": "Uber para o trabalho",
  "confianca": 0.95
}}

Se não encontrar valor monetário, retorne: {{"erro": "nao_reconhecido"}}

USER:
{mensagem}
"""
    response_text = await generate_content(prompt)
    if response_text:
        try:
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            # Normalização de valor vindo como string com vírgula
            if isinstance(data.get("valor"), str):
                try:
                    data["valor"] = float(data["valor"].replace(',', '.'))
                except Exception:
                    pass
            return data
        except json.JSONDecodeError:
            logger.error(f"Erro ao decodificar JSON do parser: {response_text}")
    # Fallback local se IA falhar
    return _local_parse_gasto(mensagem)

async def analise_mensal(dados_str: str) -> str:
    prompt = f"""
SYSTEM:
Você é um consultor financeiro pessoal. Analise os dados abaixo e gere
um relatório em português, direto e amigável.

Estrutura OBRIGATÓRIA (não altere):
📊 *Análise de {{mes}}/{{ano}}*

✅ *O que foi bem:* (máx. 2 itens específicos)
⚠️ *Ponto de atenção:* (máx. 2 itens com dado concreto)
💡 *Dica do mês:* (1 ação realizável e específica)

Regras:
- Máximo 150 palavras
- Use markdown Telegram (*bold*, _italic_)
- Seja específico: cite valores e categorias reais
- Dicas acionáveis, nunca genéricas ("economize mais" é proibido)
- Tom: colega que entende de finanças, não professor

USER:
{dados_str}
"""
    return await generate_content(prompt)

async def check_anomalia(historico: str, novo_gasto: str) -> dict:
    prompt = f"""
SYSTEM:
Dado o histórico abaixo, avalie se o novo gasto é incomum para o usuário.
Retorne APENAS JSON:

{{
  "incomum": true,
  "motivo": "Valor 3x acima da média de R$ 45 em restaurantes",
  "percentual_acima": 200
}}

USER:
Histórico: {historico}
Novo gasto: {novo_gasto}
"""
    response_text = await generate_content(prompt)
    try:
        clean_text = response_text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except json.JSONDecodeError:
        logger.error(f"Erro ao decodificar JSON de anomalia: {response_text}")
        return {"incomum": False}

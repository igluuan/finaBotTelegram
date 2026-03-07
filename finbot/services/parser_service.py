import json
import logging
import re
from datetime import date, timedelta
from typing import Optional, Dict, Any
from finbot.services.ai_service import generate_content

logger = logging.getLogger(__name__)

def parse_user_date(text: str, today: Optional[date] = None) -> date:
    if today is None:
        today = date.today()
    t = text.lower()
    if "ontem" in t:
        return today - timedelta(days=1)
    
    m = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', t)
    if not m:
        return today
        
    day = int(m.group(1))
    month = int(m.group(2))
    year_str = m.group(3)
    
    if year_str:
        year = int(year_str)
        if year < 100:
            year = 2000 + year if year < 70 else 1900 + year
    else:
        year = today.year
        
    try:
        base_date = date(year, month, day)
    except ValueError:
        return today
        
    if not year_str and base_date > today + timedelta(days=1):
        try:
            base_date = date(year - 1, month, day)
        except ValueError:
            return today
            
    return base_date

def _local_parse_expense(message: str) -> Dict[str, Any]:
    """
    Local fallback to extract amount, category and description from simple messages.
    """
    msg = message.strip().lower()
    # Extract first number (accepts comma or dot)
    m = re.search(r'(?P<amount>\d+[\.,]\d+|\d+)', msg)
    if not m:
        return {"error": "not_recognized"}
    
    raw_amount = m.group("amount").replace(',', '.')
    try:
        amount = float(raw_amount)
    except Exception:
        return {"error": "not_recognized"}

    # Remove number to analyze words
    text_without_num = (msg[:m.start()] + " " + msg[m.end():]).strip()
    # Normalize spaces
    text_without_num = " ".join(text_without_num.split())
    description = text_without_num.strip() if text_without_num else ""

    # Category heuristics by keywords
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
        if any(kw in text_without_num for kw in kws):
            cat = k
            break

    return {
        "amount": amount,
        "category": cat,
        "description": description.strip().title() if description else "",
        "confidence": 0.9
    }

async def parse_expense(message: str) -> Dict[str, Any]:
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
{message}
"""
    response_text = await generate_content(prompt)
    if response_text:
        try:
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            
            # Normalize amount coming as string with comma
            val = data.get("valor")
            if isinstance(val, str):
                try:
                    val = float(val.replace(',', '.'))
                except Exception:
                    pass
            
            # Map Portuguese keys from prompt to English internal keys
            if "erro" in data:
                 return {"error": "not_recognized"}
                 
            return {
                "amount": val,
                "category": data.get("categoria"),
                "description": data.get("descricao"),
                "confidence": data.get("confianca")
            }
            
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from parser: {response_text}")
            
    # Fallback local if AI fails
    return _local_parse_expense(message)

async def analyze_monthly_report(data_str: str) -> str:
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
{data_str}
"""
    return await generate_content(prompt)

async def detect_intent(message: str) -> Dict[str, Any]:
    prompt = f"""
Classifique a mensagem do usuário em uma das intenções abaixo.
Retorne APENAS JSON válido, sem markdown.

Intenções:
- gasto: registrar uma despesa ("35 uber", "gastei 20 no almoço")
- consulta_saldo: perguntar sobre gastos/saldo ("quanto gastei?", "como estou no mês?")
- consulta_categoria: perguntar sobre categoria ("quanto gastei em alimentação?")
- dica: pedir conselho financeiro ("como economizar?", "tô gastando muito")
- saudacao: olá, oi, bom dia, /start
- outro: qualquer outra coisa

Retorne:
{{
  "intent": "gasto",
  "confianca": 0.95
}}

Mensagem: {message}
"""
    try:
        response = await generate_content(prompt)
        if not response:
             raise ValueError("Empty response")
        clean = response.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        logger.warning(f"Error detecting intent: {e}")
        return {"intent": "outro", "confianca": 0.5}

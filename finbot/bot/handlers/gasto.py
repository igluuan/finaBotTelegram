import logging
from telegram import Update
from telegram.ext import ContextTypes
from ..services import parser
from ..database import crud

logger = logging.getLogger(__name__)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    # Verificar se usuário existe, se não, criar (ou bloquear se não for ALLOWED_USER_ID)
    user = crud.get_user(user_id)
    if not user:
        # Check ALLOWED_USER_ID
        from ...config import ALLOWED_USER_ID
        if ALLOWED_USER_ID and str(user_id) != str(ALLOWED_USER_ID):
            await update.message.reply_text("⛔ Acesso não autorizado.")
            return
        crud.create_user(user_id, update.message.from_user.first_name)

    texto = update.message.text
    
    # Processar com AI
    await update.message.reply_chat_action("typing")
    resultado = await parser.parse_gasto(texto)
    
    if "erro" in resultado:
        await update.message.reply_text("❓ Não entendi esse gasto. Tente algo como '35 uber' ou 'almoço 20'.")
        return
    
    valor = resultado.get("valor")
    if isinstance(valor, str):
        try:
            valor = float(valor.replace(',', '.'))
        except Exception:
            await update.message.reply_text("Valor de gasto inválido.")
            return
    categoria = resultado.get("categoria")
    descricao = resultado.get("descricao", "")
    confianca = resultado.get("confianca", 0)
    
    if confianca < 0.7:
        # Poderia implementar confirmação aqui
        pass

    # Salvar no banco
    crud.add_gasto(user_id, valor, categoria, descricao)
    
    # Feedback
    # Calcular total da categoria no mês
    from datetime import datetime
    hoje = datetime.now()
    gastos_cat = crud.get_gastos_por_categoria(user_id, hoje.month, hoje.year)
    total_cat = next((item['total'] for item in gastos_cat if item['categoria'] == categoria), 0)
    
    # Verificar orçamento
    orcamento = crud.get_orcamento_status(user_id, hoje.month, hoje.year)
    orc_cat = next((item for item in orcamento if item['categoria'] == categoria), None)
    
    msg = f"✅ R$ {valor:.2f} em *{categoria.capitalize()}* registrado\n"
    if orc_cat and orc_cat['limite'] > 0:
        percentual = orc_cat['percentual']
        msg += f"📊 {categoria.capitalize()}: R$ {total_cat:.2f} / R$ {orc_cat['limite']:.2f} ({percentual:.1f}%)"
        if percentual > 80:
            msg += "\n⚠️ *Atenção:* Você atingiu 80% do orçamento!"
    else:
        msg += f"📊 Total {categoria.capitalize()} este mês: R$ {total_cat:.2f}"

    await update.message.reply_text(msg, parse_mode='Markdown')

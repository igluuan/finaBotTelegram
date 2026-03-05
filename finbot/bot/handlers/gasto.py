import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from ..services import parser
from ..database import crud

logger = logging.getLogger(__name__)

CONFIRMAR, AJUSTAR_CATEGORIA = range(2)

CATEGORIAS_OPCOES = {
    "Alimentação": "alimentacao",
    "Transporte": "transporte",
    "Mercado": "mercado",
    "Moradia": "moradia",
    "Lazer": "lazer",
    "Saúde": "saude",
    "Educação": "educacao",
    "Assinaturas": "assinaturas",
    "Outros": "outros",
}

async def _garantir_usuario(update: Update) -> int | None:
    if not update.message:
        return None
    user_id = update.message.from_user.id
    user = crud.get_user(user_id)
    if not user:
        from ...config import ALLOWED_USER_ID
        if ALLOWED_USER_ID and str(user_id) != str(ALLOWED_USER_ID):
            await update.message.reply_text("⛔ Acesso não autorizado.")
            return None
        crud.create_user(user_id, update.message.from_user.first_name)
    return user_id

async def iniciar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = await _garantir_usuario(update)
    if user_id is None:
        return ConversationHandler.END
    if not update.message or not update.message.text:
        return ConversationHandler.END
    texto = update.message.text
    await update.message.reply_chat_action("typing")
    resultado = await parser.parse_gasto(texto)
    if "erro" in resultado:
        await update.message.reply_text("❓ Não entendi esse gasto. Tente algo como '35 uber' ou 'almoço 20'.")
        return ConversationHandler.END
    valor = resultado.get("valor")
    if isinstance(valor, str):
        try:
            valor = float(valor.replace(',', '.'))
        except Exception:
            await update.message.reply_text("Valor de gasto inválido.")
            return ConversationHandler.END
    categoria = resultado.get("categoria")
    descricao = resultado.get("descricao", "")
    confianca = resultado.get("confianca", 0)
    from datetime import datetime, date, timedelta
    data_gasto = date.today()
    texto_lower = texto.lower()
    if "ontem" in texto_lower:
        data_gasto = date.today() - timedelta(days=1)
    else:
        import re
        m = re.search(r'(\d{1,2})[/-](\d{1,2})', texto_lower)
        if m:
            dia = int(m.group(1))
            mes = int(m.group(2))
            ano = datetime.now().year
            try:
                data_gasto = date(ano, mes, dia)
            except ValueError:
                data_gasto = date.today()
    context.user_data["gasto"] = {
        "user_id": user_id,
        "valor": valor,
        "categoria": categoria,
        "descricao": descricao,
        "texto_original": texto,
        "data": data_gasto,
    }
    if confianca < 0.7:
        teclado = ReplyKeyboardMarkup(
            [["✅ Confirmar", "✏️ Trocar categoria"], ["❌ Cancelar"]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        msg = (
            f"Vou registrar assim:\n\n"
            f"• Valor: R$ {valor:.2f}\n"
            f"• Categoria: {categoria}\n"
            f"• Descrição: {descricao or '-'}\n\n"
            f"Está correto? Você pode confirmar, trocar a categoria ou cancelar."
        )
        await update.message.reply_text(msg, reply_markup=teclado)
        return CONFIRMAR
    await _finalizar_gasto(update, context)
    return ConversationHandler.END

async def confirmar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return ConversationHandler.END
    texto = update.message.text.strip().lower()
    dados = context.user_data.get("gasto")
    if not dados:
        return ConversationHandler.END
    if "confirmar" in texto or "✅" in texto or "sim" in texto:
        await _finalizar_gasto(update, context)
        context.user_data.pop("gasto", None)
        return ConversationHandler.END
    if "trocar" in texto or "✏" in texto:
        teclado = ReplyKeyboardMarkup(
            [
                ["Alimentação", "Transporte"],
                ["Mercado", "Lazer"],
                ["Moradia", "Saúde"],
                ["Educação", "Assinaturas"],
                ["Outros"],
            ],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        await update.message.reply_text(
            "Escolha a categoria correta para este gasto:",
            reply_markup=teclado
        )
        return AJUSTAR_CATEGORIA
    await update.message.reply_text(
        "Ok, não registrei esse gasto. Tente enviar novamente com mais detalhes.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.pop("gasto", None)
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("❌ Registro cancelado.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def ajustar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return ConversationHandler.END
    escolha = update.message.text.strip()
    nova_categoria = CATEGORIAS_OPCOES.get(escolha)
    dados = context.user_data.get("gasto")
    if not dados:
        return ConversationHandler.END
    if not nova_categoria:
        await update.message.reply_text(
            "Escolha uma categoria válida usando o teclado.",
        )
        return AJUSTAR_CATEGORIA
    dados["categoria"] = nova_categoria
    context.user_data["gasto"] = dados
    await _finalizar_gasto(update, context)
    context.user_data.pop("gasto", None)
    return ConversationHandler.END

async def _finalizar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    import json
    dados = context.user_data.get("gasto")
    if not dados:
        return
    user_id = dados["user_id"]
    valor = dados["valor"]
    categoria = dados["categoria"]
    descricao = dados["descricao"]
    data_gasto = dados.get("data")
    crud.add_gasto(user_id, valor, categoria, descricao, data_registro=data_gasto)
    hoje = datetime.now()
    gastos_cat = crud.get_gastos_por_categoria(user_id, hoje.month, hoje.year)
    total_cat = next((item['total'] for item in gastos_cat if item['categoria'] == categoria), 0)
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
    if update.message:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
    try:
        historico = crud.get_historico_categoria(user_id, categoria, dias=30)
        if historico:
            hist_str = json.dumps(
                [
                    {
                        "data": g.data.isoformat(),
                        "valor": g.valor,
                        "descricao": g.descricao,
                    }
                    for g in historico
                ],
                ensure_ascii=False
            )
            data_novo = data_gasto or hoje.date()
            novo = json.dumps(
                {
                    "data": data_novo.isoformat(),
                    "valor": valor,
                    "descricao": descricao,
                },
                ensure_ascii=False
            )
            resultado_anomalia = await parser.check_anomalia(hist_str, novo)
            if resultado_anomalia.get("incomum"):
                motivo = resultado_anomalia.get("motivo", "")
                await update.message.reply_text(
                    f"⚠️ Gasto incomum detectado: {motivo}",
                    parse_mode='Markdown'
                )
    except Exception:
        pass

def get_gasto_handlers():
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, iniciar_gasto)],
        states={
            CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_gasto)],
            AJUSTAR_CATEGORIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ajustar_categoria)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        conversation_timeout=300
    )
    return [conv]

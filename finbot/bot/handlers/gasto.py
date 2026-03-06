import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from ..services import parser
from ..database import crud
from ..decorators import garantir_usuario

logger = logging.getLogger(__name__)

CONFIRMAR, AJUSTAR_CATEGORIA, METODO_PAGAMENTO, SELECIONAR_CARTAO = range(4)

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

async def _processar_valor(update: Update, valor_str: str):
    try:
        return float(valor_str.replace(',', '.'))
    except Exception:
        await update.message.reply_text("Valor de gasto inválido.")
        return None

async def _confirmar_ia(update: Update, context: ContextTypes.DEFAULT_TYPE, dados: dict, confianca: float):
    if confianca < 0.7:
        teclado = ReplyKeyboardMarkup(
            [["✅ Confirmar", "✏️ Trocar categoria"], ["❌ Cancelar"]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        msg = (
            f"Vou registrar assim:\n\n"
            f"• Valor: R$ {dados['valor']:.2f}\n"
            f"• Categoria: {dados['categoria']}\n"
            f"• Descrição: {dados['descricao'] or '-'}\n\n"
            f"Está correto? Você pode confirmar, trocar a categoria ou cancelar."
        )
        await update.message.reply_text(msg, reply_markup=teclado)
        return CONFIRMAR
    return None

@garantir_usuario
async def iniciar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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
        valor = await _processar_valor(update, valor)
        if valor is None:
            return ConversationHandler.END

    categoria = resultado.get("categoria")
    descricao = resultado.get("descricao", "")
    confianca = resultado.get("confianca", 0)
    
    from datetime import date
    data_gasto = parser.parse_user_date(texto, hoje=date.today())
    
    context.user_data["gasto"] = {
        "user_id": user_id,
        "valor": valor,
        "categoria": categoria,
        "descricao": descricao,
        "texto_original": texto,
        "data": data_gasto,
    }
    
    estado_confirmacao = await _confirmar_ia(update, context, context.user_data["gasto"], confianca)
    if estado_confirmacao is not None:
        return estado_confirmacao
    
    return await perguntar_metodo(update, context)

async def perguntar_metodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Opções simplificadas: Dinheiro, Pix, Crédito, Débito
    botoes = [
        ["💠 Pix", "💵 Dinheiro"],
        ["💳 Crédito", "💳 Débito"],
        ["Pular"]
    ]
    
    teclado = ReplyKeyboardMarkup(botoes, one_time_keyboard=True, resize_keyboard=True)
    
    dados = context.user_data["gasto"]
    await update.message.reply_text(
        f"💰 Pagamento de *R$ {dados['valor']:.2f}* ({dados['categoria']}).\n"
        "Qual foi a forma de pagamento?",
        parse_mode="Markdown",
        reply_markup=teclado
    )
    return METODO_PAGAMENTO

async def perguntar_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE, tipo_pagamento: str):
    user_id = context.user_data["gasto"]["user_id"]
    
    # Determina o tipo para filtro (credito ou debito)
    # tipo_pagamento vem como "Crédito" ou "Débito" (limpo de emojis)
    tipo_filtro = "credito" if "Crédito" in tipo_pagamento else "debito"
    
    # Buscar cartões do usuário
    cartoes = crud.get_cartoes_usuario(user_id)
    
    # Fallback de parcelas antigas
    if not cartoes:
        finais_parcelas = crud.get_user_cards(user_id)
        if finais_parcelas:
             for f in finais_parcelas:
                  cartoes.append(type('obj', (object,), {'final': f, 'nome': None, 'tipo': 'ambos'}))

    botoes = []
    
    # Filtra e cria botões
    if cartoes:
        for c in cartoes:
            # Filtra pelo tipo
            if c.tipo != 'ambos' and c.tipo != tipo_filtro:
                continue
                
            final = c.final
            nome = c.nome
            
            label = f" {nome} ({final})" if nome else f" ({final})"
            botao_texto = f"💳{label}"
            botoes.append(botao_texto)

    # Se não houver cartões específicos, finaliza com o genérico
    if not botoes:
        context.user_data["gasto"]["metodo"] = tipo_pagamento
        await _finalizar_gasto(update, context)
        return ConversationHandler.END

    # Organiza botões em linhas de 2
    menu = []
    for i in range(0, len(botoes), 2):
        menu.append(botoes[i:i+2])
        
    menu.append(["Voltar"])
    
    teclado = ReplyKeyboardMarkup(menu, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Selecione o cartão de *{tipo_pagamento}*:",
        parse_mode="Markdown",
        reply_markup=teclado
    )
    return SELECIONAR_CARTAO

async def receber_metodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    
    if texto == "Pular":
        metodo = None
    else:
        # Remove emojis para processar
        # "💳 Crédito" -> "Crédito"
        # "💳 Débito" -> "Débito"
        # "💠 Pix" -> "Pix"
        clean_text = texto.replace("💠 ", "").replace("💵 ", "").replace("💳 ", "")
        
        if clean_text in ["Crédito", "Débito"]:
            # Se for cartão, vai para seleção de cartão
            return await perguntar_cartao(update, context, clean_text)
            
        metodo = clean_text
        
    context.user_data["gasto"]["metodo"] = metodo
    await _finalizar_gasto(update, context)
    return ConversationHandler.END

async def receber_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    
    if texto == "Voltar":
        return await perguntar_metodo(update, context)
        
    # Remove emoji do cartão selecionado
    # Ex: "💳 Crédito Nubank (1234)" -> "Crédito Nubank (1234)"
    metodo = texto.replace("💳 ", "")
    
    context.user_data["gasto"]["metodo"] = metodo
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
        # Se confirmou, pergunta o método
        return await perguntar_metodo(update, context)
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
    if "cancelar" in texto or "❌" in texto:
        context.user_data.clear()
        await update.message.reply_text("❌ Registro cancelado.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
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
    
    # Após ajustar, pergunta o método
    return await perguntar_metodo(update, context)

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
    metodo = dados.get("metodo")  # Pega o método escolhido
    data_gasto = dados.get("data")
    crud.add_gasto(user_id, valor, categoria, descricao, metodo=metodo, data_registro=data_gasto)
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
    historico = crud.get_historico_categoria(user_id, categoria, dias=30)
    if historico:
        try:
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
        except TypeError:
            logger.exception(
                "Falha ao serializar historico para anomalia",
                extra={"user_id": user_id, "categoria": categoria}
            )
            return

        try:
            resultado_anomalia = await parser.check_anomalia(hist_str, novo)
        except Exception:
            logger.exception(
                "Falha ao verificar anomalia",
                extra={"user_id": user_id, "categoria": categoria}
            )
            return

        if resultado_anomalia.get("incomum"):
            motivo = resultado_anomalia.get("motivo", "")
            try:
                await update.message.reply_text(
                    f"⚠️ Gasto incomum detectado: {motivo}",
                    parse_mode='Markdown'
                )
            except TelegramError:
                logger.exception(
                    "Falha ao enviar alerta de anomalia",
                    extra={"user_id": user_id, "categoria": categoria}
                )

def get_gasto_handlers():
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, iniciar_gasto)],
        states={
            CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_gasto)],
            AJUSTAR_CATEGORIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ajustar_categoria)],
            METODO_PAGAMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_metodo)],
            SELECIONAR_CARTAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_cartao)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        conversation_timeout=300
    )
    return [conv]

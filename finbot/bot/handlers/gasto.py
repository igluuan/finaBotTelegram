import logging
import asyncio
from datetime import date
from typing import Optional, Dict, Any, List

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.error import TelegramError
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from ..services import parser, finance_service
from ..database import crud
from ..decorators import garantir_usuario
from .. import ui

logger = logging.getLogger(__name__)

# Estados da conversa
CONFIRMAR, AJUSTAR_CATEGORIA, METODO_PAGAMENTO, SELECIONAR_CARTAO = range(4)

async def _processar_valor(update: Update, valor_str: str) -> Optional[float]:
    """Converte string de valor para float com validações básicas."""
    try:
        val = float(valor_str.replace(',', '.'))
        if val <= 0:
            await update.message.reply_text("❌ O valor deve ser maior que zero.")
            return None
        if val > 1_000_000:
            await update.message.reply_text("⚠️ Valor muito alto. Verifique se digitou corretamente.")
            return None
        return val
    except ValueError:
        await update.message.reply_text("Valor de gasto inválido.")
        return None

async def _confirmar_ia(update: Update, context: ContextTypes.DEFAULT_TYPE, dados: Dict[str, Any], confianca: float) -> Optional[int]:
    """
    Se a confiança da IA for baixa, pede confirmação ao usuário.
    Retorna o próximo estado ou None se a confiança for alta.
    """
    if confianca >= 0.7:
        return None

    msg = ui.formatar_mensagem_confirmacao(
        dados['valor'],
        dados['categoria'],
        dados['descricao']
    )
    
    await update.message.reply_text(
        msg, 
        reply_markup=ui.teclado_confirmacao_gasto()
    )
    return CONFIRMAR

@garantir_usuario
async def iniciar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ponto de entrada: processa texto livre para extrair gasto."""
    if not update.message or not update.message.text:
        return ConversationHandler.END

    texto = update.message.text
    await update.message.reply_chat_action("typing")
    
    # Parsing via IA ou fallback local
    resultado = await parser.parse_gasto(texto)
    
    if "erro" in resultado:
        await update.message.reply_text(
            "❓ Não entendi esse gasto. Tente algo como '35 uber' ou 'almoço 20'."
        )
        return ConversationHandler.END
        
    valor = resultado.get("valor")
    if isinstance(valor, str):
        valor = await _processar_valor(update, valor)
        if valor is None:
            return ConversationHandler.END

    # Extração de data
    data_gasto = parser.parse_user_date(texto, hoje=date.today())
    
    # Armazena no contexto
    context.user_data["gasto"] = {
        "user_id": update.effective_user.id,
        "valor": valor,
        "categoria": resultado.get("categoria"),
        "descricao": resultado.get("descricao", ""),
        "texto_original": texto,
        "data": data_gasto,
    }
    
    # Verifica confiança da IA
    estado_confirmacao = await _confirmar_ia(
        update, 
        context, 
        context.user_data["gasto"], 
        resultado.get("confianca", 0)
    )
    
    if estado_confirmacao is not None:
        return estado_confirmacao
    
    return await perguntar_metodo(update, context)

async def perguntar_metodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pergunta o método de pagamento."""
    dados = context.user_data["gasto"]
    
    await update.message.reply_text(
        f"💰 Pagamento de *R$ {dados['valor']:.2f}* ({dados['categoria']}).\n"
        "Qual foi a forma de pagamento?",
        parse_mode="Markdown",
        reply_markup=ui.teclado_metodo_pagamento()
    )
    return METODO_PAGAMENTO

async def _buscar_cartoes(user_id: int, tipo_filtro: str) -> List[Any]:
    """Busca cartões do usuário filtrando por tipo (credito/debito)."""
    # Executa em thread separada pois é operação de banco síncrona
    cartoes = await asyncio.to_thread(crud.get_cartoes_usuario, user_id)
    
    # Fallback para cartões antigos sem cadastro completo
    if not cartoes:
        finais = await asyncio.to_thread(crud.get_user_cards, user_id)
        if finais:
            # Cria objetos compatíveis com a estrutura de cartões
            cartoes = [
                type('CartaoSimples', (object,), {'final': f, 'nome': None, 'tipo': 'ambos'})
                for f in finais
            ]
            
    return [
        c for c in cartoes 
        if c.tipo == 'ambos' or c.tipo == tipo_filtro
    ]

async def perguntar_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE, tipo_pagamento: str):
    """Mostra lista de cartões disponíveis para o tipo de pagamento selecionado."""
    user_id = context.user_data["gasto"]["user_id"]
    tipo_filtro = "credito" if "Crédito" in tipo_pagamento else "debito"
    
    cartoes_validos = await _buscar_cartoes(user_id, tipo_filtro)
    
    # Se não tem cartões, usa o método genérico e finaliza
    if not cartoes_validos:
        context.user_data["gasto"]["metodo"] = tipo_pagamento
        await _finalizar_gasto(update, context)
        return ConversationHandler.END

    # Cria botões para os cartões
    botoes = []
    for c in cartoes_validos:
        label = f" {c.nome} ({c.final})" if c.nome else f" ({c.final})"
        botoes.append(f"💳{label}")

    # Organiza em grade de 2 colunas
    menu = [botoes[i:i+2] for i in range(0, len(botoes), 2)]
    menu.append(["Voltar"])
    
    await update.message.reply_text(
        f"Selecione o cartão de *{tipo_pagamento}*:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(menu, one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECIONAR_CARTAO

async def receber_metodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a escolha do método de pagamento."""
    texto = update.message.text.strip()
    
    if texto == "Pular":
        context.user_data["gasto"]["metodo"] = None
        await _finalizar_gasto(update, context)
        return ConversationHandler.END

    # Limpa emojis e normaliza
    clean_text = texto.replace("💠 ", "").replace("💵 ", "").replace("💳 ", "")
    
    if clean_text in ["Crédito", "Débito"]:
        return await perguntar_cartao(update, context, clean_text)
        
    context.user_data["gasto"]["metodo"] = clean_text
    await _finalizar_gasto(update, context)
    return ConversationHandler.END

async def receber_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a escolha do cartão específico."""
    texto = update.message.text.strip()
    
    if texto == "Voltar":
        return await perguntar_metodo(update, context)
        
    # Remove emoji "💳 "
    metodo = texto.replace("💳 ", "")
    
    context.user_data["gasto"]["metodo"] = metodo
    await _finalizar_gasto(update, context)
    return ConversationHandler.END

async def confirmar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a resposta da confirmação da IA."""
    if not update.message:
        return ConversationHandler.END
        
    texto = update.message.text.strip().lower()
    
    if "confirmar" in texto or "✅" in texto or "sim" in texto:
        return await perguntar_metodo(update, context)
        
    if "trocar" in texto or "✏" in texto:
        await update.message.reply_text(
            "Escolha a categoria correta para este gasto:",
            reply_markup=ui.teclado_categorias_gasto()
        )
        return AJUSTAR_CATEGORIA
        
    if "cancelar" in texto or "❌" in texto:
        return await cancelar(update, context)
        
    await update.message.reply_text(
        "Ok, não registrei esse gasto. Tente enviar novamente com mais detalhes.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.pop("gasto", None)
    return ConversationHandler.END

async def ajustar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a troca manual de categoria."""
    if not update.message:
        return ConversationHandler.END
        
    escolha = update.message.text.strip()
    nova_categoria = finance_service.get_categoria_key(escolha)
    
    if not nova_categoria:
        await update.message.reply_text(
            "Escolha uma categoria válida usando o teclado.",
            reply_markup=ui.teclado_categorias_gasto()
        )
        return AJUSTAR_CATEGORIA
        
    context.user_data["gasto"]["categoria"] = nova_categoria
    return await perguntar_metodo(update, context)

def _salvar_gasto(dados: Dict[str, Any]):
    """Função auxiliar para salvar no banco (executada em thread)."""
    crud.add_gasto(
        dados["user_id"], 
        dados["valor"], 
        dados["categoria"], 
        dados["descricao"], 
        metodo=dados.get("metodo"), 
        data_registro=dados.get("data")
    )

async def _finalizar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finaliza o registro, salva no banco e envia feedback."""
    dados = context.user_data.get("gasto")
    if not dados:
        return

    # Salva no banco (thread separada para não bloquear)
    await asyncio.to_thread(_salvar_gasto, dados)
    
    # Verifica orçamento
    status_orcamento = await asyncio.to_thread(
        finance_service.verificar_orcamento,
        dados["user_id"],
        dados["categoria"],
        dados["valor"]
    )
    
    # Envia mensagem de sucesso
    msg = ui.formatar_mensagem_sucesso_gasto(
        dados["valor"],
        dados["categoria"],
        status_orcamento["total_acumulado"],
        status_orcamento["limite"],
        status_orcamento["percentual"]
    )
    
    if status_orcamento["alerta"]:
        msg += f"\n{status_orcamento['mensagem_alerta']}"
        
    if update.message:
        await update.message.reply_text(
            msg, 
            parse_mode='Markdown', 
            reply_markup=ReplyKeyboardRemove()
        )
    
    # Verifica anomalia em background (não bloqueia resposta final se falhar)
    try:
        resultado_anomalia = await finance_service.verificar_anomalia(
            dados["user_id"],
            dados["categoria"],
            dados["valor"],
            dados["descricao"],
            dados.get("data")
        )
        
        if resultado_anomalia.get("incomum"):
            motivo = resultado_anomalia.get("motivo", "")
            await update.message.reply_text(
                f"⚠️ Gasto incomum detectado: {motivo}",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Erro ao verificar anomalia: {e}", exc_info=True)

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela a operação atual."""
    context.user_data.clear()
    if update.message:
        await update.message.reply_text(
            "❌ Registro cancelado.", 
            reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END

def get_gasto_handlers():
    """Configura e retorna os handlers de conversação."""
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

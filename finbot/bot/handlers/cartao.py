from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, MessageHandler, filters
)
from ..database import crud
from ..decorators import garantir_usuario

FINAL_CARTAO, NOME_CARTAO, TIPO_CARTAO = range(3)

@garantir_usuario
async def start_add_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 **Cadastro de Cartão**\n\n"
        "Digite os **4 últimos dígitos** do cartão (ex: 4578):",
        parse_mode="Markdown"
    )
    return FINAL_CARTAO

async def receber_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    final = update.message.text.strip()
    if not final.isdigit() or len(final) != 4:
        await update.message.reply_text("❌ Digite exatamente 4 dígitos numéricos (ex: 1234).")
        return FINAL_CARTAO
    
    context.user_data['final_cartao'] = final
    await update.message.reply_text(
        "📝 Dê um **nome/apelido** para este cartão (ex: Nubank, Inter, VR):\n"
        "Ou digite /pular para deixar sem nome.",
        parse_mode="Markdown"
    )
    return NOME_CARTAO

async def receber_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    nome = texto if texto != "/pular" else None
    context.user_data['nome_cartao'] = nome
    
    teclado = ReplyKeyboardMarkup(
        [["Crédito", "Débito"], ["Ambos"]],
        one_time_keyboard=True, resize_keyboard=True
    )
    await update.message.reply_text(
        "🔄 Qual a **função** deste cartão?",
        parse_mode="Markdown",
        reply_markup=teclado
    )
    return TIPO_CARTAO

async def receber_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tipo = update.message.text.strip().lower()
    user_id = update.effective_user.id
    
    final = context.user_data['final_cartao']
    nome = context.user_data['nome_cartao']
    
    crud.add_cartao(user_id, final, nome, tipo)
    
    nome_display = f" ({nome})" if nome else ""
    await update.message.reply_text(
        f"✅ Cartão final **{final}**{nome_display} cadastrado com sucesso!",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

@garantir_usuario
async def listar_cartoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cartoes = crud.get_cartoes_usuario(user_id)
    
    if not cartoes:
        await update.message.reply_text("Nenhum cartão cadastrado.")
        return
        
    msg = "💳 **Seus Cartões:**\n\n"
    for c in cartoes:
        nome = f" - {c.nome}" if c.nome else ""
        msg += f"• **{c.final}**{nome} ({c.tipo})\n"
        
    await update.message.reply_text(msg, parse_mode="Markdown")

@garantir_usuario
async def deletar_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fluxo simples: /del_cartao 1234
    if not context.args:
        await update.message.reply_text("Use: /del_cartao [4 ultimos digitos]")
        return
        
    final = context.args[0]
    user_id = update.effective_user.id
    
    if crud.delete_cartao(user_id, final):
        await update.message.reply_text(f"🗑️ Cartão final {final} removido.")
    else:
        await update.message.reply_text(f"❌ Cartão final {final} não encontrado.")

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Operação cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def get_cartao_handlers():
    conv = ConversationHandler(
        entry_points=[CommandHandler("add_cartao", start_add_cartao)],
        states={
            FINAL_CARTAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_final)],
            NOME_CARTAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_nome)],
            TIPO_CARTAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_tipo)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )
    return [
        conv,
        CommandHandler("cartoes", listar_cartoes),
        CommandHandler("del_cartao", deletar_cartao)
    ]

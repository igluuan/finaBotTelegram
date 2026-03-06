from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from ..database import crud
from .config import ajuda  # Reutiliza a função de ajuda ao final

RENDA, DIA_FECHAMENTO = range(2)

async def start_cadastro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o fluxo de cadastro."""
    user = update.effective_user
    existing_user = crud.get_user(user.id)
    
    # Se usuário não existe, cria o básico
    if not existing_user:
        crud.create_user(user.id, user.first_name)
    
    # Verifica se já tem renda cadastrada (opcional, mas bom para não repetir)
    # Por enquanto, vamos sempre perguntar para permitir recadastro ou novos usuários
    
    await update.message.reply_text(
        f"Olá {user.first_name}! Sou o FinBot 💰.\n\n"
        "Para eu te ajudar melhor, preciso de algumas informações rápidas.\n"
        "Primeiro: *Qual é a sua renda mensal líquida aproximada?*\n"
        "(Digite apenas o valor, ex: 3500. Se não quiser informar, digite /cancel)",
        parse_mode='Markdown'
    )
    return RENDA

async def receber_renda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe a renda e pergunta o dia de fechamento."""
    text = update.message.text
    try:
        renda = float(text.replace(',', '.'))
        if renda < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Por favor, digite um valor numérico válido (ex: 3500). Tente novamente.")
        return RENDA

    # Salva temporariamente no context
    context.user_data['renda'] = renda

    await update.message.reply_text(
        "Certo! E qual é o *dia de fechamento da fatura* do seu cartão de crédito?\n"
        "(Digite um dia entre 1 e 31. Se não usar cartão, digite 1)",
        parse_mode='Markdown'
    )
    return DIA_FECHAMENTO

async def receber_dia_fechamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe o dia de fechamento e finaliza o cadastro."""
    text = update.message.text
    user_id = update.effective_user.id
    
    try:
        dia = int(text)
        if not (1 <= dia <= 31):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Por favor, digite um dia válido entre 1 e 31.")
        return DIA_FECHAMENTO

    # Salva as informações
    renda = context.user_data.get('renda')
    
    # 1. Salva a renda como Ganho recorrente
    dados_ganho = {
        "valor": renda,
        "categoria": "Salário",
        "descricao": "Renda Mensal Inicial",
        "recorrente": True,
        "dia_recebimento": 5,  # Padrão, poderia perguntar também
        "data": None # Usa hoje
    }
    with crud.get_db() as db:
        crud.criar_ganho(db, user_id, dados_ganho)
    
    # 2. Atualiza o dia de fechamento do usuário
    crud.update_user_fechamento(user_id, dia)

    await update.message.reply_text(
        "✅ *Cadastro concluído com sucesso!*\n\n"
        f"Renda definida: R$ {renda:.2f}\n"
        f"Dia de fechamento: {dia}\n\n"
        "Agora você já pode começar a usar o bot!",
        parse_mode='Markdown'
    )
    
    # Mostra a ajuda para ensinar os comandos
    await ajuda(update, context)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela o cadastro."""
    await update.message.reply_text(
        "Cadastro cancelado. Você pode usar /start para tentar novamente a qualquer momento.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def get_cadastro_handler():
    """Retorna o ConversationHandler configurado."""
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_cadastro)],
        states={
            RENDA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_renda)],
            DIA_FECHAMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_dia_fechamento)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

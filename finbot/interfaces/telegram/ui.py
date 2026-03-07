from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from typing import List, Optional

def format_balance(total_earnings: float, total_expenses: float, total_installments: float) -> str:
    balance = total_earnings - total_expenses - total_installments
    emoji_balance = "🟢" if balance >= 0 else "🔴"
    
    return (
        f"─────────────────\n"
        f"📊 *Balanço do mês:*\n"
        f"💚 Ganhos:   R$ {total_earnings:.2f}\n"
        f"🔴 Gastos:   R$ {total_expenses:.2f}\n"
        f"💳 Parcelas: R$ {total_installments:.2f}\n"
        f"─────────────────\n"
        f"{emoji_balance} *Saldo: R$ {balance:.2f}*"
    )

def yes_no_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["✅ Sim", "❌ Não"]], one_time_keyboard=True, resize_keyboard=True
    )

def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()

# --- New UI Helpers for Expense ---

def expense_confirmation_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["✅ Confirmar", "✏️ Trocar categoria"], ["❌ Cancelar"]],
        one_time_keyboard=True,
        resize_keyboard=True
    )

def payment_method_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        ["💠 Pix", "💵 Dinheiro"],
        ["💳 Crédito", "💳 Débito"],
        ["Pular"]
    ]
    return ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)

def expense_categories_keyboard() -> ReplyKeyboardMarkup:
    """Returns keyboard with expense categories."""
    # Hardcoded for UI, aligned with finance_service CATEGORY_OPTIONS
    return ReplyKeyboardMarkup(
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

def format_confirmation_message(amount: float, category: str, description: str) -> str:
    return (
        f"Vou registrar assim:\n\n"
        f"• Valor: R$ {amount:.2f}\n"
        f"• Categoria: {category}\n"
        f"• Descrição: {description or '-'}\n\n"
        f"Está correto? Você pode confirmar, trocar a categoria ou cancelar."
    )

def format_success_expense_message(
    amount: float, 
    category: str, 
    total_cat: float, 
    limit: float, 
    percentage: float
) -> str:
    msg = f"✅ R$ {amount:.2f} em *{category.capitalize()}* registrado\n"
    if limit > 0:
        msg += f"📊 {category.capitalize()}: R$ {total_cat:.2f} / R$ {limit:.2f} ({percentage:.1f}%)"
        if percentage > 80:
            msg += "\n⚠️ *Atenção:* Você atingiu 80% do orçamento!"
    else:
        msg += f"📊 Total {category.capitalize()} este mês: R$ {total_cat:.2f}"
    return msg

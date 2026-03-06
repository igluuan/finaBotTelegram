from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from typing import List, Optional

def formatar_balanco(total_ganhos: float, total_gastos: float, total_parcelas: float) -> str:
    saldo = total_ganhos - total_gastos - total_parcelas
    emoji_saldo = "🟢" if saldo >= 0 else "🔴"
    
    return (
        f"─────────────────\n"
        f"📊 *Balanço do mês:*\n"
        f"💚 Ganhos:   R$ {total_ganhos:.2f}\n"
        f"🔴 Gastos:   R$ {total_gastos:.2f}\n"
        f"💳 Parcelas: R$ {total_parcelas:.2f}\n"
        f"─────────────────\n"
        f"{emoji_saldo} *Saldo: R$ {saldo:.2f}*"
    )

def teclado_sim_nao():
    return ReplyKeyboardMarkup(
        [["✅ Sim", "❌ Não"]], one_time_keyboard=True, resize_keyboard=True
    )

def remover_teclado():
    return ReplyKeyboardRemove()

# --- Novos Helpers de UI para Gasto ---

def teclado_confirmacao_gasto() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["✅ Confirmar", "✏️ Trocar categoria"], ["❌ Cancelar"]],
        one_time_keyboard=True,
        resize_keyboard=True
    )

def teclado_metodo_pagamento() -> ReplyKeyboardMarkup:
    botoes = [
        ["💠 Pix", "💵 Dinheiro"],
        ["💳 Crédito", "💳 Débito"],
        ["Pular"]
    ]
    return ReplyKeyboardMarkup(botoes, one_time_keyboard=True, resize_keyboard=True)

def teclado_categorias_gasto() -> ReplyKeyboardMarkup:
    """Retorna teclado com as categorias de gasto."""
    # Hardcoded para UI, alinhado com CATEGORIAS_OPCOES do finance_service
    # Idealmente, importaria as chaves e faria map, mas para UI fixa é ok assim
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

def formatar_mensagem_confirmacao(valor: float, categoria: str, descricao: str) -> str:
    return (
        f"Vou registrar assim:\n\n"
        f"• Valor: R$ {valor:.2f}\n"
        f"• Categoria: {categoria}\n"
        f"• Descrição: {descricao or '-'}\n\n"
        f"Está correto? Você pode confirmar, trocar a categoria ou cancelar."
    )

def formatar_mensagem_sucesso_gasto(
    valor: float, 
    categoria: str, 
    total_cat: float, 
    limite: float, 
    percentual: float
) -> str:
    msg = f"✅ R$ {valor:.2f} em *{categoria.capitalize()}* registrado\n"
    if limite > 0:
        msg += f"📊 {categoria.capitalize()}: R$ {total_cat:.2f} / R$ {limite:.2f} ({percentual:.1f}%)"
        if percentual > 80:
            msg += "\n⚠️ *Atenção:* Você atingiu 80% do orçamento!"
    else:
        msg += f"📊 Total {categoria.capitalize()} este mês: R$ {total_cat:.2f}"
    return msg

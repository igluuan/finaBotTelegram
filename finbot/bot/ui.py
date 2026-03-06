from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

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

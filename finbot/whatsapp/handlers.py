import logging
from .client import WhatsAppClient
from .state import state_manager
from ..bot.services import parser
from ..bot.database import crud
from ..bot.ui import formatar_balanco
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)
client = WhatsAppClient()

# Estados
START = "START"
CONFIRM_EXPENSE = "CONFIRM_EXPENSE"

async def handle_message(message_body):
    # message_body é um objeto BaileysPayload do schema
    user_id = message_body.from_  # Número do WhatsApp
    text = message_body.text.strip()
    name = message_body.name
    
    # Conversão de ID
    try:
        # Remove sufixo se houver (já removido no server.js, mas por segurança)
        clean_id = user_id.replace('@s.whatsapp.net', '')
        db_user_id = int(clean_id)
    except ValueError:
        logger.error(f"User ID inválido: {user_id}")
        return

    # Garante usuário
    user = crud.get_user(db_user_id)
    if not user:
        crud.create_user(db_user_id, name)

    state = state_manager.get_state(user_id)
    cmd = text.lower()

    # --- Comandos Básicos ---
    if cmd in ["oi", "ola", "olá", "ajuda", "menu", "/help", "/start"]:
        msg = (
            f"Olá {name}! Sou o FinBot 💰.\n\n"
            "Posso registrar seus gastos e mostrar relatórios.\n"
            "Exemplos:\n"
            "👉 *'35 uber'* (registra gasto)\n"
            "👉 *'/hoje'* (ver gastos de hoje)\n"
            "👉 *'/mes'* (ver balanço do mês)\n"
            "👉 *'/semana'* (ver gastos da semana)"
        )
        await client.send_message(user_id, msg)
        state_manager.set_state(user_id, START)
        return

    # --- Relatórios ---
    if cmd == "/hoje":
        hoje = datetime.now()
        gastos = crud.get_gastos_periodo(db_user_id, hoje, hoje)
        total = sum(g.valor for g in gastos)
        msg = f"📅 *Gastos de Hoje* ({hoje.strftime('%d/%m')}):\n\n"
        if not gastos:
            msg += "Nenhum gasto registrado."
        else:
            for g in gastos:
                msg += f"• {g.categoria}: R$ {g.valor:.2f} ({g.descricao})\n"
            msg += f"\n🔴 *Total: R$ {total:.2f}*"
        await client.send_message(user_id, msg)
        return

    if cmd == "/mes":
        with crud.get_db() as db:
            total_ganhos = crud.total_ganhos_mes(db, db_user_id)
            total_gastos = crud.total_gastos_mes(db, db_user_id)
            total_parcelas = crud.total_mensal_parcelas(db, db_user_id)
            
        msg = formatar_balanco(total_ganhos, total_gastos, total_parcelas)
        await client.send_message(user_id, msg)
        return

    if state == START:
        # Tenta parsear gasto
        resultado = await parser.parse_gasto(text)
        
        if "erro" not in resultado:
            valor = resultado.get("valor")
            categoria = resultado.get("categoria")
            descricao = resultado.get("descricao", "")
            
            crud.add_gasto(db_user_id, valor, categoria, descricao, metodo="WhatsApp")
            await client.send_message(user_id, f"✅ Gasto registrado:\nR$ {valor:.2f} em {categoria} ({descricao})")
        else:
            await client.send_message(user_id, "❓ Não entendi. Tente algo como '35 uber' ou use /menu.")

    # Implementar mais fluxos conforme necessário

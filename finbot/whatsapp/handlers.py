import logging
from .client import WhatsAppClient
from .state import state_manager
from ..bot.services import parser
from ..bot.database import crud
from ..bot.ui import formatar_balanco
from datetime import date, datetime, timedelta
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
    if cmd in ["oi", "ola", "olá", "ajuda", "menu", "/help", "/start", "/ajuda"]:
        msg = (
            f"Olá {name}! Sou o FinBot 💰.\n\n"
            "Posso registrar seus gastos e mostrar relatórios completos.\n"
            "Aqui está o que posso fazer:\n\n"
            "📝 *Registrar Gastos:*\n"
            "👉 Apenas digite: *'35 uber'* ou *'almoço 20'*\n\n"
            "📊 *Relatórios:*\n"
            "👉 *'/hoje'* - Gastos de hoje\n"
            "👉 *'/semana'* - Gastos da semana\n"
            "👉 *'/mes'* - Balanço do mês\n"
            "👉 *'/categorias'* - Gastos por categoria\n\n"
            "💰 *Ganhos e Parcelas:*\n"
            "👉 (Em breve via WhatsApp, use o Telegram para gestão completa)"
        )
        await client.send_message(user_id, msg)
        state_manager.set_state(user_id, START)
        return

    # --- Relatórios ---
    if cmd == "/hoje":
        hoje = datetime.now().date()
        gastos = crud.get_gastos_periodo(db_user_id, hoje, hoje)
        total = sum(g.valor for g in gastos)
        msg = f"📅 *Gastos de Hoje* ({hoje.strftime('%d/%m')}):\n\n"
        if not gastos:
            msg += "Nenhum gasto registrado."
        else:
            for g in gastos:
                nome = g.descricao if g.descricao else g.categoria.capitalize()
                msg += f"• {nome}: R$ {g.valor:.2f}\n"
            msg += f"\n🔴 *Total: R$ {total:.2f}*"
        await client.send_message(user_id, msg)
        return

    if cmd == "/semana":
        hoje = datetime.now().date()
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        gastos = crud.get_gastos_periodo(db_user_id, inicio_semana, hoje)
        total = sum(g.valor for g in gastos)
        
        msg = f"📅 *Gastos da Semana* ({inicio_semana.strftime('%d/%m')} - {hoje.strftime('%d/%m')}):\n\n"
        if not gastos:
            msg += "Nenhum gasto registrado nesta semana."
        else:
            # Agrupar por categoria para resumo
            cats = {}
            for g in gastos:
                c = g.categoria.capitalize()
                cats[c] = cats.get(c, 0) + g.valor
            
            # Ordenar categorias por valor
            sorted_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)
            
            for cat, val in sorted_cats:
                msg += f"• {cat}: R$ {val:.2f}\n"
                
            msg += f"\n🔴 *Total da Semana: R$ {total:.2f}*"
            
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

    if cmd == "/categorias":
        agora = datetime.now()
        gastos_cat = crud.get_gastos_por_categoria(db_user_id, agora.month, agora.year)
        
        msg = f"📂 *Gastos por Categoria ({agora.strftime('%m/%Y')})*\n\n"
        
        if not gastos_cat:
            msg += "Nenhum gasto registrado neste mês."
        else:
            # Ordenar por valor
            gastos_cat.sort(key=lambda x: x['total'], reverse=True)
            total_mes = sum(item['total'] for item in gastos_cat)
            
            for item in gastos_cat:
                percentual = (item['total'] / total_mes * 100) if total_mes > 0 else 0
                msg += f"• *{item['categoria'].capitalize()}*: R$ {item['total']:.2f} ({percentual:.1f}%)\n"
                
            msg += f"\n🔴 *Total Geral: R$ {total_mes:.2f}*"
            
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
            await client.send_message(user_id, "❓ Não entendi. Tente algo como '35 uber' ou use /menu para ver as opções.")

    # Implementar mais fluxos conforme necessário

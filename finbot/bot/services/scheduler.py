from apscheduler.schedulers.asyncio import AsyncIOScheduler
from ..database import crud
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def diario_job(application):
    from ...config import ALLOWED_USER_ID
    if not ALLOWED_USER_ID:
        return
    try:
        user_id = int(ALLOWED_USER_ID)
        hoje = datetime.now().date()
        gastos = crud.get_gastos_periodo(user_id, hoje, hoje)
        total = sum(g.valor for g in gastos)
        if total > 0:
            msg = f"🔔 *Resumo do Dia*\n\nVocê gastou R$ {total:.2f} hoje.\n"
            for g in gastos:
                msg += f"- {g.categoria}: R$ {g.valor:.2f}\n"
            await application.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no job diário: {e}")

async def semanal_job(application):
    from ...config import ALLOWED_USER_ID
    if not ALLOWED_USER_ID:
        return
    try:
        user_id = int(ALLOWED_USER_ID)
        msg = "📅 *Relatório Semanal*\n\nConfira seus gastos da semana com /semana"
        await application.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no job semanal: {e}")

async def mensal_job(application):
    from ...config import ALLOWED_USER_ID
    if not ALLOWED_USER_ID:
        return
    try:
        user_id = int(ALLOWED_USER_ID)
        msg = "📅 *Relatório Mensal*\n\nO mês virou! Confira o fechamento com /mes e peça uma /dica para o próximo mês."
        await application.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no job mensal: {e}")

async def alertar_vencimentos(application):
    hoje = datetime.now().date()
    try:
        with crud.get_db() as db:
            parcelas = db.query(crud.Parcela).filter(
                crud.Parcela.quitada == False
            ).all()
        usuarios = {}
        for p in parcelas:
            vencimento = date(hoje.year, hoje.month, min(p.dia_vencimento, 28))
            diff = (vencimento - hoje).days
            if 1 <= diff <= 3:
                usuarios.setdefault(p.user_id, []).append((p, diff))
        for user_id, items in usuarios.items():
            linhas = ["⏰ *Parcelas vencendo em breve:*\n"]
            for p, diff in items:
                linhas.append(
                    f"• {p.descricao} (**** {p.cartao_final})\n"
                    f"  R$ {p.valor_parcela:.2f} — vence em {diff} dia(s)"
                )
            await application.bot.send_message(
                chat_id=user_id,
                text="\n".join(linhas),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Erro no job de alertas: {e}")

async def lembrar_ganhos_recorrentes(application):
    hoje = date.today()
    try:
        with crud.get_db() as db:
            ganhos_recorrentes = db.query(crud.Ganho).filter(
                crud.Ganho.recorrente == True,
                crud.Ganho.dia_recebimento == hoje.day
            ).all()
            for g in ganhos_recorrentes:
                ja_lancado = db.query(crud.Ganho).filter(
                    crud.Ganho.user_id == g.user_id,
                    crud.Ganho.descricao == g.descricao,
                    crud.Ganho.data >= hoje.replace(day=1)
                ).count() > 1
                if not ja_lancado:
                    await application.bot.send_message(
                        chat_id=g.user_id,
                        text=f"💵 Lembrete: hoje é dia {hoje.day}, "
                             f"você costuma receber *{g.descricao}* (R$ {g.valor:.2f}).\n"
                             f"Já recebeu? Use /add_ganho para registrar.",
                        parse_mode="Markdown"
                    )
    except Exception as e:
        logger.error(f"Erro no job de ganhos recorrentes: {e}")

def start_scheduler(application):
    scheduler.add_job(diario_job, 'cron', hour=21, minute=0, args=[application])
    scheduler.add_job(semanal_job, 'cron', day_of_week='mon', hour=8, minute=0, args=[application])
    scheduler.add_job(mensal_job, 'cron', day=1, hour=9, minute=0, args=[application])
    scheduler.add_job(alertar_vencimentos, 'cron', hour=9, minute=0, args=[application])
    scheduler.add_job(lembrar_ganhos_recorrentes, 'cron', hour=8, minute=0, args=[application])
    scheduler.start()

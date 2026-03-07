from typing import Dict, Any, List, Optional
import logging
import asyncio
from dataclasses import dataclass
from datetime import date

from finbot.core.conversation.state import conversation_state_manager, ConversationState
from finbot.services.ai_service import interpret_message, answer_natural
from finbot.services import parser_service, finance_service
from finbot.database.connection import get_db
from finbot.database.repositories.expense_repository import ExpenseRepository
from finbot.database.repositories.earning_repository import EarningRepository
from finbot.database.repositories.installment_repository import InstallmentRepository

logger = logging.getLogger(__name__)

@dataclass
class ConversationResponse:
    text: str
    suggestions: List[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    action: str = None  # e.g., 'SAVE_EXPENSE', 'SHOW_REPORT'

class ConversationManager:
    async def handle_message(self, user_id: str, message: str) -> ConversationResponse:
        state = conversation_state_manager.get_state(user_id)
        
        # Add user message to history
        state.add_message("user", message)
        
        # Interpret intent with context
        intent_data = await interpret_message(message, state.history)
        intent_type = intent_data.get("type", "unknown")
        
        logger.info(f"User: {user_id}, State: {state.state}, Intent: {intent_type}, Data: {intent_data}")

        response = await self._process_intent(user_id, state, intent_data, message)
        
        # Add assistant response to history
        state.add_message("assistant", response.text)
        
        return response

    async def _process_intent(self, user_id: str, state: ConversationState, intent_data: dict, original_message: str) -> ConversationResponse:
        intent_type = intent_data.get("type")
        
        # Handle cancellations
        if intent_type == 'cancellation':
            conversation_state_manager.set_state(user_id, "START")
            state.clear_draft()
            return ConversationResponse(
                text="Cancelado. O que deseja fazer agora? 👌",
                suggestions=["Adicionar despesa", "Ver saldo", "Relatório mensal"]
            )

        # Handle confirmations (if waiting for one)
        if state.state == "WAITING_CONFIRMATION":
            if intent_type == 'confirmation' or (intent_type == 'unknown' and original_message.lower() in ['sim', 's', 'ok', 'confirmar', 'yes', '✅']):
                return await self._execute_transaction(user_id, state)
            elif intent_type in ['expense', 'income', 'installment']:
                # User corrected data instead of just confirming
                state.update_draft(intent_data)
                return self._generate_confirmation_request(state.transaction_draft)
            else:
                 # Assume correction or new command
                if intent_data.get("value") or intent_data.get("category"):
                     state.update_draft(intent_data)
                     return self._generate_confirmation_request(state.transaction_draft)

        # Start new transaction flow
        if intent_type in ['expense', 'income', 'installment']:
            conversation_state_manager.set_state(user_id, "WAITING_CONFIRMATION")
            state.clear_draft()
            state.update_draft(intent_data)
            
            # Check for missing required fields
            if not intent_data.get("category") and intent_type == 'expense':
                 conversation_state_manager.set_state(user_id, "WAITING_CATEGORY")
                 return ConversationResponse(
                     text="Qual a categoria dessa despesa?",
                     suggestions=["Alimentação", "Transporte", "Lazer", "Casa", "Outros"]
                 )
            
            return self._generate_confirmation_request(state.transaction_draft)
            
        # Handle category answer
        if state.state == "WAITING_CATEGORY":
            category = intent_data.get("category") or original_message
            # Map common category names if needed
            mapped_category = finance_service.get_category_key(category) or category
            
            state.update_draft({"category": mapped_category})
            conversation_state_manager.set_state(user_id, "WAITING_CONFIRMATION")
            return self._generate_confirmation_request(state.transaction_draft)

        # Handle reports and balance
        if intent_type in ['balance', 'report']:
            return ConversationResponse(
                text="Gerando relatório... 📊", 
                action="GENERATE_REPORT", 
                structured_data=intent_data
            )

        # Handle general questions
        if intent_type == 'question':
            answer = await answer_natural(original_message, {})
            return ConversationResponse(text=answer)

        # Fallback / Unknown
        return ConversationResponse(
            text="Não entendi bem. Tente algo como 'Gastei 50 no almoço' ou 'Uber 20'.",
            suggestions=["Adicionar despesa", "Ver saldo"]
        )

    def _generate_confirmation_request(self, data: dict) -> ConversationResponse:
        t_type_map = {
            "expense": "Despesa",
            "income": "Receita",
            "installment": "Parcelamento"
        }
        t_type = t_type_map.get(data.get("type"), "Transação")
            
        val = data.get("value", 0)
        cat = data.get("category", "Geral")
        desc = data.get("description", "")
        date_str = data.get("date", "Hoje")
        
        msg = (
            f"Entendi assim:\n\n"
            f"📝 **Tipo:** {t_type}\n"
            f"💰 **Valor:** R$ {val}\n"
            f"🏷️ **Categoria:** {cat}\n"
            f"📅 **Data:** {date_str}\n"
        )
        if desc:
            msg += f"ℹ️ **Descrição:** {desc}\n"
            
        msg += "\nConfirma? ✅"
        
        return ConversationResponse(
            text=msg,
            suggestions=["Confirmar ✅", "Editar ✏️", "Cancelar ❌"]
        )

    async def _execute_transaction(self, user_id: str, state: ConversationState) -> ConversationResponse:
        data = state.transaction_draft
        
        # Parse date
        date_str = data.get("date", "hoje")
        parsed_date = parser_service.parse_user_date(date_str, today=date.today()) or date.today()
        
        try:
            # Execute in thread to avoid blocking loop with sync DB calls
            await asyncio.to_thread(self._save_to_db, user_id, data, parsed_date)
            
            # Reset state
            conversation_state_manager.set_state(user_id, "START")
            state.clear_draft()
            
            return ConversationResponse(
                text="Salvo com sucesso! ✅",
                action="SAVE_TRANSACTION",
                structured_data=data,
                suggestions=["Adicionar outro", "Ver saldo", "Relatório"]
            )
        except Exception as e:
            logger.error(f"Error saving transaction: {e}")
            return ConversationResponse(
                text="Ocorreu um erro ao salvar. Tente novamente.",
                suggestions=["Tentar novamente", "Cancelar"]
            )

    def _save_to_db(self, user_id: str, data: dict, date_record: date):
        with get_db() as db:
            try:
                uid = int(user_id)
            except ValueError:
                # Fallback for testing with string IDs, assuming mapped or using default
                uid = 1 
                
            if data.get("type") == "expense":
                ExpenseRepository.create(
                    db,
                    uid,
                    float(data.get("value", 0)),
                    data.get("category", "Outros"),
                    data.get("description", ""),
                    payment_method=data.get("payment_method", "Outros"),
                    date_record=date_record
                )
            elif data.get("type") == "income":
                 # Prepare data for EarningRepository
                 earning_data = {
                     "amount": float(data.get("value", 0)),
                     "category": data.get("category", "Outros"),
                     "description": data.get("description", "Receita"),
                     "date": date_record
                 }
                 EarningRepository.create(db, uid, earning_data)
                 
            elif data.get("type") == "installment":
                # Prepare data for InstallmentRepository
                # Missing fields will need defaults
                inst_data = {
                    "total_amount": float(data.get("value", 0)),
                    "total_installments": int(data.get("installment_count", 1)),
                    "description": data.get("description", "Parcelamento"),
                    "card_last_digits": "0000", # Default or ask user?
                    "current_installment": 1,
                    "due_day": date_record.day,
                    "category": data.get("category", "Outros")
                }
                InstallmentRepository.create(db, uid, inst_data)

conversation_manager = ConversationManager()

from typing import Dict, Any, List, Optional
import logging
import asyncio
import re
from dataclasses import dataclass
from datetime import date

from finbot.core.conversation.state import conversation_state_manager, ConversationState
from finbot.services.ai_service import NATURAL_LANGUAGE_EXAMPLES, interpret_message, answer_natural
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

    def _is_confirmation_text(self, message: str) -> bool:
        lowered = (message or "").strip().lower()
        return lowered in {"sim", "s", "ok", "confirmar", "confirma", "yes", "✅", "pode confirmar", "pode"}

    def _is_edit_text(self, message: str) -> bool:
        lowered = (message or "").strip().lower()
        return any(token in lowered for token in ["editar", "edita", "corrigir", "corrige", "ajustar", "ajusta", "mudar", "altera"])

    def _is_negative_confirmation_text(self, message: str) -> bool:
        lowered = (message or "").strip().lower()
        return lowered in {"nao", "não", "n", "não", "cancelar", "desistir"}

    def _extract_number(self, text: str) -> float | None:
        match = re.search(r"(\d+[\.,]\d+|\d+)", text or "")
        if not match:
            return None
        return float(match.group(1).replace(",", "."))

    def _extract_installment_count(self, text: str) -> int | None:
        match = re.search(r"(\d+)\s*x\b", (text or "").lower())
        if match:
            return int(match.group(1))

        match = re.search(r"(\d+)", text or "")
        if match:
            return int(match.group(1))
        return None

    def _normalize_category(self, category: str | None) -> str | None:
        if not category:
            return None

        cleaned = category.strip()
        mapped = finance_service.get_category_key(cleaned)
        if mapped:
            return mapped

        aliases = {
            "alimentacao": "alimentacao",
            "alimentação": "alimentacao",
            "comida": "alimentacao",
            "transporte": "transporte",
            "uber": "transporte",
            "mercado": "mercado",
            "casa": "moradia",
            "moradia": "moradia",
            "saude": "saude",
            "saúde": "saude",
            "lazer": "lazer",
            "educacao": "educacao",
            "educação": "educacao",
            "assinaturas": "assinaturas",
            "outros": "outros",
        }
        return aliases.get(cleaned.lower(), cleaned.lower())

    def _required_fields(self, data: dict) -> list[str]:
        transaction_type = data.get("type")
        if transaction_type == "expense":
            required = ["value", "category"]
        elif transaction_type == "income":
            required = ["value"]
        elif transaction_type == "installment":
            required = ["value", "installment_count"]
        else:
            return []

        return [field for field in required if not data.get(field)]

    def _next_missing_response(self, state: ConversationState) -> ConversationResponse | None:
        missing_fields = self._required_fields(state.transaction_draft)
        if not missing_fields:
            return None

        first_missing = missing_fields[0]
        if first_missing == "value":
            conversation_state_manager.set_state(state.user_id, "WAITING_AMOUNT")
            label = "desse gasto" if state.transaction_draft.get("type") == "expense" else "dessa receita"
            if state.transaction_draft.get("type") == "installment":
                label = "desse parcelamento"
            return ConversationResponse(text=f"Faltou só o valor {label}. Quanto foi?")

        if first_missing == "category":
            conversation_state_manager.set_state(state.user_id, "WAITING_CATEGORY")
            return ConversationResponse(
                text="Qual categoria dessa despesa?",
                suggestions=["Alimentação", "Transporte", "Mercado", "Moradia", "Outros"],
            )

        if first_missing == "installment_count":
            conversation_state_manager.set_state(state.user_id, "WAITING_INSTALLMENT_COUNT")
            return ConversationResponse(text="Em quantas parcelas foi?")

        return None

    def _merge_user_correction(self, state: ConversationState, intent_data: dict, original_message: str) -> None:
        patch_data: dict[str, Any] = {}

        if intent_data.get("type") in {"expense", "income", "installment"}:
            patch_data["type"] = intent_data["type"]

        if intent_data.get("value") is not None:
            patch_data["value"] = intent_data["value"]
        elif state.state == "WAITING_AMOUNT":
            extracted = self._extract_number(original_message)
            if extracted is not None:
                patch_data["value"] = extracted

        if intent_data.get("category"):
            patch_data["category"] = self._normalize_category(intent_data["category"])
        elif state.state == "WAITING_CATEGORY":
            patch_data["category"] = self._normalize_category(original_message)

        if intent_data.get("description"):
            patch_data["description"] = intent_data["description"]

        if intent_data.get("date"):
            patch_data["date"] = intent_data["date"]

        if intent_data.get("installment_count"):
            patch_data["installment_count"] = intent_data["installment_count"]
        elif state.state == "WAITING_INSTALLMENT_COUNT":
            installment_count = self._extract_installment_count(original_message)
            if installment_count:
                patch_data["installment_count"] = installment_count

        if patch_data:
            state.update_draft(patch_data)

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
            if intent_type == 'confirmation' or (intent_type == 'unknown' and self._is_confirmation_text(original_message)):
                return await self._execute_transaction(user_id, state)
            if intent_type == 'cancellation' or self._is_negative_confirmation_text(original_message):
                conversation_state_manager.set_state(user_id, "START")
                state.clear_draft()
                return ConversationResponse(
                    text="Cancelado. Precisa de outra coisa?", suggestions=["Adicionar despesa", "Ver saldo"], action="CANCEL_TRANSACTION"
                )
            if self._is_edit_text(original_message) and not any(intent_data.get(field) for field in ["value", "category", "installment_count"]):
                return ConversationResponse(
                    text="Me diga só o que quer mudar. Exemplo: 'foi 52', 'categoria mercado' ou '3x'."
                )

            self._merge_user_correction(state, intent_data, original_message)
            next_step = self._next_missing_response(state)
            if next_step:
                return next_step
            if state.transaction_draft:
                conversation_state_manager.set_state(user_id, "WAITING_CONFIRMATION")
                return self._generate_confirmation_request(state.transaction_draft)

        # Start new transaction flow
        if intent_type in ['expense', 'income', 'installment']:
            conversation_state_manager.set_state(user_id, "WAITING_CONFIRMATION")
            state.clear_draft()
            draft = dict(intent_data)
            if draft.get("category"):
                draft["category"] = self._normalize_category(draft["category"])
            state.update_draft(draft)

            next_step = self._next_missing_response(state)
            if next_step:
                return next_step
            return self._generate_confirmation_request(state.transaction_draft)
            
        if state.state in {"WAITING_AMOUNT", "WAITING_CATEGORY", "WAITING_INSTALLMENT_COUNT"}:
            self._merge_user_correction(state, intent_data, original_message)
            next_step = self._next_missing_response(state)
            if next_step:
                return next_step
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
            return ConversationResponse(text=answer, suggestions=["Gastei 40 no uber", "Recebi 2500", "Quanto gastei essa semana?"])

        # Fallback / Unknown
        return ConversationResponse(
            text="Não entendi bem. Tente algo como 'Gastei 50 no almoço' ou 'Uber 20'.",
            suggestions=NATURAL_LANGUAGE_EXAMPLES[:3]
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
            f"Confere isso?\n"
            f"Tipo: {t_type}\n"
            f"Valor: R$ {val}\n"
            f"Categoria: {cat}\n"
            f"Data: {date_str}\n"
        )
        if desc:
            msg += f"Descrição: {desc}\n"
            
        msg += "\nResponda 'sim' para confirmar ou 'não' para cancelar."
        
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
            
            saved_type = data.get("type", "transação")
            saved_value = float(data.get("value", 0))
            saved_description = data.get("description") or data.get("category", "outros")

            return ConversationResponse(
                text=f"Salvei {saved_type} de R$ {saved_value:.2f} em {saved_description}.",
                action="SAVE_TRANSACTION",
                structured_data=data,
                suggestions=["Adicionar outro", "Quanto gastei essa semana?", "Resumo do mês"]
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

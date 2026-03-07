import pytest

from finbot.core.conversation.manager import conversation_manager
from finbot.core.conversation.state import conversation_state_manager
from finbot.services.ai_service import _fallback_interpret_message


@pytest.fixture(autouse=True)
def clear_state():
    conversation_state_manager._store.clear()
    yield
    conversation_state_manager._store.clear()


@pytest.mark.asyncio
async def test_expense_without_amount_prompts_for_value(monkeypatch):
    async def fake_interpret(message, history=None):
        return {"type": "expense", "value": None, "category": "moradia", "description": "aluguel", "date": "hoje"}

    monkeypatch.setattr("finbot.core.conversation.manager.interpret_message", fake_interpret)

    response = await conversation_manager.handle_message("1", "paguei aluguel hoje")

    assert "Quanto foi?" in response.text
    assert conversation_state_manager.get_state("1").state == "WAITING_AMOUNT"


@pytest.mark.asyncio
async def test_waiting_amount_accepts_numeric_correction(monkeypatch):
    responses = [
        {"type": "expense", "value": None, "category": "moradia", "description": "aluguel", "date": "hoje"},
        {"type": "unknown"},
    ]

    async def fake_interpret(message, history=None):
        return responses.pop(0)

    monkeypatch.setattr("finbot.core.conversation.manager.interpret_message", fake_interpret)

    first = await conversation_manager.handle_message("1", "paguei aluguel hoje")
    second = await conversation_manager.handle_message("1", "1200")

    assert "Quanto foi?" in first.text
    assert "Confere isso?" in second.text
    assert "1200.0" in second.text or "1200" in second.text


@pytest.mark.asyncio
async def test_question_uses_local_help_when_ai_returns_empty(monkeypatch):
    async def fake_interpret(message, history=None):
        return {"type": "question", "question_text": "ajuda"}

    async def fake_answer(message, context):
        return "Posso registrar gastos, receitas e consultas."

    monkeypatch.setattr("finbot.core.conversation.manager.interpret_message", fake_interpret)
    monkeypatch.setattr("finbot.core.conversation.manager.answer_natural", fake_answer)

    response = await conversation_manager.handle_message("1", "ajuda")

    assert "registrar gastos" in response.text
    assert response.suggestions


def test_fallback_detects_category_balance_query():
    result = _fallback_interpret_message("quanto gastei com mercado essa semana")

    assert result["type"] == "balance"
    assert result["category"] == "mercado"
    assert result["period"] == "week"


def test_fallback_detects_income_balance_query():
    result = _fallback_interpret_message("quanto recebi esse mês")

    assert result["type"] == "balance"
    assert result["metric"] == "income"
    assert result["period"] == "month"

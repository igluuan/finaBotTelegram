from finbot.whatsapp.handlers import _safe_report


def test_safe_report_uses_category_period_report(monkeypatch):
    monkeypatch.setattr(
        "finbot.whatsapp.handlers.ReportService.get_category_period_report",
        lambda user_id, category, period: f"category:{user_id}:{category}:{period}",
    )

    result = _safe_report(
        7,
        "quanto gastei com mercado essa semana",
        {"category": "mercado", "period": "week"},
    )

    assert result == "category:7:mercado:week"


def test_safe_report_uses_income_period_report(monkeypatch):
    monkeypatch.setattr(
        "finbot.whatsapp.handlers.ReportService.get_income_period_report",
        lambda user_id, period: f"income:{user_id}:{period}",
    )

    result = _safe_report(
        9,
        "quanto recebi esse mês",
        {"metric": "income", "period": "month"},
    )

    assert result == "income:9:month"

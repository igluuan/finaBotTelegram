import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from finbot.whatsapp.client import WhatsAppClient
from finbot.whatsapp.state import StateManager

@pytest.fixture
def mock_httpx(mocker):
    return mocker.patch("httpx.AsyncClient")

@pytest.mark.asyncio
async def test_send_message(mock_httpx):
    client = WhatsAppClient()
    # No Baileys client, token e phone_id não são usados no Python
    
    mock_post = AsyncMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"success": True}
    
    # Configure o retorno do contexto __aenter__ para ser o mock_instance que tem o método post
    mock_instance = AsyncMock()
    mock_instance.post = mock_post
    mock_httpx.return_value.__aenter__.return_value = mock_instance

    response = await client.send_message("55119999", "Teste")
    
    # Ensure response is awaited if it's a coroutine
    if hasattr(response, '__await__'):
        response = await response
        
    assert response == {"success": True}
    
    # Verifica se a URL chamada foi a do serviço local Baileys
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:3000/send-message"
    assert kwargs['json'] == {"to": "55119999", "text": "Teste"}

def test_state_manager():
    sm = StateManager()
    user = "user1"
    
    assert sm.get_state(user) == "START"
    
    sm.set_state(user, "PROCESSANDO")
    assert sm.get_state(user) == "PROCESSANDO"
    
    sm.update_data(user, {"valor": 10})
    data = sm.get_data(user)
    assert data["valor"] == 10
    
    sm.clear_user(user)
    assert sm.get_state(user) == "START"

from pydantic import BaseModel, Field

class WhatsAppPayload(BaseModel):
    from_: str = Field(..., alias="from")
    text: str
    name: str = "Usuário"

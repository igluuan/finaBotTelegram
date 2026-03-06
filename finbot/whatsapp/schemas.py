from pydantic import BaseModel, Field

class BaileysPayload(BaseModel):
    from_: str = Field(..., alias="from")
    text: str
    name: str = "Usuário"

from pydantic import BaseModel, Field, ConfigDict


class BaileysPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    from_: str = Field(..., alias="from", min_length=8)
    reply_to: str | None = None
    text: str = Field(..., min_length=1)
    name: str = "Usuario"
    message_id: str | None = None
    timestamp: int | None = None

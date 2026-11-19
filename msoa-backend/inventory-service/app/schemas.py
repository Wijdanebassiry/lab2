from pydantic import BaseModel, Field, field_validator


class Item(BaseModel):
    productId: str
    quantity: int = Field(gt=0)

    @field_validator("productId", mode="before")
    @classmethod
    def to_str(cls, v):
        # accept 1 or "1" from the frontend
        return str(v)


class ItemsRequest(BaseModel):
    items: list[Item] = Field(min_length=1)
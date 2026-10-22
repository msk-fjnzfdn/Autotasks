from pydantic import BaseModel, Field
from datetime import datetime


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)


class UserRead(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class BlockCreate(BaseModel):
    type: str
    name: str = Field(min_length=1, max_length=100)
    params: dict = {}
    position: int = 0


class BlockUpdate(BaseModel):
    name: str | None = None
    params: dict | None = None
    position: int | None = None


class BlockRead(BlockCreate):
    id: int

    class Config:
        from_attributes = True


class RunRead(BaseModel):
    id: int
    chain_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    logs: list

    class Config:
        from_attributes = True


class BlockTestIn(BaseModel):
    input: dict = {}

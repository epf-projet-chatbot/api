from pydantic import BaseModel, EmailStr

class TemplateCreate(BaseModel):
    attr1: str
    attr2: EmailStr
    attr3: str
    attr4: int
    attr5: float

class TemplateResponse(TemplateCreate):
    id: str

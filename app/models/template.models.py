from typing import Optional, Any

from beanie import Document
from pydantic import BaseModel, EmailStr


class Template(Document):
    attr1: str
    attr2: EmailStr
    attr3: str
    attr4: int
    attr5: float

    class Config:
        json_schema_extra = {
            "example": {
                "attr1": "Abdulazeez Abdulazeez Adeshina",
                "attr2": "abdul@school.com",
                "attr3": "Water resources engineering",
                "attr4": 4,
                "attr5": "3.76",
            }
        }

    class Settings:
        name = "template"
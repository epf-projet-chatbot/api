from beanie import Document
from pydantic import Field, HttpUrl, BaseModel
from typing import Optional, List
from datetime import datetime
from beanie import PydanticObjectId

class Attachment(BaseModel):
    filename: str
    url: HttpUrl

class Message(Document):
    id: Optional[PydanticObjectId] = Field(None, alias="_id")
    discussion_id: PydanticObjectId = Field(...)
    content: str = Field(...)
    date_created: datetime = Field(default_factory=datetime.utcnow)
    attachments: Optional[List[Attachment]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "60d5ec49f8d2e4b8b4e7b8c0",
                "discussion_id": "60d5ec49f8d2e4b8b4e7b8c2",
                "content": "Bonjour, comment ça va ?",
                "date_created": "2023-10-01T12:00:00Z",
                "attachments": [
                    {
                        "filename": "image.png",
                        "url": "https://example.com/image.png"
                    }
                ],
            }
        }

    class Settings:
        name = "message"
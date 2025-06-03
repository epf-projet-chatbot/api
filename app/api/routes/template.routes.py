from fastapi import APIRouter, HTTPException
from typing import List

from controllers import template_controller
from schemas.template_schema import TemplateCreate, TemplateResponse

router = APIRouter(
    prefix="/templates",
    tags=["Templates"]
)

@router.post("/", response_model=TemplateResponse)
async def create_template(data: TemplateCreate):
    return await template_controller.create_template(data)

@router.get("/", response_model=List[TemplateResponse])
async def list_templates():
    return await template_controller.get_all_templates()

@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    template = await template_controller.get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.delete("/{template_id}")
async def delete_template(template_id: str):
    success = await template_controller.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"detail": "Deleted successfully"}

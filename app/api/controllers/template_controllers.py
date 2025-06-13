from models.template_model import Template
from schemas.template_schema import TemplateCreate
from typing import List

async def create_template(data: TemplateCreate) -> Template:
    template = Template(**data.dict())
    await template.insert()
    return template

async def get_all_templates() -> List[Template]:
    return await Template.find_all().to_list()

async def get_template_by_id(template_id: str) -> Template | None:
    return await Template.get(template_id)

async def delete_template(template_id: str) -> bool:
    template = await Template.get(template_id)
    if template:
        await template.delete()
        return True
    return False
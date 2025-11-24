"""
Service pour la gestion des templates (logique métier)
"""
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from api.repositories.template_repository import TemplateRepository


class TemplateService:
    """Service contenant la logique métier pour les templates"""
    
    def __init__(self, template_repo: TemplateRepository):
        self.template_repo = template_repo
    
    async def create_template(self, template_data: dict) -> Dict[str, Any]:
        """
        Créer un nouveau template
        Logique métier: validation des données
        """

        if "name" in template_data:
            existing = await self.template_repo.find_by_name(template_data["name"])
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Template with name '{template_data['name']}' already exists"
                )
        
        template = await self.template_repo.create(template_data)
        return template
    
    async def get_template_by_id(self, template_id: str) -> Dict[str, Any]:
        """Récupérer un template par ID"""
        template = await self.template_repo.get_by_id(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with id {template_id} not found"
            )
        return template
    
    async def get_all_templates(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Récupérer tous les templates"""
        templates = await self.template_repo.get_all(skip=skip, limit=limit)
        return templates
    
    async def update_template(
        self, 
        template_id: str, 
        template_data: dict
    ) -> Dict[str, Any]:
        """
        Mettre à jour un template
        Logique métier: vérifier que le template existe
        """

        existing = await self.template_repo.get_by_id(template_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with id {template_id} not found"
            )
        

        updated = await self.template_repo.update(template_id, template_data)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update template"
            )
        
        return updated
    
    async def delete_template(self, template_id: str) -> bool:
        """Supprimer un template"""

        existing = await self.template_repo.get_by_id(template_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with id {template_id} not found"
            )
        
        success = await self.template_repo.delete(template_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete template"
            )
        
        return True
    
    async def find_template_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Trouver un template par nom"""
        template = await self.template_repo.find_by_name(name)
        return template

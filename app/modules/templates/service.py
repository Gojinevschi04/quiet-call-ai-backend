from collections.abc import Sequence
from typing import Annotated

from fastapi import Depends

from app.core.logging import get_logger
from app.modules.templates.exceptions import TemplateNameExistsError, TemplateNotFoundError
from app.modules.templates.models import DialogTemplate
from app.modules.templates.repository import TemplateRepository
from app.modules.templates.schema import TemplateCreate, TemplateUpdate

logger = get_logger(__name__)


class TemplateService:
    def __init__(
        self,
        template_repository: Annotated[TemplateRepository, Depends(TemplateRepository)],
    ) -> None:
        self.template_repository = template_repository

    async def create_template(self, data: TemplateCreate) -> DialogTemplate:
        existing = await self.template_repository.get_by_name(data.name)
        if existing:
            raise TemplateNameExistsError(f"Template with name '{data.name}' already exists")

        template = DialogTemplate(
            name=data.name,
            base_script=data.base_script,
            required_slots=data.required_slots,
            language=data.language,
        )
        return await self.template_repository.create(template)

    async def get_template(self, template_id: int) -> DialogTemplate:
        template = await self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template with id {template_id} not found")
        return template

    async def get_templates(
        self,
        limit: int = 50,
        offset: int = 0,
        include_inactive: bool = False,
    ) -> Sequence[DialogTemplate]:
        templates, _ = await self.template_repository.get_all_paginated(
            limit, offset, include_inactive=include_inactive
        )
        return templates

    async def update_template(self, template_id: int, data: TemplateUpdate) -> DialogTemplate:
        template = await self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template with id {template_id} not found")

        if data.name is not None:
            existing = await self.template_repository.get_by_name(data.name)
            if existing and existing.id != template_id:
                raise TemplateNameExistsError(f"Template with name '{data.name}' already exists")
            template.name = data.name
        if data.base_script is not None:
            template.base_script = data.base_script
        if data.required_slots is not None:
            template.required_slots = data.required_slots

        return await self.template_repository.update(template)

    async def delete_template(self, template_id: int) -> bool:
        template = await self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template with id {template_id} not found")
        if not template.is_active:
            raise TemplateNotFoundError(f"Template with id {template_id} not found")
        return await self.template_repository.deactivate(template_id)

    async def restore_template(self, template_id: int) -> bool:
        """Re-activate a soft-deleted template so it appears again in the catalog."""
        template = await self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template with id {template_id} not found")
        if template.is_active:
            return False
        return await self.template_repository.restore(template_id)

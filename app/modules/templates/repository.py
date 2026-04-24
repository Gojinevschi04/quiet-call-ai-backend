from collections.abc import Sequence

from sqlmodel import func, select

from app.core.repositories import Repository
from app.modules.templates.models import DialogTemplate


class TemplateRepository(Repository):
    async def create(self, template: DialogTemplate) -> DialogTemplate:
        self._session.add(template)
        await self._session.commit()
        await self._session.refresh(template)
        return template

    async def get_by_id(self, template_id: int) -> DialogTemplate | None:
        result = await self._session.exec(select(DialogTemplate).where(DialogTemplate.id == template_id))
        return result.first()

    async def get_by_name(self, name: str) -> DialogTemplate | None:
        result = await self._session.exec(
            select(DialogTemplate).where(DialogTemplate.name == name, DialogTemplate.is_active.is_(True))
        )
        return result.first()

    async def get_names_by_ids(self, template_ids: set[int]) -> dict[int, str]:
        """Batch-fetch template names for a set of ids — returns {id: name}."""
        if not template_ids:
            return {}
        result = await self._session.exec(
            select(DialogTemplate.id, DialogTemplate.name).where(DialogTemplate.id.in_(template_ids))
        )
        return {template_id: template_name for template_id, template_name in result.all()}

    async def get_all(self) -> Sequence[DialogTemplate]:
        result = await self._session.exec(
            select(DialogTemplate).where(DialogTemplate.is_active.is_(True)).order_by(DialogTemplate.name)
        )
        return result.all()

    async def get_all_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        include_inactive: bool = False,
    ) -> tuple[Sequence[DialogTemplate], int]:
        query = select(DialogTemplate).order_by(DialogTemplate.name).offset(offset).limit(limit)
        count_query = select(func.count()).select_from(DialogTemplate)
        if not include_inactive:
            query = query.where(DialogTemplate.is_active.is_(True))
            count_query = count_query.where(DialogTemplate.is_active.is_(True))

        result = await self._session.exec(query)
        templates = result.all()
        count_result = await self._session.exec(count_query)
        total = count_result.one()

        return templates, total

    async def update(self, template: DialogTemplate) -> DialogTemplate:
        await self._session.commit()
        await self._session.refresh(template)
        return template

    async def deactivate(self, template_id: int) -> bool:
        template = await self.get_by_id(template_id)
        if not template:
            return False
        template.is_active = False
        await self._session.commit()
        await self._session.refresh(template)
        return True

    async def restore(self, template_id: int) -> bool:
        """Re-activate a soft-deleted template (opposite of deactivate)."""
        template = await self.get_by_id(template_id)
        if not template or template.is_active:
            return False
        template.is_active = True
        await self._session.commit()
        await self._session.refresh(template)
        return True

    async def delete(self, template_id: int) -> bool:
        template = await self.get_by_id(template_id)
        if not template:
            return False
        await self._session.delete(template)
        await self._session.commit()
        return True

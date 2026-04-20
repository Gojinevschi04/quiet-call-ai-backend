from collections.abc import Sequence

from sqlmodel import select

from app.core.repositories import Repository
from app.modules.files.models import File


class FileRepository(Repository):
    async def create(self, file_record: File) -> File:
        self._session.add(file_record)
        await self._session.commit()
        await self._session.refresh(file_record)
        return file_record

    async def get_by_id(self, file_id: int, user_id: int) -> File | None:
        result = await self._session.exec(select(File).where(File.id == file_id, File.user_id == user_id))
        return result.first()

    async def get_by_hash(self, content_hash: str, user_id: int) -> File | None:
        result = await self._session.exec(
            select(File).where(File.content_hash == content_hash, File.user_id == user_id)
        )
        return result.first()

    async def update(self, file_record: File) -> File:
        await self._session.commit()
        await self._session.refresh(file_record)
        return file_record

    async def delete(self, file_id: int, user_id: int) -> bool:
        file_record = await self.get_by_id(file_id, user_id)
        if not file_record:
            return False

        await self._session.delete(file_record)
        await self._session.commit()
        return True

    async def get_all_by_user(self, user_id: int) -> Sequence[File]:
        result = await self._session.exec(select(File).where(File.user_id == user_id))
        return result.all()

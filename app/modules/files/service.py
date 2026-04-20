import hashlib
import mimetypes
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import Depends

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.files.exceptions import UnsupportedFileTypeError
from app.modules.files.models import File
from app.modules.files.repository import FileRepository
from app.modules.files.schema import FileContentResponse, FileType
from app.modules.users.repository import UserRepository

logger = get_logger(__name__)


class FileService:
    def __init__(
        self,
        file_repository: Annotated[FileRepository, Depends(FileRepository)],
        user_repository: Annotated[UserRepository, Depends(UserRepository)],
    ) -> None:
        self.file_repository = file_repository
        self.user_repository = user_repository
        self.upload_dir = settings.STORAGE_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file_content: bytes, filename: str, user_id: int) -> File:
        file_type = self._get_file_type(filename)
        content_hash = hashlib.sha256(file_content).hexdigest()

        existing_file = await self.file_repository.get_by_hash(content_hash, user_id)
        if existing_file:
            return existing_file

        file_extension = Path(filename).suffix
        uuid_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = self.upload_dir / uuid_filename

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)

        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User does not exist")

        file_record = File(
            filename=uuid_filename,
            original_filename=filename,
            file_path=str(file_path),
            file_size=len(file_content),
            file_type=file_type,
            user_id=user_id,
            content_hash=content_hash,
        )

        return await self.file_repository.create(file_record)

    async def get_file(self, file_id: int, user_id: int) -> File | None:
        return await self.file_repository.get_by_id(file_id, user_id)

    async def get_files(self, user_id: int) -> Sequence[File]:
        return await self.file_repository.get_all_by_user(user_id)

    async def delete_file(self, file_id: int, user_id: int) -> bool:
        file_record = await self.file_repository.get_by_id(file_id, user_id)
        if not file_record:
            return False

        if Path(file_record.file_path).exists():
            Path(file_record.file_path).unlink()

        return await self.file_repository.delete(file_id, user_id)

    async def get_file_content(self, file_id: int, user_id: int) -> FileContentResponse | None:
        file_record = await self.file_repository.get_by_id(file_id, user_id)
        if not file_record:
            return None

        file_path = Path(file_record.file_path)
        if not file_path.exists():
            return None

        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()

        content_type, _ = mimetypes.guess_type(file_record.original_filename)
        if not content_type:
            content_type = "application/octet-stream"

        return FileContentResponse(
            content=content,
            original_filename=file_record.original_filename,
            content_type=content_type,
        )

    def _get_file_type(self, filename: str) -> FileType:
        extension = Path(filename).suffix.lower()
        type_mapping = {
            ".pdf": FileType.PDF,
            ".docx": FileType.DOCX,
        }
        if extension_type := type_mapping.get(extension):
            return extension_type
        raise UnsupportedFileTypeError("Unsupported file type")

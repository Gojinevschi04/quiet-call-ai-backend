from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field

from app.core.models import BaseModel
from app.modules.files.schema import FileType


class File(BaseModel, table=True):
    filename: str = Field(index=True, nullable=False)
    original_filename: str = Field(nullable=False)
    file_path: str = Field(nullable=False)
    file_size: int = Field(nullable=False)
    file_type: FileType = Field(nullable=False)
    # ON DELETE CASCADE — deleting a user cleans up their files instead of
    # blocking the delete with a FK violation.
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    content_hash: str = Field(index=True, nullable=True)

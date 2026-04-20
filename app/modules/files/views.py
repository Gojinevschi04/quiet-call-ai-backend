from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app.core.schema import MessageResponse
from app.modules.files.schema import FileResponse
from app.modules.files.service import FileService
from app.modules.users.middleware import get_current_user
from app.modules.users.models import User

router = APIRouter(prefix="/files", tags=["files"])


def _get_download_url(request: Request, file_id: int) -> str:
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/files/{file_id}/download"


@router.post("/upload")
async def upload_file_view(
    file: Annotated[UploadFile, File()],
    file_service: Annotated[FileService, Depends(FileService)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> FileResponse:
    if not file.filename:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="No file provided")

    try:
        file_content = await file.read()
        file_record = await file_service.save_file(file_content, file.filename, current_user.id)

        return FileResponse(
            id=file_record.id,
            original_filename=file_record.original_filename,
            file_size=file_record.file_size,
            file_type=file_record.file_type,
            created_at=file_record.created_at,
            updated_at=file_record.updated_at,
            download_url=_get_download_url(request, file_record.id),
        )
    except Exception as e:
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail="Could not save file") from e


@router.get("/")
async def get_files_view(
    file_service: Annotated[FileService, Depends(FileService)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> list[FileResponse]:
    files = await file_service.get_files(current_user.id)

    file_list = []
    for file in files:
        file_list.append(
            FileResponse(
                id=file.id,
                original_filename=file.original_filename,
                file_size=file.file_size,
                file_type=file.file_type,
                created_at=file.created_at,
                updated_at=file.updated_at,
                download_url=_get_download_url(request, file.id),
            )
        )

    return file_list


@router.get("/{file_id}")
async def get_file_view(
    file_id: int,
    file_service: Annotated[FileService, Depends(FileService)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> FileResponse:
    file_record = await file_service.get_file(file_id, current_user.id)

    if not file_record:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="File not found")

    return FileResponse(
        id=file_record.id,
        original_filename=file_record.original_filename,
        file_size=file_record.file_size,
        file_type=file_record.file_type,
        created_at=file_record.created_at,
        updated_at=file_record.updated_at,
        download_url=_get_download_url(request, file_record.id),
    )


@router.get("/{file_id}/download")
async def download_file_view(
    file_id: int,
    file_service: Annotated[FileService, Depends(FileService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    file_data = await file_service.get_file_content(file_id, current_user.id)

    if not file_data:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="File not found")

    headers = {"Content-Disposition": f'attachment; filename="{file_data.original_filename}"'}

    return Response(content=file_data.content, media_type=file_data.content_type, headers=headers)


@router.delete("/{file_id}")
async def delete_file_view(
    file_id: int,
    file_service: Annotated[FileService, Depends(FileService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    success = await file_service.delete_file(file_id, current_user.id)

    if not success:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="File not found")

    return MessageResponse(message="File deleted successfully")

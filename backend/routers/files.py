"""Hermes WebUI — Files Router
=================================
File listing and download for user-uploaded and agent-generated files.
Now user-isolated: each logged-in user only sees their own workspace.
"""

import os
import mimetypes
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import FileResponse, JSONResponse

from config import get_upload_dir
from user_auth import get_user_workspace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])

WORKSPACE_ROOT = Path.home() / "Shared" / "员工工作区"


@router.get("/list")
async def list_files(request: Request):
    """List files. Admin (server token) sees all users; normal users see only their own."""
    username = getattr(request.state, "auth_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")

    is_admin = (username == "server")

    if is_admin:
        # Admin mode: show all users' files, grouped by user
        entries = []
        if WORKSPACE_ROOT.exists():
            for user_dir in sorted(WORKSPACE_ROOT.iterdir()):
                if not user_dir.is_dir():
                    continue
                for label in ("上传", "生成"):
                    dirpath = user_dir / label
                    if not dirpath.exists():
                        continue
                    try:
                        for f in sorted(dirpath.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                            if f.is_file() and not f.name.startswith("."):
                                size = f.stat().st_size
                                entries.append({
                                    "name": f.name,
                                    "size": size,
                                    "size_hr": _format_size(size),
                                    "mtime": f.stat().st_mtime,
                                    "source": f"{user_dir.name}/{label}",
                                    "download_url": f"/api/files/download/admin/{user_dir.name}/{label}/{f.name}",
                                })
                    except PermissionError:
                        continue
        return {"files": entries, "total": len(entries), "username": "管理员", "is_admin": True}

    # Normal user mode
    workspace = get_user_workspace(username)
    if not workspace or not workspace.exists():
        return {"files": [], "total": 0, "username": username, "is_admin": False}

    entries = []
    for label, dirpath in [("上传", workspace / "上传"), ("生成", workspace / "生成")]:
        if not dirpath.exists():
            continue
        try:
            for f in sorted(dirpath.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if f.is_file() and not f.name.startswith("."):
                    size = f.stat().st_size
                    entries.append({
                        "name": f.name,
                        "size": size,
                        "size_hr": _format_size(size),
                        "mtime": f.stat().st_mtime,
                        "source": label,
                        "download_url": f"/api/files/download/{label}/{f.name}",
                    })
        except PermissionError:
            continue

    return {"files": entries, "total": len(entries), "username": username, "workspace": str(workspace), "is_admin": False}


@router.get("/download/{source:path}/{filename:path}")
async def download_file(source: str, filename: str, request: Request):
    """Download a file. Admin can download any user's file."""
    username = getattr(request.state, "auth_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")

    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid path")

    is_admin = (username == "server")

    if is_admin and source.startswith("admin/"):
        # Admin download: /api/files/download/admin/username/label/filename
        parts = source.split("/", 2)
        if len(parts) < 3:
            raise HTTPException(status_code=400, detail="Invalid admin path")
        _, admin_username, label = parts
        workspace = get_user_workspace(admin_username)
        if not workspace:
            raise HTTPException(status_code=404, detail="用户不存在")
        if label not in ("上传", "生成"):
            raise HTTPException(status_code=400, detail="无效的目录")
        filepath = workspace / label / filename
    else:
        # Normal user download: only own files
        if ".." in source:
            raise HTTPException(status_code=400, detail="Invalid path")
        workspace = get_user_workspace(username)
        if not workspace:
            raise HTTPException(status_code=404, detail="用户工作区不存在")
        if source not in ("上传", "生成"):
            raise HTTPException(status_code=400, detail="无效的目录")
        filepath = workspace / source / filename

    media_type, _ = mimetypes.guess_type(str(filepath))
    if media_type is None:
        media_type = "application/octet-stream"

    from audit import audit_file_download
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
    audit_file_download(username, filename, source, ip)

    return FileResponse(
        path=str(filepath),
        media_type=media_type,
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
            f'; filename*=UTF-8\'\'{filename}',
        },
    )


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    else:
        return f"{size / 1024 / 1024 / 1024:.1f} GB"

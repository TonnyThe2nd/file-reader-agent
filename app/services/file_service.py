from pathlib import Path

from fastapi import HTTPException, UploadFile

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".csv": "text/plain",
    ".json": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


async def read_attachment(file: UploadFile, limit: int) -> tuple[bytes, str]:
    mime_type = MIME_TYPES.get(Path(file.filename or "").suffix.lower())
    if not mime_type:
        raise HTTPException(
            415, "Formato nao suportado. Use PDF, TXT, MD, CSV, JSON, PNG, JPEG ou WEBP."
        )
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, f"Arquivo excede o limite de {limit} bytes.")
    if not content:
        raise HTTPException(422, "O arquivo esta vazio.")
    if mime_type == "text/plain":
        try:
            if not content.decode("utf-8-sig").strip():
                raise HTTPException(422, "O arquivo nao contem texto.")
        except UnicodeDecodeError:
            raise HTTPException(422, "Arquivos de texto devem usar UTF-8.") from None
    signatures = {
        "application/pdf": content.startswith(b"%PDF-"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }
    if mime_type in signatures and not signatures[mime_type]:
        raise HTTPException(422, "O conteudo do arquivo nao corresponde ao formato informado.")
    return content, mime_type

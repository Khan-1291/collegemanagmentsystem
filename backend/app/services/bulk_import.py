import csv
import io
from typing import Any, Type

from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.models.models import Department
from app.models.models import User, UserRole
from app.core.deps import resolve_department_id

MAX_IMPORT_SIZE = 2 * 1024 * 1024
MAX_IMPORT_ROWS = 500


async def parse_import_file(
    file: UploadFile,
    schema: Type[BaseModel],
    required_headers: set[str],
) -> list[tuple[int, BaseModel]]:
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only CSV files can be imported.",
        )

    content = await file.read(MAX_IMPORT_SIZE + 1)
    if len(content) > MAX_IMPORT_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CSV file exceeds the 2 MB import limit.",
        )

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file must use UTF-8 encoding.",
        ) from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file must include a header row and at least one record.",
        )

    headers = [header.strip() for header in reader.fieldnames if header]
    if len(headers) != len(reader.fieldnames) or len(set(headers)) != len(headers):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV header names must be non-empty and unique.",
        )

    missing_headers = sorted(required_headers - set(headers))
    unknown_headers = sorted(set(headers) - set(schema.model_fields))
    if missing_headers or unknown_headers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "CSV headers do not match the selected enrollment type.",
                "missing_headers": missing_headers,
                "unknown_headers": unknown_headers,
            },
        )

    parsed: list[tuple[int, BaseModel]] = []
    errors: list[dict[str, Any]] = []
    for row_number, row in enumerate(reader, start=2):
        if row.get(None):
            errors.append(
                {
                    "row": row_number,
                    "errors": [{"field": "row", "message": "Row contains more values than the header."}],
                }
            )
            continue
        if not row or all(value is None or not value.strip() for value in row.values()):
            continue
        if row_number > MAX_IMPORT_ROWS + 1:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"CSV import is limited to {MAX_IMPORT_ROWS} records.",
            )

        normalized = {}
        for key, value in row.items():
            if key is not None:
                normalized[key.strip()] = value.strip() or None if value is not None else None
        try:
            parsed.append((row_number, schema.model_validate(normalized)))
        except ValidationError as exc:
            errors.append(
                {
                    "row": row_number,
                    "errors": [
                        {
                            "field": ".".join(str(part) for part in issue["loc"]),
                            "message": issue["msg"],
                        }
                        for issue in exc.errors()
                    ],
                }
            )

    if not parsed and not errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file contains no enrollment records.",
        )
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "One or more CSV rows are invalid.", "rows": errors},
        )
    return parsed


def ensure_computer_science_department(db: Session) -> Department:
    department = db.query(Department).filter(Department.code == "CS").first()
    if department is None:
        department = Department(
            name="Computer Science",
            code="CS",
            description="Computer Science Department",
        )
        db.add(department)
        db.flush()
    return department


def resolve_enrollment_department(
    db: Session,
    user: User,
    requested_department_id: int | None,
) -> Department:
    if user.role == UserRole.SUPER_ADMIN and requested_department_id is None:
        return ensure_computer_science_department(db)
    department_id = resolve_department_id(db, user, requested_department_id)
    department = db.query(Department).filter(Department.id == department_id).first()
    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {department_id} not found.",
        )
    return department


def duplicate_rows(records: list[tuple[int, BaseModel]], field: str) -> list[int]:
    seen: set[str] = set()
    duplicates: list[int] = []
    for row_number, record in records:
        value = str(getattr(record, field)).strip().casefold()
        if value in seen:
            duplicates.append(row_number)
        else:
            seen.add(value)
    return duplicates

"""Create the first Super Admin through an interactive password prompt."""

import argparse
from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash
from app.database import SessionLocal
from app.models.models import User, UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Super Admin email address")
    parser.add_argument("--full-name", required=True, help="Super Admin full name")
    args = parser.parse_args()

    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email.strip().lower()))
    except ValidationError:
        parser.error("Provide a valid email address.")
    full_name = args.full_name.strip()
    if not full_name:
        parser.error("Full name must not be blank.")

    password = getpass("New Super Admin password (minimum 12 UTF-8 bytes): ")
    confirmation = getpass("Confirm password: ")
    password_bytes = len(password.encode("utf-8"))
    if password_bytes < 12:
        parser.error("Password must contain at least 12 UTF-8 bytes.")
    if password_bytes > 72:
        parser.error("Password cannot exceed 72 UTF-8 bytes because the application uses bcrypt.")
    if password != confirmation:
        parser.error("Passwords do not match.")

    db = SessionLocal()
    try:
        if db.query(User.id).filter(User.email == email).first():
            parser.error(f"An account already exists for {email}.")
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Super Admin account created for {email}.")
    except IntegrityError as exc:
        db.rollback()
        parser.error(f"Could not create the account because a record conflicts: {exc.orig}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

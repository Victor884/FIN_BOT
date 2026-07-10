"""
Script para criar usuários de teste no banco de dados.
Uso: python scripts/create_users.py
"""

import sys
import os
import secrets

# Garante que o pacote finbot seja encontrado
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from finbot.core.security import hash_password
from finbot.core.settings import Settings
from finbot.db.models import UserRecord
from finbot.db.session import get_engine
from sqlalchemy.orm import Session
from sqlalchemy import select


USERS_TO_CREATE = [
    {
        "name": "Admin",
        "email": "admin@finbot.local",
        "role": "ADMIN",
    },
    {
        "name": "Usuario Teste",
        "email": "user@finbot.local",
        "role": "USER",
    },
]


def create_users() -> None:
    settings = Settings()
    engine = get_engine(settings.database_url)

    created_credentials: list[tuple[str, str, str]] = []
    with Session(engine) as session:
        for user_data in USERS_TO_CREATE:
            existing = session.scalars(
                select(UserRecord).where(
                    UserRecord.email == user_data["email"].lower()
                )
            ).first()

            if existing:
                print(f"[SKIP] Usuário já existe: {user_data['email']} (role={existing.role})")
                continue

            password = secrets.token_urlsafe(12)
            user = UserRecord(
                name=user_data["name"],
                email=user_data["email"].lower(),
                password_hash=hash_password(password),
                role=user_data["role"],
                status="ACTIVE",
            )
            session.add(user)
            session.flush()
            created_credentials.append((user_data["role"], user_data["email"], password))
            print(f"[OK]   Criado: {user_data['email']} | role={user_data['role']} | id={user.id}")

        session.commit()
        if created_credentials:
            print("\nCredenciais locais geradas (anote agora; as senhas nao serao exibidas novamente):")
            print("-" * 72)
            for role, email, password in created_credentials:
                print(f"  [{role:5}]  {email}  /  {password}")
            print("-" * 72)
        else:
            print("\nNenhum usuario novo foi criado.")


if __name__ == "__main__":
    create_users()

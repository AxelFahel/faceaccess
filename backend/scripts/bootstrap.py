"""Initial bootstrap script to seed default organization, roles, permissions,
superadmin and legal basis records.
"""
from __future__ import annotations

import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.permissions import PERMISSIONS, ROLES
from app.core.security import hash_secret
from app.db.base import Base
from app.db.session import get_engine, get_sessionmaker
from app.models.auth import Permission, Role, User
from app.models.organization import Department, Organization, Unit
from app.models.privacy import LegalBasisRecord, PrivacyNotice


def seed_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    SessionLocal = get_sessionmaker()

    with SessionLocal() as db:
        # 1. Permissions
        existing_perms = {p.code: p for p in db.execute(select(Permission)).scalars().all()}
        for code, desc in PERMISSIONS.items():
            if code not in existing_perms:
                perm = Permission(code=code, description=desc)
                db.add(perm)
                existing_perms[code] = perm

        # 2. Roles
        existing_roles = {r.code: r for r in db.execute(select(Role)).scalars().all()}
        for r_code, r_data in ROLES.items():
            role = existing_roles.get(r_code)
            if not role:
                role = Role(code=r_code, name=r_data["name"], description=r_data["description"])
                db.add(role)
                existing_roles[r_code] = role
            role.permissions = [existing_perms[p] for p in r_data["permissions"] if p in existing_perms]

        # 3. Organization & Default Unit/Dept
        org = db.execute(select(Organization).limit(1)).scalar_one_or_none()
        if not org:
            org = Organization(name="Matriz Corporativa", timezone="America/Fortaleza")
            db.add(org)
            db.flush()

        unit = db.execute(select(Unit).where(Unit.organization_id == org.id)).scalar_one_or_none()
        if not unit:
            unit = Unit(organization_id=org.id, name="Sede Principal", code="SEDE-01")
            db.add(unit)
            db.flush()

        dept = db.execute(select(Department).where(Department.organization_id == org.id)).scalar_one_or_none()
        if not dept:
            dept = Department(organization_id=org.id, unit_id=unit.id, name="Tecnologia da Informação", code="TI")
            db.add(dept)
            db.flush()

        # 4. Legal Basis & Notice
        lb = db.execute(select(LegalBasisRecord).limit(1)).scalar_one_or_none()
        if not lb:
            lb = LegalBasisRecord(
                organization_id=org.id,
                processing_activity="Controle de Acesso e Registro Interno de Presença",
                data_categories="Representação biométrica vetorial criptografada, registros de presença e identificadores funcionais",
                legal_basis="Art. 11, II, g (Prevenção à fraude e segurança do titular) c/c Art. 7º, V",
                legal_basis_description="Tratamento destinado à autenticação biométrica individual em instalações restritas e prevenção de fraudes de acesso corporativo.",
                purpose="Garantir a segurança física patrimonial e confirmação inequívoca de presença do colaborador.",
            )
            db.add(lb)
            db.flush()

        pn = db.execute(select(PrivacyNotice).limit(1)).scalar_one_or_none()
        if not pn:
            pn = PrivacyNotice(
                organization_id=org.id,
                version="1.0",
                title="Aviso de Privacidade para Verificação Facial e Acesso",
                content="A empresa utiliza verificação biométrica 1:1 estritamente em ambiente local para garantia de segurança e registro presencial...",
                effective_from=org.created_at.date() if org.created_at else org.timezone,  # type: ignore
                is_active=True,
            )
            db.add(pn)

        # 5. Admin User
        admin_email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "admin@faceaccess.com")
        admin_user = db.execute(select(User).where(User.email == admin_email)).scalar_one_or_none()
        if not admin_user:
            raw_pass = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "Admin@Secure2026!")
            admin_user = User(
                email=admin_email,
                full_name="Administrador do Sistema",
                password_hash=hash_secret(raw_pass),
                is_active=True,
                all_units=True,
                organization_id=org.id,
            )
            admin_user.roles = [existing_roles["superadmin"], existing_roles["admin"]]
            db.add(admin_user)
            print(f"[BOOTSTRAP] Usuário administrador criado: {admin_email}")

        db.commit()
        print("[BOOTSTRAP] Banco de dados populado com sucesso.")


if __name__ == "__main__":
    seed_db()

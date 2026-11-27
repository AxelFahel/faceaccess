"""Permission catalog and default role → permission mapping (RBAC).

Enforcement happens in the backend through ``require_permission`` dependencies;
the frontend only uses this information to hide UI elements.
"""
from __future__ import annotations

PERMISSIONS: dict[str, str] = {
    # Administração / infraestrutura
    "settings:read": "Consultar configurações do sistema",
    "settings:manage": "Alterar configurações do sistema",
    "users:read": "Consultar usuários",
    "users:manage": "Gerenciar usuários, perfis e escopos",
    "roles:read": "Consultar perfis e permissões",
    # Organização
    "org:read": "Consultar estrutura organizacional",
    "org:manage": "Gerenciar estrutura organizacional",
    # Funcionários
    "employees:read": "Consultar funcionários (no escopo)",
    "employees:manage": "Cadastrar/editar/ativar/inativar funcionários",
    "employees:export": "Exportar dados de funcionários",
    # Biometria
    "biometrics:read": "Consultar situação biométrica",
    "biometrics:enroll": "Realizar cadastro biométrico",
    "biometrics:revoke": "Revogar cadastro biométrico",
    # Acesso
    "access:read": "Consultar regras e eventos de acesso",
    "access:manage": "Gerenciar locais, grupos e regras de acesso",
    "access:review": "Revisar eventos de acesso (exceções)",
    # Terminais
    "terminals:read": "Consultar terminais",
    "terminals:manage": "Gerenciar terminais e credenciais",
    # Presença
    "attendance:read": "Consultar registros de presença (no escopo)",
    "attendance:manual": "Registrar presença manual autorizada",
    "attendance:adjust": "Aprovar/rejeitar ajustes de presença",
    "justifications:review": "Analisar justificativas",
    # Relatórios
    "reports:read": "Consultar relatórios",
    "reports:export": "Exportar relatórios (PDF/CSV/XLSX)",
    "dashboard:read": "Consultar dashboard",
    # Auditoria / privacidade
    "audit:read": "Consultar trilha de auditoria",
    "privacy:read": "Consultar registros de privacidade",
    "privacy:manage": "Gerenciar avisos, bases legais, solicitações, retenção e incidentes",
    # Autoatendimento
    "self:read": "Consultar os próprios dados e registros",
    "self:request": "Enviar justificativas, contestações e solicitações de titular",
    # Terminal (principal de máquina)
    "terminal:operate": "Operações de terminal (verificação e registro)",
}

ALL = set(PERMISSIONS)

ROLES: dict[str, dict] = {
    "superadmin": {
        "name": "Superadministrador",
        "description": "Configurações gerais e infraestrutura.",
        "permissions": ALL - {"terminal:operate"},
    },
    "admin": {
        "name": "Administrador",
        "description": "Funcionários, unidades, terminais e permissões.",
        "permissions": {
            "users:read", "users:manage", "roles:read", "org:read", "org:manage",
            "employees:read", "employees:manage", "employees:export",
            "biometrics:read", "biometrics:enroll", "biometrics:revoke",
            "access:read", "access:manage", "access:review",
            "terminals:read", "terminals:manage", "attendance:read", "attendance:manual",
            "reports:read", "reports:export", "dashboard:read", "privacy:read",
            "settings:read", "self:read", "self:request",
        },
    },
    "hr": {
        "name": "Recursos Humanos",
        "description": "Frequência, justificativas, relatórios e ajustes autorizados.",
        "permissions": {
            "org:read", "employees:read", "employees:export", "biometrics:read",
            "attendance:read", "attendance:manual", "attendance:adjust", "justifications:review",
            "reports:read", "reports:export", "dashboard:read", "privacy:read",
            "self:read", "self:request",
        },
    },
    "manager": {
        "name": "Gestor",
        "description": "Consulta dos funcionários do seu departamento.",
        "permissions": {
            "org:read", "employees:read", "attendance:read", "justifications:review",
            "reports:read", "dashboard:read", "access:read", "self:read", "self:request",
        },
    },
    "operator": {
        "name": "Operador",
        "description": "Operações autorizadas de cadastro e controle de acesso.",
        "permissions": {
            "org:read", "employees:read", "biometrics:read", "biometrics:enroll",
            "access:read", "access:review", "terminals:read", "attendance:read", "attendance:manual",
            "dashboard:read", "self:read", "self:request",
        },
    },
    "auditor": {
        "name": "Auditor",
        "description": "Consulta de logs e auditoria, sem alteração.",
        "permissions": {
            "audit:read", "org:read", "users:read", "roles:read", "privacy:read",
            "access:read", "terminals:read", "reports:read", "dashboard:read", "settings:read",
            "self:read",
        },
    },
    "employee": {
        "name": "Funcionário",
        "description": "Consulta dos próprios registros, justificativas e correções.",
        "permissions": {"self:read", "self:request"},
    },
    "terminal": {
        "name": "Terminal",
        "description": "Operações restritas de acesso e presença (credencial de dispositivo).",
        "permissions": {"terminal:operate"},
    },
}

# Roles whose holders see every unit unless restricted explicitly.
GLOBAL_SCOPE_ROLES = {"superadmin"}
# Roles limited to their department scopes.
DEPARTMENT_SCOPE_ROLES = {"manager"}

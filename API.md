# Especificação da API REST (v1) — FaceAccess

A API do FaceAccess é estritamente versionada no caminho base `/api/v1/`.

---

## 1. Padrão de Respostas

### Sucesso
Retornos em formato JSON com código HTTP semântico (200, 201). Listagens paginadas adotam o envelope:
```json
{
  "items": [...],
  "total": 120,
  "page": 1,
  "page_size": 20,
  "pages": 6
}
```

### Erro
```json
{
  "error": {
    "code": "validation_error",
    "message": "Qualidade da captura insuficiente.",
    "details": [...],
    "request_id": "93f119f9b6cc47f7a154933b9ab0bed1"
  }
}
```

---

## 2. Endpoints Principais

### Autenticação & Sessões
- `POST /api/v1/auth/login`: Autenticação por e-mail e senha com suporte a MFA.
- `POST /api/v1/auth/mfa/verify`: Validação de segundo fator TOTP.
- `POST /api/v1/auth/refresh`: Renovação segura com rotação de refresh token.
- `GET /api/v1/auth/me`: Perfil do usuário autenticado e permissões.

### Funcionários
- `GET /api/v1/employees`: Listagem paginada com busca por nome, matrícula ou unidade.
- `POST /api/v1/employees`: Cadastro de colaborador com definição opcional de PIN.
- `GET /api/v1/employees/{id}`: Detalhes do colaborador.
- `PUT /api/v1/employees/{id}`: Atualização cadastral.

### Biometria Facial
- `POST /api/v1/biometrics/enroll`: Cadastro biométrico multi-captura com verificação de qualidade, vivacidade e cifragem AES-256-GCM.
- `POST /api/v1/biometrics/revoke/{employee_id}`: Revogação com descarte definitivo de vetor biométrico.

### Terminal & Kiosk
- `POST /api/v1/kiosk/verify`: Verificação 1:1 individual com validação facial ou PIN, liberação de acesso e registro de presença.

### Gestão & Presença
- `GET /api/v1/attendance`: Consulta de registros de ponto com filtros de data e colaborador.
- `GET /api/v1/dashboard/metrics`: Indicadores consolidados em tempo real.
- `GET /api/v1/reports/attendance/csv`: Exportação auditada em formato CSV.
- `GET /api/v1/terminals`: Gerenciamento de dispositivos autorizados.
- `POST /api/v1/terminals/activate`: Ativação de terminal com código seguro único.

### Privacidade & Auditoria
- `GET /api/v1/privacy/legal-basis`: Consulta de bases legais registradas.
- `GET /api/v1/privacy/audit-logs`: Consulta da trilha encadeada de auditoria.

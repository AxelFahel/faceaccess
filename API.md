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
# Cadastro biométrico de funcionários e convidados (27/11/2026)

- Funcionário: `POST /api/v1/biometrics/capture-check`, `POST /api/v1/biometrics/enroll`, `POST /api/v1/biometrics/revoke/{employee_id}`.
- Convidado: `POST /api/v1/events/guests/capture-check` (`guest_id`, `image_base64`), `POST /api/v1/events/guests/enroll` (`guest_id`, `images_base64`), `POST /api/v1/events/guests/{guest_id}/revoke` (sem corpo).
- Captura/cadastro exigem `biometrics:enroll`; revogação exige `biometrics:revoke`. Organização e unidade são verificadas no servidor; funcionários também respeitam escopo de departamento.
- Ambos os cadastros exigem exatamente `enrollment_captures` imagens e validam qualidade, vivacidade e consistência. `capture-check` devolve `accepted`, `message`, `reasons`, `required_captures`; não grava template.
- Convidado cancelado/bloqueado ou evento inativo/encerrado: 422. Escopo indevido: 403. Revogar preserva o convite e elimina o template cifrado.

## Orientação da câmera do totem

`POST /api/v1/kiosk/capture-check` recebe `image_base64` (até 4 milhões de caracteres) e `operation_type` (`attendance` ou `access`). Usa credenciais de terminal e verifica a operação autorizada. Retorna `accepted` e `message` com base em posição, tamanho do rosto, qualidade e vivacidade. Não identifica pessoas nem grava acesso/ponto. A rota `/verify` revalida a captura independentemente antes de identificar e autorizar.

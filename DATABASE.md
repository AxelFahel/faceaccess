# Modelagem e Dicionário de Dados — FaceAccess

Este documento descreve as entidades, esquemas e regras de integridade do banco de dados relacional (PostgreSQL).

---

## 1. Esquema Geral

O banco de dados utiliza UUIDv4 como identificador primário em todas as tabelas, garantindo unicidade distribuída e dificultando enumeração externa.

### Schemas Lógicos:
- **`public`**: Estrutura organizacional, colaboradores, terminais, logs de acesso, auditoria e presenças.
- **`biometric`**: Isolamento lógico das representações biométricas cifradas e histórico de enrollments.

---

## 2. Entidades Principais

| Tabela | Finalidade | Regras de Integridade |
|---|---|---|
| `organizations` | Cadastro da entidade controladora | CNPJ / Nome legal |
| `units` | Unidades operacionais e filiais | `UNIQUE(organization_id, code)` |
| `departments` | Departamentos e centros de custo | `UNIQUE(organization_id, code)` |
| `positions` | Cargos cadastrados | `UNIQUE(organization_id, code)` |
| `employees` | Dados funcionais de colaboradores | `UNIQUE(registration_number)`, `UNIQUE(email)` |
| `users` | Usuários do painel com RBAC | `UNIQUE(email)` |
| `roles` & `permissions` | Matriz de controle de acesso | Códigos unificados de permissão |
| `terminals` | Dispositivos físicos (totens/kiosks) | `UNIQUE(code)` |
| `biometric_enrollments` | Templates vetoriais cifrados | `UNIQUE(employee_id)` onde `status = 'active'` |
| `verification_events` | Logs de tentativas 1:1 | Sem imagens ou dados biométricos |
| `access_events` | Decisões de liberação física | Vínculo com regras de acesso |
| `attendance_records` | Registros de ponto e presença | Imutabilidade; prevenção de duplicidade |
| `attendance_adjustments`| Ajustes autorizados de ponto | Fluxo de aprovação com trilha de auditoria |
| `audit_logs` | Trilha de auditoria encadeada | Hash encadeado + HMAC com chave secreta |
| `legal_basis_records` | Registro de operações de tratamento LGPD | Base legal conforme art. 7º/11 da LGPD |

---

## 3. Retenção e Descarte Seguro
- Colaboradores inativados podem ter suas representações biométricas revogadas com zeramento imediato dos campos `template_ciphertext` e `template_nonce`.
- Registros de verificação (`verification_events`) possuem política de expiração após cumprimento da finalidade de auditoria.

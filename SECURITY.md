# Diretrizes de Segurança da Informação — FaceAccess

Este documento especifica a arquitetura de segurança, os controles criptográficos e as proteções implementadas no FaceAccess.

---

## 1. Princípios de Segurança desde a Concepção (Security by Design)

- **Menor Privilégio (Least Privilege)**:
  - O banco de dados opera com roles segregadas.
  - Acesso à API restrito por RBAC rigoroso no backend.
  - Terminais físicos usam credenciais de máquina dedicadas (`X-Terminal-Code` / `X-Terminal-Secret`), com permissões restritas a `terminal:operate`.
- **Defesa em Profundidade**:
  - Proteção contra brute force por meio de bloqueio exponencial e limitação de taxa (sliding window rate-limiting).
  - Sanitização de entradas em todas as camadas com Pydantic v2.
  - Hash de senhas exclusivamente via Argon2id (RFC 9106).
  - Trilha de auditoria encadeada imutável (HMAC-SHA-256).

---

## 2. Criptografia em Trânsito e em Repouso

### Representações Biométricas (Templates 512-D)
- **Algoritmo**: AES-256-GCM (Authenticated Encryption with Associated Data).
- **Nonce**: 96 bits (12 bytes) gerados por fonte criptográfica segura do sistema operacional (`os.urandom`) para cada cifragem.
- **AAD (Authenticated Associated Data)**: Cada cifragem embute o ID de enrollment, o ID do funcionário e a versão do motor (`faceaccess:template:v1:{enrollment_id}:{employee_id}:{engine_version}`). Isso impede ataques de transposição de chaves ou transplante de vetores entre registros no banco de dados.
- **Keyring**: Suporte a rotação de chaves. O campo `key_id` armazena qual chave cifrou o registro, permitindo transição contínua sem interrupção de serviço.

### Senhas e Segredos
- **Senhas de Usuários**: Hasheadas com **Argon2id** com salt individual criptográfico.
- **PINs de Alternativa Não Biométrica**: Hasheados com **Argon2id**.
- **Tokens de Sessão e Credenciais de Terminais**: Armazenados no banco apenas como hash **SHA-256**. O segredo original nunca é persistido em claro.
- **Segredos TOTP (MFA)**: Cifrados com chave dedicada `DATA_ENCRYPTION_KEY` antes de serem gravados.

---

## 3. Segurança de Rede e Proteção Web

- **Headers HTTP de Segurança (Security Headers)**:
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()` (restritivo nas rotas administrativas)
  - `Cache-Control: no-store` em todas as rotas `/api/`
- **Isolamento de Imagens**:
  - As imagens enviadas para verificação ou cadastro residem estritamente em memória volátil (RAM) e são eliminadas imediatamente após a computação das features.
  - Nenhuma imagem bruta de câmera é persistida em disco, volumes persistentes ou banco de dados.

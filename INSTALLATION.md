# Guia de Instalação e Implantação — FaceAccess

Este guia detalha o processo de instalação, configuração de ambiente e implantação do FaceAccess em infraestrutura local/on-premises (bare-metal, VMs Linux ou Docker).

---

## 1. Pré-requisitos de Sistema

### Hardware Recomendado (Servidor / Host)
- **CPU**: 4 núcleos x86_64 (mínimo) / 8 núcleos (recomendado para concorrência de 10+ terminais).
- **Memória RAM**: 8 GB (mínimo) / 16 GB (recomendado).
- **Armazenamento**: 40 GB livres (SSD/NVMe para cache de modelos e logs de auditoria).
- **GPU (Opcional)**: NVIDIA com CUDA 12+ (caso deseje aceleração com `onnxruntime-gpu`).

### Software
- **Docker**: Engine 24+ ou Docker Desktop.
- **Docker Compose**: Plugin v2 ou superior.
- **Navegador**: Google Chrome, Edge ou Firefox atualizados (para suporte à WebRTC/getUserMedia nos totens).

---

## 2. Instalação via Docker Compose (Recomendada)

### Passo 1: Preparar Arquivo de Variáveis de Ambiente
Crie um arquivo `.env` seguro no diretório raiz do projeto:

```bash
cp .env.example .env
```

Gere chaves criptográficas fortes para o ambiente:
```bash
# Gerar chaves aleatórias de 32 bytes em Base64
python -c "import os, base64; print('JWT_SECRET=' + base64.b64encode(os.urandom(32)).decode())"
python -c "import os, base64; print('AUDIT_HMAC_KEY=' + base64.b64encode(os.urandom(32)).decode())"
python -c "import os, base64; print('DATA_ENCRYPTION_KEY=' + base64.b64encode(os.urandom(32)).decode())"
```

Configure as variáveis no `.env`:
- `POSTGRES_USER`: Usuário do banco PostgreSQL.
- `POSTGRES_PASSWORD`: Senha de alta entropia.
- `JWT_SECRET`: Segredo de assinatura de tokens JWT.
- `AUDIT_HMAC_KEY`: Chave HMAC-SHA-256 para o hash encadeado de auditoria.
- `BIOMETRIC_KEYS`: Keyring JSON com chaves AES-256 (`{"k1": "<base64 32 bytes>"}`).
- `DATA_ENCRYPTION_KEY`: Chave AES-256 para segredos em repouso (segredos TOTP de MFA).

### Passo 2: Pré-download dos Modelos UniFace (Isolado e Verificado)
Antes de desconectar a rede externa do ambiente de produção, execute o download dos modelos homologados (MIT / Apache-2.0):

```bash
docker compose run --rm backend python scripts/download_models.py
```

Isso baixará e validará via SHA-256:
- `retinaface_mnet_v2.onnx` (Detecção)
- `adaface_ir_18.onnx` (Extração 512-D)
- `minifasnet_v2.onnx` (Anti-spoofing)
- `ediffiqa_t.onnx` (Qualidade)

### Passo 3: Inicialização dos Containers
```bash
docker compose up -d --build
```

### Passo 4: Execução do Bootstrap Inicial
Popule a estrutura organizacional básica e o administrador inicial:
```bash
docker compose exec backend python scripts/bootstrap.py
```

---

## 3. Instalação Manual (Bare Metal / Desenvolvimento)

### Backend
1. Crie o ambiente virtual:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
   ```
2. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Inicialize o banco e inicie a API:
   ```bash
   python scripts/bootstrap.py
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

### Frontend
1. Instale os módulos Node:
   ```bash
   cd frontend
   npm install
   ```
2. Inicie o servidor de desenvolvimento ou gere a build:
   ```bash
   npm run build
   npm run preview
   ```

# FaceAccess — Sistema de Controle de Acesso e Presença Biométrica Facial

Sistema corporativo completo, modular e seguro para gestão de colaboradores, controle de acesso físico e registro de presença por verificação biométrica facial 1:1, utilizando os modelos oficiais e licenças permissivas da biblioteca **UniFace**.

Desenvolvido para execução **100% local e privada**, sem tráfego de fotografias, dados sensíveis ou representações biométricas para serviços externos.

O cadastro facial usa o [UniFace oficial](https://github.com/yakhyo/uniface), fixado na versão 4.3.0. A tela de selfie guiada captura pela câmera, analisa cada imagem no servidor e solicita três capturas aprovadas (configurável por `ENROLLMENT_CAPTURES`, entre 1 e 5). RetinaFace verifica o enquadramento, eDifFIQA avalia a qualidade, MiniFASNet faz a análise passiva de vivacidade e AdaFace gera a representação facial. O servidor repete as verificações e confere a consistência entre as capturas antes de gravar o template criptografado.

A câmera requer HTTPS ou localhost. O fluxo não integra a conta ou as bases biométricas do gov.br, nem implementa desafios ativos de movimentos. A análise passiva precisa ser validada com câmeras e condições reais antes do uso operacional; testes com o motor `fake` não medem resistência a fraude.

Ao abrir o cadastro, a orientação por voz já inicia habilitada e a câmera captura automaticamente, uma imagem por vez, com intervalo entre análises. Somente capturas aprovadas avançam o progresso; ao completar a quantidade exigida, o cadastro é salvo automaticamente. É possível pausar, refazer, silenciar ou repetir a orientação. Falhas de comunicação ou 15 reprovações consecutivas pausam o fluxo; a gravação não é repetida automaticamente após erro. A captura também pausa enquanto a aba fica oculta.

A voz usa um serviço local em português disponível no dispositivo; se indisponível ou bloqueada pelo navegador, a tela informa o problema e mantém as instruções escritas. O microfone não é utilizado.

As requisições têm limite de espera de 30 segundos (60 segundos para a gravação final). Ao ocorrer timeout na gravação, confira a lista antes de repetir: interromper a espera no navegador não desfaz uma operação já recebida pelo servidor. Os modelos devem ser preparados previamente com `scripts/download_models.py` e `UNIFACE_CACHE_DIR`; a captura não inicia downloads. Depois de atualizar o código Python, reinicie o backend para carregar as novas rotas.

---

## 🚀 Tecnologias

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, Recharts.
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, Argon2id, PyJWT, Cryptography.
- **Biometria (UniFace)**:
  - *Detector*: RetinaFace MobileNetV2 (MIT)
  - *Extrator de Embeddings*: AdaFace IR-18 512-D (MIT)
  - *Liveness / Anti-Spoofing*: MiniFASNet V2 (Apache-2.0)
  - *Qualidade da Imagem*: eDifFIQA-T (MIT)
- **Banco de Dados**: PostgreSQL 16 (UUIDv4, Esquema segregado, Criptografia AES-256-GCM para templates).
- **DevOps**: Docker, Docker Compose, Nginx.

---

## 📋 Pré-requisitos

- Docker & Docker Compose instalados.
- Ou Python 3.11/3.12 e Node.js 20+ para desenvolvimento local.

---

## 🛠️ Inicialização Rápida (Docker Compose)

1. **Clonar e configurar o ambiente:**
   ```bash
   cp .env.example .env
   ```

2. **Subir os serviços:**
   ```bash
   docker compose up -d --build
   ```

3. **Acessar as interfaces locais:**
   - **Painel Administrativo**: [http://localhost](http://localhost)
   - **Terminal Modo Kiosk**: [http://localhost/kiosk](http://localhost/kiosk)
   - **Documentação da API (OpenAPI/Swagger)**: [http://localhost/api/docs](http://localhost/api/docs)

---

## 🔒 Credenciais Padrão de Inicialização

- **E-mail**: `admin@faceaccess.com`
- **Senha**: `Admin@Secure2026!`

---

## 🏷️ Versão 1.0.0 (Release Notes)

- **Biometria 1:1 UniFace**: Modelos locais de inferência com licenças permissivas comerciais (RetinaFace, AdaFace IR-18, MiniFASNet V2 e eDifFIQA-T).
- **Totem Kiosk Autônomo**:
  - Reconhecimento facial contínuo sem toques na tela;
  - Validação visual com feedback animado em verde (autorizado/registrado) e vermelho (rejeitado/não autorizado);
  - Gravação automática de presença no horário oficial do servidor;
  - Alternativa contingencial por matrícula e PIN.
- **Suporte Mobile e HTTPS Local**:
  - HMR e servidor com certificado SSL automático (`@vitejs/plugin-basic-ssl`);
  - Viewports e controles otimizados para smartphones, tablets e totens dedicados;
  - Compatibilidade com captura direta de câmera nativa de smartphones.
- **Conformidade LGPD**:
  - Descarte imediato das imagens capturadas após extração do vetor biométrico;
  - Armazenamento em envelope criptográfico autenticado AES-256-GCM;
  - Trilha de auditoria encadeada com assinaturas HMAC-SHA-256 (tamper-evident).

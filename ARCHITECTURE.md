# Arquitetura do FaceAccess

## 1. Visão Geral
O FaceAccess adota uma arquitetura em camadas orientada a serviços (Clean Architecture / Modular Monolith):

```
[ Frontend SPA (React + Vite) ] / [ Totem Kiosk ]
                     │ (HTTP/REST + JWT)
                     ▼
             [ Nginx Reverse Proxy ]
                     │
                     ▼
          [ FastAPI Application ]
    ┌────────────────┬────────────────┐
    │  Controllers   │   Middlewares  │
    │  (API Routes)  │  (RateLimit/CSP)
    └───────┬────────┴────────┬───────┘
            ▼                 ▼
   [ Business Services ]  [ Audit Trail (HMAC) ]
            │
    ┌───────┴────────────────────────┐
    ▼                                ▼
[ Biometric Engine Abstraction ]  [ SQLAlchemy Repositories ]
    │                                │
    ├─ RetinaFace (Detector)         ▼
    ├─ AdaFace IR-18 (Embedding) [ PostgreSQL Database ]
    ├─ MiniFASNet V2 (Liveness)     ├─ public schema (Cadastros)
    └─ eDifFIQA-T (Quality)         └─ biometric schema (AES-256-GCM)
```

## 2. Camada Biométrica Isolada
A abstração `BiometricEngine` isola a biblioteca de visão computacional da lógica de negócio. Modelos são executados localmente via ONNX Runtime (CPU ou GPU CUDA). Nenhuma imagem é retida após o processamento.

## 3. Cadastro compartilhado, regras por vínculo

Decisão de 27/11/2026: manter o monólito modular FastAPI + React. O tamanho atual do produto não justifica distribuir autenticação, biometria e autorização em microsserviços. A câmera e o processamento facial são compartilhados; elegibilidade, armazenamento e autorização continuam específicos de cada vínculo.

Fluxo: `EnrollmentCapture` → rota de funcionário ou convidado → `enrollment_policy` (escopo e elegibilidade) → `enrollment` (qualidade, vivacidade, consistência e normalização) → criptografia e persistência → auditoria.

| Regra | Funcionário | Convidado |
|---|---|---|
| Identidade do cadastro | Funcionário da organização/unidade/departamento | Convite associado ao evento e sua unidade |
| Elegibilidade para cadastrar | Vínculo ativo | Convite ativo/presente, evento ativo e ainda não encerrado com tolerância |
| Antecedência | Conforme vínculo | Pode cadastrar antes do evento; isso não libera entrada antecipada |
| Captura | Câmera guiada, quantidade configurada, qualidade, vivacidade, consistência | Mesma validação e mesma experiência |
| Autorização no totem | Unidade, vínculo, jornada e exceções existentes | Biometria obrigatória, unidade e janela do evento; PIN não substitui rosto |
| Finalidade de registro | Acesso/ponto conforme operação | Presença no evento, sem criar ponto de funcionário |
| Revogação | Elimina template ativo, preserva histórico | Elimina template sem excluir convite ou presença |

`capture-check` é apenas orientação: a gravação repete todas as verificações. Não existe confiança em um resultado de captura fornecido pelo cliente. A interface de convidados deixou de oferecer upload de arquivo como fluxo de cadastro. O backend rejeita captura sem vivacidade mesmo que a configuração de verificação do totem seja diferente.

Não houve migração do banco nesta etapa. Templates antigos continuam utilizáveis; novos cadastros de convidados precisam da quantidade configurada (padrão: três). Integrações que enviavam uma única foto devem ser atualizadas. O modelo atual mantém a biometria do convidado por convite: não há compartilhamento automático entre eventos ou com o cadastro funcional.

### Evolução recomendada

Se houver necessidade de reutilizar biometria entre eventos, introduzir por migração uma entidade `Person` por organização, vínculos separados `Employment` e `Invitation`, e `BiometricCredential` com versão, finalidade, validade, base de tratamento e revogação. Uma pessoa pode possuir ambos os vínculos; a autorização deve receber explicitamente o vínculo pretendido. Não fundir pessoas automaticamente só porque o rosto ou o texto do documento coincidem.

Próximas etapas independentes: política configurável de retenção e job de descarte de convidados; transação única para mudança e auditoria; tratamento de múltiplos convites válidos na identificação do totem; consolidação das decisões do totem em serviços de autorização por vínculo. O bloqueio de evento vencido nesta entrega impede novo cadastro/acesso, mas **não executa descarte automático**. Não apresentar expiração de acesso como eliminação do template.

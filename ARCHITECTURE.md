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

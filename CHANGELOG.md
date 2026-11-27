# Histórico de Mudanças — FaceAccess

## [1.0.0] - 2026-11-27

### Implementado
- Arquitetura limpa e desacoplada com backend FastAPI e frontend React 18 / Tailwind CSS.
- Abstração completa para o motor biométrico UniFace (`BiometricEngine`).
- Seleção estrita de modelos com licenças comerciais permissivas (RetinaFace MIT, AdaFace MIT, MiniFASNet Apache-2.0, eDifFIQA-T MIT).
- Criptografia AES-256-GCM para vetores biométricos com chave rotacionável e AAD.
- Trilha de auditoria encadeada com autenticação HMAC-SHA-256.
- Interface web administrativa SaaS completa (Dashboard, Funcionários, Câmera WebRTC para enrollment).
- Modo Kiosk independente e responsivo para totens com suporte a leitura biométrica e PIN de contingência.
- Configuração pronta para Docker Compose com banco de dados PostgreSQL e servidor Nginx.

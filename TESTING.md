# Estratégia e Guia de Testes — FaceAccess

Este guia descreve como os testes automatizados são organizados e executados no FaceAccess.

---

## 1. Níveis de Teste

- **Testes Unitários de Criptografia & Helpers (`app/core/crypto.py`)**:
  - Validação de integridade do AES-256-GCM.
  - Verificação de falha ao adulterar o AAD (*Associated Authenticated Data*).
  - Validação de tempo constante em comparação de segredos.
- **Testes de Integração da API (`tests/test_api_flow.py`)**:
  - Ciclo de vida completo: Login -> Cadastro de funcionário -> Matrícula biométrica -> Ativação de terminal -> Verificação 1:1 Kiosk -> Registro de presença imutável.
- **Smoke Test do Pipeline Biométrico Real (`scripts/download_models.py` & teste local)**:
  - Avaliação do UniFace com imagens sintéticas para medição de latência, taxa de acerto de similaridade, vivacidade e pontuação de qualidade.

---

## 2. Execução dos Testes

```bash
cd backend
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pytest -v tests/
```

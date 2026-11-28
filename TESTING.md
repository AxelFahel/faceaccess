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
# Regressão do cadastro compartilhado

Validação em 27/11/2026: 21 testes de backend e 4 testes de comunicação frontend aprovados; build TypeScript/Vite concluído.

```powershell
cd backend
.venv/Scripts/python.exe -m pytest tests/test_api_flow.py tests/test_enrollment_policy.py -q
cd ../frontend
npm run build
node --test tests/api.test.mjs
```

Os testes acima usam banco temporário e motor biométrico falso. Cobrem qualidade do fluxo, vivacidade ausente, quantidade de capturas, pessoas inconsistentes, vetores inválidos, elegibilidade, organização/unidade, cadastro e revogação de convidado, além do fluxo existente de funcionário/totem. Não medem acurácia biométrica real. `guest_enrollment_case.py` é carregado pelo módulo de integração para compartilhar a mesma fixture de banco.

Os scripts legados `test_guest_mandatory_biometrics.py`, `test_guest_and_blocked.py` e `test_work_schedule_and_exceptions.py` dependem de servidor e arquivos locais; não fazem parte desta execução isolada. O primeiro ainda envia uma única foto: precisa ser adaptado para a quantidade configurada e capturas reais com vivacidade antes de ser usado como teste manual.

Validação operacional pendente: câmera real, orientação por voz, dispositivo de portaria e modelo de vivacidade instalado. Esta alteração não reinicia serviços nem aplica migrações ao banco em uso.

## Totem com orientação visual

Executar também `tests/test_camera_guidance.py` no comando do backend: total de 31 testes aprovados. Casos incluem rosto ausente, distante, próximo demais, deslocado, imagem de câmera vertical, qualidade insuficiente e vivacidade ausente. A integração testa a autenticação da pré-análise e a ausência de decisão de acesso nesse retorno. Build frontend e quatro testes de comunicação passaram.

Conferir no equipamento real: vermelho com orientação de ajuste; azul com varredura ao analisar; verde somente após pré-análise aprovada, com varredura durante o reconhecimento; resultado final separado. Testar negar câmera, ocultar a aba, trocar de modo durante uma requisição e preferência de movimento reduzido. A varredura é um indicador visual de processamento, não uma exibição de landmarks do modelo.

Após a alteração do totem, a API local foi reiniciada preservando sua configuração. Health retornou `ok` e `/api/openapi.json` confirmou a publicação de `/api/v1/kiosk/capture-check`. A validação física com câmera continua pendente.

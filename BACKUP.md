# Procedimentos de Backup, Restauração e Recuperação — FaceAccess

Este documento especifica a estratégia de backup e recuperação de desastres (DR) para instalações corporativas do FaceAccess.

---

## 1. O Que Deve Ser Incluído no Backup

1. **Dump Lógico do Banco PostgreSQL**:
   - Dados organizacionais, registros de colaboradores, presenças, regras de acesso e auditoria.
   - Tabelas de biometria cifrada (`biometric_enrollments`).
2. **Keyring Criptográfico**:
   - Arquivo de segredos contendo `BIOMETRIC_KEYS` e `DATA_ENCRYPTION_KEY`.
   - **Nota**: Sem as chaves correspondentes, os dados biométricos em repouso no dump do banco tornam-se indecifráveis. O backup das chaves deve ser mantido em cofre separado.
3. **Cache de Modelos Locais (Opcional)**:
   - Os arquivos `.onnx` baixados podem ser preservados para agilizar instalações sem conexão à internet.

---

## 2. Procedimento de Backup

### Backup Automatizado do Banco
```bash
# Executado no host do servidor:
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
docker compose exec -T db pg_dump -U faceaccess_user -d faceaccess -F c > /backup/faceaccess_db_${BACKUP_DATE}.dump

# Cifrar o arquivo de dump com GPG ou Age antes de transferir para armazenamento seguro:
gpg --symmetric --cipher-algo AES256 /backup/faceaccess_db_${BACKUP_DATE}.dump
```

---

## 3. Procedimento de Restauração

```bash
# 1. Parar serviços de backend:
docker compose stop backend

# 2. Restaurar o banco de dados:
docker compose exec -T db pg_restore -U faceaccess_user -d faceaccess --clean /backup/faceaccess_db_target.dump

# 3. Reiniciar backend:
docker compose start backend
```

# Conformidade LGPD & Privacidade (Privacy by Design)

O FaceAccess foi projetado sob os princípios de **Privacy by Design** e **Privacy by Default** da Lei Geral de Proteção de Dados (Lei nº 13.709/2018):

1. **Eliminação Imediata de Imagens**: Fotografias capturadas em enrollments ou no kiosk são processadas em memória e descartadas imediatamente após a extração vetorial.
2. **Criptografia Autenticada de Representações Biométricas**: Os vetores biométricos são cifrados com AES-256-GCM com chave rotacionável e *Authenticated Associated Data (AAD)* atrelado ao ID do colaborador.
3. **Alternativa Não Biométrica Obrigatória**: Disponibilização de verificação individual por senha/PIN funcional para funcionários que não puderem ou não quiserem utilizar biometria.
4. **Sem Monitoramento Passivo**: O sistema opera exclusivamente em modalidade 1:1 com participação ativa e voluntária. Não há detecção contínua ou vigilância indiscriminada.
5. **Trilha de Auditoria com Hash Encadeado**: Registro imutável de mutações assinado com HMAC-SHA-256.

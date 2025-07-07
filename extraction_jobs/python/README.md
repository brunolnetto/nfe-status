# Monitor de Status NFe

Monitora e armazena periodicamente o status dos serviços da NFe, realizando scraping do portal oficial, persistindo o histórico em banco SQLite (com SCD2), exportando para JSON e aplicando políticas de retenção automáticas.

---

## ✨ Funcionalidades

- **Scraping automatizado** do status dos serviços NFe via Playwright.
- **Persistência histórica** (SCD2) em banco SQLite.
- **Exportação para JSON** com escrita atômica (segura contra corrupção).
- **Política de retenção** automática por idade (dias) e tamanho do banco (MB).
- **Configuração flexível** via variáveis de ambiente (inclusive nomes de tabelas/campos).
- **Controle de versão do schema** e migração automática.
- **Timestamps em UTC** para consistência e segurança.
- **Logs detalhados** e configuráveis.
- **Testes automatizados** com alta cobertura.

---

## 🚀 Como Usar

1. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

2. **Configure as variáveis de ambiente** (opcional, veja abaixo).

3. **Execute manualmente:**
   ```bash
   python nfe_status.py
   ```

4. **Ou agende via cron (exemplo a cada 15 minutos):**
   ```
   */15 * * * * /usr/bin/env bash -c 'cd /caminho/para/seu/projeto && /usr/bin/python3 nfe_status.py'
   ```

---

## ⚙️ Configuração

Todas as opções podem ser definidas via variáveis de ambiente:

| Variável                      | Padrão                | Descrição                                               |
|-------------------------------|-----------------------|---------------------------------------------------------|
| `NFE_URL`                     | URL oficial NFe       | URL da página de disponibilidade                        |
| `NFE_DB_PATH`                 | `disponibilidade.db`  | Caminho do banco SQLite                                 |
| `NFE_JSON_PATH`               | `disponibilidade.json`| Caminho do arquivo JSON de saída                        |
| `NFE_LOG_LEVEL`               | `INFO`                | Nível de log (DEBUG, INFO, WARNING, ERROR)              |
| `NFE_LOG_FILE`                | `nfe_status.log`      | Caminho do arquivo de log                               |
| `NFE_RETENTION_MAX_MB`        | `10`                  | Tamanho máximo do banco (MB) antes de deletar antigos   |
| `NFE_RETENTION_MAX_DAYS`      | `30`                  | Idade máxima dos registros (dias)                       |
| `NFE_TABLE_NAME`              | `disponibilidade`     | Nome da tabela principal                                |
| `NFE_FIELD_AUTORIZADOR`       | `autorizador`         | Nome do campo: autorizador                              |
| `NFE_FIELD_STATUS_JSON`       | `status_json`         | Nome do campo: status JSON                              |
| `NFE_FIELD_VALID_FROM`        | `valid_from`          | Nome do campo: início da validade                       |
| `NFE_FIELD_VALID_TO`          | `valid_to`            | Nome do campo: fim da validade                          |
| `NFE_FIELD_IS_CURRENT`        | `is_current`          | Nome do campo: flag de registro atual                   |

---

## 🗄️ Esquema do Banco de Dados

Todos os campos são configuráveis via variáveis de ambiente:

```sql
CREATE TABLE disponibilidade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    autorizador TEXT NOT NULL,
    status_json TEXT NOT NULL,
    valid_from TEXT NOT NULL, -- UTC ISO8601
    valid_to TEXT,            -- UTC ISO8601
    is_current INTEGER NOT NULL DEFAULT 1
);
```

- **Controle de versão do schema:** O script gerencia e migra o schema automaticamente conforme evoluções.

---

## 🕒 Política de Retenção

- **Por idade:** Registros com `valid_to` mais antigos que `NFE_RETENTION_MAX_DAYS` (padrão: 30 dias) são removidos.
- **Por tamanho:** Se o arquivo do banco exceder `NFE_RETENTION_MAX_MB` (padrão: 10MB), registros antigos são removidos até ficar abaixo do limite.
- Ambas as políticas são aplicadas após cada execução.

---

## 🕰️ Timestamps

- **Todos os horários são armazenados e comparados em UTC** (ISO8601), garantindo consistência e segurança contra problemas de fuso horário.

---

## 📤 Saída JSON

- O arquivo JSON é gerado **de forma atômica** (escrito em arquivo temporário e renomeado), evitando corrupção.
- Exemplo de saída:
```json
{
  "checked_at": "2024-01-15T10:30:00Z",
  "statuses": [
    {
      "Autorizador": "SVAN",
      "Status": "verde",
      "tipo": "Sefaz Virtual Ambiente Nacional",
      "ufs_autorizador": ["MA"]
    }
  ],
  "metadata": {
    "total_records": 1,
    "generated_at": "2024-01-15T10:30:00Z",
    "version": "2.0"
  }
}
```

---

## 🛡️ Tratamento de Erros

- **Rede:** Timeout, HTTP e falhas de conexão.
- **Parsing:** Estrutura HTML inválida ou dados malformados.
- **Banco:** Conexão, bloqueio, corrupção e migração de schema.
- **Arquivo:** Permissões, espaço em disco, escrita atômica.

---

## 📝 Logs

- Logs detalhados em console e arquivo, com nível configurável.
- Exemplo:
  ```
  2024-01-15 10:30:00,123 - __main__ - INFO - Iniciando monitoramento NFE
  2024-01-15 10:30:01,456 - __main__ - INFO - HTML coletado com sucesso
  2024-01-15 10:30:02,789 - __main__ - INFO - 15 linhas processadas
  ```

---

## 🧪 Testes

- Testes unitários e de integração cobrindo scraping, persistência, política de retenção, escrita JSON, erros e contexto.
- Para rodar:
  ```bash
  python test_nfe_status.py
  ```

---

## 📦 Dependências

- **playwright**: Automação de navegador/headless scraping
- **beautifulsoup4**: Parsing HTML
- **lxml**: Backend rápido para parsing
- **sqlite3**: Banco de dados local
- **pytest** (opcional): Testes

---

## 📄 Licença

MIT. Veja o arquivo LICENSE.

---

## ⚠️ Aviso

Este script é para fins educacionais e de monitoramento. Respeite sempre os termos de uso e o robots.txt do site alvo.

---

## 🤝 Contribuição

1. Faça um fork
2. Crie um branch de feature
3. Implemente e teste
4. Envie um Pull Request

---

Dúvidas ou sugestões? Abra uma issue!
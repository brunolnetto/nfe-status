# Monitor de Status NFe (Python + PostgreSQL)

Monitora e armazena periodicamente o status dos serviços da NFe, realizando scraping do portal oficial, persistindo o histórico em banco PostgreSQL (SCD2), exportando para JSON e aplicando políticas de retenção.

---

## 🚀 Como Usar

1. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

2. **Configure o banco PostgreSQL:**
   ```sh
   createdb -h <host> -U <user> nfe
   # ou via psql: CREATE DATABASE nfe;
   ```

3. **Defina as variáveis de ambiente (exemplo):**
   ```sh
   export NFE_PG_HOST=localhost
   export NFE_PG_USER=postgres
   export NFE_PG_PASSWORD=postgres
   export NFE_PG_DATABASE=nfe
   # ...ou defina no .env
   ```

4. **Execute:**
   ```bash
   python nfe_status.py
   ```

---

## ⚙️ Configuração (Principais variáveis)

| Variável            | Padrão      | Descrição                  |
|---------------------|-------------|----------------------------|
| NFE_PG_HOST         | localhost   | Host do PostgreSQL         |
| NFE_PG_PORT         | 5432        | Porta do PostgreSQL        |
| NFE_PG_USER         | postgres    | Usuário do PostgreSQL      |
| NFE_PG_PASSWORD     | postgres    | Senha do PostgreSQL        |
| NFE_PG_DATABASE     | nfe         | Nome do banco de dados     |
| NFE_TABLE_NAME      | disponibilidade | Nome da tabela         |
| NFE_JSON_PATH       | disponibilidade.json | Caminho do JSON    |
| NFE_LOG_FILE        | nfe_status.log | Caminho do log         |
| NFE_RETENTION_MAX_DAYS | 30        | Retenção (dias)            |

---

## 🗄️ Exemplo de Tabela PostgreSQL

```sql
CREATE TABLE disponibilidade (
    id SERIAL PRIMARY KEY,
    autorizador TEXT NOT NULL,
    status_json TEXT NOT NULL,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP,
    is_current INTEGER NOT NULL DEFAULT 1
);
```

---

## 📝 Logging Rotativo

O log é gravado em `nfe_status.log` com rotação automática (10MB, 7 arquivos). Exemplo de configuração:

```python
import logging
from logging.handlers import RotatingFileHandler
handler = RotatingFileHandler('nfe_status.log', maxBytes=10_000_000, backupCount=7)
logging.basicConfig(level=logging.INFO, handlers=[handler])
```

---

## ⏰ Agendamento (cron)

Exemplo para rodar a cada hora:
```sh
0 * * * * python /caminho/absoluto/para/nfe_status.py
```
> Os logs já vão para o arquivo configurado. Redirecione apenas erros críticos se desejar: `2>> erro_cron.log`

---

## 🧪 Testes

Para rodar:
```bash
python test_nfe_status.py
```

---

## 📦 Dependências
- playwright
- beautifulsoup4
- lxml
- psycopg2

---

## 🤝 Contribuição
1. Fork o repositório
2. Crie um branch
3. Implemente e teste
4. Envie um Pull Request

---

Dúvidas? Abra uma issue!
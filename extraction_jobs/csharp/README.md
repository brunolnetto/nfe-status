# NFE Status CSharp

Uma implementação em C# para monitorar e armazenar o status dos serviços da NFe brasileira. Realiza scraping do portal oficial, persiste o histórico em banco de dados PostgreSQL (SCD2), exporta para JSON e aplica políticas automáticas de retenção.

---

## ✨ Funcionalidades

- Coleta automática do status dos serviços NFe usando Playwright para .NET.
- Persistência histórica (SCD2) em PostgreSQL.
- Exportação atômica para JSON (seguro contra corrupção).
- Política de retenção automática por idade (dias).
- Configuração flexível via variáveis de ambiente ou arquivo JSON.
- Controle de versão do schema e migração automática.
- Timestamps em UTC para consistência.
- Log detalhado e configurável.
- Testes automatizados com xUnit.

---

## 🚀 Como Usar

1. **Instale o .NET 8 SDK**  
   [Baixe e instale o .NET 8](https://dotnet.microsoft.com/pt-br/download/dotnet/8.0)

2. **Instale as dependências:**  
   No diretório do projeto:
   ```bash
   dotnet restore
   ```

3. **Configure as variáveis de ambiente** (opcional, veja abaixo).

4. **Execute manualmente:**
   ```bash
   dotnet run --project nfe-status-csharp
   ```

5. **Ou agende via cron (exemplo a cada 15 minutos):**
   ```
   */15 * * * * dotnet run --project /caminho/absoluto/para/nfe-status-csharp appsettings.json >> cron.log 2>&1
   ```

---

## ⚙️ Configuração

Todas as opções podem ser definidas por variáveis de ambiente **ou** por um arquivo JSON (`appsettings.json`).

| Variável                  | Padrão                        | Descrição                                      |
|--------------------------|-------------------------------|------------------------------------------------|
| `NFE_URL`                | URL oficial da NFe            | URL da página de status                        |
| `NFE_PG_HOST`            | `localhost`                   | Host do PostgreSQL                             |
| `NFE_PG_PORT`            | `5432`                        | Porta do PostgreSQL                            |
| `NFE_PG_USER`            | `postgres`                    | Usuário do PostgreSQL                          |
| `NFE_PG_PASSWORD`        | `postgres`                    | Senha do PostgreSQL                            |
| `NFE_PG_DATABASE`        | `nfe`                         | Nome do banco de dados                         |
| `NFE_JSON_PATH`          | `disponibilidade.json`        | Caminho do arquivo JSON de saída               |
| `NFE_LOG_LEVEL`          | `Information`                 | Nível de log (Debug, Information, Warning, Error)|
| `NFE_LOG_FILE`           | `nfe_status.log`              | Caminho do arquivo de log                      |
| `NFE_RETENTION_MAX_DAYS` | `30`                          | Idade máxima dos registros (dias)              |
| `NFE_TABLE_NAME`         | `disponibilidade`             | Nome da tabela principal                       |

### Usando um arquivo de configuração JSON

Crie um arquivo chamado `appsettings.json` no diretório do projeto com conteúdo como:

```json
{
  "PgConnectionString": "Host=customhost;Port=5432;Username=meuusuario;Password=minhasenha;Database=meubanco",
  "Url": "https://www.nfe.fazenda.gov.br/portal/disponibilidade.aspx",
  "JsonPath": "disponibilidade.json",
  "LogLevel": "Information",
  "LogFile": "nfe_status.log",
  "RetentionMaxMb": 10,
  "RetentionMaxDays": 30,
  "DbSchemaVersion": 2,
  "TableName": "disponibilidade"
}
```

Execute o projeto com:

```
dotnet run appsettings.json
```

Qualquer variável de ambiente definida irá sobrescrever o valor do arquivo JSON.

---

## 🗄️ Esquema do Banco de Dados (PostgreSQL)

```sql
CREATE TABLE disponibilidade (
    id SERIAL PRIMARY KEY,
    autorizador TEXT,
    status_json TEXT,
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current INTEGER DEFAULT 1
);
```

---

## 🕒 Política de Retenção

- **Por idade:** Registros com `valid_from` mais antigos que `NFE_RETENTION_MAX_DAYS` são removidos.

---

## 📤 Saída JSON

- O arquivo JSON é escrito de forma atômica (arquivo temporário + rename).
- Exemplo de saída:
  ```json
  {
    "checked_at": "2024-01-15T10:30:00Z",
    "statuses": [
      {
        "autorizador": "SVAN",
        "status": "verde",
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

## 🧪 Testes

- Os testes estão no projeto `NfeStatusCSharp.Tests`.
- Para rodar:
  ```bash
  dotnet test NfeStatusCSharp.Tests
  ```

---

## 📦 Dependências

- Microsoft.Playwright
- HtmlAgilityPack
- System.Text.Json
- Microsoft.Extensions.Logging
- Npgsql
- xUnit
- Serilog

---

## 📄 Licença

MIT. Veja o arquivo LICENSE.

---

## 🤝 Contribuindo

1. Faça um fork do repositório
2. Crie um branch para sua feature
3. Implemente e teste
4. Envie um Pull Request

---

Dúvidas ou sugestões? Abra uma issue!

## Agendamento Automático (Cron Job)

Você pode agendar a execução automática deste projeto para coletar e salvar o status da NFE periodicamente. Veja como configurar em diferentes sistemas operacionais:

### Linux (usando cron)

1. Gere o comando para rodar o projeto, por exemplo:
   ```sh
   cd /caminho/para/seu/projeto/extraction_jobs/csharp/nfe-status-csharp
   dotnet run appsettings.json
   ```
2. Edite o crontab:
   ```sh
   crontab -e
   ```
3. Adicione uma linha para executar a cada hora (exemplo):
   ```
   0 * * * * dotnet run --project /caminho/absoluto/para/nfe-status-csharp appsettings.json
   ```
   > Os logs do sistema já serão gravados automaticamente em `nfe_status.log` (e arquivos rotacionados) pelo Serilog. Não é necessário redirecionar a saída para outro arquivo.
   > Se desejar capturar apenas erros do processo (ex: falha do .NET), use: `2>> erro_cron.log`

### Windows (usando Agendador de Tarefas)

1. Abra o "Agendador de Tarefas" (Task Scheduler).
2. Crie uma nova tarefa básica.
3. Defina a frequência desejada (ex: diária, a cada hora, etc).
4. Na ação, escolha "Iniciar um programa" e configure:
   - **Programa/script:** `dotnet`
   - **Argumentos:** `run appsettings.json`
   - **Iniciar em:** `C:\Users\SeuUsuario\github\nfe-status\extraction_jobs\csharp\nfe-status-csharp`
5. Salve e ative a tarefa.

> Certifique-se de que o .NET SDK está instalado e disponível no PATH do sistema.

### Observações
- Sempre teste manualmente o comando antes de agendar.
- Use variáveis de ambiente ou o arquivo `appsettings.json` para configurar a conexão e outros parâmetros.
- Consulte os logs para verificar se a execução automática está funcionando corretamente.

## 📝 Logs e Rotação Automática

O projeto utiliza [Serilog](https://serilog.net/) para logging estruturado e rotação automática de arquivos de log.

- O log é gravado no arquivo definido por `LogFile` (padrão: `nfe_status.log`).
- A rotação ocorre diariamente **ou** ao atingir 10 MB por arquivo.
- Até 7 arquivos antigos de log são mantidos automaticamente.
- O comportamento pode ser customizado alterando os parâmetros em `Program.cs` ou via configuração.

**Exemplo de configuração padrão:**
```csharp
Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Information()
    .WriteTo.File(
        config.LogFile,
        rollingInterval: RollingInterval.Day,
        fileSizeLimitBytes: 10_000_000, // 10 MB
        rollOnFileSizeLimit: true,
        retainedFileCountLimit: 7,
        shared: true
    )
    .CreateLogger();
```

> Os logs são essenciais para auditoria e troubleshooting. Consulte os arquivos rotacionados para histórico.

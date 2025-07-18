# NFE Status CSharp

## Configuration

You can configure the application using either environment variables or a JSON config file (e.g., `appsettings.json`).

### Using a JSON Config File

Create a file named `appsettings.json` in the project directory with content like:

```json
{
  "PgConnectionString": "Host=customhost;Port=5432;Username=myuser;Password=mypass;Database=mydb",
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

Run the application with:

```
dotnet run appsettings.json
```

### Overriding with Environment Variables

Any value set as an environment variable will override the value from the config file. For example:

- `NFE_PG_HOST`, `NFE_PG_PORT`, `NFE_PG_USER`, `NFE_PG_PASSWORD`, `NFE_PG_DATABASE` (for connection string)
- `NFE_URL`, `NFE_JSON_PATH`, `NFE_LOG_LEVEL`, `NFE_LOG_FILE`, `NFE_RETENTION_MAX_MB`, `NFE_RETENTION_MAX_DAYS`, `NFE_DB_SCHEMA_VERSION`, `NFE_TABLE_NAME`

If no config file is provided, the application will use environment variables or default values. 
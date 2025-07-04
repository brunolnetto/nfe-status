# NFe Status Monitor (C#)

A C# implementation for monitoring and storing the status of Brazilian NFe services. It scrapes the official portal, persists historical data in SQLite (with SCD2), exports to JSON, and applies automatic retention policies.

---

## ✨ Features

- Automated scraping of NFe service status using Playwright for .NET.
- Historical persistence (SCD2) in SQLite.
- Atomic JSON export (safe against corruption).
- Automatic retention policy by age (days) and database size (MB).
- Flexible configuration via environment variables.
- Schema version control and automatic migration.
- UTC timestamps for consistency.
- Detailed, configurable logging.
- Automated tests with xUnit.

---

## 🚀 How to Use

1. **Install .NET 8 SDK**  
   [Download and install .NET 8](https://dotnet.microsoft.com/en-us/download/dotnet/8.0)

2. **Install dependencies:**  
   In the project directory:
   ```bash
   dotnet restore
   ```

3. **Configure environment variables** (optional, see below).

4. **Run manually:**
   ```bash
   dotnet run --project nfe-status-csharp
   ```

5. **Or schedule via cron (example every 15 minutes):**
   ```
   */15 * * * * NFE_DB_PATH=/absolute/path/disponibilidade.db NFE_JSON_PATH=/absolute/path/disponibilidade.json NFE_LOG_FILE=/absolute/path/nfe_status.log dotnet run --project /absolute/path/to/nfe-status-csharp
   ```

---

## ⚙️ Configuration

All options can be set via environment variables:

| Variable                | Default                   | Description                                 |
|-------------------------|---------------------------|---------------------------------------------|
| `NFE_URL`               | Official NFe URL          | Status page URL                             |
| `NFE_DB_PATH`           | `disponibilidade.db`      | SQLite database path                        |
| `NFE_JSON_PATH`         | `disponibilidade.json`    | Output JSON file path                       |
| `NFE_LOG_LEVEL`         | `Information`             | Log level (Debug, Information, Warning, Error)|
| `NFE_LOG_FILE`          | `nfe_status.log`          | Log file path                               |
| `NFE_RETENTION_MAX_MB`  | `10`                      | Max DB size (MB) before deleting old records|
| `NFE_RETENTION_MAX_DAYS`| `30`                      | Max record age (days)                       |
| `NFE_TABLE_NAME`        | `disponibilidade`         | Main table name                             |

---

## 🗄️ Database Schema

```sql
CREATE TABLE disponibilidade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    autorizador TEXT NOT NULL,
    status_json TEXT NOT NULL,
    valid_from TEXT NOT NULL, -- UTC ISO8601
    valid_to TEXT,
    is_current INTEGER NOT NULL DEFAULT 1
);
```

---

## 🕒 Retention Policy

- **By age:** Records with `valid_to` older than `NFE_RETENTION_MAX_DAYS` are removed.
- **By size:** If the DB file exceeds `NFE_RETENTION_MAX_MB`, old records are deleted until under the limit.

---

## 📤 JSON Output

- The JSON file is written atomically (temp file + rename).
- Example output:
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

## 🧪 Tests

- Tests are in the `NfeStatusCSharp.Tests` project.
- To run:
  ```bash
  dotnet test ../NfeStatusCSharp.Tests
  ```

---

## 📦 Dependencies

- Microsoft.Playwright
- HtmlAgilityPack
- System.Data.SQLite
- System.Text.Json
- Microsoft.Extensions.Logging
- xUnit

---

## 📄 License

MIT. See LICENSE file.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Implement and test
4. Submit a Pull Request

---

Questions or suggestions? Open an issue!
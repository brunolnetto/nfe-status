# NFe Status Monitor Suite

A multi-language suite for monitoring and storing the status of Brazilian NFe services, with both Python and C# implementations.

---

## Projects

- **nfe-status/python/**  
  Python implementation (see [python/README.md](python/README.md) for full details)
- **nfe-status/csharp/nfe-status-csharp/**  
  C# implementation (see [csharp/README.md](csharp/README.md) for full details)

---

## Features

- Automated scraping of NFe service status from the official portal.
- Historical persistence (SCD2) in SQLite.
- Atomic JSON export.
- Automatic retention policy by age and size.
- Flexible configuration via environment variables.
- Schema version control and migration.
- UTC timestamps for consistency.
- Detailed, configurable logging.
- Automated tests.

---

## Quick Start

### Python

```bash
cd nfe-status/python
pip install -r requirements.txt
playwright install
python3 nfe_status.py
```

### C#

```bash
cd nfe-status/csharp/nfe-status-csharp
dotnet restore
dotnet run --project nfe-status-csharp
```

---

## Scheduling

- Use `cron` to schedule periodic runs (see each project's README for examples).

---

## License

MIT. See LICENSE file.

---

## Contributing

See each project's README for contribution guidelines.

---

Questions or suggestions? Open an issue!

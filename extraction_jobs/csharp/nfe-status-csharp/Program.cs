using System;
using System.IO;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Playwright;
using HtmlAgilityPack;
using System.Collections.Generic;
using Npgsql;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Globalization;
using System.Text;
using ILogger = Microsoft.Extensions.Logging.ILogger;
using System.Data.Common;
using NodaTime;
using NodaTime.TimeZones;

namespace NfeStatusCSharp
{
    public class NfeStatusResult
    {
        public string? CheckedAt { get; set; }
        public List<Dictionary<string, object?>> Statuses { get; set; } = new();
        public bool Success { get; set; }
        public string? ErrorMessage { get; set; }
    }

    public class Program
    {
        static async Task Main(string[] args)
        {
            NfeConfig config;
            if (args.Length > 0 && File.Exists(args[0]))
            {
                config = NfeConfig.LoadFromFile(args[0]);
                // Override with env vars if set
                var envConfig = NfeConfig.LoadFromEnvironment();
                if (!string.IsNullOrEmpty(envConfig.PgConnectionString)) config.PgConnectionString = envConfig.PgConnectionString;
                if (!string.IsNullOrEmpty(envConfig.Url)) config.Url = envConfig.Url;
                if (!string.IsNullOrEmpty(envConfig.JsonPath)) config.JsonPath = envConfig.JsonPath;
                if (!string.IsNullOrEmpty(envConfig.LogLevel)) config.LogLevel = envConfig.LogLevel;
                if (!string.IsNullOrEmpty(envConfig.LogFile)) config.LogFile = envConfig.LogFile;
                if (envConfig.RetentionMaxMb != 10) config.RetentionMaxMb = envConfig.RetentionMaxMb;
                if (envConfig.RetentionMaxDays != 30) config.RetentionMaxDays = envConfig.RetentionMaxDays;
                if (envConfig.DbSchemaVersion != 2) config.DbSchemaVersion = envConfig.DbSchemaVersion;
                if (!string.IsNullOrEmpty(envConfig.TableName)) config.TableName = envConfig.TableName;
            }
            else
            {
                config = NfeConfig.LoadFromEnvironment();
            }

            // Configurar Serilog para rotação de logs
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

            var loggerFactory = LoggerFactory.Create(builder =>
            {
                builder.AddSerilog();
            });
            var logger = loggerFactory.CreateLogger<Program>();

            logger.LogInformation("Starting NFE status monitor...");

            try
            {
                // Fetch HTML using Playwright
                string? html = await FetchHtmlAsync(config.Url, logger);
                logger.LogInformation($"Fetched HTML length: {html?.Length}");
                if (html == null)
                {
                    logger.LogError("Fetched HTML is null");
                    return;
                }
                // Parse HTML and extract NFE status
                var nfeResult = ParseNfeStatusHtml(html, logger);
                logger.LogInformation($"Parsed {nfeResult.Statuses.Count} NFE status rows.");

                // Persist to PostgreSQL with SCD2 logic
                var db = new NfeStatusDatabase(config.PgConnectionString, config.TableName, logger);
                db.Initialize();
                db.PersistStatuses(nfeResult);

                // Apply retention policy
                db.ApplyRetentionPolicy(config.RetentionMaxDays, config.RetentionMaxMb);

                // Serialize to JSON file
                SaveJsonResult(config.JsonPath, nfeResult, logger);

                logger.LogInformation("NFE status monitor completed successfully.");
            }
            catch (Exception ex)
            {
                logger.LogError($"Fatal error in NFE status monitor: {ex.Message}");
            }
            finally
            {
                Log.CloseAndFlush();
            }
        }

        static async Task<string> FetchHtmlAsync(string url, ILogger logger)
        {
            using var playwright = await Playwright.CreateAsync();
            await using var browser = await playwright.Chromium.LaunchAsync(new BrowserTypeLaunchOptions { Headless = true });
            var page = await browser.NewPageAsync();
            logger.LogInformation($"Navigating to {url}");
            var response = await page.GotoAsync(url);
            if (response == null || !response.Ok)
            {
                logger.LogError($"Failed to load page: {url}");
                throw new Exception($"Failed to load page: {url}");
            }
            var content = await page.ContentAsync();
            logger.LogInformation("Successfully fetched HTML content");
            return content;
        }

        public static NfeStatusResult ParseNfeStatusHtml(string html, ILogger logger)
        {
            var result = new NfeStatusResult();
            try
            {
                if (html == null)
                {
                    logger.LogError("HTML input is null");
                    result.Success = false;
                    result.ErrorMessage = "HTML input is null";
                    return result;
                }
                var doc = new HtmlDocument();
                doc.LoadHtml(html);
                // Find the table by id (as in the Python code)
                var table = doc.GetElementbyId("ctl00_ContentPlaceHolder1_gdvDisponibilidade2");
                if (table == null)
                {
                    logger.LogError("NFE status table not found in HTML.");
                    result.Success = false;
                    result.ErrorMessage = "Table not found";
                    return result;
                }
                // Extract caption for timestamp
                var captionNode = table.SelectSingleNode(".//caption");
                string? checkedAt = null;
                if (captionNode != null)
                {
                    var captionText = captionNode.InnerText;
                    var match = Regex.Match(captionText, @"Última Verificação:\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})");
                    if (match.Success)
                    {
                        if (DateTime.TryParseExact(match.Groups[1].Value, "dd/MM/yyyy HH:mm:ss", null, System.Globalization.DateTimeStyles.AssumeLocal, out var dt))
                        {
                            checkedAt = dt.ToUniversalTime().ToString("o");
                        }
                    }
                }
                result.CheckedAt = checkedAt;
                // Extract headers
                var headerRow = table.SelectSingleNode(".//tr[1]");
                var headers = new List<string>();
                var thNodes = headerRow?.SelectNodes(".//th");
                if (thNodes == null)
                {
                    logger.LogError("Table headers not found");
                    result.Success = false;
                    result.ErrorMessage = "Table headers not found";
                    return result;
                }
                foreach (var th in thNodes)
                {
                    headers.Add(NormalizeKey(th.InnerText.Trim()));
                }
                // Validate headers
                if (!headers.Contains("autorizador") || headers.Count < 2)
                {
                    logger.LogError($"Invalid table headers: {string.Join(", ", headers)}");
                    result.Success = false;
                    result.ErrorMessage = "Invalid table structure";
                    return result;
                }
                // Prepare image map and autorizador info (as in Python)
                var imgMap = new Dictionary<string, string> {
                    {"bola_verde_P.png", "verde"},
                    {"bola_amarela_P.png", "amarelo"},
                    {"bola_vermelho_P.png", "vermelho"},
                    {"bola_cinza_P.png", "cinza"}
                };
                var autorizadorInfo = new Dictionary<string, Dictionary<string, object>> {
                    {"SVAN", new Dictionary<string, object>{{"tipo", "Sefaz Virtual Ambiente Nacional"}, {"ufs_autorizador", new List<string>{"MA"}}}},
                    {"SVRS", new Dictionary<string, object>{{"tipo", "Sefaz Virtual Rio Grande do Sul"}, {"ufs_autorizador", new List<string>{"AC","AL","AP","CE","DF","ES","PA","PB","PI","RJ","RN","RO","RR","SC","SE","TO"}}, {"ufs_consulta_cadastro", new List<string>{"AC","ES","RN","PB","SC"}}}},
                    {"SVC-AN", new Dictionary<string, object>{{"tipo", "Contingência Nacional"}, {"ufs_contingencia", new List<string>{"AC","AL","AP","CE","DF","ES","MG","PA","PB","PI","RJ","RN","RO","RR","RS","SC","SE","SP","TO"}}}},
                    {"SVC-RS", new Dictionary<string, object>{{"tipo", "Contingência RS"}, {"ufs_contingencia", new List<string>{"AM","BA","GO","MA","MS","MT","PE","PR"}}}}
                };
                // Extract data rows
                var dataRows = table.SelectNodes(".//tr[position()>1]");
                if (dataRows != null)
                {
                    foreach (var row in dataRows)
                    {
                        var cells = row.SelectNodes(".//td");
                        if (cells == null || cells.Count != headers.Count)
                            continue;
                        var dict = new Dictionary<string, object?>();
                        string? autorizador = null;
                        for (int i = 0; i < headers.Count; i++)
                        {
                            var cell = cells[i];
                            var key = headers[i];
                            var img = cell.SelectSingleNode(".//img");
                            if (img != null && img.Attributes["src"] != null)
                            {
                                var filename = img.Attributes["src"].Value.Split('/').Last();
                                dict[key] = imgMap.ContainsKey(filename) ? imgMap[filename] : "desconhecido";
                                if (!imgMap.ContainsKey(filename))
                                    logger.LogWarning($"Unknown image filename: {filename}");
                            }
                            else
                            {
                                var text = cell.InnerText.Trim();
                                dict[key] = string.IsNullOrEmpty(text) ? null : text;
                            }
                            if (key == "autorizador")
                                autorizador = dict[key]?.ToString();
                        }
                        // Enrich metadata
                        if (!string.IsNullOrEmpty(autorizador) && autorizadorInfo.ContainsKey(autorizador))
                        {
                            foreach (var kv in autorizadorInfo[autorizador])
                            {
                                if (kv.Value is List<string> list)
                                    dict[NormalizeKey(kv.Key)] = list;
                                else
                                    dict[NormalizeKey(kv.Key)] = kv.Value;
                            }
                        }
                        // Build normalized dictionary for JSON output
                        var normalizedDict = new Dictionary<string, object?>();
                        foreach (var kv in dict)
                        {
                            normalizedDict[NormalizeKey(kv.Key)] = kv.Value;
                        }
                        result.Statuses.Add(normalizedDict);
                    }
                }
                result.Success = true;
            }
            catch (Exception ex)
            {
                logger.LogError($"Error parsing HTML: {ex.Message}");
                result.Success = false;
                result.ErrorMessage = ex.Message;
            }
            return result;
        }

        // Normalize a string to snake_case, ASCII-only, no accents
        public static string NormalizeKey(string input)
        {
            if (string.IsNullOrEmpty(input)) return input;
            // Remove accents
            string normalized = input.Normalize(System.Text.NormalizationForm.FormD);
            var sb = new StringBuilder();
            foreach (var c in normalized)
            {
                var uc = CharUnicodeInfo.GetUnicodeCategory(c);
                if (uc != UnicodeCategory.NonSpacingMark)
                    sb.Append(c);
            }
            normalized = sb.ToString().Normalize(System.Text.NormalizationForm.FormC);
            // Replace spaces and special chars with underscores, make lower
            normalized = Regex.Replace(normalized, "[^a-zA-Z0-9]", "_");
            normalized = Regex.Replace(normalized, "_+", "_");
            normalized = normalized.Trim('_').ToLowerInvariant();
            return normalized;
        }

        static void SaveJsonResult(string jsonPath, NfeStatusResult result, ILogger logger)
        {
            try
            {
                var dir = Path.GetDirectoryName(jsonPath);
                if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                    Directory.CreateDirectory(dir);
                var options = new JsonSerializerOptions { WriteIndented = true };
                options.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter());
                var tempFile = Path.GetTempFileName();
                File.WriteAllText(tempFile, JsonSerializer.Serialize(result, options));
                File.Move(tempFile, jsonPath, true);
                logger.LogInformation($"Saved JSON result to {jsonPath}");
            }
            catch (Exception ex)
            {
                logger.LogError($"Failed to save JSON file: {ex.Message}");
            }
        }
    }

    public class NfeStatusDatabase
    {
        private readonly string _connectionString;
        private readonly string _tableName;
        private readonly ILogger _logger;

        public NfeStatusDatabase(string connectionString, string tableName, ILogger logger)
        {
            _connectionString = connectionString;
            _tableName = tableName;
            _logger = logger;
        }

        public void EnsureDatabaseExists()
        {
            try
            {
                using var conn = new Npgsql.NpgsqlConnection(_connectionString);
                conn.Open();
            }
            catch (Npgsql.PostgresException ex) when (ex.SqlState == "3D000") // database does not exist
            {
                _logger.LogWarning($"Database does not exist. Attempting to create: {GetDatabaseNameFromConnectionString(_connectionString)}");
                CreateDatabase();
            }
            catch (Exception ex)
            {
                _logger.LogError($"Failed to connect to database: {ex.Message}");
                throw;
            }
        }

        private void CreateDatabase()
        {
            var builder = new Npgsql.NpgsqlConnectionStringBuilder(_connectionString);
            var dbName = builder.Database;
            builder.Database = "postgres";
            using var conn = new Npgsql.NpgsqlConnection(builder.ConnectionString);
            conn.Open();
            using var cmd = conn.CreateCommand();
            cmd.CommandText = $"CREATE DATABASE \"{dbName}\";";
            try
            {
                cmd.ExecuteNonQuery();
                _logger.LogInformation($"Database '{dbName}' created successfully.");
            }
            catch (Npgsql.PostgresException ex) when (ex.SqlState == "42P04") // already exists
            {
                _logger.LogWarning($"Database '{dbName}' already exists.");
            }
        }

        private static string GetDatabaseNameFromConnectionString(string connStr)
        {
            var builder = new Npgsql.NpgsqlConnectionStringBuilder(connStr);
            return builder.Database;
        }

        public void Initialize()
        {
            EnsureDatabaseExists();
            using var conn = new NpgsqlConnection(_connectionString);
            conn.Open();
            var cmd = conn.CreateCommand();
            cmd.CommandText = $@"
                CREATE TABLE IF NOT EXISTS {_tableName} (
                    id SERIAL PRIMARY KEY,
                    autorizador TEXT,
                    status_json TEXT,
                    valid_from TIMESTAMP,
                    valid_to TIMESTAMP,
                    is_current INTEGER DEFAULT 1
                );";
            cmd.ExecuteNonQuery();
        }

        public void PersistStatuses(NfeStatusResult result)
        {
            if (!result.Success)
            {
                _logger.LogError("Cannot persist invalid data");
                return;
            }
            using var conn = new NpgsqlConnection(_connectionString);
            conn.Open();
            foreach (var row in result.Statuses)
            {
                var autorizador = row.ContainsKey("autorizador") ? row["autorizador"]?.ToString() : null;
                if (string.IsNullOrEmpty(autorizador))
                    continue;
                var statusJson = System.Text.Json.JsonSerializer.Serialize(row);
                var tz = DateTimeZoneProviders.Tzdb["America/Sao_Paulo"];
                var nowSp = SystemClock.Instance.GetCurrentInstant().InZone(tz).ToDateTimeUtc();
                // SCD2: Close previous record if status changed
                var checkCmd = conn.CreateCommand();
                checkCmd.CommandText = $"SELECT id, status_json FROM {_tableName} WHERE autorizador = @aut AND is_current = 1 ORDER BY valid_from DESC LIMIT 1";
                checkCmd.Parameters.AddWithValue("@aut", autorizador);
                using var reader = checkCmd.ExecuteReader();
                bool statusChanged = true;
                int? prevId = null;
                string? prevJson = null;
                if (reader.Read())
                {
                    prevId = reader.GetInt32(0);
                    prevJson = reader.GetString(1);
                    if (prevJson == statusJson)
                        statusChanged = false;
                }
                reader.Close();
                if (statusChanged)
                {
                    if (prevId.HasValue)
                    {
                        var closeCmd = conn.CreateCommand();
                        closeCmd.CommandText = $"UPDATE {_tableName} SET valid_to = @now, is_current = 0 WHERE id = @id";
                        closeCmd.Parameters.AddWithValue("@now", nowSp);
                        closeCmd.Parameters.AddWithValue("@id", prevId.Value);
                        closeCmd.ExecuteNonQuery();
                    }
                    var insertCmd = conn.CreateCommand();
                    insertCmd.CommandText = $@"INSERT INTO {_tableName} (autorizador, status_json, valid_from, valid_to, is_current) VALUES (@aut, @json, @now, NULL, 1)";
                    insertCmd.Parameters.AddWithValue("@aut", autorizador);
                    insertCmd.Parameters.AddWithValue("@json", statusJson);
                    insertCmd.Parameters.AddWithValue("@now", nowSp);
                    insertCmd.ExecuteNonQuery();
                    _logger.LogInformation($"Inserted new status for {autorizador}");
                }
                else
                {
                    _logger.LogInformation($"No change for {autorizador}, skipping insert.");
                }
            }
        }

        public void ApplyRetentionPolicy(int maxDays, int maxMb)
        {
            try
            {
                using var conn = new NpgsqlConnection(_connectionString);
                conn.Open();
                // Delete records older than maxDays
                if (maxDays > 0)
                {
                    var cutoff = DateTime.UtcNow.AddDays(-maxDays);
                    var delCmd = conn.CreateCommand();
                    delCmd.CommandText = $"DELETE FROM {_tableName} WHERE valid_from < @cutoff";
                    delCmd.Parameters.AddWithValue("@cutoff", cutoff);
                    int deleted = delCmd.ExecuteNonQuery();
                    _logger.LogInformation($"Retention: Deleted {deleted} records older than {maxDays} days.");
                }
                // DB file size logic removed for PostgreSQL
            }
            catch (Exception ex)
            {
                _logger.LogError($"Error applying retention policy: {ex.Message}");
            }
        }
    }

    public class NfeConfig
    {
        public string Url { get; set; } = "https://www.nfe.fazenda.gov.br/portal/disponibilidade.aspx";
        public string PgConnectionString { get; set; } = "Host=localhost;Port=5432;Username=postgres;Password=postgres;Database=nfe";
        public string JsonPath { get; set; } = "disponibilidade.json";
        public string LogLevel { get; set; } = "Information";
        public string LogFile { get; set; } = "nfe_status.log";
        public int RetentionMaxMb { get; set; } = 10;
        public int RetentionMaxDays { get; set; } = 30;
        public int DbSchemaVersion { get; set; } = 2;
        public string TableName { get; set; } = "disponibilidade";

        public static NfeConfig LoadFromEnvironment()
        {
            var host = Environment.GetEnvironmentVariable("NFE_PG_HOST") ?? "localhost";
            var port = Environment.GetEnvironmentVariable("NFE_PG_PORT") ?? "5432";
            var user = Environment.GetEnvironmentVariable("NFE_PG_USER") ?? "postgres";
            var password = Environment.GetEnvironmentVariable("NFE_PG_PASSWORD") ?? "postgres";
            var db = Environment.GetEnvironmentVariable("NFE_PG_DATABASE") ?? "nfe";
            var connStr = $"Host={host};Port={port};Username={user};Password={password};Database={db}";
            return new NfeConfig
            {
                Url = Environment.GetEnvironmentVariable("NFE_URL") ?? "https://www.nfe.fazenda.gov.br/portal/disponibilidade.aspx",
                PgConnectionString = connStr,
                JsonPath = Environment.GetEnvironmentVariable("NFE_JSON_PATH") ?? "disponibilidade.json",
                LogLevel = Environment.GetEnvironmentVariable("NFE_LOG_LEVEL") ?? "Information",
                LogFile = Environment.GetEnvironmentVariable("NFE_LOG_FILE") ?? "nfe_status.log",
                RetentionMaxMb = int.TryParse(Environment.GetEnvironmentVariable("NFE_RETENTION_MAX_MB"), out var mb) ? mb : 10,
                RetentionMaxDays = int.TryParse(Environment.GetEnvironmentVariable("NFE_RETENTION_MAX_DAYS"), out var days) ? days : 30,
                DbSchemaVersion = int.TryParse(Environment.GetEnvironmentVariable("NFE_DB_SCHEMA_VERSION"), out var ver) ? ver : 2,
                TableName = Environment.GetEnvironmentVariable("NFE_TABLE_NAME") ?? "disponibilidade"
            };
        }

        public static NfeConfig LoadFromFile(string filePath)
        {
            if (!File.Exists(filePath))
                throw new FileNotFoundException($"Config file not found: {filePath}");
            var json = File.ReadAllText(filePath);
            return JsonSerializer.Deserialize<NfeConfig>(json) ?? new NfeConfig();
        }
    }
}

import re
import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from contextlib import contextmanager
import unicodedata

from playwright.sync_api import sync_playwright, Page, Browser
from bs4 import BeautifulSoup, Tag
from logging.handlers import RotatingFileHandler
import psycopg2

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from pytz import timezone as ZoneInfo

# --- CONFIGURATION ---
class Config:
    """Configuration class with environment variable support for PostgreSQL."""
    URL = os.getenv("NFE_URL", "https://www.nfe.fazenda.gov.br/portal/disponibilidade.aspx")
    PG_HOST = os.getenv("NFE_PG_HOST", "localhost")
    PG_PORT = os.getenv("NFE_PG_PORT", "5432")
    PG_USER = os.getenv("NFE_PG_USER", "postgres")
    PG_PASSWORD = os.getenv("NFE_PG_PASSWORD", "postgres")
    PG_DATABASE = os.getenv("NFE_PG_DATABASE", "nfe")
    PG_CONN_STR = f"host={PG_HOST} port={PG_PORT} user={PG_USER} password={PG_PASSWORD} dbname={PG_DATABASE}"
    JSON_PATH = os.getenv("NFE_JSON_PATH", "disponibilidade.json")
    LOG_LEVEL = os.getenv("NFE_LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("NFE_LOG_FILE", "nfe_status.log")
    RETENTION_MAX_MB = int(os.getenv("NFE_RETENTION_MAX_MB", 10))
    RETENTION_MAX_DAYS = int(os.getenv("NFE_RETENTION_MAX_DAYS", 30))
    DB_SCHEMA_VERSION = 2
    TABLE_NAME = os.getenv("NFE_TABLE_NAME", "disponibilidade")
    FIELD_AUTORIZADOR = os.getenv("NFE_FIELD_AUTORIZADOR", "autorizador")
    FIELD_STATUS_JSON = os.getenv("NFE_FIELD_STATUS_JSON", "status_json")
    FIELD_VALID_FROM = os.getenv("NFE_FIELD_VALID_FROM", "valid_from")
    FIELD_VALID_TO = os.getenv("NFE_FIELD_VALID_TO", "valid_to")
    FIELD_IS_CURRENT = os.getenv("NFE_FIELD_IS_CURRENT", "is_current")

# Map image filenames to status
IMG_MAP = {
    "bola_verde_P.png": "verde",
    "bola_amarela_P.png": "amarelo",
    "bola_vermelho_P.png": "vermelho",
    "bola_cinza_P.png": "cinza",
}

# Autorizador metadata
AUTORIZADOR_INFO = {
    "SVAN": {"tipo": "Sefaz Virtual Ambiente Nacional", "ufs_autorizador": ["MA"]},
    "SVRS": {
        "tipo": "Sefaz Virtual Rio Grande do Sul",
        "ufs_autorizador": ["AC","AL","AP","CE","DF","ES","PA","PB","PI","RJ","RN","RO","RR","SC","SE","TO"],
        "ufs_consulta_cadastro": ["AC","ES","RN","PB","SC"]
    },
    "SVC-AN": {"tipo": "Contingência Nacional", "ufs_contingencia": ["AC","AL","AP","CE","DF","ES","MG","PA","PB","PI","RJ","RN","RO","RR","RS","SC","SE","SP","TO"]},
    "SVC-RS": {"tipo": "Contingência RS", "ufs_contingencia": ["AM","BA","GO","MA","MS","MT","PE","PR"]}
}

# Pre-compile regex for timestamp
TS_RE = re.compile(r"Última Verificação:\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})")

# Timezone configurável
NFE_TIMEZONE = os.getenv("NFE_TIMEZONE", "America/Sao_Paulo")

@dataclass
class NFEResult:
    """Data class for NFE status results."""
    checked_at: Optional[str]
    statuses: List[Dict[str, Any]]
    success: bool
    error_message: Optional[str] = None

class NFEMonitorError(Exception):
    """Custom exception for NFE monitoring errors."""
    pass

def normalize_key(key: str) -> str:
    key = ''.join(
        c for c in unicodedata.normalize('NFD', key)
        if unicodedata.category(c) != 'Mn'
    )
    key = re.sub(r'[^a-zA-Z0-9]', '_', key)
    key = re.sub(r'_+', '_', key)
    return key.strip('_').lower()

class NFEStatusMonitor:
    def __init__(self, config: Config = Config()):
        self.config = config
        self.logger = self.setup_logging()

    def setup_logging(self) -> logging.Logger:
        """Setup logging configuration using environment variable for log level, with rotação automática de arquivos."""
        log_level = os.getenv("NFE_LOG_LEVEL", "INFO").upper()
        log_level_value = getattr(logging, log_level, logging.INFO)
        handlers = [
            RotatingFileHandler(self.config.LOG_FILE, maxBytes=10_000_000, backupCount=7, encoding='utf-8'),
            logging.StreamHandler()
        ]
        logging.basicConfig(
            level=log_level_value,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        return logging.getLogger(__name__)

    @contextmanager
    def get_browser_session(self):
        """Context manager for Playwright browser session."""
        playwright = None
        browser = None
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=True)
            yield browser
        except Exception as e:
            raise NFEMonitorError(f"Failed to initialize browser: {e}")
        finally:
            if browser:
                browser.close()
            if playwright:
                playwright.stop()

    def fetch_html(self) -> str:
        """Fetches the page HTML via Playwright with error handling."""
        self.logger.info(f"Fetching HTML from {self.config.URL}")
        try:
            with self.get_browser_session() as browser:
                page = browser.new_page()
                # Set timeout and user agent
                page.set_default_timeout(30000)  # 30 seconds
                page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                # Navigate to page
                response = page.goto(self.config.URL)
                if not response or response.status != 200:
                    raise NFEMonitorError(f"HTTP {response.status if response else 'Unknown'} error")
                # Wait for table to load
                page.wait_for_selector("#ctl00_ContentPlaceHolder1_gdvDisponibilidade2", timeout=10000)
                html = page.content()
                self.logger.info("Successfully fetched HTML content")
                return html
        except Exception as e:
            self.logger.error(f"Failed to fetch HTML: {e}")
            raise NFEMonitorError(f"Failed to fetch HTML: {e}") from e

    @staticmethod
    def validate_table(table: Tag, logger: logging.Logger) -> bool:
        """Validates that the table has the expected structure."""
        if not table:
            logger.error("Table not found in HTML")
            return False
        headers = table.find("tr")
        if not headers:
            logger.error("Table headers not found")
            return False
        th_elements = headers.find_all("th")
        if len(th_elements) < 2:
            logger.error("Table has insufficient columns")
            return False
        expected_headers = ["Autorizador", "Status"]
        found_headers = [th.get_text(strip=True) for th in th_elements]
        if not any(header in found_headers for header in expected_headers):
            logger.error(f"Expected headers not found. Found: {found_headers}")
            return False
        return True

    @staticmethod
    def parse_timestamp(caption: Tag, logger: logging.Logger) -> Optional[datetime]:
        """Parse timestamp from table caption with validation."""
        if not caption:
            logger.warning("No caption found for timestamp extraction")
            return None
        caption_text = caption.get_text(separator=" ")
        match = TS_RE.search(caption_text)
        if not match:
            logger.warning(f"Timestamp pattern not found in caption: {caption_text}")
            return None
        try:
            ts = datetime.strptime(match.group(1), "%d/%m/%Y %H:%M:%S")
            logger.info(f"Parsed timestamp: {ts}")
            return ts
        except ValueError as e:
            logger.error(f"Failed to parse timestamp '{match.group(1)}': {e}")
            return None

    def parse_and_enrich(self, html: str) -> NFEResult:
        """Parses the HTML, extracts statuses, timestamp, and enriches each row."""
        self.logger.info("Starting HTML parsing and enrichment")
        try:
            soup = BeautifulSoup(html, "lxml")
            table = soup.find("table", id="ctl00_ContentPlaceHolder1_gdvDisponibilidade2")
            if not self.validate_table(table, self.logger):
                return NFEResult(checked_at=None, statuses=[], success=False, error_message="Invalid table structure")
            # Extract headers
            headers = [th.get_text(strip=True) for th in table.find("tr").find_all("th")]
            self.logger.info(f"Found headers: {headers}")
            # Extract timestamp
            ts = self.parse_timestamp(table.caption, self.logger)
            rows = []
            data_rows = table.find_all("tr")[1:]  # Skip header row
            for idx, tr in enumerate(data_rows):
                try:
                    cells = tr.find_all("td")
                    if len(cells) != len(headers):
                        self.logger.warning(f"Row {idx + 1}: Cell count mismatch. Expected {len(headers)}, got {len(cells)}")
                        continue
                    row = {}
                    autorizador = None
                    # Parse cells
                    for cell_idx, cell in enumerate(cells):
                        key = normalize_key(headers[cell_idx])
                        img = cell.find("img")
                        if img:
                            filename = img["src"].split("/")[-1]
                            row[key] = IMG_MAP.get(filename, "desconhecido")
                            if filename not in IMG_MAP:
                                self.logger.warning(f"Unknown image filename: {filename}")
                        else:
                            text = cell.get_text(strip=True)
                            row[key] = text or None
                        if key == "autorizador":
                            autorizador = row[key]
                    # Enrich metadata
                    meta = AUTORIZADOR_INFO.get(autorizador, {})
                    if not meta:
                        for code, info in AUTORIZADOR_INFO.items():
                            for val in info.values():
                                if isinstance(val, list) and autorizador in val:
                                    meta = {"relacionado_a": code}
                                    break
                    # Normalize meta keys too
                    row.update({normalize_key(k): v for k, v in meta.items()})
                    rows.append(row)
                except Exception as e:
                    self.logger.error(f"Error parsing row {idx + 1}: {e}")
                    continue
            self.logger.info(f"Successfully parsed {len(rows)} rows")
            return NFEResult(
                checked_at=ts.isoformat() if ts else None,
                statuses=rows,
                success=True
            )
        except Exception as e:
            self.logger.error(f"Failed to parse HTML: {e}")
            return NFEResult(checked_at=None, statuses=[], success=False, error_message=str(e))

    @contextmanager
    def get_db_connection(self, retries=3, backoff=0.5):
        """Context manager for database connections with retry logic."""
        conn = None
        attempt = 0
        while attempt < retries:
            try:
                conn = psycopg2.connect(self.config.PG_CONN_STR)
                yield conn
                break
            except psycopg2.OperationalError as e:
                self.logger.error(f"Database connection failed (attempt {attempt+1}): {e}")
                attempt += 1
                if attempt >= retries:
                    raise NFEMonitorError(f"Database connection failed after {retries} attempts: {e}")
                import time
                time.sleep(backoff * (2 ** (attempt - 1)))
            finally:
                if conn:
                    conn.close()

    def init_db(self) -> bool:
        """Initializes PostgreSQL database with SCD2 schema, indices, and schema versioning."""
        self.logger.info(f"Initializing database in PostgreSQL: {self.config.PG_DATABASE}")
        try:
            with self.get_db_connection() as conn:
                cur = conn.cursor()
                # Always create the table first
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.TABLE_NAME} (
                        id SERIAL PRIMARY KEY,
                        {self.config.FIELD_AUTORIZADOR} TEXT NOT NULL,
                        {self.config.FIELD_STATUS_JSON} TEXT NOT NULL,
                        {self.config.FIELD_VALID_FROM} TIMESTAMP NOT NULL,
                        {self.config.FIELD_VALID_TO} TIMESTAMP,
                        {self.config.FIELD_IS_CURRENT} INTEGER NOT NULL DEFAULT 1
                    )
                """)
                # Create indices if not exist
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.config.FIELD_AUTORIZADOR} ON {self.config.TABLE_NAME}({self.config.FIELD_AUTORIZADOR})")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.config.FIELD_VALID_FROM} ON {self.config.TABLE_NAME}({self.config.FIELD_VALID_FROM})")
                conn.commit()
                self.logger.info("Database initialized successfully")
                return True
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            return False

    @staticmethod
    def status_changed(prev_status: dict, new_status: dict) -> bool:
        """Return True if the status dicts are different."""
        return prev_status != new_status

    def persist(self, data: NFEResult) -> bool:
        """Implements SCD2: Persists each row, tracking history based on checked_at timestamp."""
        if not data.success or not data.checked_at:
            self.logger.error("Cannot persist invalid data")
            return False
        self.logger.info(f"Persisting {len(data.statuses)} records to database (SCD2)")
        try:
            with self.get_db_connection() as conn:
                cur = conn.cursor()
                ts = datetime.fromisoformat(data.checked_at)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                ts_str = ts.astimezone(timezone.utc)
                success_count = 0
                for row in data.statuses:
                    autorizador = row.get("autorizador")
                    if not autorizador:
                        self.logger.warning("Skipping row without autorizador")
                        continue
                    status_json = json.dumps(row, ensure_ascii=False)
                    # Get current record for this autorizador
                    cur.execute(
                        f"SELECT id, {self.config.FIELD_STATUS_JSON}, {self.config.FIELD_VALID_FROM} FROM {self.config.TABLE_NAME} WHERE {self.config.FIELD_AUTORIZADOR}=%s AND {self.config.FIELD_IS_CURRENT}=1 ORDER BY {self.config.FIELD_VALID_FROM} DESC LIMIT 1",
                        (autorizador,)
                    )
                    current = cur.fetchone()
                    status_changed = True
                    if current:
                        prev_status = json.loads(current[1])
                        if not self.status_changed(prev_status, row):
                            status_changed = False
                    if status_changed:
                        # Close previous record
                        if current:
                            cur.execute(
                                f"UPDATE {self.config.TABLE_NAME} SET {self.config.FIELD_VALID_TO}=%s, {self.config.FIELD_IS_CURRENT}=0 WHERE id=%s",
                                (ts_str, current[0])
                            )
                        # Insert new record
                        cur.execute(
                            f"""
                            INSERT INTO {self.config.TABLE_NAME} ({self.config.FIELD_AUTORIZADOR}, {self.config.FIELD_STATUS_JSON}, {self.config.FIELD_VALID_FROM}, {self.config.FIELD_VALID_TO}, {self.config.FIELD_IS_CURRENT})
                            VALUES (%s, %s, %s, NULL, 1)
                            """,
                            (autorizador, status_json, ts_str)
                        )
                        success_count += 1
                    else:
                        self.logger.info(f"No change for {autorizador}, skipping insert.")
                conn.commit()
                self.logger.info(f"SCD2: {success_count} new records inserted.")
                # Apply retention policy after insert
                self.apply_retention_policy(conn)
                return True
        except Exception as e:
            self.logger.error(f"Failed to persist data: {e}")
            return False

    def apply_retention_policy(self, conn=None):
        """Apply retention policy by age. If conn is None, open a new connection."""
        max_days = self.config.RETENTION_MAX_DAYS
        now = datetime.now(ZoneInfo(NFE_TIMEZONE))
        close_conn = False
        try:
            if conn is None:
                conn = psycopg2.connect(self.config.PG_CONN_STR)
                close_conn = True
            cur = conn.cursor()
            # Age-based retention: delete records where valid_to is older than max_days
            cutoff = now - timedelta(days=max_days)
            cur.execute(
                f"DELETE FROM {self.config.TABLE_NAME} WHERE {self.config.FIELD_VALID_TO} IS NOT NULL AND {self.config.FIELD_VALID_TO} < %s",
                (cutoff,)
            )
            conn.commit()
            self.logger.info("Retention policy applied (age: %d days)", max_days)
        except Exception as e:
            self.logger.error(f"Failed to apply retention policy: {e}")
        finally:
            if close_conn:
                conn.close()

    def save_json(self, data: NFEResult) -> bool:
        """Writes enriched data to a JSON file atomically."""
        if not data.success:
            self.logger.error("Cannot save invalid data to JSON")
            return False
        self.logger.info(f"Saving data to {self.config.JSON_PATH}")
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config.JSON_PATH) if os.path.dirname(self.config.JSON_PATH) else '.', exist_ok=True)
            import tempfile
            dir_name = os.path.dirname(self.config.JSON_PATH) or '.'
            with tempfile.NamedTemporaryFile('w', encoding="utf-8", dir=dir_name, delete=False) as tf:
                json.dump({
                    normalize_key("checked_at"): data.checked_at,
                    normalize_key("statuses"): data.statuses,
                    normalize_key("metadata"): {
                        normalize_key("total_records"): len(data.statuses),
                        normalize_key("generated_at"): datetime.now(ZoneInfo(NFE_TIMEZONE)).isoformat(),
                        normalize_key("version"): "2.0"
                    }
                }, tf, indent=2, ensure_ascii=False)
                tempname = tf.name
            os.replace(tempname, self.config.JSON_PATH)
            self.logger.info("JSON file saved successfully (atomic write)")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save JSON file: {e}")
            return False

    def run(self) -> int:
        """Main function with comprehensive error handling."""
        self.logger.info("Starting NFE status monitoring")
        try:
            # Initialize database
            if not self.init_db():
                self.logger.error("Failed to initialize database. Exiting.")
                return 1
            # Fetch HTML
            html = self.fetch_html()
            # Parse and enrich data
            result = self.parse_and_enrich(html)
            if not result.success:
                self.logger.error(f"Failed to parse data: {result.error_message}")
                return 1
            # Persist to database
            if not self.persist(result):
                self.logger.error("Failed to persist data to database")
                return 1
            # Save to JSON
            if not self.save_json(result):
                self.logger.error("Failed to save JSON file")
                return 1
            self.logger.info(f"✅ Successfully collected {len(result.statuses)} records at {result.checked_at}")
            return 0
        except KeyboardInterrupt:
            self.logger.info("Process interrupted by user")
            return 130
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return 1

if __name__ == "__main__":
    exit(NFEStatusMonitor().run())

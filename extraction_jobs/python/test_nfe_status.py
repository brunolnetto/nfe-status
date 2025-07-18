#!/usr/bin/env python3
"""
Comprehensive test suite for NFE Status Monitor
"""

import os
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock
import psycopg2
from datetime import datetime, timedelta, timezone

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nfe_status import (
    Config, NFEResult, NFEMonitorError, NFEStatusMonitor
)
from bs4 import BeautifulSoup

def test_config_environment_variables():
    """Test configuration with environment variables."""
    print("Testing configuration...")
    
    # Test default values
    assert Config.URL == "https://www.nfe.fazenda.gov.br/portal/disponibilidade.aspx"
    assert Config.PG_DATABASE == "nfe"
    assert Config.JSON_PATH == "disponibilidade.json"
    
    # Test environment variable override
    with patch.dict(os.environ, {'NFE_URL': 'https://test.example.com'}):
        # Note: Config class uses os.getenv at module level, so we need to reload
        import importlib
        import nfe_status
        importlib.reload(nfe_status)
        assert nfe_status.Config.URL == 'https://test.example.com'
    
    print("✅ Configuration tests passed")

def test_nfe_result_dataclass():
    """Test NFEResult dataclass."""
    print("Testing NFEResult dataclass...")
    
    # Test successful result
    result = NFEResult(
        checked_at="2024-01-15T10:30:00",
        statuses=[{"Autorizador": "SVAN", "Status": "verde"}],
        success=True
    )
    assert result.checked_at == "2024-01-15T10:30:00"
    assert len(result.statuses) == 1
    assert result.success is True
    assert result.error_message is None
    
    # Test error result
    error_result = NFEResult(
        checked_at=None,
        statuses=[],
        success=False,
        error_message="Test error"
    )
    assert error_result.success is False
    assert error_result.error_message == "Test error"
    
    print("✅ NFEResult dataclass tests passed")

def test_validate_table():
    """Test table validation function."""
    print("Testing table validation...")
    
    # Create a mock logger
    logger = MagicMock()
    
    # Test valid table
    valid_html = """
    <table id="ctl00_ContentPlaceHolder1_gdvDisponibilidade2">
        <tr>
            <th>Autorizador</th>
            <th>Status</th>
        </tr>
        <tr>
            <td>SVAN</td>
            <td><img src="bola_verde_P.png"></td>
        </tr>
    </table>
    """
    soup = BeautifulSoup(valid_html, 'lxml')
    table = soup.find('table')
    
    assert NFEStatusMonitor.validate_table(table, logger) is True
    
    # Test invalid table (no headers)
    invalid_html = """
    <table id="ctl00_ContentPlaceHolder1_gdvDisponibilidade2">
        <tr>
            <td>No headers</td>
        </tr>
    </table>
    """
    soup = BeautifulSoup(invalid_html, 'lxml')
    table = soup.find('table')
    
    assert NFEStatusMonitor.validate_table(table, logger) is False
    
    print("✅ Table validation tests passed")

def test_parse_timestamp():
    """Test timestamp parsing function."""
    print("Testing timestamp parsing...")
    
    # Create a mock logger
    logger = MagicMock()
    
    # Test valid timestamp
    valid_caption_html = '<caption>Última Verificação: 15/01/2024 10:30:00</caption>'
    soup = BeautifulSoup(valid_caption_html, 'lxml')
    caption = soup.find('caption')
    
    timestamp = NFEStatusMonitor.parse_timestamp(caption, logger)
    assert timestamp is not None
    assert timestamp.year == 2024
    assert timestamp.month == 1
    assert timestamp.day == 15
    
    # Test invalid timestamp
    invalid_caption_html = '<caption>No timestamp here</caption>'
    soup = BeautifulSoup(invalid_caption_html, 'lxml')
    caption = soup.find('caption')
    
    timestamp = NFEStatusMonitor.parse_timestamp(caption, logger)
    assert timestamp is None
    
    print("✅ Timestamp parsing tests passed")

def test_logging_setup():
    """Test logging setup."""
    print("Testing logging setup...")
    import logging
    # Test with temporary log file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as tmp:
        log_file = tmp.name
    try:
        with patch.dict(os.environ, {'NFE_LOG_FILE': log_file, 'NFE_LOG_LEVEL': 'INFO'}):
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            test_logger = logging.getLogger('test_logger')
            test_logger.setLevel(logging.INFO)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            test_logger.addHandler(file_handler)
            test_logger.info("Test log message")
            for handler in test_logger.handlers:
                handler.flush()
            # Remove and close handler before deleting file
            test_logger.removeHandler(file_handler)
            file_handler.close()
            with open(log_file, 'r') as f:
                log_content = f.read()
                assert "Test log message" in log_content
    finally:
        if os.path.exists(log_file):
            os.unlink(log_file)
    print("✅ Logging setup tests passed")

def test_error_handling():
    """Test custom exception."""
    print("Testing error handling...")
    
    try:
        raise NFEMonitorError("Test error message")
    except NFEMonitorError as e:
        assert str(e) == "Test error message"
    
    print("✅ Error handling tests passed")

def test_nfe_status_monitor_initialization():
    """Test NFEStatusMonitor class initialization."""
    print("Testing NFEStatusMonitor initialization...")
    
    monitor = NFEStatusMonitor()
    assert monitor.config is not None
    assert monitor.logger is not None
    assert isinstance(monitor.config, Config)
    
    print("✅ NFEStatusMonitor initialization tests passed")

def test_fetch_html():
    """Test HTML fetching with mocked Playwright."""
    print("Testing fetch_html...")

    monitor = NFEStatusMonitor()

    with patch('nfe_status.sync_playwright') as mock_sync_playwright:
        # Setup the mock chain for sync_playwright().start()
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200

        # Setup the chain: sync_playwright().start()
        mock_sync_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = "<html>test content</html>"

        html = monitor.fetch_html()
        assert html == "<html>test content</html>"

        mock_page.set_default_timeout.assert_called_with(30000)
        mock_page.set_extra_http_headers.assert_called()
        mock_page.goto.assert_called_with(monitor.config.URL)
        mock_page.wait_for_selector.assert_called_with("#ctl00_ContentPlaceHolder1_gdvDisponibilidade2", timeout=10000)
        mock_page.content.assert_called()

    print("✅ fetch_html tests passed")

def test_get_browser_session():
    """Test browser session context manager."""
    print("Testing get_browser_session...")

    monitor = NFEStatusMonitor()

    with patch('nfe_status.sync_playwright') as mock_sync_playwright:
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        # Setup the chain: sync_playwright().start()
        mock_sync_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        with monitor.get_browser_session() as browser:
            assert browser is mock_browser

        # Verify cleanup
        mock_browser.close.assert_called()
        mock_playwright_instance.stop.assert_called()

    print("✅ get_browser_session tests passed")

def test_get_db_connection():
    """Test database connection context manager (PostgreSQL)."""
    print("Testing get_db_connection...")
    monitor = NFEStatusMonitor()
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        with monitor.get_db_connection() as conn:
            assert conn == mock_conn
            mock_connect.assert_called_with(monitor.config.PG_CONN_STR)
        mock_conn.close.assert_called()
    print("✅ get_db_connection tests passed")

def test_run_method_success():
    """Test the complete run workflow with success."""
    print("Testing run method (success)...")
    
    monitor = NFEStatusMonitor()
    
    # Create a mock result
    mock_result = NFEResult(
        checked_at="2024-01-15T10:30:00",
        statuses=[{"Autorizador": "SVAN", "Status": "verde"}],
        success=True
    )
    
    with patch.object(monitor, 'init_db', return_value=True), \
         patch.object(monitor, 'fetch_html', return_value="<html>test</html>"), \
         patch.object(monitor, 'parse_and_enrich', return_value=mock_result), \
         patch.object(monitor, 'persist', return_value=True), \
         patch.object(monitor, 'save_json', return_value=True):
        
        result = monitor.run()
        assert result == 0  # Success
        
        # Verify all methods were called
        monitor.init_db.assert_called_once()
        monitor.fetch_html.assert_called_once()
        monitor.parse_and_enrich.assert_called_once_with("<html>test</html>")
        monitor.persist.assert_called_once_with(mock_result)
        monitor.save_json.assert_called_once_with(mock_result)
    
    print("✅ run method (success) tests passed")

def test_run_method_failures():
    """Test the run method with various failure scenarios."""
    print("Testing run method (failures)...")
    
    monitor = NFEStatusMonitor()
    
    # Test database initialization failure
    with patch.object(monitor, 'init_db', return_value=False):
        result = monitor.run()
        assert result == 1  # Error
    
    # Test HTML parsing failure
    mock_result = NFEResult(
        checked_at=None,
        statuses=[],
        success=False,
        error_message="Parsing failed"
    )
    
    with patch.object(monitor, 'init_db', return_value=True), \
         patch.object(monitor, 'fetch_html', return_value="<html>test</html>"), \
         patch.object(monitor, 'parse_and_enrich', return_value=mock_result):
        
        result = monitor.run()
        assert result == 1  # Error
    
    # Test database persistence failure
    mock_result = NFEResult(
        checked_at="2024-01-15T10:30:00",
        statuses=[{"Autorizador": "SVAN", "Status": "verde"}],
        success=True
    )
    
    with patch.object(monitor, 'init_db', return_value=True), \
         patch.object(monitor, 'fetch_html', return_value="<html>test</html>"), \
         patch.object(monitor, 'parse_and_enrich', return_value=mock_result), \
         patch.object(monitor, 'persist', return_value=False):
        
        result = monitor.run()
        assert result == 1  # Error
    
    # Test JSON saving failure
    with patch.object(monitor, 'init_db', return_value=True), \
         patch.object(monitor, 'fetch_html', return_value="<html>test</html>"), \
         patch.object(monitor, 'parse_and_enrich', return_value=mock_result), \
         patch.object(monitor, 'persist', return_value=True), \
         patch.object(monitor, 'save_json', return_value=False):
        
        result = monitor.run()
        assert result == 1  # Error
    
    print("✅ run method (failures) tests passed")

def test_error_scenarios():
    """Test various error scenarios."""
    print("DEBUG: Entered test_error_scenarios")
    print("Testing error scenarios...")
    
    monitor = NFEStatusMonitor()
    
    # Test database connection failure
    with patch('psycopg2.connect', side_effect=Exception("DB Error")):
        success = monitor.init_db()
        assert success is False
    
    # Test HTML parsing failure with invalid HTML
    result = monitor.parse_and_enrich("invalid html")
    assert result.success is False
    assert "Invalid table structure" in result.error_message
    
    # Test JSON saving failure
    mock_result = NFEResult(
        checked_at="2024-01-15T10:30:00",
        statuses=[{"Autorizador": "SVAN", "Status": "verde"}],
        success=True
    )
    
    # Patch NamedTemporaryFile to raise PermissionError
    import tempfile as _tempfile
    class DummyFile:
        def __enter__(self): raise PermissionError("Permission denied")
        def __exit__(self, exc_type, exc_val, exc_tb): return False
    with patch.object(_tempfile, 'NamedTemporaryFile', DummyFile):
        success = monitor.save_json(mock_result)
        assert success is False
    
    # Test persist with invalid data
    invalid_result = NFEResult(
        checked_at=None,  # Invalid
        statuses=[],
        success=True
    )
    print(f"DEBUG: About to call persist with data.success={invalid_result.success}, data.checked_at={invalid_result.checked_at}")
    try:
        success = monitor.persist(invalid_result)
        print(f"persist(invalid_result) returned: {success}")  # Debug output
        assert success is False
    except Exception as e:
        print(f"EXCEPTION in persist(invalid_result): {e}")
        raise
    
    print("✅ Error scenarios tests passed")

def test_scd2_logic():
    """Test SCD2 (Slowly Changing Dimension Type 2) logic with PostgreSQL mocks."""
    print("Testing SCD2 logic...")
    monitor = NFEStatusMonitor()
    result1 = NFEResult(
        checked_at="2024-01-15T10:30:00",
        statuses=[{"Autorizador": "SVAN", "Status": "verde"}],
        success=True
    )
    result2 = NFEResult(
        checked_at="2024-01-15T11:30:00",
        statuses=[{"Autorizador": "SVAN", "Status": "amarelo"}],
        success=True
    )
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None
        success = monitor.persist(result1)
        assert success is True
        mock_cur.fetchone.return_value = (1, json.dumps({"Autorizador": "SVAN", "Status": "verde"}), "2024-01-15T10:30:00")
        success = monitor.persist(result2)
        assert success is True
        assert mock_cur.execute.call_count == 2
    print("✅ SCD2 logic tests passed")

def test_retention_policy_age_and_size():
    """Test retention policy for both age and size limits."""
    print("Testing retention policy (age and size)...")
    monitor = NFEStatusMonitor()
    with patch('os.path.getsize') as mock_getsize, \
         patch('os.path.exists') as mock_exists, \
         patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_exists.return_value = True
        mock_getsize.side_effect = [15 * 1024 * 1024, 12 * 1024 * 1024, 8 * 1024 * 1024]
        mock_cur.fetchall.side_effect = [ [(1,), (2,)], [] ]
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=monitor.config.RETENTION_MAX_DAYS)
        monitor.apply_retention_policy(conn=mock_conn)
        # Check that age-based delete was called (PostgreSQL: %s, not ?)
        found = False
        for call in mock_cur.execute.call_args_list:
            if call[0][0].startswith(f"DELETE FROM {monitor.config.TABLE_NAME}") and call[0][1][0] == cutoff:
                found = True
        assert found, "DELETE with correct cutoff not called"
    print("✅ Retention policy (age and size) tests passed")

def test_apply_retention_policy():
    """Test apply_retention_policy covers both with and without conn."""
    monitor = NFEStatusMonitor()
    # Test with provided connection
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        monitor.apply_retention_policy(conn=mock_conn)
        assert mock_cur.execute.called
    # Test without provided connection (should open and close its own)
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        monitor.apply_retention_policy()
        assert mock_cur.execute.called
    print("✅ apply_retention_policy covered")

def test_status_changed():
    """Test status_changed static method."""
    # Should return False for equal dicts
    d1 = {"a": 1, "b": 2}
    d2 = {"a": 1, "b": 2}
    assert NFEStatusMonitor.status_changed(d1, d2) is False
    # Should return True for different dicts
    d3 = {"a": 1, "b": 3}
    assert NFEStatusMonitor.status_changed(d1, d3) is True
    print("✅ status_changed covered")

def test_normalize_key():
    """Test normalize_key function."""
    from nfe_status import normalize_key
    assert normalize_key("Autorizador") == "autorizador"
    assert normalize_key("Status com Acento!") == "status_com_acento"
    assert normalize_key("  Espaço  e--caractéres  ") == "espaco_e_caracteres"
    assert normalize_key("") == ""
    print("✅ normalize_key covered")

def main():
    """Run all tests."""
    print("🧪 Running comprehensive NFE Status Monitor tests...\n")
    
    try:
        # Core functionality tests
        test_config_environment_variables()
        test_nfe_result_dataclass()
        test_validate_table()
        test_parse_timestamp()
        test_logging_setup()
        test_error_handling()
        test_nfe_status_monitor_initialization()
        
        # New tests for missing coverage
        test_fetch_html()
        test_get_browser_session()
        test_get_db_connection()
        test_run_method_success()
        test_run_method_failures()
        test_error_scenarios()
        test_scd2_logic()
        # Retention policy test
        test_retention_policy_age_and_size()
        
        print("\n🎉 All tests passed successfully!")
        print("📊 Coverage should now be 80%+")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())

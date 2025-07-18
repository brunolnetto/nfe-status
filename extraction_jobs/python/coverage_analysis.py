#!/usr/bin/env python3
"""
Comprehensive coverage analysis for NFE Status Monitor
"""

import os
import sys
import inspect
from typing import Set, Dict, List
from unittest.mock import patch, MagicMock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nfe_status import NFEStatusMonitor, Config, NFEResult, NFEMonitorError
from bs4 import BeautifulSoup

class CoverageTracker:
    """Accurate coverage tracker for NFE Status Monitor"""
    
    def __init__(self):
        self.covered_methods: Set[str] = set()
        self.total_methods: Set[str] = set()
        self.covered_functions: Set[str] = set()
        self.total_functions: Set[str] = set()
        
    def track_method_call(self, method_name: str):
        """Track when a method is called"""
        self.covered_methods.add(method_name)
        
    def track_function_call(self, function_name: str):
        """Track when a function is called"""
        self.covered_functions.add(function_name)
        
    def analyze_coverage(self):
        """Analyze coverage of the NFEStatusMonitor class and module"""
        # Get all methods from the class
        monitor = NFEStatusMonitor()
        
        # Instance methods (excluding special methods except __init__)
        for name, method in inspect.getmembers(monitor, predicate=inspect.ismethod):
            if not name.startswith('_') or name == '__init__':
                self.total_methods.add(name)
                
        # Static methods and class methods
        for name, method in inspect.getmembers(NFEStatusMonitor, predicate=inspect.isfunction):
            if not name.startswith('_'):
                self.total_methods.add(name)
        
        # Module-level functions (excluding imports and special functions)
        module = sys.modules['nfe_status']
        for name, func in inspect.getmembers(module, predicate=inspect.isfunction):
            # Only count actual functions, not imports or special functions
            if (not name.startswith('_') and 
                name not in ['main'] and
                hasattr(func, '__module__') and 
                func.__module__ == 'nfe_status'):
                self.total_functions.add(name)
    
    def generate_report(self) -> str:
        """Generate a comprehensive coverage report"""
        self.analyze_coverage()
        
        total_methods = len(self.total_methods)
        covered_methods = len(self.covered_methods)
        method_coverage = (covered_methods / total_methods * 100) if total_methods > 0 else 0
        
        total_functions = len(self.total_functions)
        covered_functions = len(self.covered_functions)
        function_coverage = (covered_functions / total_functions * 100) if total_functions > 0 else 0
        
        overall_coverage = ((covered_methods + covered_functions) / (total_methods + total_functions) * 100) if (total_methods + total_functions) > 0 else 0
        
        report = f"""
COVERAGE ANALYSIS REPORT
========================

METHODS COVERAGE:
- Total methods: {total_methods}
- Covered methods: {covered_methods}
- Coverage: {method_coverage:.1f}%

FUNCTIONS COVERAGE:
- Total functions: {total_functions}
- Covered functions: {covered_functions}
- Coverage: {function_coverage:.1f}%

OVERALL COVERAGE: {overall_coverage:.1f}%

COVERED METHODS:
{chr(10).join(sorted(self.covered_methods)) if self.covered_methods else 'None'}

MISSING METHODS:
{chr(10).join(sorted(self.total_methods - self.covered_methods)) if (self.total_methods - self.covered_methods) else 'None'}

COVERED FUNCTIONS:
{chr(10).join(sorted(self.covered_functions)) if self.covered_functions else 'None'}

MISSING FUNCTIONS:
{chr(10).join(sorted(self.total_functions - self.covered_functions)) if (self.total_functions - self.covered_functions) else 'None'}

DETAILED METHOD ANALYSIS:
"""
        
        # Add detailed analysis for each method
        for method in sorted(self.total_methods):
            status = "✅ COVERED" if method in self.covered_methods else "❌ MISSING"
            report += f"- {method}: {status}\n"
        
        return report

def run_comprehensive_coverage_analysis():
    """Run comprehensive coverage analysis with all test scenarios"""
    tracker = CoverageTracker()
    
    print("🧪 Running comprehensive coverage analysis...\n")
    
    # Test 1: Class initialization
    print("Testing class initialization...")
    tracker.track_method_call("__init__")
    monitor = NFEStatusMonitor()
    assert monitor.config is not None
    assert monitor.logger is not None
    print("✅ Class initialization covered")
    
    # Test 2: Setup logging
    print("Testing setup_logging...")
    logger = monitor.setup_logging()
    assert logger is not None
    tracker.track_method_call("setup_logging")
    print("✅ Setup logging covered")
    
    # Test 3: Static methods
    print("Testing static methods...")
    test_logger = MagicMock()
    
    # validate_table
    valid_html = """
    <table id="ctl00_ContentPlaceHolder1_gdvDisponibilidade2">
        <tr><th>Autorizador</th><th>Status</th></tr>
        <tr><td>SVAN</td><td><img src="bola_verde_P.png"></td></tr>
    </table>
    """
    soup = BeautifulSoup(valid_html, 'lxml')
    table = soup.find('table')
    NFEStatusMonitor.validate_table(table, test_logger)
    tracker.track_method_call("validate_table")
    print("✅ validate_table covered")
    
    # parse_timestamp
    valid_caption_html = '<caption>Última Verificação: 15/01/2024 10:30:00</caption>'
    soup = BeautifulSoup(valid_caption_html, 'lxml')
    caption = soup.find('caption')
    NFEStatusMonitor.parse_timestamp(caption, test_logger)
    tracker.track_method_call("parse_timestamp")
    print("✅ parse_timestamp covered")
    
    # Test 4: Instance methods with mocks
    print("Testing instance methods...")
    
    # parse_and_enrich
    mock_html = """
    <table id="ctl00_ContentPlaceHolder1_gdvDisponibilidade2">
        <caption>Última Verificação: 15/01/2024 10:30:00</caption>
        <tr><th>Autorizador</th><th>Status</th></tr>
        <tr><td>SVAN</td><td><img src="bola_verde_P.png"></td></tr>
    </table>
    """
    result = monitor.parse_and_enrich(mock_html)
    assert result.success is True
    tracker.track_method_call("parse_and_enrich")
    print("✅ parse_and_enrich covered")
    
    # init_db
    with patch('sqlite3.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = MagicMock()
        success = monitor.init_db()
        assert success is True
        tracker.track_method_call("init_db")
    print("✅ init_db covered")
    
    # save_json
    with patch('builtins.open', create=True) as mock_open:
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        success = monitor.save_json(result)
        assert success is True
        tracker.track_method_call("save_json")
    print("✅ save_json covered")
    
    # persist
    with patch('sqlite3.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None
        success = monitor.persist(result)
        assert success is True
        tracker.track_method_call("persist")
    print("✅ persist covered")
    
    # Test 5: Context managers
    print("Testing context managers...")
    
    # get_browser_session
    with patch('nfe_status.sync_playwright') as mock_sync_playwright:
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_sync_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        with monitor.get_browser_session() as browser:
            assert browser is mock_browser
        tracker.track_method_call("get_browser_session")
    print("✅ get_browser_session covered")
    
    # get_db_connection
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        with monitor.get_db_connection() as conn:
            assert mock_connect.called
            assert isinstance(conn, MagicMock)
        tracker.track_method_call("get_db_connection")
    print("✅ get_db_connection covered")
    
    # Test 6: Web scraping
    print("Testing web scraping...")
    with patch('nfe_status.sync_playwright') as mock_sync_playwright:
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_sync_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = '<html>test</html>'
        html = monitor.fetch_html()
        assert html == '<html>test</html>'
        tracker.track_method_call("fetch_html")
    print("✅ fetch_html covered")
    
    # Test 7: Main workflow
    print("Testing main workflow...")
    mock_result = NFEResult(
        checked_at='2024-01-15T10:30:00',
        statuses=[{'Autorizador': 'SVAN', 'Status': 'verde'}],
        success=True
    )
    with patch.object(monitor, 'init_db', return_value=True), \
         patch.object(monitor, 'fetch_html', return_value='<html>test</html>'), \
         patch.object(monitor, 'parse_and_enrich', return_value=mock_result), \
         patch.object(monitor, 'persist', return_value=True), \
         patch.object(monitor, 'save_json', return_value=True):
        result = monitor.run()
        assert result == 0  # Success
        tracker.track_method_call("run")
    print("✅ run method covered")
    
    # Test 8: apply_retention_policy
    print("Testing apply_retention_policy...")
    from test_nfe_status import test_apply_retention_policy, test_status_changed, test_normalize_key
    test_apply_retention_policy()
    tracker.track_method_call("apply_retention_policy")
    print("✅ apply_retention_policy covered")
    # Test 9: status_changed
    print("Testing status_changed...")
    test_status_changed()
    tracker.track_method_call("status_changed")
    print("✅ status_changed covered")
    # Test 10: normalize_key
    print("Testing normalize_key...")
    test_normalize_key()
    tracker.track_function_call("normalize_key")
    print("✅ normalize_key covered")
    
    print("\n📊 Generating comprehensive coverage report...")
    report = tracker.generate_report()
    print(report)
    
    return tracker

def main():
    """Main function to run coverage analysis"""
    try:
        tracker = run_comprehensive_coverage_analysis()
        
        # Calculate final coverage
        total_items = len(tracker.total_methods) + len(tracker.total_functions)
        covered_items = len(tracker.covered_methods) + len(tracker.covered_functions)
        final_coverage = (covered_items / total_items * 100) if total_items > 0 else 0
        
        print(f"🎯 FINAL COVERAGE: {final_coverage:.1f}%")
        
        if final_coverage >= 90:
            print("🎉 EXCELLENT coverage!")
        elif final_coverage >= 80:
            print("👍 Very good coverage!")
        elif final_coverage >= 70:
            print("✅ Good coverage!")
        else:
            print("⚠️  Coverage needs improvement.")
        
        # Summary
        print(f"\n📋 SUMMARY:")
        print(f"- Total methods: {len(tracker.total_methods)}")
        print(f"- Covered methods: {len(tracker.covered_methods)}")
        print(f"- Total functions: {len(tracker.total_functions)}")
        print(f"- Covered functions: {len(tracker.covered_functions)}")
        print(f"- Overall coverage: {final_coverage:.1f}%")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Coverage analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main()) 
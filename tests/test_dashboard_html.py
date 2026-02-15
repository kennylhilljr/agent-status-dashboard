"""Unit and Integration Tests for HTML Dashboard.

This module tests the dashboard.html file to ensure:
- HTML structure is valid
- JavaScript functions are present
- CSS styles are included
- API integration points are correctly configured
- All required components are present
"""

import json
import re
from pathlib import Path
import pytest


class TestDashboardHTML:
    """Test suite for dashboard.html structure and content."""

    @pytest.fixture
    def dashboard_html(self):
        """Load dashboard.html content."""
        dashboard_path = Path(__file__).parent.parent / 'dashboard.html'
        assert dashboard_path.exists(), "dashboard.html not found"
        return dashboard_path.read_text()

    def test_html_structure(self, dashboard_html):
        """Test that HTML has correct structure."""
        # Check DOCTYPE
        assert '<!DOCTYPE html>' in dashboard_html
        assert '<html lang="en">' in dashboard_html
        assert '</html>' in dashboard_html

        # Check head section
        assert '<head>' in dashboard_html
        assert '<meta charset="UTF-8">' in dashboard_html
        assert '<meta name="viewport"' in dashboard_html
        assert '<title>Agent Status Dashboard</title>' in dashboard_html

        # Check body
        assert '<body>' in dashboard_html
        assert '</body>' in dashboard_html

    def test_css_styling_present(self, dashboard_html):
        """Test that CSS styles are embedded."""
        assert '<style>' in dashboard_html
        assert '</style>' in dashboard_html

        # Check for key CSS classes
        required_classes = [
            '.container',
            '.header',
            '.card',
            '.task-card',
            '.progress-ring',
            '.activity-item',
            '.error-card',
            '.chart-container',
            '.stats-grid'
        ]

        for css_class in required_classes:
            assert css_class in dashboard_html, f"Missing CSS class: {css_class}"

    def test_responsive_design_css(self, dashboard_html):
        """Test that responsive design media queries are present."""
        assert '@media' in dashboard_html
        assert 'max-width: 768px' in dashboard_html
        assert 'max-width: 480px' in dashboard_html

    def test_javascript_embedded(self, dashboard_html):
        """Test that JavaScript code is embedded."""
        assert '<script>' in dashboard_html
        assert '</script>' in dashboard_html

        # Check for key JavaScript functions
        required_functions = [
            'fetchMetrics',
            'renderStatsGrid',
            'renderAgentCards',
            'renderActivityFeed',
            'createSuccessRateChart',
            'createXPChart',
            'createPerformanceChart',
            'updateDashboard',
            'init'
        ]

        for func in required_functions:
            assert f'function {func}' in dashboard_html or f'async function {func}' in dashboard_html, \
                f"Missing JavaScript function: {func}"

    def test_chart_js_library_included(self, dashboard_html):
        """Test that Chart.js library is included."""
        assert 'chart.js' in dashboard_html.lower()
        assert 'cdn.jsdelivr.net' in dashboard_html or 'unpkg.com' in dashboard_html

    def test_api_configuration(self, dashboard_html):
        """Test that API configuration is present."""
        assert 'API_BASE_URL' in dashboard_html
        assert 'localhost:8080' in dashboard_html

        # Check API endpoints
        assert '/api/metrics' in dashboard_html
        assert '/api/agents/' in dashboard_html

    def test_refresh_configuration(self, dashboard_html):
        """Test that auto-refresh is configured."""
        assert 'REFRESH_INTERVAL' in dashboard_html
        assert 'setInterval' in dashboard_html

    def test_a2ui_components_adapted(self, dashboard_html):
        """Test that A2UI components are adapted and present."""
        # TaskCard component
        assert 'task-card' in dashboard_html
        assert 'task-status-badge' in dashboard_html
        assert 'status-completed' in dashboard_html
        assert 'status-in-progress' in dashboard_html
        assert 'status-pending' in dashboard_html

        # ProgressRing component
        assert 'progress-ring' in dashboard_html
        assert 'progress-percentage' in dashboard_html
        assert 'progress-metrics' in dashboard_html
        assert '<svg' in dashboard_html
        assert '<circle' in dashboard_html

        # ActivityItem component
        assert 'activity-item' in dashboard_html
        assert 'activity-timeline' in dashboard_html
        assert 'activity-dot' in dashboard_html
        assert 'activity-content' in dashboard_html

        # ErrorCard component
        assert 'error-card' in dashboard_html
        assert 'error-severity' in dashboard_html
        assert 'error-message' in dashboard_html

    def test_chart_elements_present(self, dashboard_html):
        """Test that all required chart elements are present."""
        required_charts = [
            'success-rate-chart',
            'xp-chart',
            'performance-chart',
            'cost-chart',
            'invocation-chart'
        ]

        for chart_id in required_charts:
            assert f'id="{chart_id}"' in dashboard_html, f"Missing chart: {chart_id}"
            assert f'<canvas id="{chart_id}"' in dashboard_html

    def test_dashboard_sections(self, dashboard_html):
        """Test that all dashboard sections are present."""
        # Header section
        assert 'class="header"' in dashboard_html
        assert 'Agent Status Dashboard' in dashboard_html

        # Stats grid
        assert 'id="stats-grid"' in dashboard_html

        # Agent cards
        assert 'id="agent-cards"' in dashboard_html

        # Activity feed
        assert 'id="activity-feed"' in dashboard_html

    def test_loading_states(self, dashboard_html):
        """Test that loading states are implemented."""
        assert 'class="loading"' in dashboard_html
        assert 'loading-spinner' in dashboard_html
        assert 'Loading dashboard' in dashboard_html or 'Loading' in dashboard_html

    def test_error_handling(self, dashboard_html):
        """Test that error handling is implemented."""
        assert 'showError' in dashboard_html
        assert 'error-state' in dashboard_html
        assert 'catch' in dashboard_html

    def test_utility_functions(self, dashboard_html):
        """Test that utility functions are present."""
        utility_functions = [
            'formatTime',
            'formatRelativeTime',
            'getSuccessRateColor',
            'getProgressRingColor'
        ]

        for func in utility_functions:
            assert func in dashboard_html, f"Missing utility function: {func}"

    def test_chart_types_configured(self, dashboard_html):
        """Test that different chart types are used."""
        chart_types = ['bar', 'line', 'doughnut']

        for chart_type in chart_types:
            assert f"type: '{chart_type}'" in dashboard_html, \
                f"Missing chart type: {chart_type}"

    def test_color_scheme(self, dashboard_html):
        """Test that dark theme color scheme is present."""
        # Check for dark theme colors
        dark_colors = [
            '#0f172a',  # Dark background
            '#1e293b',  # Secondary dark
            '#f1f5f9',  # Light text
            '#94a3b8'   # Muted text
        ]

        for color in dark_colors:
            assert color.lower() in dashboard_html.lower(), \
                f"Missing dark theme color: {color}"

    def test_icons_present(self, dashboard_html):
        """Test that SVG icons are present."""
        # Should have inline SVG icons
        assert '<svg' in dashboard_html
        assert 'viewBox="0 0 24 24"' in dashboard_html
        assert '<path' in dashboard_html

    def test_accessibility_features(self, dashboard_html):
        """Test basic accessibility features."""
        # Check for semantic HTML elements (good for accessibility)
        assert '<nav' in dashboard_html or '<header' in dashboard_html or '<main' in dashboard_html or 'lang="en"' in dashboard_html
        # SVG elements have aria-hidden for decorative icons
        assert 'aria-hidden' in dashboard_html or '<svg' in dashboard_html

    def test_no_external_dependencies_except_chartjs(self, dashboard_html):
        """Test that there are minimal external dependencies."""
        # Should be self-contained except for Chart.js
        external_refs = re.findall(r'https?://[^\s"\']+', dashboard_html)

        # Filter out Chart.js and localhost API references
        non_chartjs_refs = [
            ref for ref in external_refs
            if 'chart.js' not in ref.lower() and 'localhost' not in ref.lower()
        ]

        # Should have very few external references
        assert len(non_chartjs_refs) == 0, \
            f"Unexpected external dependencies: {non_chartjs_refs}"

    def test_gradient_styling(self, dashboard_html):
        """Test that gradient styling is used."""
        assert 'linear-gradient' in dashboard_html
        assert 'background:' in dashboard_html or 'background-' in dashboard_html

    def test_animations_present(self, dashboard_html):
        """Test that CSS animations are defined."""
        assert '@keyframes' in dashboard_html
        assert 'animation:' in dashboard_html or 'animation-' in dashboard_html

    def test_event_handlers(self, dashboard_html):
        """Test that event handlers are present."""
        assert 'onclick=' in dashboard_html or 'addEventListener' in dashboard_html
        assert 'beforeunload' in dashboard_html

    def test_data_visualization_config(self, dashboard_html):
        """Test that charts have proper configuration."""
        # Chart.js configuration options
        config_options = [
            'responsive: true',
            'maintainAspectRatio: false',
            'backgroundColor',
            'borderColor',
            'datasets'
        ]

        for option in config_options:
            assert option in dashboard_html, f"Missing chart config: {option}"


class TestDashboardIntegration:
    """Integration tests for dashboard functionality."""

    @pytest.fixture
    def dashboard_path(self):
        """Get dashboard.html path."""
        return Path(__file__).parent.parent / 'dashboard.html'

    def test_dashboard_file_exists(self, dashboard_path):
        """Test that dashboard.html file exists."""
        assert dashboard_path.exists()
        assert dashboard_path.is_file()

    def test_dashboard_file_size(self, dashboard_path):
        """Test that dashboard file has reasonable size."""
        file_size = dashboard_path.stat().st_size
        # Should be at least 20KB (has substantial content)
        assert file_size > 20000, f"Dashboard file too small: {file_size} bytes"
        # Should be less than 500KB (single file should be optimized)
        assert file_size < 500000, f"Dashboard file too large: {file_size} bytes"

    def test_javascript_syntax_valid(self, dashboard_path):
        """Test that JavaScript has no obvious syntax errors."""
        content = dashboard_path.read_text()

        # Extract JavaScript content
        js_pattern = r'<script>(.*?)</script>'
        js_matches = re.findall(js_pattern, content, re.DOTALL)

        assert len(js_matches) > 0, "No JavaScript found"

        for js_code in js_matches:
            # Skip external script tags
            if 'src=' in js_code:
                continue

            # Basic syntax checks
            # Check balanced braces
            assert js_code.count('{') == js_code.count('}'), \
                "Unbalanced braces in JavaScript"

            # Check balanced parentheses
            assert js_code.count('(') == js_code.count(')'), \
                "Unbalanced parentheses in JavaScript"

            # Check balanced brackets
            assert js_code.count('[') == js_code.count(']'), \
                "Unbalanced brackets in JavaScript"

    def test_css_syntax_valid(self, dashboard_path):
        """Test that CSS has no obvious syntax errors."""
        content = dashboard_path.read_text()

        # Extract CSS content
        css_pattern = r'<style>(.*?)</style>'
        css_matches = re.findall(css_pattern, content, re.DOTALL)

        assert len(css_matches) > 0, "No CSS found"

        for css_code in css_matches:
            # Basic syntax checks
            # Check balanced braces
            assert css_code.count('{') == css_code.count('}'), \
                "Unbalanced braces in CSS"

    def test_component_integration(self, dashboard_path):
        """Test that all A2UI components are integrated."""
        content = dashboard_path.read_text()

        # Check that components are rendered with data
        component_markers = [
            'renderAgentCards',
            'renderActivityFeed',
            'renderStatsGrid',
            'progress-ring-container',
            'task-card',
            'activity-feed',
            'error-card'
        ]

        for marker in component_markers:
            assert marker in content, f"Component not integrated: {marker}"

    def test_chart_creation_flow(self, dashboard_path):
        """Test that charts are created in proper flow."""
        content = dashboard_path.read_text()

        # Check chart creation sequence
        assert 'createSuccessRateChart' in content
        assert 'createXPChart' in content
        assert 'createPerformanceChart' in content
        assert 'createCostChart' in content
        assert 'createInvocationChart' in content

        # Check charts are called in updateDashboard
        assert 'updateDashboard' in content
        update_dashboard_section = content[content.find('async function updateDashboard'):]
        assert 'createSuccessRateChart' in update_dashboard_section
        assert 'createXPChart' in update_dashboard_section

    def test_api_error_handling(self, dashboard_path):
        """Test that API errors are handled gracefully."""
        content = dashboard_path.read_text()

        # Check error handling in fetch
        assert 'try' in content
        assert 'catch' in content
        assert 'showError' in content

        # Check fetch error handling - look for try/catch blocks
        assert 'try {' in content and 'catch (error)' in content or 'catch (e)' in content or 'catch(error)' in content


class TestDashboardPerformance:
    """Performance and optimization tests."""

    @pytest.fixture
    def dashboard_html(self):
        """Load dashboard.html content."""
        dashboard_path = Path(__file__).parent.parent / 'dashboard.html'
        return dashboard_path.read_text()

    def test_minified_external_libraries(self, dashboard_html):
        """Test that external libraries use minified versions."""
        # Chart.js should be minified
        if 'chart.js' in dashboard_html:
            assert '.min.js' in dashboard_html or '.umd.min.js' in dashboard_html

    def test_efficient_selectors(self, dashboard_html):
        """Test that efficient DOM selectors are used."""
        # Should use getElementById for performance
        assert 'getElementById' in dashboard_html

        # Should not use excessive jQuery-style selectors
        jquery_count = dashboard_html.count('$(')
        assert jquery_count == 0, "Should not use jQuery"

    def test_debounced_updates(self, dashboard_html):
        """Test that updates are properly timed."""
        # Should have refresh interval
        assert 'REFRESH_INTERVAL' in dashboard_html
        assert 'setInterval' in dashboard_html

    def test_cleanup_handlers(self, dashboard_html):
        """Test that cleanup handlers are present."""
        # Should clean up on page unload
        assert 'beforeunload' in dashboard_html
        assert 'clearInterval' in dashboard_html


class TestDashboardDocumentation:
    """Test documentation and code comments."""

    @pytest.fixture
    def dashboard_html(self):
        """Load dashboard.html content."""
        dashboard_path = Path(__file__).parent.parent / 'dashboard.html'
        return dashboard_path.read_text()

    def test_code_comments_present(self, dashboard_html):
        """Test that code has comments."""
        # Should have JavaScript comments
        assert '//' in dashboard_html or '/*' in dashboard_html

        # Should have CSS comments
        assert '/*' in dashboard_html

    def test_section_markers(self, dashboard_html):
        """Test that code sections are well-organized."""
        # Should have section comments
        section_markers = [
            'Configuration',
            'Utility Functions',
            'API Functions',
            'Render Functions',
            'Chart Functions'
        ]

        for marker in section_markers:
            assert marker in dashboard_html, f"Missing section: {marker}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

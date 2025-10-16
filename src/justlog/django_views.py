# django_views.py
import logging
from pathlib import Path
from typing import List, Tuple

from .log import lg


def log_viewer_view(request):
    """
    Django view for displaying logs with pagination and level filtering.

    URL parameters:
    - page: Page number (default: 1)
    - level: Minimum log level to display (default: info)
    - per_page: Number of log entries per page (default: 200)
    """
    from django.http import HttpResponse, Http404
    from django.utils.html import escape

    # Get log file path from lg instance
    if not lg.log_file_path or not lg.log_file_path.exists():
        return HttpResponse(
            '<html><body><h1>JustLog Viewer</h1><p>No log file found. '
            'Have you called setup_logging()?</p></body></html>'
        )

    # Get query parameters
    level_name = request.GET.get('level', 'info').upper()
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 200))

    # Map level names to numeric values
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

    min_level = level_map.get(level_name, logging.INFO)

    # Read and filter log lines
    log_lines = _read_and_filter_logs(lg.log_file_path, min_level)

    # Reverse so newest logs are first
    log_lines.reverse()

    # Pagination
    total_lines = len(log_lines)
    total_pages = (total_lines + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_lines = log_lines[start_idx:end_idx]

    # Build HTML response
    html = _build_html_response(
        page_lines=page_lines,
        page=page,
        total_pages=total_pages,
        total_lines=total_lines,
        level_name=level_name,
        per_page=per_page,
    )

    return HttpResponse(html)


def _read_and_filter_logs(log_path: Path, min_level: int) -> List[str]:
    """
    Reads log file and filters by minimum level.
    Returns list of log lines that meet the level threshold.
    """
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

    filtered_lines = []

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Parse log level from line
                # Expected format: "2025-10-05 15:23:45 INFO message"
                parts = line.strip().split()
                if len(parts) >= 3:
                    level_str = parts[2]
                    line_level = level_map.get(level_str, logging.NOTSET)

                    if line_level >= min_level:
                        filtered_lines.append(line)
                else:
                    # Include lines that don't match format (e.g., multi-line)
                    filtered_lines.append(line)
    except Exception as e:
        filtered_lines = [f'Error reading log file: {e}']

    return filtered_lines


def _build_html_response(
    page_lines: List[str],
    page: int,
    total_pages: int,
    total_lines: int,
    level_name: str,
    per_page: int,
) -> str:
    """
    Builds HTML response for log viewer.
    """
    from django.utils.html import escape

    # Color mapping for log levels
    level_colors = {
        'DEBUG': '#6c757d',
        'INFO': '#0d6efd',
        'WARNING': '#ffc107',
        'ERROR': '#dc3545',
        'CRITICAL': '#6f42c1',
    }

    # Build log lines HTML with syntax highlighting
    log_html_lines = []
    for line in page_lines:
        line = escape(line.rstrip())

        # Apply color to log level
        for level, color in level_colors.items():
            if f' {level} ' in line:
                line = line.replace(
                    f' {level} ',
                    f' <span style="color: {color}; font-weight: bold;">{level}</span> '
                )
                break

        log_html_lines.append(f'<div class="log-line">{line}</div>')

    log_content = '\n'.join(log_html_lines) if log_html_lines else '<p>No logs found.</p>'

    # Build pagination controls
    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < total_pages else None

    pagination_html = '<div class="pagination">'
    if prev_page:
        pagination_html += f'<a href="?level={level_name.lower()}&page={prev_page}&per_page={per_page}">« Previous</a> '
    else:
        pagination_html += '<span class="disabled">« Previous</span> '

    pagination_html += f'<span class="page-info">Page {page} of {total_pages} ({total_lines} logs)</span>'

    if next_page:
        pagination_html += f' <a href="?level={level_name.lower()}&page={next_page}&per_page={per_page}">Next »</a>'
    else:
        pagination_html += ' <span class="disabled">Next »</span>'

    pagination_html += '</div>'

    # Build level filter
    levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    level_filter_html = '<div class="level-filter">Filter by level: '
    for level in levels:
        if level == level_name:
            level_filter_html += f'<span class="active">{level}</span> '
        else:
            level_filter_html += f'<a href="?level={level.lower()}&page=1&per_page={per_page}">{level}</a> '
    level_filter_html += '</div>'

    # Complete HTML
    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>JustLog Viewer</title>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: 'Courier New', monospace;
            background-color: #1e1e1e;
            color: #d4d4d4;
            margin: 0;
            padding: 20px;
        }}
        h1 {{
            color: #4fc3f7;
            margin-bottom: 10px;
        }}
        .controls {{
            background-color: #2d2d2d;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .level-filter {{
            margin-bottom: 10px;
        }}
        .level-filter a, .pagination a {{
            color: #4fc3f7;
            text-decoration: none;
            padding: 5px 10px;
            background-color: #3a3a3a;
            border-radius: 3px;
            margin-right: 5px;
        }}
        .level-filter a:hover, .pagination a:hover {{
            background-color: #4a4a4a;
        }}
        .level-filter .active {{
            color: #fff;
            background-color: #0d6efd;
            padding: 5px 10px;
            border-radius: 3px;
            margin-right: 5px;
            font-weight: bold;
        }}
        .pagination {{
            margin-top: 10px;
        }}
        .pagination .disabled {{
            color: #666;
            padding: 5px 10px;
        }}
        .pagination .page-info {{
            color: #aaa;
            margin: 0 10px;
        }}
        .log-container {{
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 5px;
            padding: 15px;
            overflow-x: auto;
        }}
        .log-line {{
            line-height: 1.5;
            padding: 2px 0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .log-line:hover {{
            background-color: #161b22;
        }}
    </style>
</head>
<body>
    <h1>JustLog Viewer</h1>
    <div class="controls">
        {level_filter_html}
        {pagination_html}
    </div>
    <div class="log-container">
        {log_content}
    </div>
    <div class="controls">
        {pagination_html}
    </div>
</body>
</html>'''

    return html

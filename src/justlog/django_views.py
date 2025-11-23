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
    - source: Data source ('file' or 'db', default: 'file')
    """
    from django.http import HttpResponse, Http404
    from django.utils.html import escape

    # Get query parameters
    source = request.GET.get('source', 'file')
    level_name = request.GET.get('level', 'info').upper()
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 200))

    # Check if we can read from the requested source
    if source == 'file':
        if not lg.log_file_path or not lg.log_file_path.exists():
            return HttpResponse(
                '<html><body><h1>JustLog Viewer</h1><p>No log file found. '
                'Have you called setup_logging()?</p></body></html>'
            )

    # Map level names to numeric values
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

    min_level = level_map.get(level_name, logging.INFO)

    # Read log entries from the selected source
    if source == 'db':
        log_entries = _read_logs_from_database(min_level)
    else:
        log_entries = _read_and_filter_logs(lg.log_file_path, min_level)

    # Reverse so newest logs are first
    log_entries.reverse()

    # Pagination by complete entries (never split an entry)
    total_entries = len(log_entries)
    total_pages = (total_entries + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_entries = log_entries[start_idx:end_idx]

    # Build HTML response
    html = _build_html_response(
        page_entries=page_entries,
        page=page,
        total_pages=total_pages,
        total_entries=total_entries,
        level_name=level_name,
        per_page=per_page,
        source=source,
    )

    return HttpResponse(html)


def _read_logs_from_database(min_level: int) -> List[List[str]]:
    """
    Reads log entries from database and formats them like file entries.
    Returns list of log entries (each entry is a list of lines).
    """
    try:
        from .models import LogEntry
        from django.utils.html import escape
        import json

        # Query database for logs at or above min_level, ordered newest first
        entries = LogEntry.objects.filter(level__gte=min_level).order_by('-timestamp')

        formatted_entries = []
        for entry in entries:
            lines = []

            # Format main log line (matching file format)
            timestamp_str = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            level_name = entry.get_level_display()
            main_line = f'{timestamp_str} {level_name} {entry.message}'
            lines.append(main_line)

            # Add extra_args if present
            if entry.extra_args:
                for arg in entry.extra_args:
                    lines.append(f'  {arg}')

            # Add extra_kwargs if present
            if entry.extra_kwargs:
                for key, value in entry.extra_kwargs.items():
                    # Check if value looks like JSON
                    if isinstance(value, str) and (
                        (value.startswith('{') and value.endswith('}')) or
                        (value.startswith('[') and value.endswith(']'))
                    ):
                        # Multi-line formatting
                        try:
                            parsed = json.loads(value)
                            formatted = json.dumps(parsed, indent=2)
                            lines.append(f'  {key}:')
                            for line in formatted.split('\n'):
                                lines.append(f'    {line}')
                        except json.JSONDecodeError:
                            lines.append(f'  {key}: {value}')
                    else:
                        lines.append(f'  {key}: {value}')

            formatted_entries.append(lines)

        return formatted_entries

    except Exception as e:
        return [[f'Error reading from database: {e}']]


def _read_and_filter_logs(log_path: Path, min_level: int) -> List[List[str]]:
    """
    Reads log file and filters by minimum level.
    Returns list of log entries (each entry is a list of lines).
    Multi-line entries (like stack traces) are kept together.
    """
    import re

    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

    # Pattern to match log entry start: date/time followed by log level
    # Example: "2025-10-05 15:23:45 INFO message"
    log_start_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}')

    entries = []
    current_entry = []
    current_level = logging.NOTSET

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Check if this line starts a new log entry
                if log_start_pattern.match(line):
                    # Save previous entry if it meets the level threshold
                    if current_entry and current_level >= min_level:
                        entries.append(current_entry)

                    # Start new entry
                    current_entry = [line]

                    # Parse log level from line
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        level_str = parts[2]
                        current_level = level_map.get(level_str, logging.NOTSET)
                    else:
                        current_level = logging.NOTSET
                else:
                    # Continuation line (e.g., stack trace)
                    if current_entry:
                        current_entry.append(line)

            # Don't forget the last entry
            if current_entry and current_level >= min_level:
                entries.append(current_entry)

    except Exception as e:
        entries = [[f'Error reading log file: {e}\n']]

    return entries


def _build_html_response(
    page_entries: List[List[str]],
    page: int,
    total_pages: int,
    total_entries: int,
    level_name: str,
    per_page: int,
    source: str = 'file',
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

    # Build log entries HTML with syntax highlighting
    log_html_entries = []
    for entry in page_entries:
        entry_html_lines = []
        for line in entry:
            line = escape(line.rstrip())

            # Apply color to log level (only in first line)
            for level, color in level_colors.items():
                if f' {level} ' in line:
                    line = line.replace(
                        f' {level} ',
                        f' <span style="color: {color}; font-weight: bold;">{level}</span> ',
                        1  # Only replace first occurrence
                    )
                    break

            entry_html_lines.append(line)

        # Wrap each complete entry in a div
        entry_html = '<div class="log-entry">' + '<br>'.join(entry_html_lines) + '</div>'
        log_html_entries.append(entry_html)

    log_content = '\n'.join(log_html_entries) if log_html_entries else '<p>No logs found.</p>'

    # Build pagination controls
    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < total_pages else None

    pagination_html = '<div class="pagination">'
    if prev_page:
        pagination_html += f'<a href="?source={source}&level={level_name.lower()}&page={prev_page}&per_page={per_page}">« Previous</a> '
    else:
        pagination_html += '<span class="disabled">« Previous</span> '

    pagination_html += f'<span class="page-info">Page {page} of {total_pages} ({total_entries} entries)</span>'

    if next_page:
        pagination_html += f' <a href="?source={source}&level={level_name.lower()}&page={next_page}&per_page={per_page}">Next »</a>'
    else:
        pagination_html += ' <span class="disabled">Next »</span>'

    pagination_html += '</div>'

    # Build source selector
    source_selector_html = '<div class="source-selector">Source: '
    for src in ['file', 'db']:
        src_label = 'File' if src == 'file' else 'Database'
        if src == source:
            source_selector_html += f'<span class="active">{src_label}</span> '
        else:
            source_selector_html += f'<a href="?source={src}&level={level_name.lower()}&page=1&per_page={per_page}">{src_label}</a> '
    source_selector_html += '</div>'

    # Build level filter
    levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    level_filter_html = '<div class="level-filter">Filter by level: '
    for level in levels:
        if level == level_name:
            level_filter_html += f'<span class="active">{level}</span> '
        else:
            level_filter_html += f'<a href="?source={source}&level={level.lower()}&page=1&per_page={per_page}">{level}</a> '
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
        .source-selector {{
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid #3a3a3a;
        }}
        .level-filter {{
            margin-bottom: 10px;
        }}
        .source-selector a, .source-selector .active {{
            color: #4fc3f7;
            text-decoration: none;
            padding: 5px 10px;
            background-color: #3a3a3a;
            border-radius: 3px;
            margin-right: 5px;
        }}
        .source-selector .active {{
            color: #fff;
            background-color: #28a745;
            font-weight: bold;
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
        .log-entry {{
            line-height: 1.5;
            padding: 8px 0;
            white-space: pre-wrap;
            word-wrap: break-word;
            border-bottom: 1px solid #21262d;
            margin-bottom: 5px;
        }}
        .log-entry:last-child {{
            border-bottom: none;
        }}
        .log-entry:hover {{
            background-color: #161b22;
        }}
    </style>
</head>
<body>
    <h1>JustLog Viewer</h1>
    <div class="controls">
        {source_selector_html}
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

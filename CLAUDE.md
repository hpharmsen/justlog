# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- **Activate virtual environment**: `source venv/bin/activate` (or use direnv with `.envrc`)
- **Install development dependencies**: `pip install build twine` (for packaging)
- **Test import**: `python -c "from src.justlog import lg, setup_logging; print('Import successful')"`
- **Linting**: `ruff check src/` and `ruff format src/` (configured with line-length = 100)

### Packaging Commands

- **Build package**: `python -m build` (creates wheel and source distribution in `dist/`)
- **Upload to TestPyPI**: `twine upload --repository testpypi dist/*`
- **Upload to PyPI**: `twine upload dist/*`
- **Install locally**: `pip install -e .` (editable install for development)

## Project Structure

This is a Python logging utility packaged for PyPI distribution:

- `src/justlog/`: Main package directory
  - `__init__.py`: Package exports (`lg`, `setup_logging`) and version info
  - `log.py`: Core logging module with `_LoggerProxy` class and `lg` singleton
- `src/__init__.py`: Makes src a package for development
- `pyproject.toml`: Package metadata and build configuration
- `README.md`: Package documentation for PyPI
- Uses a virtual environment in `venv/` directory
- Project uses direnv for environment management (`.envrc` file)
- Configured with Ruff linter (100 character line length)

## Architecture

The project implements a singleton-pattern logging proxy:

- `_LoggerProxy` class provides a facade over Python's standard logging
- `lg` is the importable singleton instance used throughout applications
- Supports file rotation, stderr output, and automatic log cleanup based on age
- Handles uncaught exceptions by logging them before termination
- Self-bootstraps with minimal stderr logger if setup_logging() not called

Key features:
- Rotating file handler with configurable size limits and backup counts
- Optional stderr output with separate log level control
- Automatic directory creation for log files
- Time-based log cleanup (backup_days parameter)
- Exception hook integration for uncaught exception logging
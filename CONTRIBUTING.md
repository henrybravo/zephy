# Contributing to Zephy

Thank you for your interest in contributing to Zephy!

## Getting Started

### Prerequisites

- Python 3.10 or higher
- `uv` package manager (recommended) or `pip`

### Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/henrybravo/zephy.git
   cd zephy
   ```

2. Create and activate a virtual environment:
   ```bash
   uv venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   uv pip install -e .[dev]
   ```

## Running Tests

```bash
pytest tests/ -v --cov=zephy --cov-report=html
```

## Code Style

We follow PEP 8 guidelines. Before submitting, please run:

```bash
black zephy/
flake8 zephy/
mypy zephy/
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Commit your changes (`git commit -m 'Add some feature'`)
7. Push to your fork (`git push origin feature/your-feature`)
8. Open a Pull Request

## Reporting Issues

Please use GitHub Issues to report bugs or request features. Include:

- Clear description of the issue
- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Your environment (OS, Python version, etc.)

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help maintain a welcoming community

## Questions?

Feel free to open an issue for questions or discussions.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

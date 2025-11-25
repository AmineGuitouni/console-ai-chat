# ai-chat-console

Advanced AI console chat application with multi-provider support, tool calling, and MCP integration.

## Quick Start

1. Create a virtual environment and install dev tools (recommended):

   ```powershell
   python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -U pip
   pip install hatchling uv
   ```

2. Configure your API keys (see [Security](#security) section below):

   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml and add your API key
   ```

3. Run the console:

   ```powershell
   uv run ai-chat chat
   ```

## Security

**⚠️ IMPORTANT: Never commit API keys or secrets to version control!**

### API Key Management

This application requires API keys to access AI providers. Follow these best practices:

1. **Use the config.yaml file** (automatically gitignored):
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your actual API key
   ```

2. **Or use environment variables**:
   ```bash
   export AI_API_KEY="your-api-key-here"
   export AI_PROVIDER="anthropic"
   export AI_MODEL="claude-3-5-sonnet-20241022"
   ```

3. **Protected files** (automatically excluded by .gitignore):
   - `config.yaml` - Configuration with API keys
   - `.env` - Environment variables
   - `*.key`, `*.pem`, `*.p12` - Certificate/key files

### Pre-commit Hooks

Install pre-commit hooks to prevent accidental secret commits:

```bash
pip install pre-commit
pre-commit install
```

This will automatically scan for secrets before each commit.

See [SECURITY.md](SECURITY.md) for more details on security practices and reporting vulnerabilities.
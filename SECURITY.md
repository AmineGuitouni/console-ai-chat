# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it by:

1. **DO NOT** create a public GitHub issue
2. Send a private report to the repository maintainers
3. Include a detailed description of the vulnerability
4. Include steps to reproduce if applicable

We will acknowledge receipt of your report within 48 hours and provide a timeline for a fix.

## Secret Management

This application requires API keys to function. **NEVER** commit API keys, tokens, or other secrets to the repository.

### Best Practices

1. **Use Environment Variables**: Store API keys in environment variables or `.env` files
   ```bash
   export AI_API_KEY="your-api-key-here"
   ```

2. **Use Configuration Files**: Store API keys in `config.yaml` (which is gitignored)
   - Copy `config.example.yaml` to `config.yaml`
   - Update the `api_key` field with your actual key
   - The `config.yaml` file is automatically excluded from version control

3. **Never Hardcode**: Do not hardcode API keys in source code

### Protected Files

The following files are automatically excluded from version control via `.gitignore`:
- `config.yaml` - Main configuration file with API keys
- `.env` - Environment variables file
- `*.key` - Private key files
- `*.pem` - Certificate files
- `*.p12` - Certificate files

### Pre-commit Hooks

This project uses pre-commit hooks to prevent accidental secret commits:

1. Install pre-commit hooks:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

2. The hooks will automatically:
   - Scan for hardcoded secrets using gitleaks
   - Detect private keys
   - Validate YAML/JSON files
   - Format and lint code

### Continuous Security Scanning

GitHub Actions automatically scans for secrets on:
- Every push to main/develop branches
- Every pull request
- Daily scheduled scans

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Updates

Security updates will be released as soon as possible after a vulnerability is confirmed.

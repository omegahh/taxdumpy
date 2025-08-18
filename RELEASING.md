# Release Guide for taxdumpy

This document explains how to release new versions of taxdumpy to PyPI.

## Setup (One-time configuration)

### 1. PyPI Account Setup

1. Create accounts on:
   - [PyPI](https://pypi.org/account/register/) (production)
   - [Test PyPI](https://test.pypi.org/account/register/) (testing)

2. Enable 2FA on both accounts

3. Create API tokens:
   - Go to Account Settings → API tokens
   - Create a token with scope "Entire account" or specific to your package

### 2. GitHub Repository Setup

#### Configure PyPI Trusted Publishing (Recommended)

PyPI now supports "trusted publishing" which eliminates the need for API tokens in GitHub Actions.

1. Go to your PyPI project page
2. Navigate to "Publishing" tab
3. Add a new trusted publisher with:
   - **Owner**: `your-github-username`
   - **Repository name**: `taxdumpy`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `release`

#### Alternative: GitHub Secrets (if not using trusted publishing)

If you prefer using API tokens:

1. Go to your GitHub repository → Settings → Secrets and variables → Actions
2. Add repository secrets:
   - `PYPI_API_TOKEN`: Your PyPI API token
   - `TEST_PYPI_API_TOKEN`: Your Test PyPI API token

### 3. Local Development Setup

Install release dependencies:

```bash
pip install build twine
```

## Release Process

### Option 1: Automated Release (Recommended)

1. **Create a release via GitHub Actions**:
   - Go to your repository on GitHub
   - Click "Actions" → "Release" workflow
   - Click "Run workflow"
   - Enter the version number (e.g., `1.2.3`)
   - Choose if it's a pre-release
   - Click "Run workflow"

2. **What happens automatically**:
   - Updates version in `pyproject.toml`
   - Runs full test suite
   - Creates git tag
   - Creates GitHub release with changelog
   - Builds package
   - Publishes to PyPI

### Option 2: Semi-Automated Release

Use the release script:

```bash
# Test release (uploads to Test PyPI)
python scripts/release.py --version 1.2.3 --test --upload

# Production release
python scripts/release.py --version 1.2.3 --upload
```

### Option 3: Manual Release

1. **Update version** in `pyproject.toml`
2. **Run tests**: `python -m pytest tests/ -v`
3. **Check formatting**: `black --check src/ tests/`
4. **Commit and tag**:
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 1.2.3"
   git tag v1.2.3
   git push origin main
   git push origin v1.2.3
   ```
5. **Build package**: `python -m build --clean`
6. **Upload to PyPI**: `python -m twine upload dist/*`

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **Major** (`X.0.0`): Breaking changes
- **Minor** (`0.X.0`): New features, backwards compatible
- **Patch** (`0.0.X`): Bug fixes, backwards compatible

### Pre-release versions:
- **Alpha**: `1.2.3-alpha.1` (early development)
- **Beta**: `1.2.3-beta.1` (feature complete, testing)
- **Release Candidate**: `1.2.3-rc.1` (final testing)

## Workflow Triggers

The GitHub Actions workflows are triggered by:

### CI Workflow (`ci.yml`)
- Push to `main` or `develop` branches
- Pull requests to `main`
- Runs tests, linting, and builds package

### Production Release (`publish.yml`)
- Push of version tags (e.g., `v1.2.3`)
- Manual GitHub releases
- Publishes to PyPI

### Test Release (`publish-test.yml`)
- Push of pre-release tags (e.g., `v1.2.3-alpha.1`)
- Manual trigger
- Publishes to Test PyPI

### Release Workflow (`release.yml`)
- Manual trigger only
- Creates complete release with changelog

## Testing Releases

Before releasing to production PyPI:

1. **Test on Test PyPI**:
   ```bash
   python scripts/release.py --version 1.2.3-beta.1 --test --upload
   ```

2. **Install from Test PyPI**:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ taxdumpy==1.2.3b1
   ```

3. **Verify installation**:
   ```bash
   taxdumpy --help
   python -c "import taxdumpy; print(taxdumpy.__version__)"
   ```

## Troubleshooting

### Common Issues

1. **Version already exists on PyPI**:
   - Cannot re-upload the same version
   - Increment version number

2. **Build fails**:
   - Check `pyproject.toml` syntax
   - Ensure all dependencies are listed
   - Run `python -m build --clean` locally

3. **Tests fail in CI**:
   - Run tests locally: `python -m pytest tests/ -v`
   - Check for platform-specific issues
   - Review test data paths

4. **Trusted publishing fails**:
   - Verify publisher configuration on PyPI
   - Check workflow name and environment match
   - Ensure repository has correct permissions

### Emergency Fixes

If you need to quickly fix a critical issue:

1. Create a hotfix branch from the tag
2. Make minimal changes
3. Test thoroughly
4. Release as patch version (e.g., `1.2.3` → `1.2.4`)

## Post-Release

After a successful release:

1. **Verify on PyPI**: Check [https://pypi.org/project/taxdumpy/](https://pypi.org/project/taxdumpy/)
2. **Test installation**: `pip install taxdumpy`
3. **Update documentation** if needed
4. **Announce release** in relevant channels
5. **Create release notes** with:
   - New features
   - Bug fixes
   - Breaking changes
   - Migration guide (if needed)

## Security Notes

- Never commit API tokens to version control
- Use trusted publishing when possible
- Regularly rotate API tokens
- Review workflow permissions
- Keep dependencies updated
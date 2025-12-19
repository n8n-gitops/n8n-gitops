# Release Process

This document describes the process for creating a new release of n8n-gitops.

## Prerequisites

- Write access to the repository
- `gh` CLI tool installed (optional, for automated release creation)
- All changes merged to `main` branch
- All tests passing

## Release Checklist

### 1. Update Version Number

Update the version in `n8n_gitops/__init__.py`:

```python
__version__ = "X.Y.Z"  # Update to new version
```

**Version Format:**
- **Major (X)**: Breaking changes or major feature releases
- **Minor (Y)**: New features, backward compatible
- **Patch (Z)**: Bug fixes, backward compatible

### 2. Update CHANGELOG

Update `CHANGELOG.md` with the new version and release notes:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing features

### Fixed
- Bug fixes

### Removed
- Removed features
```

**Guidelines:**
- Use [Keep a Changelog](https://keepachangelog.com/) format
- Use ISO date format (YYYY-MM-DD)
- Group changes by category: Added, Changed, Deprecated, Removed, Fixed, Security
- Be descriptive and user-focused
- Include code examples where helpful

### 3. Commit Version Changes

```bash
git add n8n_gitops/__init__.py CHANGELOG.md
git commit -m "Release vX.Y.Z"
git push origin main
```

### 4. Create Git Tag

Create an annotated tag with the version number:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

**Important:** The tag must follow the format `vX.Y.Z` (with the `v` prefix) to trigger the GitHub Actions workflow.

### 5. Wait for CI Build

After pushing the tag:

1. Go to [GitHub Actions](../../actions)
2. Wait for the "Build, Lint and Test" workflow to complete
3. Verify all jobs passed (test and build)
4. The Linux binary will be uploaded as an artifact

### 6. Create GitHub Release

#### Option A: Using GitHub Web Interface

1. Go to [Releases](../../releases)
2. Click "Draft a new release"
3. Choose the tag: `vX.Y.Z`
4. Set the release title: `vX.Y.Z` or `n8n-gitops vX.Y.Z`
5. Copy the relevant section from `CHANGELOG.md` into the release description
6. Download the Linux binary artifact from the GitHub Actions run
7. Attach the binary to the release as `n8n-gitops-linux`
8. Check "Set as the latest release" (if applicable)
9. Click "Publish release"

#### Option B: Using GitHub CLI

```bash
# Download the artifact from the workflow run
gh run download --name n8n-gitops-linux

# Create the release with the artifact
gh release create vX.Y.Z \
  --title "n8n-gitops vX.Y.Z" \
  --notes-file <(sed -n "/## \[X.Y.Z\]/,/## \[/p" CHANGELOG.md | head -n -1) \
  n8n-gitops-linux/n8n-gitops#n8n-gitops-linux
```

## Release Artifacts

Each release should include:

- **Source code** (automatically included by GitHub)
- **Linux binary**: `n8n-gitops-linux` (built by GitHub Actions)
- **Release notes**: Extracted from CHANGELOG.md

## Post-Release

After creating the release:

1. Verify the release appears on the [Releases page](../../releases)
2. Test the binary download and execution
3. Announce the release (if applicable)
4. Close any related milestone

## Example: Complete Release Process

Here's a complete example for releasing version 0.3.0:

```bash
# 1. Update version in n8n_gitops/__init__.py
# Change: __version__ = "0.3.0"

# 2. Update CHANGELOG.md
# Add section for [0.3.0] with release notes

# 3. Commit changes
git add n8n_gitops/__init__.py CHANGELOG.md
git commit -m "Release v0.3.0"
git push origin main

# 4. Create and push tag
git tag -a v0.3.0 -m "Release v0.3.0"
git push origin v0.3.0

# 5. Wait for GitHub Actions to complete
# Monitor at: https://github.com/YOUR_USERNAME/n8n-gitops/actions

# 6. Create GitHub release
gh run download --name n8n-gitops-linux
gh release create v0.3.0 \
  --title "n8n-gitops v0.3.0" \
  --notes-file <(sed -n "/## \[0.3.0\]/,/## \[/p" CHANGELOG.md | head -n -1) \
  n8n-gitops-linux/n8n-gitops#n8n-gitops-linux
```

## Troubleshooting

### Build Fails

If the GitHub Actions build fails:

1. Fix the issue in your code
2. Delete the tag: `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z`
3. Start the release process again

### Wrong Version Number

If you need to change the version after tagging:

1. Delete the tag: `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z`
2. Update the version number
3. Amend the commit: `git commit --amend`
4. Force push: `git push origin main -f`
5. Create the tag again

### Release Already Exists

If a release with the same tag already exists:

1. Delete the release on GitHub
2. Delete the tag: `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z`
3. Start over

## Automation Opportunities

Consider automating the release process with:

- **GitHub Actions workflow** to automatically create releases when tags are pushed
- **Release Drafter** to automatically generate release notes from PRs
- **Semantic Release** to automatically determine version numbers based on commit messages

Example automated release workflow (`.github/workflows/release.yml`):

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - name: Download artifact
        uses: actions/download-artifact@v4
        with:
          name: n8n-gitops-linux
          path: dist/

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: dist/n8n-gitops
          generate_release_notes: true
          draft: false
```

## Notes

- Always test the release binary before publishing
- Keep the CHANGELOG up to date throughout development
- Use semantic versioning consistently
- Coordinate with contributors before major releases
- Consider creating a release candidate (e.g., v1.0.0-rc.1) for major versions

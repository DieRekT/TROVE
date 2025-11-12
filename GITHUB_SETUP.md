# 🔗 GitHub Setup & Sharing Guide

## Current Git Status

- **Branch**: `feature/deep-research`
- **Commits**: 4 commits
- **Remote**: None (not yet configured)
- **Status**: Has uncommitted changes

## 🚀 Setup GitHub Repository

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Create a new repository (e.g., `trove` or `archive-detective`)
3. **Don't** initialize with README, .gitignore, or license (we already have these)
4. Copy the repository URL (e.g., `https://github.com/yourusername/trove.git`)

### Step 2: Add Remote and Push

```bash
# Add remote repository
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# Or if using SSH:
# git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git

# Verify remote
git remote -v

# Stage all changes (except ignored files)
git add .

# Commit changes
git commit -m "Add full text scraping, tracked articles, and tunnel support"

# Push to GitHub
git push -u origin feature/deep-research

# Or push to main/master
# git checkout -b main
# git push -u origin main
```

### Step 3: Create Pull Request (if on feature branch)

1. Go to your GitHub repository
2. Click "Compare & pull request"
3. Review changes and create PR
4. Merge to main branch when ready

## 📤 Sharing via GitHub

### Option 1: Direct Repository Access

1. **Make repository public** (or add collaborators)
   - Go to Settings → General → Danger Zone → Change visibility
   - Or add collaborators: Settings → Collaborators → Add people

2. **Share repository URL**
   ```
   https://github.com/YOUR_USERNAME/YOUR_REPO
   ```

### Option 2: GitHub Integration in Cursor

1. **Open Cursor Settings**
   - Cmd+, (Mac) or Ctrl+, (Windows/Linux)
   - Search for "GitHub"

2. **Enable GitHub Integration**
   - Sign in with GitHub account
   - Authorize Cursor to access repositories

3. **Share via Cursor**
   - Cmd+K → Type "Share" → Select "Generate GitHub Repo Invite"
   - Or use GitHub Copilot integration if available

### Option 3: GitHub Gists (for code snippets)

For sharing specific files or code snippets:

```bash
# Install GitHub CLI (optional)
brew install gh  # macOS
# or download from https://cli.github.com

# Authenticate
gh auth login

# Create a gist
gh gist create app/archive_detective/article_io.py --public
```

## 🔒 Security Checklist

Before pushing to GitHub, ensure:

- [ ] `.env` files are ignored (✅ already in .gitignore)
- [ ] Database files are ignored (✅ added to .gitignore)
- [ ] Tunnel URLs are ignored (✅ added to .gitignore)
- [ ] API keys are not hardcoded
- [ ] Sensitive data is removed from code
- [ ] Credentials are stored in environment variables

## 📝 Recommended Git Workflow

### Feature Branch Workflow

```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes and commit
git add .
git commit -m "Add new feature"

# Push to GitHub
git push -u origin feature/new-feature

# Create Pull Request on GitHub
# Merge to main after review
```

### Commit Message Guidelines

- Use clear, descriptive messages
- Reference issues/PRs if applicable
- Examples:
  - `Add full text scraping with trafilatura fallback`
  - `Fix reader view text truncation issue`
  - `Implement tracked articles with 50-item limit`
  - `Add ngrok tunnel support for public access`

## 🔄 Syncing with Remote

```bash
# Pull latest changes
git pull origin main

# Push local changes
git push origin feature/deep-research

# Fetch without merging
git fetch origin

# View remote branches
git branch -r
```

## 🆘 Troubleshooting

### "Remote already exists"
```bash
# Remove existing remote
git remote remove origin

# Add new remote
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
```

### "Permission denied"
```bash
# Check SSH keys
ssh -T git@github.com

# Or use HTTPS with personal access token
git remote set-url origin https://YOUR_TOKEN@github.com/YOUR_USERNAME/YOUR_REPO.git
```

### "Large files rejected"
```bash
# Remove large files from history (use git-filter-repo)
# Or use Git LFS for large files
git lfs install
git lfs track "*.bin"
git add .gitattributes
```

## 📚 Additional Resources

- [GitHub Docs](https://docs.github.com/)
- [Git Handbook](https://guides.github.com/introduction/git-handbook/)
- [Cursor GitHub Integration](https://cursor.sh/docs)

## 🎯 Next Steps

1. ✅ Update `.gitignore` (done)
2. ⏳ Create GitHub repository
3. ⏳ Add remote and push
4. ⏳ Share repository URL or invite collaborators
5. ⏳ Set up CI/CD (optional)
6. ⏳ Configure branch protection (optional)


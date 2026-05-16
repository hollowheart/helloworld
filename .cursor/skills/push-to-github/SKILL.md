---
name: push-to-github
description: >-
  Guides first-time and ongoing Git pushes to GitHub over HTTPS or SSH: local
  commits vs remote, adding `origin`, setting upstream, Personal Access Tokens
  (PAT), and fixing "No configured push destination". Use when the user wants
  to push code to GitHub, configure `git remote`, authenticate with a token,
  or troubleshoot push errors.
---

# Push code to GitHub

## Concepts

| Action | Effect |
|--------|--------|
| `git commit` | Records snapshots **locally** only |
| `git push` | Uploads commits to the **remote** (e.g. GitHub) |

`git config user.name` / `user.email` are **commit author metadata**, not GitHub login credentials.

---

## Checklist

- [ ] Commits exist locally (`git status` clean or only untracked; latest work committed)
- [ ] Remote `origin` points at the GitHub repo (`git remote -v`)
- [ ] Auth works: **HTTPS + PAT** or **SSH key** on GitHub
- [ ] Push with upstream set: `git push -u origin <branch>` (first time for that branch)

---

## First-time: new repo on GitHub

1. Create an empty repository on GitHub; copy the clone URL (HTTPS or SSH).

2. In the project root:

   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

3. Add remote (pick one URL style):

   ```bash
   git remote add origin https://github.com/<user>/<repo>.git
   # or
   git remote add origin git@github.com:<user>/<repo>.git
   ```

4. Align default branch name if needed (`main` is common on GitHub):

   ```bash
   git branch -M main
   git push -u origin main
   ```

---

## Existing clone / remote already on GitHub

```bash
git add .
git commit -m "<message>"
git push
```

If the branch has no upstream yet:

```bash
git push -u origin HEAD
# or
git push -u origin main
```

Verify remote:

```bash
git remote -v
```

---

## Error: `fatal: No configured push destination`

Meaning: no remote configured for this repo, or the current branch has no upstream.

**Fix:**

1. If `git remote -v` shows nothing:

   ```bash
   git remote add origin https://github.com/<user>/<repo>.git
   git push -u origin <branch>
   ```

2. If `origin` exists but `git push` still fails:

   ```bash
   git push -u origin <branch>
   ```

One-off push without adding a named remote (rare):

```bash
git push https://github.com/<user>/<repo>.git <branch>
```

---

## HTTPS authentication (Personal Access Token)

GitHub does **not** accept account passwords for Git over HTTPS. Use a **Personal Access Token (PAT)**.

1. GitHub: **Settings → Developer settings → Personal access tokens**
   - **Fine-grained** or **Tokens (classic)** — generate a new token with repo access as needed.
2. Copy the token **once** when shown; GitHub will not show the full token again.
3. When Git prompts for credentials:
   - **Username**: GitHub username
   - **Password**: paste the **PAT** (not the web login password)

Store tokens in OS credential manager when prompted; do not commit tokens or paste them into repositories or chat.

---

## SSH (alternative to HTTPS)

1. Generate an SSH key pair; add the **public** key to GitHub: **Settings → SSH and GPG keys**.
2. Use remote URL `git@github.com:<user>/<repo>.git`.
3. `git push` uses the SSH agent; no PAT in the remote URL.

---

## Confirm pushes reached GitHub

- `git status`: should **not** say `ahead of 'origin/<branch>'` after a successful push (for that branch).
- On the GitHub website: repository **Commits** tab should list the new commit.

---

## Security

- Revoke leaked or unused tokens on the same GitHub settings page.
- For enterprise GitHub, create PATs on that host’s domain, not `github.com`, if applicable.

\# Release Gate (single source of truth)



\## DEV (repo/.venv)

1\) Update branch + run tests:

&nbsp;  - `.\\scripts\\smoke\_test.ps1`

2\) Build wheel locally (optional sanity):

&nbsp;  - `python -m build --wheel`



\## Merge

3\) PR → review → merge to `main`



\## Tag + GitHub Release (source of PROD truth)

4\) Create tag on `main`:

&nbsp;  - `git pull`

&nbsp;  - `git tag vX.Y.Z`

&nbsp;  - `git push origin vX.Y.Z`

5\) Wait for GitHub Actions `release.yml` to publish Release + attach `dist/\*.whl`.



\## PROD (prod/venv)

6\) Deploy pinned tag:

&nbsp;  - `.\\scripts\\install\_release.ps1 -Tag vX.Y.Z`

&nbsp;  - `.\\scripts\\healthcheck.ps1`



\## Rollback

\- Redeploy previous tag:

&nbsp; - `.\\scripts\\install\_release.ps1 -Tag vA.B.C`

&nbsp; - `.\\scripts\\healthcheck.ps1`




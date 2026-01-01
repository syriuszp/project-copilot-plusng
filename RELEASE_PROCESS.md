\# Release / Deploy Process (ProjectCopilot)



\## Rule: PROD only from tagged GitHub Release wheel

\- No direct installs from repo into PROD.

\- No PYTHONPATH to repo in PROD runs.



\## Steps

1\) Work in `repo/` using `repo\\.venv`

2\) PR → review → merge to `main`

3\) Create tag `vX.Y.Z` on `main`

4\) GitHub Actions builds wheel and publishes GitHub Release with `dist/\*.whl`

5\) On PROD machine:

&nbsp;  - `prod\\scripts\\install\_release.ps1 -Tag vX.Y.Z`

&nbsp;  - `prod\\scripts\\healthcheck.ps1`

6\) Backup is scheduled daily: "ProjectCopilot PROD - Backup DB"



\## Emergency

\- If last release is bad: redeploy previous tag with `install\_release.ps1 -Tag vA.B.C`




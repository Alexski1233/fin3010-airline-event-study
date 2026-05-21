# Publishing

This local repo is ready to publish, but the current environment cannot create a new GitHub repository directly.

Recommended GitHub repo name:

```text
fin3010-airline-event-study
```

## Publish Code-Only Version

Create an empty GitHub repository first. Do not add a README, license, or `.gitignore` in the GitHub UI.

Then run:

```bash
git remote add origin https://github.com/Alexski1233/fin3010-airline-event-study.git
git push -u origin main
```

This publishes the clean code/notebook version only. Raw data and the PDF stay local.

## If the Repo Is Private

If you decide to use a private repository and want the local data or report included, add them intentionally:

```bash
git add -f data report/FIN3010_final_exam_paper.pdf
git commit -m "Add local course data and report"
git push
```

Only do this if data-sharing rights and co-author approval are clear.

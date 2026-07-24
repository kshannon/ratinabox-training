# RatInABox — Lab Training

A hands-on guide to the **[RatInABox](https://github.com/RatInABox-Lab/RatInABox)**
library, built around one concrete goal: generating **synthetic training data** for computational cognitive 
neuroscience projects.

The content is published as a [Quarto](https://quarto.org) website. This README is the
**developer / maintainer** guide: how to install, build, verify, and deploy.

---

## Requirements

- **[pixi](https://pixi.sh)**
  Install: `curl -fsSL https://pixi.sh/install.sh | bash`
- That's it. pixi pins Python 3.11, RatInABox 1.15.3, the scientific stack, JupyterLab, and
  (optionally) Quarto and PyTorch — all from the committed `pixi.lock`.

## Quick start

```bash
pixi install        # build the default environment from the lockfile
pixi run verify     # sanity-check the RatInABox API (expect: ALL 27 CHECKS PASSED)
pixi run lab        # open JupyterLab and work the notebooks
```

## Working locally — the two loops

**Notebooks (learning / building datasets):**
```bash
pixi run lab
```

**Website (editing the content, with live reload):**
```bash
pixi run -e site preview-site    # serves the site locally and auto-refreshes on save
```
Edit any `.md` / `.qmd` / `.ipynb`, hit save, and the browser preview updates itself. When
you want a static build instead, `pixi run -e site build-site` writes `_site/`.

## Repository layout

| Path | What it is |
|------|------------|
| `modules/` | The five module write-ups (`module_N_*.md`) — tutorial + homework |
| `notebooks/` | Starter notebooks (`module_N_starter.ipynb`) — imports + scaffolding, **no answers** |
| `solutions/` | `00_ANSWERS_AND_LLM_TUTOR.md` (the deliverable) + `_frag_*.md` (its build inputs) |
| `reference/` | `api_cheatsheet.md`, `reading_list.md`, `whats_missing_and_next_steps.md` |
| `scripts/` | Verification + generation scripts (see below) |
| `data/` | Generated `.npz` datasets land here (gitignored; `.gitkeep` keeps the dir) |
| `index.qmd`, `about.qmd` | Website landing page and about/roadmap |
| `_quarto.yml` | Website config (nav, theme, what gets rendered) |
| `pixi.toml`, `pixi.lock` | Environment definition and pinned lockfile (**commit both**) |

## Environments

Three pixi environments:

| Env | Adds | Use it for | Command |
|-----|------|------------|---------|
| `default` | RiaB + scientific + Jupyter stack | Everything: modules, notebooks, verification | `pixi run <task>` |
| `dl` | PyTorch | For advanced modules| `pixi run -e dl lab` |
| `site` | Quarto CLI | Building/previewing the website | `pixi run -e site <task>` |

Install a non-default env once with `pixi install -e dl` / `pixi install -e site`.

## Common tasks

All defined in `pixi.toml` under `[tasks]`:

| Command | What it does |
|---------|--------------|
| `pixi run lab` | Launch JupyterLab |
| `pixi run verify` | Run `scripts/verify_install.py` — verfifies the RiaB API surface |
| `pixi run verify-solutions` | Execute **every** worked solution block |
| `pixi run -e site build-site` | Render the website to `_site/` |
| `pixi run -e site preview-site` | Live-reloading local preview (auto-opens a browser) |

## Building the website

```bash
pixi run -e site preview-site     # iterate: live-reloads as you edit
pixi run -e site build-site       # one-off render to _site/
```

- Quarto renders your existing `.md` and `.ipynb` files directly — there are **no duplicate
  copies** to keep in sync.
- **v1 does not execute code at build time** (`execute: enabled: false` in `_quarto.yml`);
  tutorial snippets render as-is because they were already verified by the scripts. Flipping
  execution on later will run module code so figures render inline.
- `_site/` and `.quarto/` are build output — gitignored, never committed.


## Regenerating derived files

Two files are **generated**, not hand-edited:

- **Starter notebooks** come from `scripts/build_notebooks.py`. Edit the problem definitions
  there, then `pixi run python scripts/build_notebooks.py` to rewrite `notebooks/*.ipynb`.
- **`solutions/00_ANSWERS_AND_LLM_TUTOR.md`** is assembled from the `solutions/_frag_*.md`
  fragments by `scripts/assemble_solutions.py`. Edit the fragments, then
  `pixi run python scripts/assemble_solutions.py` to rebuild the combined doc.



### Dev Notes:
- **Always commit `pixi.lock`** alongside `pixi.toml`. Never `.gitignore` it — it's what makes
  the laptop match the desktop.
- `.pixi/` (the built env) is **not** committed; it's rebuilt locally from the lockfile. A
  fresh `git clone` therefore has no env — `pixi install` builds it clean, so the laptop is
  never affected by this.


## CI and deployment

`.github/workflows/ci.yml` runs on every push to `main`, every pull request, and on demand
(**Actions → CI → Run workflow**). Both environments come from the committed `pixi.lock`
via `prefix-dev/setup-pixi`, so CI installs the same pinned packages you have locally.

| Job | Environment | What it does |
|-----|-------------|--------------|
| `verify` | `default` | `pixi run verify` — the RatInABox API smoke test |
| `build-site` | `site` | `quarto render` → uploads `_site/` as a Pages artifact |
| `deploy` | — | Publishes the artifact to GitHub Pages (**`main` pushes only**) |

`build-site` runs on pull requests too, so a broken render is caught before merge — it just
doesn't deploy. `deploy` needs *both* other jobs green; if you'd rather publish docs even when
the RiaB smoke test is red, drop `verify` from that job's `needs:`.

The `verify-solutions` gate (executing every worked answer block) is deliberately **not** in
CI yet — it's slow and still run by hand: `pixi run verify-solutions`.

### One-time setup

GitHub Pages must be told to take its content from Actions rather than from a branch:

**Settings → Pages → Build and deployment → Source → GitHub Actions**

After that, every push to `main` republishes <https://kshannon.github.io/ratinabox-training/>.

### Pinned versions

`PIXI_VERSION` at the top of the workflow pins the pixi CLI to the version that produced
`pixi.lock`. `pixi install --locked` in CI **fails** if `pixi.toml` and `pixi.lock` have drifted
— so when you change dependencies, commit the regenerated lockfile in the same commit.

## Maintenance notes

- **Pin RatInABox.** It's pinned to `>=1.15.3,<2` in `pixi.toml`; defaults and signatures
  shift across releases. Bump deliberately and re-run both verify scripts.
- **The frag --> assemble flow:** never hand-edit `00_ANSWERS_AND_LLM_TUTOR.md`; edit the
  `_frag_*.md` and re-run `assemble_solutions.py`.

# ROSHAN.OS Setup Instructions

Welcome to the **ROSHAN.OS** terminal profile README dashboard! This architecture automatically fetches your live GitHub statistics, generates a custom grayscale ASCII portrait of you, and compiles them into a premium, responsive developer dashboard for both dark and light modes.

---

## 🛠 How It Works

1. **`generate.py`**: The central compiler. It fetches stats via the GitHub API, caches them in `cache/stats.json`, converts your `assets/profile.png` into monochrome ASCII grids, compiles the SVG templates, and embeds the avatar directly as base64 so it is 100% self-contained.
2. **GitHub Actions**: Every day, a workflow runs `generate.py` using your temporary token, updates the statistics and SVGs, and automatically commits and pushes the changes back to your profile repository.
3. **`README.md`**: Contains a single `<picture>` block that tells GitHub whether to display the dark mode terminal (`dark_mode.svg`) or light mode terminal (`light_mode.svg`) depending on the visitor's OS/browser theme.

---

## 🚀 Local Run and Verification

To run and test the SVGs locally on your system:

### 1. Install Dependencies
Ensure you have Python 3.10+ installed. Open a terminal in this directory and run:
```bash
pip install -r requirements.txt
```

### 2. Configure Profile Picture
* Place your high-quality portrait image in `assets/profile.png`.
* *Note: If this file is missing, the generator script will automatically attempt to download your current GitHub profile avatar as `assets/profile.png` on the first run.*

### 3. Run the Generator
To generate/compile the SVGs locally without a token (which uses public REST API and estimates stats):
```bash
python generate.py
```

To run with full authentic stats, you can supply a personal GitHub Token:
```bash
# Windows PowerShell
$env:GITHUB_TOKEN="your_personal_access_token"
python generate.py

# Linux/macOS
GITHUB_TOKEN="your_personal_access_token" python generate.py
```

### 4. Inspect Outputs
* Open the newly generated [dark_mode.svg](file:///c:/Users/yogir/rly09/dark_mode.svg) and [light_mode.svg](file:///c:/Users/yogir/rly09/light_mode.svg) files in any web browser to see the layout, alignment, and animations.

---

## 🔒 Deploying to GitHub

When you push this repository to GitHub, the workflow in `.github/workflows/update.yml` runs automatically.

1. **Verify Repository Permissions**:
   * Go to your repository settings: **Settings > Actions > General**.
   * Scroll down to **Workflow permissions**.
   * Ensure **Read and write permissions** is selected. This allows the workflow bot to push the generated SVGs back to your repository.
2. **Automatic Secret Handling**:
   * The action uses `${{ secrets.GITHUB_TOKEN }}`, which is automatically provided by GitHub. You do not need to create or configure any custom secrets!

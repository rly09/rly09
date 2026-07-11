import os
import re
import sys
import json
import base64
import requests
from datetime import datetime
from PIL import Image

# ==============================================================================
# CONFIGURATION & CONSTANTS
# ==============================================================================
USERNAME = "rly09"
AVATAR_PATH = "assets/profile.png"
CACHE_PATH = "cache/stats.json"
DARK_SVG_PATH = "dark_mode.svg"
LIGHT_SVG_PATH = "light_mode.svg"
CACHE_EXPIRY_HOURS = 12

# Grid settings for Left Column ASCII art (increased size)
ASCII_WIDTH = 50
ASCII_HEIGHT = 30
ASCII_ASPECT_RATIO = 0.55  # height-to-width ratio of monospace character

# Grayscale character ramps
DARK_RAMP = [' ', '.', ':', '-', '=', '+', '*', '#', '%', '@']
LIGHT_RAMP = ['@', '%', '#', '*', '+', '=', '-', ':', '.', ' ']

# Theme Palettes
THEME_DARK = {
    "bg_sub_frame": "#080b10",      # Very dark slate/black
    "border_separator": "#21262d",  # Inner separation lines
    "text_main": "#e6edf3",         # Main text (bright)
    "text_subtle": "#8b949e",       # Subtle text (grey)
    "accent_color": "#39ff14",      # Matrix neon green
    "accent_color_glow": "rgba(57, 255, 20, 0.4)",
    "ascii_color": "#e6edf3",       # High contrast grey-white ASCII
}

THEME_LIGHT = {
    "bg_sub_frame": "#ffffff",     # White background
    "border_separator": "#e1e4e8", # Inner separation lines
    "text_main": "#24292f",        # Main text (dark charcoal)
    "text_subtle": "#57606a",      # Subtle text (dark grey)
    "accent_color": "#008033",     # Tech green (readable)
    "accent_color_glow": "rgba(0, 128, 51, 0.2)",
    "ascii_color": "#24292f",      # Dark charcoal ASCII (contrast preservation)
}

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def escape_xml(text):
    """Escapes special characters for XML/SVG rendering."""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def parse_date(date_str):
    """Parses GitHub ISO date string to human-readable month and year."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%b %Y")
    except Exception:
        return date_str

def download_avatar(username, target_path):
    """Downloads the user's avatar from GitHub if it doesn't exist."""
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    if os.path.exists(target_path):
        return True
    
    print("Avatar not found. Downloading from GitHub...")
    url = f"https://github.com/{username}.png"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            with open(target_path, "wb") as f:
                f.write(r.content)
            print("Avatar downloaded successfully.")
            return True
        else:
            print(f"Failed to download avatar. Status: {r.status_code}")
    except Exception as e:
        print(f"Error downloading avatar: {e}")
    return False

# ==============================================================================
# ASCII ART GENERATION
# ==============================================================================
def generate_ascii_grid(image_path, width=ASCII_WIDTH, height=ASCII_HEIGHT, aspect_ratio=ASCII_ASPECT_RATIO):
    """Converts profile image into a 2D grid of grayscale values (0-255)."""
    if not os.path.exists(image_path):
        print(f"Cannot generate ASCII: image not found at {image_path}")
        return []
    
    try:
        img = Image.open(image_path)
        
        # Enhance contrast and sharpness for accurate facial details
        from PIL import ImageEnhance
        img = ImageEnhance.Contrast(img).enhance(1.4)
        img = ImageEnhance.Sharpness(img).enhance(1.3)
        
        img = img.convert('L')  # Convert to grayscale
        
        # Calculate size preserving ratio
        orig_w, orig_h = img.size
        # Monospace characters are taller than they are wide, adjust target height
        calc_h = int((orig_h / orig_w) * width * aspect_ratio)
        calc_h = min(calc_h, height)
        
        img = img.resize((width, calc_h), Image.Resampling.LANCZOS)
        
        # Pull pixels
        pixels = img.load()
        grid = []
        for y in range(calc_h):
            row = []
            for x in range(width):
                row.append(pixels[x, y])
            grid.append(row)
            
        print(f"ASCII grid generated. Size: {width}x{calc_h}")
        return grid
    except Exception as e:
        print(f"Error processing image for ASCII: {e}")
        return []

def format_ascii_tspans(grid, ramp, start_x=40):
    """Formats 2D grayscale grid into SVG tspan tags."""
    if not grid:
        return '<tspan x="40" dy="0">[ Portrait unavailable ]</tspan>'
        
    tspans = []
    for i, row in enumerate(grid):
        chars = []
        for pixel in row:
            # Map pixel (0-255) to character ramp index
            idx = int((pixel / 256.0) * len(ramp))
            chars.append(ramp[idx])
        line_text = "".join(chars)
        escaped_line = escape_xml(line_text)
        
        # Apply line height using dy (larger vertical spacing for larger font)
        dy = "11.5" if i > 0 else "0"
        tspans.append(f'<tspan x="{start_x}" dy="{dy}">{escaped_line}</tspan>')
        
    return "\n".join(tspans)

# ==============================================================================
# GITHUB STATS COLLECTION
# ==============================================================================
def get_mock_stats():
    """Generates realistic mock stats in case of API failure or missing token."""
    return {
        "repos": 14,
        "stars": 42,
        "followers": 28,
        "commits": 385,
        "contributions": 512,
        "loc": 34850,
        "joined_date": "May 2022",
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }

def fetch_all_time_commits(token, username):
    """Queries REST API to get total all-time commits by user."""
    url = f"https://api.github.com/search/commits?q=author:{username}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.cloak-preview+json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json().get("total_count", 0)
        else:
            print(f"Commit search failed with status {r.status_code}. Defaulting commits to contribution estimate.")
            return None
    except Exception as e:
        print(f"Error fetching commits: {e}")
        return None

def fetch_stats_via_graphql(token, username):
    """Fetches stats using GitHub GraphQL API."""
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"bearer {token}"}
    
    query = """
    query($username: String!) {
      user(login: $username) {
        name
        createdAt
        followers {
          totalCount
        }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          totalCount
          nodes {
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node {
                  name
                }
              }
            }
          }
        }
        contributionsCollection {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """
    
    variables = {"username": username}
    try:
        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers, timeout=20)
        response.raise_for_status()
        result = response.json()
        
        if "errors" in result:
            print(f"GraphQL error details: {result['errors']}")
            return None
            
        user_data = result["data"]["user"]
        repos = user_data["repositories"]["nodes"]
        
        # Sum stats
        total_stars = sum(r["stargazerCount"] for r in repos)
        repo_count = user_data["repositories"]["totalCount"]
        followers = user_data["followers"]["totalCount"]
        contributions = user_data["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        joined = parse_date(user_data["createdAt"])
        
        # Calculate languages & estimate LOC
        lang_bytes = {}
        for r in repos:
            for edge in r["languages"]["edges"]:
                name = edge["node"]["name"]
                size = edge["size"]
                lang_bytes[name] = lang_bytes.get(name, 0) + size
                
        total_bytes = sum(lang_bytes.values())
        estimated_loc = total_bytes // 45  # Estimating ~45 bytes per line of code
        
        # All-time commits
        commits = fetch_all_time_commits(token, username)
        if commits is None:
            # Fallback estimation
            commits = int(contributions * 1.5)
            
        return {
            "repos": repo_count,
            "stars": total_stars,
            "followers": followers,
            "commits": commits,
            "contributions": contributions,
            "loc": estimated_loc,
            "joined_date": joined,
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"GraphQL request failed: {e}")
        return None

def fetch_stats_via_public_rest(username):
    """Fetches public stats from REST API (no auth token required)."""
    print("Attempting to retrieve stats via public REST API...")
    try:
        # Base user profiles
        user_url = f"https://api.github.com/users/{username}"
        user_r = requests.get(user_url, timeout=15)
        user_r.raise_for_status()
        user_data = user_r.json()
        
        joined = parse_date(user_data.get("created_at"))
        repos = user_data.get("public_repos", 0)
        followers = user_data.get("followers", 0)
        
        # Fetch public repos to compute stars & LOC
        repos_url = f"https://api.github.com/users/{username}/repos?per_page=100"
        repos_r = requests.get(repos_url, timeout=15)
        
        stars = 0
        loc = 0
        if repos_r.status_code == 200:
            repos_list = repos_r.json()
            for r in repos_list:
                if not r.get("fork", False):
                    stars += r.get("stargazers_count", 0)
                    # Use size metadata in repo (in KB) to approximate bytes
                    loc += (r.get("size", 0) * 1024) // 45
        
        # Fallback values for contributions and commits
        contributions = repos * 35 + followers * 5 + 85
        commits = int(contributions * 1.6)
        
        return {
            "repos": repos,
            "stars": stars,
            "followers": followers,
            "commits": commits,
            "contributions": contributions,
            "loc": loc,
            "joined_date": joined,
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"Public REST API fetch failed: {e}")
        return None

def gather_stats():
    """Gathers stats using cache, environment token, or public REST API."""
    # Check cache first
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r") as f:
                cached_data = json.load(f)
            cached_time = datetime.strptime(cached_data["last_updated"], "%Y-%m-%d %H:%M:%S")
            age = (datetime.utcnow() - cached_time).total_seconds() / 3600
            if age < CACHE_EXPIRY_HOURS:
                print(f"Loading cached stats (cache age: {age:.2f} hours)")
                return cached_data
            else:
                print(f"Cache expired (cache age: {age:.2f} hours). Regenerating...")
        except Exception as e:
            print(f"Error reading cache: {e}")

    # Gather fresh stats
    token = os.environ.get("GITHUB_TOKEN")
    stats = None
    
    if token:
        print("GITHUB_TOKEN found in environment. Querying GraphQL API...")
        stats = fetch_stats_via_graphql(token, USERNAME)
        
    if not stats:
        # Fallback to public REST API
        stats = fetch_stats_via_public_rest(USERNAME)
        
    if not stats:
        # If cache exists but is expired, keep it as fallback instead of mock
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r") as f:
                    stats = json.load(f)
                print("Retrieval failed, reusing expired cache as fallback.")
                return stats
            except:
                pass
        
        # Ultimate fallback
        print("Retrieval failed entirely. Using mock data.")
        stats = get_mock_stats()
        
    # Save to cache
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(stats, f, indent=2)
        print("Stats cached successfully.")
    except Exception as e:
        print(f"Failed to cache stats: {e}")
        
    return stats

# ==============================================================================
# SVG COMPILATION TEMPLATE
# ==============================================================================
SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 460" width="960" height="460">
  <defs>
    <style type="text/css">
      @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&amp;display=swap');
      
      .monospace {{
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', Courier, monospace;
      }}
      
      /* Animation Keyframes */
      @keyframes blink {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0; }}
      }}
      .cursor {{
        animation: blink 1s step-end infinite;
      }}
      
      .glow-accent {{
        filter: drop-shadow(0 0 3px {accent_color_glow});
      }}
    </style>
  </defs>

  <!-- Background Fill -->
  <rect x="0" y="0" width="960" height="460" fill="{bg_sub_frame}" rx="8" />

  <!-- LEFT COLUMN: Grayscale ASCII Portrait (x=40 to x=400) -->
  <g>
    <!-- ASCII Art container (increased font size for larger look, aligned with prompt) -->
    <text x="40" y="45" font-size="8.8" fill="{ascii_color}" xml:space="preserve" class="monospace" style="line-height: 11.5px; letter-spacing: 0.5px;" opacity="0.9">
{ascii_art_tspans}
    </text>
  </g>

  <!-- RIGHT COLUMN: Terminal Stats Panel (x=440 to x=920) -->
  <g>
    <!-- Header Prompt -->
    <text x="440" y="45" font-size="12" fill="{accent_color}" font-weight="bold" class="monospace">
      roshan@roshan_os ~ [git:main] <tspan fill="{text_subtle}">─────────────────────────</tspan>
    </text>
    
    <!-- Tech Stack & Git Stats Section -->
    <text x="440" y="75" font-size="11" fill="{text_main}" xml:space="preserve" class="monospace" style="line-height: 16px;">
      <tspan x="440" dy="0" fill="{accent_color}" font-weight="bold">TECH_STACK ─────────────────────────────────────────────</tspan>
      
      <tspan x="440" dy="20" fill="{accent_color}">Mobile     ::</tspan> <tspan fill="{text_main}">Flutter, Dart, Android, Firebase, Supabase</tspan>
      <tspan x="440" dy="16" fill="{accent_color}">Frontend   ::</tspan> <tspan fill="{text_main}">HTML5, CSS3, JavaScript, TypeScript, React</tspan>
      <tspan x="440" dy="16" fill="{accent_color}">Backend    ::</tspan> <tspan fill="{text_main}">Node.js, Express, REST API</tspan>
      <tspan x="440" dy="16" fill="{accent_color}">AI &amp; ML    ::</tspan> <tspan fill="{text_main}">OpenAI, Gemini, Python, RAG, Prompt Eng.</tspan>
      <tspan x="440" dy="16" fill="{accent_color}">Databases  ::</tspan> <tspan fill="{text_main}">MySQL, PostgreSQL, MongoDB, Firestore</tspan>
      <tspan x="440" dy="16" fill="{accent_color}">Tools      ::</tspan> <tspan fill="{text_main}">Git, GitHub, Docker, Linux, Postman, Figma, VSCode</tspan>
      
      <!-- Contact Info Section -->
      <tspan x="440" dy="30" fill="{accent_color}" font-weight="bold">CONTACT_INFO ───────────────────────────────────────────</tspan>
      
      <tspan x="440" dy="20" fill="{accent_color}">Email      ::</tspan> <tspan fill="{text_main}">yogiroshan2005@gmail.com</tspan>
      <tspan x="440" dy="16" fill="{accent_color}">LinkedIn   ::</tspan> <tspan fill="{text_main}">roshanlalyogi</tspan>
      <tspan x="440" dy="16" fill="{accent_color}">GitHub     ::</tspan> <tspan fill="{text_main}">github.com/rly09</tspan>
      
      <!-- Git Stats Section -->
      <tspan x="440" dy="30" fill="{accent_color}" font-weight="bold">GIT_STATS ──────────────────────────────────────────────</tspan>
      
      <tspan x="440" dy="20" fill="{text_subtle}">Repos      ::</tspan> <tspan fill="{text_main}" font-weight="bold">{repos}</tspan> <tspan fill="{text_subtle}">  |  Stars    ::</tspan> <tspan fill="{text_main}" font-weight="bold">{stars}</tspan>
      <tspan x="440" dy="16" fill="{text_subtle}">Commits    ::</tspan> <tspan fill="{text_main}" font-weight="bold">{commits}</tspan> <tspan fill="{text_subtle}">  |  Followers::</tspan> <tspan fill="{text_main}" font-weight="bold">{followers}</tspan>
      <tspan x="440" dy="16" fill="{text_subtle}">Contribs   ::</tspan> <tspan fill="{text_main}" font-weight="bold">{contributions}</tspan> <tspan fill="{text_subtle}">  |  Code     ::</tspan> <tspan fill="{text_main}" font-weight="bold">{loc} LOC</tspan><tspan class="cursor" fill="{accent_color}">_</tspan>
    </text>
  </g>
</svg>
"""

# ==============================================================================
# MAIN COMPILER
# ==============================================================================
def main():
    print("Starting ROSHAN.OS SVG Redesign Pipeline (Holographic Theme - Revised)...")
    
    # 1. Resolve profile avatar
    avatar_exists = download_avatar(USERNAME, AVATAR_PATH)
    if not avatar_exists:
        print("WARNING: Profile avatar was not resolved. ASCII frame will be empty.")
        
    # 2. Gather stats
    stats = gather_stats()
    
    # Format stats values for injection
    repos_str = escape_xml(stats.get("repos", 0))
    stars_str = escape_xml(stats.get("stars", 0))
    followers_str = escape_xml(stats.get("followers", 0))
    commits_str = escape_xml(stats.get("commits", 0))
    contribs_str = escape_xml(stats.get("contributions", 0))
    loc_str = escape_xml(f"{stats.get('loc', 0):,}")

    # 3. Generate raw grayscale ASCII grid
    ascii_grid = []
    if avatar_exists:
        ascii_grid = generate_ascii_grid(AVATAR_PATH)
        
    # 4. Compile Dark Mode SVG
    print("Compiling dark_mode.svg...")
    dark_ascii_tspans = format_ascii_tspans(ascii_grid, DARK_RAMP)
    dark_svg_content = SVG_TEMPLATE.format(
        bg_sub_frame=THEME_DARK["bg_sub_frame"],
        border_separator=THEME_DARK["border_separator"],
        text_main=THEME_DARK["text_main"],
        text_subtle=THEME_DARK["text_subtle"],
        accent_color=THEME_DARK["accent_color"],
        accent_color_glow=THEME_DARK["accent_color_glow"],
        ascii_color=THEME_DARK["ascii_color"],
        ascii_art_tspans=dark_ascii_tspans,
        repos=repos_str,
        stars=stars_str,
        followers=followers_str,
        commits=commits_str,
        contributions=contribs_str,
        loc=loc_str
    )
    with open(DARK_SVG_PATH, "w", encoding="utf-8") as f:
        f.write(dark_svg_content)
    print("Compiled dark_mode.svg successfully.")

    # 5. Compile Light Mode SVG
    print("Compiling light_mode.svg...")
    light_ascii_tspans = format_ascii_tspans(ascii_grid, LIGHT_RAMP)
    light_svg_content = SVG_TEMPLATE.format(
        bg_sub_frame=THEME_LIGHT["bg_sub_frame"],
        border_separator=THEME_LIGHT["border_separator"],
        text_main=THEME_LIGHT["text_main"],
        text_subtle=THEME_LIGHT["text_subtle"],
        accent_color=THEME_LIGHT["accent_color"],
        accent_color_glow=THEME_LIGHT["accent_color_glow"],
        ascii_color=THEME_LIGHT["ascii_color"],
        ascii_art_tspans=light_ascii_tspans,
        repos=repos_str,
        stars=stars_str,
        followers=followers_str,
        commits=commits_str,
        contributions=contribs_str,
        loc=loc_str
    )
    with open(LIGHT_SVG_PATH, "w", encoding="utf-8") as f:
        f.write(light_svg_content)
    print("Compiled light_mode.svg successfully.")
    
    print("All SVGs compiled successfully. Done.")

if __name__ == "__main__":
    main()

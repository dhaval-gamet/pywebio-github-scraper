import requests
import json
import time
import os
import csv
from pywebio.input import input_group, input, NUMBER, actions
from pywebio.output import (
    put_text, put_success, put_table, put_markdown,
    put_scrollable, put_buttons, toast, put_file, use_scope,
    clear_scope, put_processbar, set_processbar
)
from pywebio import start_server

OUTPUT_FILE = "top_github_users.json"
CSV_FILE = "top_github_users.csv"

# ---------- Helper Functions ----------
def load_existing_users():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list) and all(isinstance(u, dict) and "login" in u and "html_url" in u for u in data):
                    return data
        except json.JSONDecodeError:
            pass
    return []

def save_users(users):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def save_csv(users):
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Username", "Profile URL"])
        for user in users:
            writer.writerow([user["login"], user["html_url"]])

# ---------- Main Scraper ----------
def get_github_users(min_followers=100, start_page=1, max_pages=3, location=None, min_repos=None):
    all_users = load_existing_users()
    seen_logins = set(user["login"] for user in all_users)

    with use_scope('progress', clear=True):
        put_processbar('bar')
        total_steps = max_pages

    collected = 0

    for page in range(start_page, start_page + max_pages):
        query = f"followers:>={min_followers}"
        if location:
            query += f" location:{location}"
        if min_repos:
            query += f" repos:>={min_repos}"

        url = f"https://api.github.com/search/users?q={query}&per_page=100&page={page}"
        headers = {"Accept": "application/vnd.github.v3+json"}

        response = requests.get(url, headers=headers)

        if response.status_code == 403:
            reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait_time = max(reset_time - int(time.time()), 1)
            toast(f"⏳ GitHub Rate Limit! {wait_time} सेकंड इंतजार कर रहे हैं...", color="warn")
            time.sleep(wait_time)
            continue

        if response.status_code != 200:
            toast(f"❌ API Error {response.status_code}", color="error")
            break

        data = response.json()
        items = data.get("items", [])

        new_users = [
            {"login": item["login"], "html_url": item["html_url"]}
            for item in items if item["login"] not in seen_logins
        ]

        all_users.extend(new_users)
        seen_logins.update(u["login"] for u in new_users)

        collected += len(new_users)
        save_users(all_users)
        set_processbar('bar', (page - start_page + 1) / total_steps)
        time.sleep(1)

        if len(items) == 0:
            break

    save_csv(all_users)
    return all_users, collected

# ---------- Main UI ----------
def github_user_scraper_app():
    put_markdown("## 🐙 GitHub टॉप यूज़र्स स्क्रैपर (PyWebIO वेब ऐप)")

    action = actions(label="कृपया एक विकल्प चुनें:", buttons=[
        {"label": "👉 Scrape Users", "value": "scrape"},
        {"label": "🧹 Clear Saved Data", "value": "clear"},
        {"label": "⬇️ Download CSV", "value": "download"},
    ])

    if action == "clear":
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
        if os.path.exists(CSV_FILE):
            os.remove(CSV_FILE)
        toast("✅ फाइलें साफ़ कर दी गईं।", color="success")
        return github_user_scraper_app()

    if action == "download":
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'rb') as f:
                put_file("top_github_users.csv", f.read(), "📥 CSV डाउनलोड करें")
        else:
            toast("⚠️ कोई CSV फाइल नहीं मिली!", color="warn")
        return github_user_scraper_app()

    user_input = input_group("🔧 पैरामीटर दर्ज करें:", [
        input("न्यूनतम followers", name="min_followers", type=NUMBER, value=100),
        input("शुरुआती पेज", name="start_page", type=NUMBER, value=1),
        input("अधिकतम पेज", name="max_pages", type=NUMBER, value=3),
        input("स्थान (जैसे India)", name="location", placeholder="Optional"),
        input("न्यूनतम repositories", name="min_repos", type=NUMBER, placeholder="Optional", value=None)
    ])

    put_text("🚀 स्क्रैपिंग शुरू हो रही है...").style('color: green')
    with use_scope('progress', clear=True):
        usernames, added = get_github_users(
            min_followers=user_input['min_followers'],
            start_page=user_input['start_page'],
            max_pages=user_input['max_pages'],
            location=user_input['location'],
            min_repos=user_input['min_repos']
        )

    if usernames:
        put_success(f"🎉 कुल {len(usernames)} यूज़र्स JSON और CSV में सेव कर दिए गए हैं।")
        put_scrollable(
            put_table([["Username", "Profile"]] + [[u["login"], u["html_url"]] for u in usernames]),
            height=400
        )
        with open(CSV_FILE, 'rb') as f:
            put_file("top_github_users.csv", f.read(), "📥 CSV डाउनलोड करें")
    else:
        put_text("⚠️ कोई नया यूज़र नहीं मिला।")

# ---------- Run Server ----------
if __name__ == '__main__':
    start_server(github_user_scraper_app, port=8080, debug=True)

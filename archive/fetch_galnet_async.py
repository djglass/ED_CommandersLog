import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import datetime
import os
import re

# Game year adjustment if needed (for in-game dates)
GAME_YEAR_OFFSET = 1286

async def fetch_page(session, url):
    async with session.get(url) as response:
        return await response.text()

async def fetch_article(session, uid):
    url = f"https://community.elitedangerous.com/galnet/uid/{uid}"
    html = await fetch_page(session, url)
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract title from the h3 element with the expected classes
    title_tag = soup.find("h3", class_="hiLite galnetNewsArticleTitle")
    title = title_tag.get_text(strip=True) if title_tag else "No Title"
    
    # Extract publication date from the first <p> tag
    date_tag = soup.find("p")
    if date_tag:
        date_str = date_tag.get_text(strip=True)
        try:
            # Expecting format like "04 Jun 3300"
            date_obj = datetime.datetime.strptime(date_str, "%d %b %Y")
            if date_obj.year >= 3300:
                date_obj = date_obj.replace(year=date_obj.year - GAME_YEAR_OFFSET)
            date_iso = date_obj.isoformat()
        except Exception:
            date_iso = date_str  # Fallback if parsing fails
    else:
        date_iso = ""
    
    # Extract content from the second <p> tag (if available)
    p_tags = soup.find_all("p")
    content = p_tags[1].get_text(strip=True) if len(p_tags) > 1 else ""
    
    return {
        "uid": uid,
        "title": title,
        "date": date_iso,
        "content": content,
        "link": url
    }

async def fetch_all_articles():
    articles = {}
    async with aiohttp.ClientSession() as session:
        page = 1
        while True:
            # Use query string pagination: page=1,2,3,...
            url = "https://community.elitedangerous.com/en/galnet" if page == 1 else f"https://community.elitedangerous.com/en/galnet?page={page}"
            print(f"Fetching page {page} from {url}...")
            html = await fetch_page(session, url)
            soup = BeautifulSoup(html, "html.parser")
            
            # Find all article title elements by class
            article_tags = soup.find_all("h3", class_="hiLite galnetNewsArticleTitle")
            if not article_tags:
                print(f"No articles found on page {page}, ending pagination.")
                break
            
            new_uids_found = False
            for tag in article_tags:
                a_tag = tag.find("a")
                if a_tag and "href" in a_tag.attrs:
                    href = a_tag["href"]
                    # Expect hrefs like "/galnet/uid/<UID>"
                    if href.startswith("/galnet/uid/"):
                        uid = href.replace("/galnet/uid/", "").strip("/")
                        if uid not in articles:
                            articles[uid] = None
                            new_uids_found = True
            # Check for a "Next" link in the page (if pagination is explicit)
            next_link = soup.find("a", string=re.compile("next", re.IGNORECASE))
            if not new_uids_found or not next_link:
                print(f"No new UIDs or next link found on page {page}, stopping pagination.")
                break
            page += 1
        
        # Fetch details for each article UID
        article_list = []
        for uid in articles.keys():
            article_data = await fetch_article(session, uid)
            article_list.append(article_data)
            print(f"Fetched article: {article_data['title']}")
        return article_list

def load_existing_articles(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    return data
            except Exception as e:
                print(f"Error loading existing JSON: {e}")
    return []

def merge_articles(existing, new):
    existing_uids = {article["uid"] for article in existing if "uid" in article}
    new_articles = [article for article in new if article["uid"] not in existing_uids]
    merged = existing + new_articles
    return merged, new_articles

async def main():
    # Ensure the rag_data folder exists
    output_dir = "rag_data"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "galnet_articles.json")
    
    print("Fetching articles from Galnet...")
    new_articles = await fetch_all_articles()
    print(f"Total articles fetched from site: {len(new_articles)}")
    
    # Load existing articles if the file exists
    existing_articles = load_existing_articles(output_file)
    merged_articles, added_articles = merge_articles(existing_articles, new_articles)
    
    if added_articles:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(merged_articles, f, indent=2)
        print(f"Updated {output_file} with {len(added_articles)} new article(s).")
    else:
        print("No new articles found. File remains unchanged.")

if __name__ == "__main__":
    asyncio.run(main())

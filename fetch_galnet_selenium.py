import json
import os
import datetime
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Adjust game year if needed (for in-game date correction)
GAME_YEAR_OFFSET = 1286

def get_article_details(driver, uid):
    url = f"https://community.elitedangerous.com/galnet/uid/{uid}"
    driver.get(url)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "h3.hiLite.galnetNewsArticleTitle"))
    )
    title = driver.find_element(By.CSS_SELECTOR, "h3.hiLite.galnetNewsArticleTitle").text.strip()
    
    p_tags = driver.find_elements(By.TAG_NAME, "p")
    if p_tags:
        date_str = p_tags[0].text.strip()
        try:
            date_obj = datetime.datetime.strptime(date_str, "%d %b %Y")
            if date_obj.year >= 3300:
                date_obj = date_obj.replace(year=date_obj.year - GAME_YEAR_OFFSET)
            date_iso = date_obj.isoformat()
        except Exception:
            date_iso = date_str
    else:
        date_iso = ""
    
    content = p_tags[1].text.strip() if len(p_tags) > 1 else ""
    
    return {
        "uid": uid,
        "title": title,
        "date": date_iso,
        "content": content,
        "link": url
    }

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

def main():
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(options=options)
    
    base_url = "https://community.elitedangerous.com/en/galnet"
    driver.get(base_url)
    WebDriverWait(driver, 10).until(lambda d: d.find_element(By.TAG_NAME, "body"))
    
    # Locate the archive container by its ID
    try:
        archive_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "block-frontier-galnet-frontier-galnet-block-filter"))
        )
    except Exception as e:
        print("Could not locate the archive container:", e)
        driver.quit()
        return
    
    # Grab all archive date links inside the container
    date_link_elements = archive_container.find_elements(By.CSS_SELECTOR, "a.galnetLinkBoxLink")
    print(f"Found {len(date_link_elements)} archive date links.")
    
    # Extract href values to avoid stale element references
    date_hrefs = [elem.get_attribute("href") for elem in date_link_elements]
    
    articles = {}
    for date_href in date_hrefs:
        # If date_href doesn't start with "http", prepend the base URL
        if not date_href.startswith("http"):
            full_url = "https://community.elitedangerous.com" + date_href
        else:
            full_url = date_href
        print(f"Processing archive page: {full_url}")
        driver.get(full_url)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h3.hiLite.galnetNewsArticleTitle"))
            )
        except Exception:
            print(f"No articles found on archive page: {full_url}")
            continue
        
        article_elements = driver.find_elements(By.CSS_SELECTOR, "h3.hiLite.galnetNewsArticleTitle")
        for article_elem in article_elements:
            try:
                a_tag = article_elem.find_element(By.TAG_NAME, "a")
                href = a_tag.get_attribute("href")
                if "/galnet/uid/" in href:
                    uid = href.split("/galnet/uid/")[-1].strip("/")
                    articles[uid] = None
            except Exception as ex:
                print("Error processing an article element:", ex)
    
    print(f"Total unique article UIDs found: {len(articles)}")
    
    article_list = []
    for uid in articles.keys():
        try:
            article_data = get_article_details(driver, uid)
            article_list.append(article_data)
            print(f"Fetched article: {article_data['title']}")
        except Exception as e:
            print(f"Error fetching details for UID {uid}:", e)
    
    driver.quit()
    
    output_dir = "rag_data"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "galnet_articles.json")
    existing_articles = load_existing_articles(output_file)
    merged_articles, added_articles = merge_articles(existing_articles, article_list)
    
    if added_articles:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(merged_articles, f, indent=2)
        print(f"Updated {output_file} with {len(added_articles)} new article(s).")
    else:
        print("No new articles found. File remains unchanged.")

if __name__ == "__main__":
    main()

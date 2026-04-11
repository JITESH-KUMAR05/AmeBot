# here we have knowledge base builder
import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from config import (
    MANUAL_DATA_PATH,
    SCRAPED_DATA_PATH,
    CHUNK_SIZE,
    CHUNK_OVERLAP
)

# pages from where we get the data
AMENIFY_PAGES = [
    {"url":"https://www.amenify.com", "title":"Home"},
    {"url":"https://www.amenify.in", "title":"Home-india"},
    {"url":"https://www.amenify.com/resident-services", "title":"Resident-services"},
    {"url": "https://www.amenify.com/resident-protection-plan",        "title": "Resident-protection-plan"},
    {"url": "https://www.amenify.com/cleaningservices1", "title": "Cleaning-services"},
    {"url": "https://www.amenify.com/about-us", "title": "About-us"},
    {"url": "https://www.amenify.com/providers-1", "title": "Providers"},
    {"url": "https://www.amenify.com/property-managers-2", "title": "Property-managers"},
    {"url": "https://www.amenify.com/home", "title": "Home-2"},
    
    
]

# Headers to make a re

Headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Scraping function 
def scrape_page(url: str, title: str) -> dict | None:
    """
    Fetch a single page and extract the text from it
    returns a dict with title, url and content - or None on failure
    """
    try:
        time.sleep(1) # so that we will not get blocked
        response = requests.get(url, headers=Headers, timeout=10)
        response.raise_for_status() # raise exception for bad request

        soup =  BeautifulSoup(response.content, "html.parser")

        # remove noise ie the script tag and other tags

        for tag in soup(["script","style","nav","footer","header","noscript","iframe","form"]):
            tag.decompose() # remove the tags and it's content from the dom tree
        
        # now whatever is visible that we have to take and consider as unnecessary we already removed
        text = soup.get_text(separator="\n", strip=True)

        # if there are 3 or more blank names then remove them
        text = re.sub(r'\n{3,}', '\n\n', text)

        # filtering out the very short lines ie maybe the button text 

        lines = [line for line in text.split("\n") if len(line.strip() > 30)]

        clean_text = "\n".join(lines)

        print(f"Scraped: {title} - ({len(clean_text)} chars)")

        return {"title": title, "url" : url, "content": clean_text}
    
    except requests.RequestException as e:
        print(f"Failed to scrape {url} : {e}")
        return None

def scrape_amenify() -> list[dict]:
    """
    Scrape all the pages mentioned and 
    return as a list of {title, url, content} dicts
    """
    print("Starting the sraping of website")
    results  = []
    for page in AMENIFY_PAGES:
        doc = scrape_page(page["url"], page["title"])
        if doc:
            results.append(doc)
    
    # saving this so that we can just do it once and use it again
    os.makedirs("data", exist_ok=True)
    with open(SCRAPED_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(results)} pages to {SCRAPED_DATA_PATH}")
    return results

# Fallback where we have manually written data

def load_raw_documents() -> list[dict]:
    """
    Fallback chain:
    1. Manual curated JSON
    2. Previously scraped cache
    3. Live scraping data
    """
    # 1 Manual data
    if os.path.exists(MANUAL_DATA_PATH):
        try:
            with open(MANUAL_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data and len(data)>0:
                print(f"loaded manually written data {len(data)} documents")
                return data
        except (json.JSONDecodeError, KeyError):
            print("Manually written data is malformed falling back")
    
    # 2 Scraped cache
    if os.path.exists(SCRAPED_DATA_PATH):
        try:
            with open(SCRAPED_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data and len(data) > 0:
                print(f"loaded the scraped cache {len(data)} documents")
                return data
        except (json.JSONDecodeError, KeyError):
            print("Scraped data is malformed falling back")
    
    # 3 Live scraping
    print("No local data/cache found, scraping live website...")
    return scrape_amenify()

# Chunking 

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks
    """
    words = text.split()
    chunks = []
    start = 0

    while(start < len(words)):
        end = start + chunk_size
        chunk = " ".join(words[start:end])

        if(len(words[start:end]) > 50):
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks
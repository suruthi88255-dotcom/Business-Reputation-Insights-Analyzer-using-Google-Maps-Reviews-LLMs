import time
import pandas as pd
import urllib.parse
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- ⚙️ CONFIGURATION ⚙️ ---
MAX_REVIEWS_TO_FETCH = 100
HEADLESS_MODE = False        

# --- 🛠️ HELPER FUNCTIONS 🛠️ ---

def get_clean_filename(query):
    clean_name = re.sub(r'[^a-zA-Z0-9]', '_', query).lower()
    return f"data/{clean_name}_reviews.csv"

def get_driver():
    chrome_options = Options()
    if HEADLESS_MODE:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def save_data(df, specific_filename):
    if not os.path.exists("data"):
        os.makedirs("data")
    
    df.to_csv(specific_filename, index=False)
    # Sync to generic file for Analyzer
    df.to_csv("data/reviews_raw.csv", index=False)
    
    print(f"\n✅ Data saved to: {specific_filename}")
    print(f"✅ Data synced to: data/reviews_raw.csv")

# --- 🧠 FORCE FETCH LOGIC 🧠 ---

def run_scraper(user_query):
    # 1. CACHE CHECK
    filename = get_clean_filename(user_query)
    if os.path.exists(filename):
        print(f"⚡ CACHE HIT: Found data in '{filename}'")
        try:
            # Load valid cache and sync it for the Analyzer
            df = pd.read_csv(filename)
            df.to_csv("data/reviews_raw.csv", index=False)
            print("   (Synced cache to active workspace)")
            return
        except:
            print("   (Cache corrupted, fetching fresh data...)")

    # 2. START BROWSER
    print(f"🚀 Launching Scraper for: '{user_query}'")
    driver = get_driver()
    wait = WebDriverWait(driver, 15)

    try:
        # Search Google Maps
        encoded_query = urllib.parse.quote(user_query)
        url = f"https://www.google.com/maps/search/{encoded_query}"
        driver.get(url)
        time.sleep(5) # Allow load

        # 3. RESULT SELECTION
        if "/maps/place/" in driver.current_url:
            print("⭐ Direct Page Detected. Fetching Reviews...")
            scrape_reviews_force(driver, filename)
        else:
            print("⭐ Search List Detected. Forcing click on TOP RESULT...")
            try:
                # Click the first result card
                first_result = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "hfpxzc")))
                driver.execute_script("arguments[0].click();", first_result)
                print("   ...Clicked Top Result. Waiting for panel to load...")
                time.sleep(5) 
                scrape_reviews_force(driver, filename)
            except Exception as e:
                print(f"❌ Error finding/clicking result: {e}")
                print("   The search might have returned 0 results.")

    except Exception as e:
        print(f"❌ Critical Error: {e}")
    finally:
        print("🛑 Closing Browser...")
        driver.quit()

# --- 🏗️ THE FORCE REVIEW SCRAPER ---

def scrape_reviews_force(driver, filename):
    wait = WebDriverWait(driver, 10)
    
    # 1. AGGRESSIVE TAB HUNTING
    print("👆 Hunting for 'Reviews' tab...")
    tab_clicked = False
    
    # Method A: Specific Selectors
    strategies = [
        "//button[contains(@aria-label, 'Reviews')]",
        "//div[@role='tablist']//button[2]", 
        "//button[.//div[text()='Reviews']]"
    ]
    
    for xpath in strategies:
        try:
            if "button[" in xpath:
                 elements = driver.find_elements(By.XPATH, xpath)
                 if elements:
                     driver.execute_script("arguments[0].click();", elements[0])
                     tab_clicked = True
                     print("   ✅ Clicked Reviews tab (Strategy A)!")
                     break
            else:
                btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                driver.execute_script("arguments[0].click();", btn)
                tab_clicked = True
                print("   ✅ Clicked Reviews tab (Strategy A)!")
                break
        except:
            continue
            
    # Method B: The "Nuclear" Option (Loop all buttons)
    if not tab_clicked:
        print("   ⚠️ Strategy A failed. Trying Strategy B (Scan all buttons)...")
        try:
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                txt = btn.text
                aria = btn.get_attribute("aria-label")
                if (txt and "Reviews" in txt) or (aria and "Reviews" in aria):
                    driver.execute_script("arguments[0].click();", btn)
                    tab_clicked = True
                    print("   ✅ Clicked Reviews tab (Strategy B)!")
                    break
        except:
            pass

    time.sleep(3) 

    # 2. SCROLL LOOP
    print(f"⬇️ Scrolling to fetch reviews...")
    
    reviews_data = []
    iterations = 0
    max_iterations_without_data = 10  # <--- UPDATED TO 10
    
    while len(reviews_data) < MAX_REVIEWS_TO_FETCH:
        iterations += 1
        
        # BROADER SELECTORS
        cards = driver.find_elements(By.CSS_SELECTOR, "div[data-review-id]")
        if not cards:
            cards = driver.find_elements(By.CLASS_NAME, "jftiEf")
        
        if len(cards) > 0:
            driver.execute_script("arguments[0].scrollIntoView(true);", cards[-1])
        else:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
        
        time.sleep(2)
        
        # --- FAILURE CHECK ---
        if len(cards) == 0:
            print(f"   ...Iteration {iterations}: No reviews found yet.")
            
            if iterations >= max_iterations_without_data:
                print("\n" + "="*50)
                print("⚠️  NO TEXT REVIEWS FOUND. CHECKING GENERAL RATING...")
                
                # --- FALLBACK: ROBUST RATING EXTRACTOR ---
                try:
                    rating_val = 0.0
                    
                    # Try 1: The Aria Label on the stars
                    try:
                        star_elem = driver.find_element(By.XPATH, "//*[@role='img' and contains(@aria-label, 'stars')]")
                        rating_text = star_elem.get_attribute("aria-label")
                        rating_val = float(re.findall(r"\d+\.\d+", rating_text)[0])
                    except:
                        pass
                        
                    # Try 2: The big text number
                    if rating_val == 0.0:
                        try:
                            text_elem = driver.find_element(By.CLASS_NAME, "MW4etd")
                            rating_val = float(text_elem.text)
                        except:
                            pass
                    
                    if rating_val > 0:
                        # Generate Interpretation
                        sentiment = "Neutral"
                        if rating_val >= 4.5: sentiment = "Excellent / Highly Recommended"
                        elif rating_val >= 4.0: sentiment = "Good / Positive"
                        elif rating_val >= 3.0: sentiment = "Average / Okay"
                        elif rating_val >= 2.0: sentiment = "Poor / Below Average"
                        else: sentiment = "Bad / Not Recommended"
                        
                        print(f"⭐ General Rating Found: {rating_val}/5.0")
                        print(f"📊 Verdict: {sentiment}")
                        
                        fallback_data = [{
                            "author": "Google Summary",
                            "rating": rating_val,
                            "text": f"Overall rating is {rating_val}. Verdict: {sentiment}",
                            "date": "Today"
                        }]
                        
                        df = pd.DataFrame(fallback_data)
                        save_data(df, filename)
                        return
                    else:
                        raise Exception("Rating value still 0")

                except Exception as e:
                    print(f"❌ Could not find general rating: {e}")
                    print("   Adjust the search try to add more specific words")
                
                print("="*50 + "\n")
                return 
        
        # Normal Loop Logic
        current_count = len(cards)
        if current_count >= MAX_REVIEWS_TO_FETCH: break
        
        if current_count > 0 and current_count == len(reviews_data):
            if iterations > (max_iterations_without_data + 5): 
                 print("   🛑 End of reviews list reached.")
                 break
        
        if current_count > len(reviews_data):
             reviews_data = [0] * current_count
             iterations = 0 

    # 3. EXTRACTION
    all_cards = driver.find_elements(By.CSS_SELECTOR, "div[data-review-id]")
    if not all_cards:
        all_cards = driver.find_elements(By.CLASS_NAME, "jftiEf")
        
    final_data = []
    
    if len(all_cards) == 0:
        print("⚠️ No reviews extracted.")
        return

    print(f"\n🔍 Parsing text from {len(all_cards)} reviews...\n")
    print("="*50)
    
    for i, card in enumerate(all_cards[:MAX_REVIEWS_TO_FETCH]):
        try:
            author = card.get_attribute("aria-label") or "Unknown"
            try:
                text = card.find_element(By.CLASS_NAME, "wiI7pd").text
            except:
                text = "[No Text - Rating Only]"
            try:
                rating_str = card.find_element(By.CSS_SELECTOR, "span[role='img']").get_attribute("aria-label")
                rating = float(rating_str.split(" ")[0])
            except:
                rating = 0.0
                
            print(f"Review #{i+1}")
            print(f"👤 {author}")
            print(f"⭐ {rating}/5.0")
            print(f"💬 {text[:100]}...") 
            print("-" * 30)

            final_data.append({
                "author": author,
                "rating": rating,
                "text": text,
                "date": "Recent"
            })
        except:
            continue
            
    df = pd.DataFrame(final_data)
    save_data(df, filename)

# If this file is run directly (not imported), use input
if __name__ == "__main__":
    print("--- 🌍 GOOGLE MAPS FORCE-FETCH SCRAPER 🌍 ---")
    user_input = input("Enter Query: ")
    if user_input.strip():
        run_scraper(user_input)
    else:
        print("❌ Query cannot be empty")
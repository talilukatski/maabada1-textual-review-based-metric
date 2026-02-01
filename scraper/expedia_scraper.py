import time
import random
import csv
from seleniumwire import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Your proxy credentials ---
PROXY_HOST = "..."
PROXY_PORT = "..."
PROXY_USER = "..."
PROXY_PASS = "..."

# --- Hotels list ---
HOTELS_LIST = [
    {"location": "city, country", "url": ""},
    {"location": "city, country", "url": ""},
]
OUTPUT_FILE = "scraped_expedia.csv"
TARGET_REVIEWS_PER_HOTEL = 30
DEBUG_MODE = True


def init_driver():
    # --- Configure proxy + disable SSL verification (fix for Chrome red screen) ---
    proxy_options = {
        'proxy': {
            'http': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
            'https': f'https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
            'no_proxy': 'localhost,127.0.0.1'
        },
        'verify_ssl': False  # <--- Critical: prevents certificate errors inside the proxy
    }

    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")

    # --- Chrome flags to suppress security warnings ---
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--ignore-ssl-errors')

    print("Initializing driver with SSL-Bypass & Proxy...")

    driver = uc.Chrome(
        options=options,
        seleniumwire_options=proxy_options,
        version_main=142
    )
    return driver


def scrape_single_hotel(driver, hotel_data):
    url = hotel_data["url"]
    location = hotel_data["location"]
    hotel_reviews = []

    print(f"\n--- Starting Scraping: {location} ---")

    try:
        driver.get(url)
        # If the red privacy screen still appears, try clicking: Advanced -> Proceed
        try:
            if "Privacy error" in driver.title or "not private" in driver.page_source:
                print("⚠️ Handling SSL Privacy Error page...")
                driver.execute_script('document.getElementById("details-button").click();')
                time.sleep(1)
                driver.execute_script('document.getElementById("proceed-link").click();')
                time.sleep(3)
        except:
            pass  # If it fails or isn't needed, continue normally

        time.sleep(random.uniform(6, 10))

        wait = WebDriverWait(driver, 20)

        # --- Step 1: Open the reviews modal ---
        try:
            see_all_xpath = "//button[contains(text(), 'See all') and contains(text(), 'reviews')]"
            see_all_button = wait.until(EC.presence_of_element_located((By.XPATH, see_all_xpath)))
            driver.execute_script("arguments[0].scrollIntoView(true);", see_all_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", see_all_button)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'section[data-stid="reviews-container"]')))
            time.sleep(3)
        except Exception:
            print("Could not open reviews modal (button not found or blocked).")
            # Screenshot on failure helps diagnose what went wrong
            driver.save_screenshot(f"error_{location[:5]}.png")
            return []

        # --- Step 2: Click "Load more" until enough reviews are loaded ---
        print("Loading more reviews...")
        while len(hotel_reviews) < TARGET_REVIEWS_PER_HOTEL:
            try:
                articles = driver.find_elements(By.TAG_NAME, "article")
                if len(articles) >= TARGET_REVIEWS_PER_HOTEL + 5:
                    break
                more_button = driver.find_element(By.ID, "load-more-reviews")
                driver.execute_script("arguments[0].scrollIntoView(true);", more_button)
                time.sleep(random.uniform(1.5, 3))
                driver.execute_script("arguments[0].click();", more_button)
                time.sleep(random.uniform(2, 4))
            except Exception:
                break

        # --- Step 3: Extract and clean the review text ---
        print("Extracting data...")
        review_cards = driver.find_elements(By.TAG_NAME, "article")

        for i, card in enumerate(review_cards):
            try:
                full_text = card.text
                lines = full_text.split('\n')
                rating = "N/A"

                # A. Rating
                for line in lines:
                    if "/10" in line:
                        rating = line.split("/")[0].strip()
                        break

                # B. Find the date line and cut everything before it
                cut_index = -1
                for idx, line in enumerate(lines):
                    if any(year in line for year in ["2024", "2025", "2026", "2023"]):
                        cut_index = idx
                        break

                if cut_index != -1:
                    remaining_lines = lines[cut_index + 1:]
                else:
                    remaining_lines = lines

                # C. Remove "Stayed...", "Liked/Disliked", etc. and keep only meaningful review lines
                clean_candidates = []
                for line in remaining_lines:
                    line_clean = line.strip()
                    line_lower = line_clean.lower()

                    if line_lower.startswith("stayed"):
                        break
                    if "liked:" in line_lower:
                        continue
                    if "disliked:" in line_lower:
                        continue
                    if "verified review" in line_lower:
                        continue
                    if "translate with google" in line_lower:
                        continue

                    if len(line_clean) > 2:
                        clean_candidates.append(line_clean)

                review_body = " ".join(clean_candidates).strip()

                if rating != "N/A" and review_body:
                    hotel_reviews.append({
                        "Location": location,
                        "Rating": rating,
                        "Review": review_body
                    })

            except Exception:
                continue

            if len(hotel_reviews) >= TARGET_REVIEWS_PER_HOTEL:
                break

    except Exception as e:
        print(f"Error scraping hotel: {e}")

    return hotel_reviews


if __name__ == "__main__":
    driver = init_driver()

    # Quick IP test to confirm proxy is actually used
    try:
        print("Verifying Proxy Connection...")
        driver.get("https://ipv4.icanhazip.com")
        # Small wait so we don't accidentally read a transient error page
        time.sleep(2)
        print(f"CONNECTED VIA IP: {driver.find_element(By.TAG_NAME, 'body').text.strip()}")
    except:
        print("Warning: IP check skipped or failed.")

    with open(OUTPUT_FILE, mode='w', newline='', encoding='utf-8-sig') as file:
        fieldnames = ["Location", "Rating", "Review"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for hotel in HOTELS_LIST:
            if "PUT_URL" in hotel["url"]:
                continue

            data = scrape_single_hotel(driver, hotel)
            if data:
                writer.writerows(data)
                print(f"--> Saved {len(data)} rows for {hotel['location']}.")
            else:
                print(f"--> No data found for {hotel['location']}.")

            time.sleep(3)

    driver.quit()
    print("Done.")


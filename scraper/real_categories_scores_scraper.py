import time
import csv
from seleniumwire import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# CONFIG
# =========================

# Output CSV file name (no extension here). The script will create/append to this file.
OUTPUT_FILE = "scraped_booking_real_scores.csv"

# Proxy configuration for routing traffic (useful for avoiding blocks / rate limits).
PROXY_HOST = "..."
PROXY_PORT = "..."
PROXY_USER = "..."
PROXY_PASS = "..."
CHROME_VERSION = 142  # Keep this aligned with your installed/target Chrome major version.

# List of hotels to scrape.
# IMPORTANT: Add hotels from Booking here (each item should include city/country/hotel_name/url).
HOTELS_LIST = [
    {
        "city": "",
        "country": "",
        "hotel_name": "",
        "url": ""
    },
    {
        "city": "",
        "country": "",
        "hotel_name": "",
        "url": ""
    }
]

# =========================
# DRIVER SETUP
# =========================
def init_driver(headless=False):
    # Selenium Wire proxy config (HTTP + HTTPS) so all browser requests go through the proxy.
    # verify_ssl=False helps when the proxy MITM/cert chain causes SSL validation issues.
    proxy_options = {
        'proxy': {
            'http': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
            'https': f'https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
            'no_proxy': 'localhost,127.0.0.1'  # Do not proxy local traffic.
        },
        'verify_ssl': False
    }

    # Chrome options for stability + fewer SSL/cert interruptions.
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")  # Consistent layout for selectors.
    options.add_argument('--ignore-certificate-errors')  # Avoid cert errors (common with proxies).
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument("--lang=en-US")  # Forces English UI (helps stable text/selectors).

    # Prevent background tab throttling/freezing (helps when running long scrapes).
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")

    # Headless mode is optional; some anti-bot systems behave differently in headless.
    if headless:
        options.add_argument("--headless=new")

    print("Initializing driver with Proxy & SSL Bypass...")

    # Use undetected_chromedriver to reduce detection likelihood.
    driver = uc.Chrome(
        options=options,
        seleniumwire_options=proxy_options,
        version_main=142
    )
    return driver


# =========================
# COOKIES & NAVIGATION
# =========================
def handle_cookies(driver):
    # Attempts to click "Accept cookies" if present.
    # This prevents popups from blocking navigation/clicks on the page.
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button[id*="accept"], button[data-testid*="accept"]')
            )
        )
        driver.execute_script("arguments[0].click();", btn)  # JS click can bypass overlay issues.
        time.sleep(1)  # Small delay to let the banner disappear.
        print("[i] Cookies accepted")
    except:
        # If no cookies banner exists (or selector changes), continue silently.
        pass


def open_reviews_tab(driver):
    # Tries multiple selectors because Booking may A/B test the reviews tab.
    # The goal is to ensure the review subscores section is visible/loaded.
    wait = WebDriverWait(driver, 15)
    selectors = [
        '[data-testid="review-score-link"]',
        '[data-testid="Property-Header-Nav-Tab-trigger-reviews"]',
        'a[href*="#tab-reviews"]',
        'a[href*="blockdisplay"]'
    ]

    print("[i] Looking for reviews tab...")
    for sel in selectors:
        try:
            # Wait for element presence (not necessarily clickable) and then click via JS.
            el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            driver.execute_script("arguments[0].scrollIntoView(true);", el)
            time.sleep(1)  # Let scrolling settle before clicking.
            driver.execute_script("arguments[0].click();", el)
            print(f"[i] Opened reviews using selector: {sel}")
            return
        except:
            # Try the next selector if this one fails.
            continue
    print("⚠️ Warning: Could not find explicit reviews tab button.")


# =========================
# SCORE EXTRACTION LOGIC
# =========================
def extract_category_scores(driver):
    """
    Finds all review subscore rows, identifies the category name,
    and extracts the score from aria-valuenow (usually a 0..1 value).
    """

    # Maps visible category labels into stable output keys.
    # (Booking sometimes spells Wifi/WiFi differently.)
    CATEGORY_MAP = {
        "Staff": "Staff",
        "Facilities": "Facilities",
        "Cleanliness": "Cleanliness",
        "Comfort": "Comfort",
        "Location": "Location",
        "Free WiFi": "Free_Wifi",
        "Free Wifi": "Free_Wifi"
    }

    # Default scores (0.0) so the CSV always has consistent columns.
    scores = {
        "Staff": 0.0,
        "Facilities": 0.0,
        "Cleanliness": 0.0,
        "Comfort": 0.0,
        "Location": 0.0,
        "Free_Wifi": 0.0
    }

    try:
        # Each row should include label text + a meter element with aria-valuenow.
        rows = driver.find_elements(By.CSS_SELECTOR, '[data-testid="review-subscore"]')

        print(f"[i] Found {len(rows)} category rows. Parsing...")

        for row in rows:
            try:
                # Identify which category this row represents using its text.
                row_text = row.text
                target_category = None
                for key, val in CATEGORY_MAP.items():
                    if key in row_text:
                        target_category = val
                        break

                # Skip unknown categories we don't track.
                if not target_category:
                    continue

                # Extract score from the meter (aria-valuenow often like 0.94).
                meter = row.find_element(By.CSS_SELECTOR, '[role="meter"]')
                raw_val = meter.get_attribute("aria-valuenow")

                # Convert 0..1 to 0..10 and round to 1 decimal place for readability.
                if raw_val:
                    final_score = round(float(raw_val) * 10, 1)
                    scores[target_category] = final_score
                    print(f"   -> {target_category}: {final_score}")

            except:
                # If a single row fails (missing meter / different structure), ignore and continue.
                continue

    except Exception as e:
        # Any unexpected failure should not crash the whole scrape; return whatever we have.
        print(f"⚠️ Error extracting scores: {e}")

    return scores


def scrape_booking_hotel(driver, hotel_url, country, city, hotel_name):
    # Main per-hotel routine:
    # - open hotel page
    # - accept cookies
    # - navigate to reviews
    # - ensure all reviews/subscores are loaded
    # - extract subscores and write to CSV
    wait = WebDriverWait(driver, 25)

    # Force English content for more stable UI/selectors.
    if "lang=en-us" not in hotel_url:
        hotel_url += "&lang=en-us" if "?" in hotel_url else "?lang=en-us"

    print(f"[i] Opening hotel page: {hotel_name}")
    driver.get(hotel_url)
    time.sleep(5)  # Initial load buffer (Booking can be heavy / JS-driven).

    handle_cookies(driver)

    # Scroll slightly so lazy-loaded review components can start loading.
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.25);")
    time.sleep(1)

    # 1) Open the reviews tab (critical: subscores often won't exist before this).
    open_reviews_tab(driver)

    # 2) Click "Show all reviews" if Booking hides content behind a filter/expander.
    # This step helps ensure full data loads (especially subscores widgets).
    time.sleep(2)
    try:
        show_all_btn = driver.find_elements(
            By.XPATH,
            "//button[contains(., 'Show all reviews')] | //span[contains(text(), 'Show all reviews')]"
        )
        if show_all_btn:
            print("[!] Detected hidden reviews filter. Clicking 'Show all reviews'...")
            driver.execute_script("arguments[0].click();", show_all_btn[0])
            time.sleep(3)  # Wait for refreshed/expanded content.
    except:
        # If the button isn't present or XPath changes, continue.
        pass

    # 3) Extra wait to reduce race conditions before reading meters.
    time.sleep(2)

    # 4) Extract category subscores from the loaded reviews section.
    category_scores = extract_category_scores(driver)

    # 5) Append results to CSV.
    # Note: output columns must match the header in MAIN.
    with open(OUTPUT_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            hotel_name, country, city,
            category_scores["Staff"],
            category_scores["Facilities"],
            category_scores["Cleanliness"],
            category_scores["Comfort"],
            category_scores["Location"],
            category_scores["Free_Wifi"]
        ])
        f.flush()  # Ensures data is written even if the script stops later.

    print(f"✅ DONE – Saved scores for {hotel_name}\n")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    import os

    # Create the CSV file with header row if it doesn't exist yet.
    if not os.path.isfile(OUTPUT_FILE):
        print(f"[i] Creating new file: {OUTPUT_FILE}")
        with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow([
                "HotelName", "Country", "City",
                "Staff", "Facilities", "Cleanliness",
                "Comfort", "Location", "Free_Wifi"
            ])
    else:
        # If file already exists, we append new rows (do not overwrite).
        print(f"[i] Found existing file: {OUTPUT_FILE} - Appending new data...")

    # Start browser (set headless=True for server/CI runs, but may reduce reliability on some sites).
    driver = init_driver(headless=False)

    try:
        # Quick sanity check: verify outbound IP (confirms proxy is working).
        print("[i] Verifying proxy...")
        try:
            driver.get("https://ipv4.icanhazip.com")
            time.sleep(2)
            print(f"[i] CONNECTED VIA IP: {driver.find_element(By.TAG_NAME, 'body').text.strip()}")
        except:
            # If this fails, the scrape might still work; continue.
            print("⚠️ Proxy verification timed out/failed (continuing)")

        # Iterate hotels and scrape each one.
        for i, hotel in enumerate(HOTELS_LIST):
            print(f"--- Processing hotel {i + 1}/{len(HOTELS_LIST)}: {hotel['hotel_name']} ---")

            scrape_booking_hotel(
                driver,
                hotel_url=hotel["url"],
                country=hotel["country"],
                city=hotel["city"],
                hotel_name=hotel["hotel_name"]
            )

            # Cooldown between hotels to reduce bot detection / rate limiting.
            print("[i] Cooling down for 5 seconds...")
            time.sleep(5)

    finally:
        # Always close the browser, even if an exception happens.
        driver.quit()
        print("\n✅ ALL DONE – driver closed")
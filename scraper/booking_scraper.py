import time
import csv
from seleniumwire import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# CONFIG
# =========================

# CSV output file (created once with headers if missing, then appended to).
OUTPUT_FILE = "scraped_booking.csv"

# Proxy credentials (keep these exactly as provided by your proxy provider).
# Used to route requests and reduce blocking / rate limiting.
PROXY_HOST = "..."
PROXY_PORT = "..."
PROXY_USER = "..."
PROXY_PASS = "..."

# Safety limit: maximum number of reviews to scrape per hotel.
MAX_REVIEWS = 500

# Must match the Chrome major version used by undetected_chromedriver on your machine.
CHROME_VERSION = 142  # Make sure this matches your installed Chrome version.


# =========================
# INPUT DATA
# =========================

# Hotels to scrape.
# Fill this list with Booking hotel pages (city/country/hotel_name/url).
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
# DRIVER
# =========================
def init_driver(headless=False):
    # Selenium Wire proxy config (HTTP + HTTPS).
    # verify_ssl=False reduces SSL/cert failures when proxies intercept traffic.
    proxy_options = {
        'proxy': {
            'http': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
            'https': f'https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
            'no_proxy': 'localhost,127.0.0.1'  # Don't proxy local traffic.
        },
        'verify_ssl': False  # Key toggle to avoid SSL "red screen" issues with some proxies.
    }

    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")  # Stable layout for element selectors.

    # Reduce browser security prompts and cert warnings (important for proxied HTTPS).
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--ignore-ssl-errors')

    # Booking is heavily localized; forcing English makes UI text more consistent.
    options.add_argument("--lang=en-US")

    # Prevent Chrome throttling when the window is in the background (helps long scraping runs).
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")

    # Headless mode is optional; some anti-bot systems behave differently in headless.
    if headless:
        options.add_argument("--headless=new")

    print("Initializing driver with Proxy & SSL Bypass...")

    # Create undetected_chromedriver instance with Selenium Wire proxy support.
    driver = uc.Chrome(
        options=options,
        seleniumwire_options=proxy_options,  # Proxy is applied here.
        version_main=142  # Must match your Chrome major version.
    )
    return driver

# =========================
# COOKIES
# =========================
def handle_cookies(driver):
    # Attempts to click an "accept cookies" button if present.
    # Prevents cookie banners from blocking clicks and overlays on Booking pages.
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button[id*="accept"], button[data-testid*="accept"]')
            )
        )
        driver.execute_script("arguments[0].click();", btn)  # JS click can bypass overlays.
        time.sleep(1)  # Let the banner close before continuing.
        print("[i] Cookies accepted")
    except:
        # If no banner exists or selector changed, continue silently.
        pass


# =========================
# OPEN REVIEWS TAB
# =========================
def open_reviews_tab(driver):
    # Booking may change markup or run experiments, so we try multiple selectors.
    # Goal: open/activate the Reviews section so review cards and pagination appear.
    wait = WebDriverWait(driver, 15)

    # Candidate selectors for a "Reviews" tab/link/button.
    selectors = [
        '[data-testid="review-score-link"]',
        '[data-testid="Property-Header-Nav-Tab-trigger-reviews"]',
        'a[href*="#tab-reviews"]',
        'a[href*="blockdisplay"]'
    ]

    print("[i] Looking for reviews tab...")
    for sel in selectors:
        try:
            el = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", el)
            time.sleep(1)  # Let scrolling settle before click.
            driver.execute_script("arguments[0].click();", el)
            print(f"[i] Opened reviews using selector: {sel}")
            return
        except:
            # Try next selector if this one doesn't work.
            continue

    # Not always an error: sometimes the page already lands in the reviews section.
    print("⚠️ Warning: Could not find explicit reviews tab button (might already be open).")


# =========================
# MAIN SCRAPER
# =========================
def scrape_booking_hotel(
        driver,
        hotel_url,
        country,
        city,
        hotel_name,
        max_reviews=500
):
    # Per-hotel routine:
    # 1) load hotel page (force English)
    # 2) accept cookies
    # 3) open reviews section
    # 4) collect review cards across pagination until max_reviews reached
    wait = WebDriverWait(driver, 25)

    # Force English via URL to reduce localization differences in the reviews UI.
    if "lang=en-us" not in hotel_url:
        if "?" in hotel_url:
            hotel_url += "&lang=en-us"
        else:
            hotel_url += "?lang=en-us"

    print(f"[i] Opening hotel page: {hotel_name}")
    print(f"[i] URL: {hotel_url}")

    driver.get(hotel_url)
    time.sleep(5)  # Initial buffer for JS-heavy Booking pages.

    handle_cookies(driver)

    # Light scroll to trigger lazy-loading of sections/components.
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.25);")
    time.sleep(1)

    # Ensure we are in the Reviews section before scraping cards.
    open_reviews_tab(driver)

    # If Booking shows an empty dialog until "Show all reviews" is clicked, handle it here.
    time.sleep(2)  # Give the dialog a moment to appear.
    try:
        # Use flexible XPath because the element may be a button or nested text span.
        show_all_btn = driver.find_elements(
            By.XPATH,
            "//button[contains(., 'Show all reviews')] | //span[contains(text(), 'Show all reviews')]"
        )

        if show_all_btn:
            print("[!] Detected hidden reviews filter. Clicking 'Show all reviews'...")
            driver.execute_script("arguments[0].click();", show_all_btn[0])
            time.sleep(3)  # Wait for reviews to reload/expand.
    except Exception as e:
        # Not fatal: the button may not exist on all pages/layouts.
        pass


    # Wait for any known review container/card to appear.
    print("[i] Waiting for reviews container...")
    try:
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, '[role="dialog"], .c-review-block, [data-testid="review-card"]')
            )
        )
    except:
        # We'll still try to scrape; sometimes content loads slowly or selectors differ.
        print("⚠️ Wait timed out, trying to scrape anyway...")

    time.sleep(3)  # Extra buffer to reduce race conditions when reading card content.

    collected = 0  # Total unique reviews written for this hotel.
    seen_reviews = set()  # Dedup guard: prevents saving the same text twice.

    # Ensure output file exists and has headers before appending.
    # (Append mode prevents overwriting previous runs/hotels.)
    import os
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["HotelName", "Country", "City", "Rating", "Date", "Review"])

    # Append-only write: add new rows continuously as we scrape.
    with open(OUTPUT_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        while collected < max_reviews:
            # Locate review cards (multiple selectors to handle different Booking layouts).
            cards = driver.find_elements(By.CSS_SELECTOR, '[data-testid="review-card"], li.review_item')

            if not cards:
                print("[!] No reviews found on this page.")
                break

            print(f"[i] Processing {len(cards)} cards on current view...")

            for card in cards:
                if collected >= max_reviews:
                    break

                parts = []  # Combined review text segments (positive + negative or fallback).
                has_content = False  # Tracks whether we successfully extracted explicit text blocks.

                # Step 1: Preferred extraction via Booking's positive/negative blocks (more reliable formatting).
                try:
                    pos = card.find_element(By.CSS_SELECTOR, '[data-testid="review-positive-text"]').text.strip()
                    if pos:
                        parts.append(pos)
                        has_content = True
                except:
                    pass

                try:
                    neg = card.find_element(By.CSS_SELECTOR, '[data-testid="review-negative-text"]').text.strip()
                    if neg:
                        parts.append(neg)
                        has_content = True
                except:
                    pass

                # Step 2: Fallback extraction ("bulldozer") if structured blocks are missing/empty in Selenium.
                # This grabs the raw card text and filters out UI/system lines and hotel responses.
                if not has_content:
                    try:
                        raw_text = card.text
                        clean_lines = []
                        stop_reading = False

                        for line in raw_text.split('\n'):
                            # Stop capturing once we hit the hotel's response section.
                            if "Hotel response" in line or "Responded on" in line:
                                stop_reading = True

                            if stop_reading:
                                continue

                            line_lower = line.lower()

                            # Filter common UI noise / metadata lines.
                            if "reviewed:" in line_lower:
                                continue
                            if "score" in line_lower and len(line) < 10:
                                continue
                            if "helpful" in line_lower:
                                continue
                            if "read more" in line_lower:
                                continue

                            # Keep only lines that look like real content.
                            if len(line) > 5:
                                clean_lines.append(line)

                        if clean_lines:
                            parts.append(" ".join(clean_lines))

                    except:
                        pass

                # Combine extracted segments into one review text string.
                review_text = " ".join(parts).strip()

                # Final validation + dedup.
                if not review_text or review_text in seen_reviews:
                    continue

                # Skip placeholder/empty reviews.
                if "no comments available" in review_text.lower():
                    continue

                # Extract numeric score if present.
                try:
                    raw_score = card.find_element(By.CSS_SELECTOR, '[data-testid="review-score"]').text.strip()
                    score = raw_score.replace("Scored", "").replace("Score", "").strip().split()[0]
                except:
                    score = "N/A"

                seen_reviews.add(review_text)

                # Write a single row for this review.
                # NOTE: This writes 4 fields, while the header above includes 6 columns (Rating, Date, Review).
                # Keeping this untouched as requested; adjust later if you want column alignment.
                writer.writerow([hotel_name, country, city, score, review_text])
                f.flush()  # Persist incrementally in case the run stops mid-way.

                collected += 1
                print(f"[+] {collected}/{max_reviews} | Rate: {score}")

            # Paginate to next page of reviews (if available).
            if collected >= max_reviews:
                break

            try:
                next_btn = driver.find_element(
                    By.CSS_SELECTOR, 'button[aria-label="Next page"]'
                )
                if not next_btn.is_enabled():
                    print("[i] Next button disabled. End.")
                    break

                driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_btn)
                print("[>>] Clicked Next Page...")
                time.sleep(4)  # Wait for the next page of cards to load.
            except:
                # If pagination control is missing, we reached the end (or layout differs).
                print("[i] No next page button – stopping")
                break

    print(f"\n✅ DONE – collected {collected} reviews")



# =========================
# RUN
# =========================
if __name__ == "__main__":

    # Create the output file once with headers (if missing), then always append.
    import os

    file_exists = os.path.isfile(OUTPUT_FILE)

    # If file does not exist, create it and write headers.
    if not file_exists:
        print(f"[i] Creating new file: {OUTPUT_FILE}")
        with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["HotelName", "Country", "City", "Rating", "Review"])
    else:
        print(f"[i] Found existing file: {OUTPUT_FILE} - Appending new data...")

    # Start the browser session (headless=False for visibility/debugging).
    driver = init_driver(headless=False)

    # Optional: quick proxy check by printing the outbound IP.
    try:
        print("Verifying Proxy...")
        driver.get("https://ipv4.icanhazip.com")
        time.sleep(2)
        print(f"CONNECTED VIA IP: {driver.find_element(By.TAG_NAME, 'body').text.strip()}")
    except:
        pass

    try:
        # Iterate over all hotels in HOTELS_LIST and scrape each one.
        for i, hotel in enumerate(HOTELS_LIST):
            print(f"\n--- Processing hotel {i + 1}/{len(HOTELS_LIST)}: {hotel['hotel_name']} ---")

            scrape_booking_hotel(
                driver,
                hotel_url=hotel['url'],
                country=hotel['country'],
                city=hotel['city'],
                hotel_name=hotel['hotel_name'],
                max_reviews=MAX_REVIEWS
            )

            # Cooldown reduces risk of detection / throttling between hotels.
            print("Cooling down for 30 seconds...")
            time.sleep(30)


    finally:
        # Always close the driver cleanly.
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

        print("All Done.")

import time
import random
import json
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# ── CONFIG ──────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = "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"

MODEL = "openrouter/owl-alpha"   # Or "deepseek/deepseek-r1:free"

YOUR_NAME  = "Dibash Humagain"
YOUR_EMAIL = "dibushumaga@gmail.com"

CHROMIUM_BINARY  = "/usr/bin/chromium"
CHROMIUM_PROFILE = "/home/dibas/.config/chromium"

NEXT_BUTTONS   = ["अर्को", "Next", "下一页", "Continue", "अगाडि बढ्नुहोस्"]
SUBMIT_BUTTONS = ["पेस गर्नुहोस्", "Submit", "提交", "सबमिट गर्नुहोस्"]

# Speed tuning – reduce delays (in seconds)
INITIAL_WAIT = 2          # was 4
PAGE_LOAD_WAIT = 2        # was 3
CLICK_DELAY = (0.2, 0.4)  # was (0.3, 0.6)
QUESTION_DELAY = (0.5, 1.0) # was (1.0, 1.8)
# ────────────────────────────────────────────────────────────────────────


# ── AI LOGIC (unchanged – chain‑of‑thought) ─────────────────────────────

def ask_ai(question: str, options: list) -> int:
    letters = ['A', 'B', 'C', 'D', 'E', 'F'][:len(options)]
    options_text = "\n".join([f"{letters[i]}. {opt}" for i, opt in enumerate(options)])

    prompt = f"""You are answering a multiple choice question accurately.

Question: {question}

Options:
{options_text}

Think step by step about which answer is correct, then on the LAST line write ONLY:
ANSWER: <letter>

Example last line: ANSWER: B"""

    for attempt in range(3):
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                data=json.dumps({
                    "model": MODEL,
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}]
                }),
                timeout=45
            )

            if response.status_code != 200:
                print(f"  ⚠️ API error {response.status_code}: {response.text[:200]}")
                time.sleep(1)
                continue

            result = response.json()
            raw = result["choices"][0]["message"]["content"].strip()

            if "<think>" in raw and "</think>" in raw:
                think_part = raw[raw.index("<think>")+7 : raw.index("</think>")]
                print(f"  🧠 Reasoning: {think_part[:200]}{'...' if len(think_part) > 200 else ''}")
            else:
                print(f"  🧠 Response: {raw[:300]}{'...' if len(raw) > 300 else ''}")

            for line in reversed(raw.splitlines()):
                line_up = line.strip().upper()
                if line_up.startswith("ANSWER:"):
                    letter = line_up.replace("ANSWER:", "").strip()
                    if letter in letters:
                        idx = letters.index(letter)
                        print(f"  ✅ AI chose: {letter} → {options[idx]}")
                        return idx

            for line in reversed(raw.splitlines()):
                stripped = line.strip().upper()
                if stripped in letters:
                    idx = letters.index(stripped)
                    print(f"  ✅ AI chose (fallback): {stripped} → {options[idx]}")
                    return idx

            print(f"  ⚠️ Could not parse letter (attempt {attempt+1})")
        except Exception as e:
            print(f"  ⚠️ Request error (attempt {attempt+1}): {e}")
            time.sleep(1)

    print("  ❌ All retries failed — defaulting to option A")
    return 0


# ── HELPERS (with reduced delays) ───────────────────────────────────────

def human_delay(min_s, max_s):
    time.sleep(random.uniform(min_s, max_s))


def fill_name_email(driver):
    inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email']")
    name_filled = email_filled = False

    for inp in inputs:
        typ  = inp.get_attribute("type") or ""
        aria = (inp.get_attribute("aria-label") or "").lower()
        plc  = (inp.get_attribute("placeholder") or "").lower()

        is_email = typ == "email" or "email" in aria or "email" in plc or "इमेल" in aria
        is_name  = "name" in aria or "name" in plc or "नाम" in aria

        if is_email and not email_filled:
            inp.clear()
            inp.send_keys(YOUR_EMAIL)
            print(f"  ✅ EMAIL: {YOUR_EMAIL}")
            email_filled = True
        elif is_name and not name_filled:
            inp.clear()
            inp.send_keys(YOUR_NAME)
            print(f"  ✅ NAME: {YOUR_NAME}")
            name_filled = True
        elif not name_filled:
            inp.clear()
            inp.send_keys(YOUR_NAME)
            print(f"  ✅ NAME (first field): {YOUR_NAME}")
            name_filled = True
        elif name_filled and not email_filled:
            inp.clear()
            inp.send_keys(YOUR_EMAIL)
            print(f"  ✅ EMAIL (second field): {YOUR_EMAIL}")
            email_filled = True

    return name_filled, email_filled


def click_button(driver, texts):
    for text in texts:
        try:
            xpaths = [
                f"//*[contains(text(),'{text}')]",
                f"//div[@role='button'][contains(.,'{text}')]",
                f"//button[contains(.,'{text}')]"
            ]
            for xp in xpaths:
                btns = driver.find_elements(By.XPATH, xp)
                for btn in btns:
                    if btn.is_displayed() and btn.is_enabled():
                        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                        human_delay(*CLICK_DELAY)
                        driver.execute_script("arguments[0].click();", btn)
                        print(f"  ✅ Clicked: '{text}'")
                        return True
        except Exception:
            continue
    return False


def extract_questions(driver):
    questions = []
    time.sleep(2)  # reduced from 3

    cards = driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
    if not cards:
        cards = driver.find_elements(By.CSS_SELECTOR, "div[jsname='Cpkphb']")
    if not cards:
        print("  ⚠️ No question containers found.")
        return []

    print(f"  Found {len(cards)} question containers")

    for card in cards:
        try:
            question_text = ""
            heading = card.find_elements(By.CSS_SELECTOR, "[role='heading']")
            if heading:
                question_text = heading[0].text.strip()
            if not question_text:
                lines = card.text.split("\n")
                if lines:
                    question_text = lines[0].strip()
            if not question_text:
                continue

            options = []
            radio_buttons = card.find_elements(By.CSS_SELECTOR, "[role='radio']")

            for radio in radio_buttons:
                opt_text = radio.get_attribute("aria-label") or radio.text.strip()
                if not opt_text:
                    spans = radio.find_elements(By.CSS_SELECTOR, "span")
                    if spans:
                        opt_text = spans[-1].text.strip()
                if opt_text:
                    options.append(opt_text)

            if len(options) >= 2:
                questions.append({
                    "question":      question_text,
                    "options":       options,
                    "radio_buttons": radio_buttons
                })
                print(f"  📝 Q: {question_text[:60]}{'...' if len(question_text) > 60 else ''} ({len(options)} options)")
        except Exception as e:
            print(f"  ⚠️ Error parsing card: {e}")

    return questions


def answer_question(driver, q):
    print(f"\n❓ {q['question']}")
    for i, opt in enumerate(q['options']):
        print(f"   {chr(65+i)}. {opt}")

    idx = ask_ai(q['question'], q['options'])
    idx = max(0, min(idx, len(q['radio_buttons']) - 1))

    try:
        rb = q['radio_buttons'][idx]
        driver.execute_script("arguments[0].scrollIntoView(true);", rb)
        human_delay(*CLICK_DELAY)
        driver.execute_script("arguments[0].click();", rb)
        print(f"  ✅ Selected: {q['options'][idx]}")
        return True
    except Exception as e:
        print(f"  ❌ Click failed: {e}")
        return False


# ── MAIN BOT (headless + faster) ────────────────────────────────────────

def run_bot(form_url: str):
    opts = Options()
    opts.binary_location = CHROMIUM_BINARY
    opts.add_argument(f"--user-data-dir={CHROMIUM_PROFILE}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--headless=new")               # <--- HEADLESS MODE
    opts.add_argument("--disable-gpu")                # recommended for headless
    opts.add_argument("--window-size=1920,1080")      # avoid missing elements

    print(f"🚀 Launching Chromium in HEADLESS mode (invisible) with your profile...")
    print(f"   🤖 Model: {MODEL}\n")

    driver = webdriver.Chrome(options=opts)

    try:
        print("🌐 Opening form...")
        driver.get(form_url)
        time.sleep(INITIAL_WAIT)

        print("\n📝 Filling name/email fields...")
        fill_name_email(driver)

        print("\n🔍 Looking for Next button...")
        if click_button(driver, NEXT_BUTTONS):
            time.sleep(PAGE_LOAD_WAIT)

            page = 1
            while True:
                print(f"\n📄 Page {page} — extracting questions...")
                questions = extract_questions(driver)

                if questions:
                    print(f"   Found {len(questions)} questions\n")
                    for q in questions:
                        answer_question(driver, q)
                        human_delay(*QUESTION_DELAY)
                else:
                    print("   No questions on this page.")

                if click_button(driver, NEXT_BUTTONS):
                    time.sleep(PAGE_LOAD_WAIT)
                    page += 1
                else:
                    break
        else:
            print("ℹ️  No Next button — checking for questions on this page...")
            questions = extract_questions(driver)
            if questions:
                for q in questions:
                    answer_question(driver, q)
                    human_delay(*QUESTION_DELAY)

        print("\n📤 Submitting form...")
        time.sleep(1)
        if not click_button(driver, SUBMIT_BUTTONS):
            print("⚠️  Submit button not found – maybe already submitted?")

        print("\n✅ Bot finished!")
        print("   (No browser window was shown – headless mode)")
        time.sleep(2)

    except Exception as e:
        import traceback
        print(f"❌ Fatal error: {e}")
        traceback.print_exc()
    finally:
        print("👋 Shutting down...")
        driver.quit()


# ── ENTRY POINT ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Google Form Bot — Headless + Chain‑of‑Thought")
    print("=" * 60)
    print(f"   Model : {MODEL}")
    print(f"   Name  : {YOUR_NAME}")
    print(f"   Email : {YOUR_EMAIL}")
    print("   Mode  : HEADLESS (browser runs invisibly)")
    print()

    url = input("Paste the Google Form link: ").strip()
    if url:
        run_bot(url)
    else:
        print("No link provided. Exiting.")
NEXT_BUTTONS   = ["अर्को", "Next", "下一页", "Continue", "अगाडि बढ्नुहोस्"]

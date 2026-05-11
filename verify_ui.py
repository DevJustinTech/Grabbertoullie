import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    print("Navigating to http://localhost:3001")
    page.goto("http://localhost:3001")

    # Wait for the UI to load
    page.wait_for_selector("input[type='text']")

    # Verify input is a child of a form
    form_element = page.evaluate("() => document.querySelector('input[type=\"text\"]').closest('form') !== null")
    if form_element:
        print("✅ SUCCESS: Input element is wrapped in a <form>")
    else:
        print("❌ ERROR: Input element is NOT wrapped in a <form>")

    # Verify input is NOT disabled initially
    is_disabled = page.evaluate("() => document.querySelector('input[type=\"text\"]').disabled")
    if not is_disabled:
        print("✅ SUCCESS: Input element is NOT disabled initially")
    else:
        print("❌ ERROR: Input element is disabled initially")

    print("Typing in the input and simulating an IME keypress (like 'Enter' during composition)...")

    # Intercept API to slow down response and check loading state
    def handle_route(route):
        time.sleep(2)
        route.fulfill(status=200, body='{"type": "status", "message": "Simulated loading"}')

    page.route("**/api/chat", handle_route)

    input_selector = "input[type='text']"
    page.fill(input_selector, "The Hobbit")

    # Take a screenshot before pressing enter
    page.screenshot(path="before_submit.png")

    print("Submitting the form...")
    page.press(input_selector, "Enter")

    # Wait a bit to enter loading state
    time.sleep(0.5)

    # Take a screenshot during loading state
    page.screenshot(path="during_loading.png")

    # Check if input is disabled during loading
    is_disabled_loading = page.evaluate("() => document.querySelector('input[type=\"text\"]').disabled")
    if not is_disabled_loading:
        print("✅ SUCCESS: Input element remains enabled during loading to preserve focus")
    else:
        print("❌ ERROR: Input element became disabled during loading")

    # Check if button is disabled
    is_button_disabled = page.evaluate("() => document.querySelector('button[type=\"submit\"]').disabled")
    if is_button_disabled:
        print("✅ SUCCESS: Submit button is disabled during loading")
    else:
        print("❌ ERROR: Submit button is NOT disabled during loading")

    browser.close()

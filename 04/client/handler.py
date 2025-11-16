from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
from time import sleep


firefox_options = webdriver.FirefoxOptions()
firefox_options.add_argument("--headless")
firefox_options.set_preference("dom.disable_open_during_load", True)
firefox_options.set_preference(
    "dom.popup_allowed_events",
    "change click dblclick auxclick mousedown mouseup pointerdown pointerup notificationclick reset submit touchend contextmenu",
)
firefox_options.set_preference("dom.block_multiple_popups", True)

username = "admin"
password = os.environ.get("ADMIN_PASSWORD", "admin123")
appHostname = os.environ.get("INTERNAL_HOST", "http://web:8080")


def visit(url):
    """
    Admin bot visits a URL after logging in.
    Used to review reported personal spaces.
    """
    driver = webdriver.Remote(
        command_executor="http://firefox:4444/wd/hub", options=firefox_options
    )

    driver.set_page_load_timeout(30)
    driver.implicitly_wait(2)
    print(f"Admin bot started processing {url}")

    try:
        # Navigate to login page
        driver.get(f"{appHostname}/login")

        # Fill in login form
        username_field = driver.find_element(By.NAME, "username")
        password_field = driver.find_element(By.NAME, "password")

        username_field.send_keys(username)
        password_field.send_keys(password)

        # Submit the form
        password_field.submit()

        # Wait for login to complete
        sleep(2)

        print(f"Admin bot logged in, visiting {url}")

        # Visit the reported user's space
        driver.get(url)

        # Stay on page to let any scripts execute
        sleep(10)

        print(f"Admin bot finished reviewing {url}")
    except Exception as e:
        print(f"Error during admin bot visit: {e}")
    finally:
        driver.quit()

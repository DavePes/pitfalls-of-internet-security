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
password = os.environ.get("ADMIN_PASSWORD", None)
appHostname = os.environ.get("INTERNAL_HOST", "http://web:8080")


def visit(url):
    """
    Admin bot visits a URL after logging in.
    """
    driver = webdriver.Remote(
        command_executor="http://firefox:4444/wd/hub", options=firefox_options
    )

    driver.set_page_load_timeout(40)
    driver.implicitly_wait(5)
    print(f"started processing {url}")
    # Navigate to login page
    driver.get(f"{appHostname}/login")

    # Fill in login form
    username_field = driver.find_element(By.NAME, "username")
    password_field = driver.find_element(By.NAME, "password")

    username_field.send_keys(username)
    password_field.send_keys(password)
    password_field.submit()

    # Wait for login to complete
    sleep(2)

    # Visit the reported post
    driver.get(url)

    # Stay on page for a bit
    sleep(40)

    driver.quit()

#!/usr/bin/env python3

import time
import configargparse
from selenium import webdriver
#from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

def set_viewport_size(driver, width, height):
    # Set initial window size
    driver.set_window_size(width, height)

    # Get actual viewport size
    actual_width = driver.execute_script("return window.innerWidth")
    actual_height = driver.execute_script("return window.innerHeight")

    # Compute window chrome (browser decorations)
    delta_width = width - actual_width
    delta_height = height - actual_height

    # Resize window to compensate
    driver.set_window_size(width + delta_width, height + delta_height)

# Parse command-line arguments
p = configargparse.ArgParser()
p.add_argument('name', type=str, help='Name of the screenshot task')
p.add_argument('url', type=str, help='URL or file:/// path to capture')
p.add_argument('width', type=int, help='Viewport width in pixels')
p.add_argument('height', type=int, help='Viewport height in pixels')
args = p.parse_args()

# Setup headless browser
options = Options()
options.add_argument("--headless")
#options.add_argument(f"--window-size={args.width},{args.height}")
options.add_argument("--disable-gpu")  # Required for some headless systems

driver = webdriver.Firefox(options=options)

set_viewport_size(driver, args.width, args.height)

# Load page and take screenshot
driver.get(args.url)
time.sleep(3)  # Allow page to render (optional)

filename = f"screenshots/{args.name}.png"
driver.save_screenshot(filename)

driver.quit()
print("Saved screenshot as:", filename)


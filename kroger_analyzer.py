from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
import time
import re
import random
from textblob import TextBlob
import pandas as pd
from collections import Counter
import tempfile
import os
from urllib.parse import urljoin, quote_plus
from datetime import datetime, timedelta
import json
import requests

class KrogerReviewAnalyzer:
    def __init__(self, use_selenium=True, headless=True):
        self.use_selenium = use_selenium
        self.headless = headless
        self.session = None
        self.driver = None
        
        # Cincinnati Kroger store information (multiple options)
        self.cincinnati_stores = {
            'downtown': {
                'store_id': '01400465',  # Oakley
                'zip_code': '45202',
                'city': 'Cincinnati',
                'state': 'OH',
                'name': 'Oakley'
            },
            'green_township': {
                'store_id': '01400444',  # Green Township
                'zip_code': '45211',
                'city': 'Cincinnati', 
                'state': 'OH',
                'name': 'Green Township'
            },
            'university': {
                'store_id': '01400929',  # University Plaza
                'zip_code': '45219',
                'city': 'Cincinnati',
                'state': 'OH', 
                'name': 'University Plaza'
            },
            'hartwell': {
                'store_id': '01400405',  # Hartwell
                'zip_code': '45215',
                'city': 'Cincinnati',
                'state': 'OH',
                'name': 'Hartwell'
            }
        }
        
        # Default to downtown Cincinnati location
        self.cincinnati_store = self.cincinnati_stores['downtown']
        
        # VSCode/Local environment user agents (more diverse)
        self.user_agents = [
            # Windows VSCode typical
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
            # Mac VSCode typical  
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            # Linux VSCode typical
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        if use_selenium:
            success = self._setup_selenium_with_location()
            if not success:
                print("Selenium setup failed, falling back to requests-only mode")
                self.use_selenium = False
                self._setup_requests_with_location()
        else:
            self._setup_requests_with_location()


    def _setup_selenium_with_location(self):

        try:
            print("Setting up Selenium with Cincinnati Kroger location...")
            
            chrome_options = Options()
            
            # Make it look like a real local Chrome instance
            if self.headless:
                chrome_options.add_argument('--headless=new')
            
            # Core options for Docker compatibility
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # CRITICAL: Remove automation indicators
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Mimic real local browser
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            
            # Set Cincinnati location in browser (geolocation override)
            # Cincinnati coordinates: 39.1031, -84.5120
            chrome_options.add_argument('--enable-features=GeolocationAPI')
            
            # Local browser window size
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--start-maximized')
            
            # Real user agent
            local_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            chrome_options.add_argument(f'--user-agent={local_ua}')
            
            # Mimic local Chrome profile preferences with Cincinnati location
            prefs = {
                "profile.default_content_setting_values": {
                    "notifications": 1,
                    "popups": 0,
                    "geolocation": 1,    # Allow location for Cincinnati
                    "media_stream": 1,
                },
                "profile.managed_default_content_settings": {
                    "images": 1
                },
                "intl.accept_languages": "en-US,en",
                "profile.default_content_settings.popups": 0,
                "extensions.settings": {},
                # Set Cincinnati timezone
                "profile.content_settings.exceptions.automatic_downloads": {
                    "*,*": {"last_modified": "13000000000000000", "setting": 1}
                }
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Additional browser flags
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--enable-features=NetworkService,NetworkServiceLogging')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-client-side-phishing-detection')
            chrome_options.add_argument('--disable-crash-reporter')
            chrome_options.add_argument('--disable-oopr-debug-crash-dump')
            chrome_options.add_argument('--no-crash-upload')
            chrome_options.add_argument('--disable-low-res-tiling')
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_argument('--silent')
            
            # Set Chrome binary location for Docker
            chrome_options.binary_location = "/usr/bin/google-chrome"
            
            # Create service
            service = Service(executable_path="/usr/local/bin/chromedriver")
            
            # Initialize driver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # CRITICAL: Hide webdriver property immediately
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            # Set Cincinnati geolocation
            self.driver.execute_cdp_cmd("Emulation.setGeolocationOverride", {
                "latitude": 39.1031,
                "longitude": -84.5120,
                "accuracy": 100
            })
            
            # Add more realistic navigator properties
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5], // Fake plugins array
                });
            """)
            
            # Set realistic timeouts
            self.driver.set_page_load_timeout(90)
            self.driver.implicitly_wait(20)
            
            # Now set the Cincinnati store location
            success = self._set_cincinnati_store_location()
            if not success:
                print("⚠️ Warning: Could not set Cincinnati store location, proceeding anyway")
            
            print("✅ Selenium configured with Cincinnati location")
            return True
            
        except Exception as e:
            print(f"❌ Selenium setup failed: {e}")
            return False
    
    def set_cincinnati_store(self, store_name='downtown'):
        """Set specific Cincinnati store location"""
        if store_name in self.cincinnati_stores:
            self.cincinnati_store = self.cincinnati_stores[store_name]
            print(f"✅ Set Cincinnati store to: {self.cincinnati_store['name']}")
            return True
        else:
            print(f"❌ Unknown store: {store_name}. Available: {list(self.cincinnati_stores.keys())}")
      
        try:
            print("Setting up Selenium with Cincinnati Kroger location...")
            
            chrome_options = Options()
            
            # Make it look like a real local Chrome instance
            if self.headless:
                chrome_options.add_argument('--headless=new')
            
            # Core options for Docker compatibility
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # CRITICAL: Remove automation indicators
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Mimic real local browser
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            
            # Set Cincinnati location in browser (geolocation override)
            # Cincinnati coordinates: 39.1031, -84.5120
            chrome_options.add_argument('--enable-features=GeolocationAPI')
            
            # Local browser window size
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--start-maximized')
            
            # Real user agent
            local_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            chrome_options.add_argument(f'--user-agent={local_ua}')
            
            # Mimic local Chrome profile preferences with Cincinnati location
            prefs = {
                "profile.default_content_setting_values": {
                    "notifications": 1,
                    "popups": 0,
                    "geolocation": 1,    # Allow location for Cincinnati
                    "media_stream": 1,
                },
                "profile.managed_default_content_settings": {
                    "images": 1
                },
                "intl.accept_languages": "en-US,en",
                "profile.default_content_settings.popups": 0,
                "extensions.settings": {},
                # Set Cincinnati timezone
                "profile.content_settings.exceptions.automatic_downloads": {
                    "*,*": {"last_modified": "13000000000000000", "setting": 1}
                }
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Additional browser flags
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--enable-features=NetworkService,NetworkServiceLogging')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-client-side-phishing-detection')
            chrome_options.add_argument('--disable-crash-reporter')
            chrome_options.add_argument('--disable-oopr-debug-crash-dump')
            chrome_options.add_argument('--no-crash-upload')
            chrome_options.add_argument('--disable-low-res-tiling')
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_argument('--silent')
            
            # Set Chrome binary location for Docker
            chrome_options.binary_location = "/usr/bin/google-chrome"
            
            # Create service
            service = Service(executable_path="/usr/local/bin/chromedriver")
            
            # Initialize driver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # CRITICAL: Hide webdriver property immediately
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            # Set Cincinnati geolocation
            self.driver.execute_cdp_cmd("Emulation.setGeolocationOverride", {
                "latitude": 39.1031,
                "longitude": -84.5120,
                "accuracy": 100
            })
            
            # Add more realistic navigator properties
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5], // Fake plugins array
                });
            """)
            
            # Set realistic timeouts
            self.driver.set_page_load_timeout(90)
            self.driver.implicitly_wait(20)
            
            # Now set the Cincinnati store location
            success = self._set_cincinnati_store_location()
            if not success:
                print("⚠️ Warning: Could not set Cincinnati store location, proceeding anyway")
            
            print("✅ Selenium configured with Cincinnati location")
            return True
            
        except Exception as e:
            print(f"❌ Selenium setup failed: {e}")
            return False
            
    
    def _set_cincinnati_store_location(self):
        """Navigate to Kroger and set Cincinnati store location"""
        try:
            print("🏪 Setting Cincinnati Kroger store location...")
            
            # Go to Kroger homepage first
            self.driver.get("https://www.kroger.com")
            time.sleep(5)
            
            # Look for store locator or location setter
            store_selectors = [
                '[data-testid="store-selector"]',
                '[data-testid="store-locator"]',
                '.store-selector',
                '.store-locator',
                '[aria-label*="store"]',
                '[aria-label*="location"]',
                'button[data-testid*="store"]',
                'a[href*="store"]',
                '.header-store-info',
                '#store-selector'
            ]
            
            store_element = None
            for selector in store_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        store_element = elements[0]
                        print(f"✅ Found store selector with: {selector}")
                        break
                except:
                    continue
            
            if store_element:
                try:
                    # Click the store selector
                    self.driver.execute_script("arguments[0].click();", store_element)
                    time.sleep(3)
                    
                    # Try to enter Cincinnati zip code
                    zip_selectors = [
                        'input[placeholder*="zip"]',
                        'input[placeholder*="ZIP"]',
                        'input[name*="zip"]',
                        'input[id*="zip"]',
                        'input[type="text"]'
                    ]
                    
                    for selector in zip_selectors:
                        try:
                            zip_inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if zip_inputs:
                                zip_input = zip_inputs[0]
                                zip_input.clear()
                                zip_input.send_keys(self.cincinnati_store['zip_code'])
                                time.sleep(2)
                                
                                # Try to submit or search
                                zip_input.send_keys('\n')  # Press Enter
                                time.sleep(5)
                                
                                print(f"✅ Entered Cincinnati ZIP: {self.cincinnati_store['zip_code']}")
                                
                                # Look for Cincinnati stores and select one
                                self._select_cincinnati_store()
                                return True
                        except:
                            continue
                except Exception as e:
                    print(f"⚠️ Could not interact with store selector: {e}")
            
            # Alternative: Try direct URL with location
            try:
                print("🔄 Trying alternative method: direct URL with location...")
                location_url = f"https://www.kroger.com/stores/search?searchText={self.cincinnati_store['zip_code']}"
                self.driver.get(location_url)
                time.sleep(5)
                
                # Try to select a Cincinnati store
                self._select_cincinnati_store()
                return True
                
            except Exception as e:
                print(f"⚠️ Alternative method failed: {e}")
            
            # Final attempt: Set cookies/localStorage with Cincinnati location
            try:
                print("🔄 Final attempt: Setting location via JavaScript...")
                
                # Set location in localStorage (common pattern)
                location_data = {
                    'storeId': self.cincinnati_store['store_id'],
                    'zipCode': self.cincinnati_store['zip_code'],
                    'city': self.cincinnati_store['city'],
                    'state': self.cincinnati_store['state']
                }
                
                self.driver.execute_script(f"""
                    localStorage.setItem('selectedStore', '{json.dumps(location_data)}');
                    localStorage.setItem('storeId', '{self.cincinnati_store["store_id"]}');
                    localStorage.setItem('zipCode', '{self.cincinnati_store["zip_code"]}');
                """)
                
                # Also try setting cookies
                self.driver.add_cookie({
                    'name': 'storeId',
                    'value': self.cincinnati_store['store_id'],
                    'domain': '.kroger.com'
                })
                
                self.driver.add_cookie({
                    'name': 'zipCode', 
                    'value': self.cincinnati_store['zip_code'],
                    'domain': '.kroger.com'
                })
                
                print("✅ Set Cincinnati location via JavaScript")
                
                # Refresh to apply location
                self.driver.refresh()
                time.sleep(5)
                
                return True
                
            except Exception as e:
                print(f"⚠️ JavaScript method failed: {e}")
                
            return False
            
        except Exception as e:
            print(f"❌ Failed to set Cincinnati store location: {e}")
            return False
    
    def _select_cincinnati_store(self):
        """Try to select a specific Cincinnati store from results"""
        try:
            print("🏪 Looking for Cincinnati store options...")
            
            # Look for store cards or results
            store_selectors = [
                '.store-card',
                '.store-result',
                '[data-testid*="store"]',
                '.store-item',
                '[class*="store"]'
            ]
            
            for selector in store_selectors:
                try:
                    stores = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    print(f"Found {len(stores)} potential stores with {selector}")
                    
                    for store in stores[:3]:  # Check first 3 stores
                        store_text = store.text.lower()
                        if 'cincinnati' in store_text or self.cincinnati_store['zip_code'] in store_text:
                            try:
                                # Look for select button within store
                                select_buttons = store.find_elements(By.CSS_SELECTOR, 
                                    'button, a[role="button"], [data-testid*="select"]')
                                
                                if select_buttons:
                                    self.driver.execute_script("arguments[0].click();", select_buttons[0])
                                    time.sleep(3)
                                    print("✅ Selected Cincinnati store!")
                                    return True
                                else:
                                    # Try clicking the store itself
                                    self.driver.execute_script("arguments[0].click();", store)
                                    time.sleep(3)
                                    print("✅ Clicked Cincinnati store!")
                                    return True
                            except:
                                continue
                except:
                    continue
            
            # If no specific selection worked, just click the first store
            try:
                first_store_button = self.driver.find_elements(By.CSS_SELECTOR, 
                    'button:contains("Select"), button:contains("Choose"), [data-testid*="select"]')
                if first_store_button:
                    self.driver.execute_script("arguments[0].click();", first_store_button[0])
                    time.sleep(3)
                    print("✅ Selected first available store")
                    return True
            except:
                pass
                
            return False
            
        except Exception as e:
            print(f"⚠️ Store selection failed: {e}")
            return False
    
    def _setup_requests_with_location(self):
        """Setup requests session with Cincinnati location headers"""
        print("Setting up requests session with Cincinnati location...")
        self.session = requests.Session()
        
        # Cincinnati-specific headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Sec-CH-UA': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"Windows"',
            'sec-ch-ua-platform-version': '"10.0.0"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-model': '""',
        }
        
        self.session.headers.update(headers)
        self.session.timeout = 45
        
        # Set Cincinnati location cookies
        self.session.cookies.set('storeId', self.cincinnati_store['store_id'], domain='.kroger.com')
        self.session.cookies.set('zipCode', self.cincinnati_store['zip_code'], domain='.kroger.com')
        
        print("✅ Requests session configured with Cincinnati location")
    
    def _setup_selenium_like_local(self):
        """Setup Selenium to mimic local VSCode environment"""
        try:
            print("Setting up Selenium to mimic local VSCode environment...")
            
            chrome_options = Options()
            
            # Make it look like a real local Chrome instance
            # Key: Remove most headless indicators
            if self.headless:
                chrome_options.add_argument('--headless=new')
            
            # Core options for Docker compatibility
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # CRITICAL: Remove automation indicators
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Mimic real local browser
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            
            # Local browser window size (not server-like)
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--start-maximized')
            
            # Real user agent (Windows developer machine)
            local_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            chrome_options.add_argument(f'--user-agent={local_ua}')
            
            # Mimic local Chrome profile preferences
            prefs = {
                "profile.default_content_setting_values": {
                    "notifications": 1,  # Allow notifications (like local)
                    "popups": 0,
                    "geolocation": 1,    # Allow location (like local)
                    "media_stream": 1,   # Allow camera/mic (like local)
                },
                "profile.managed_default_content_settings": {
                    "images": 1
                },
                # Mimic real browser language settings
                "intl.accept_languages": "en-US,en",
                "profile.default_content_settings.popups": 0,
                # Add some "realistic" extensions (just metadata)
                "extensions.settings": {},
                # Timezone like a real user
                "profile.content_settings.exceptions.automatic_downloads": {
                    "*,*": {"last_modified": "13000000000000000", "setting": 1}
                }
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Additional "real browser" flags
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--enable-features=NetworkService,NetworkServiceLogging')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-client-side-phishing-detection')
            chrome_options.add_argument('--disable-crash-reporter')
            chrome_options.add_argument('--disable-oopr-debug-crash-dump')
            chrome_options.add_argument('--no-crash-upload')
            chrome_options.add_argument('--disable-low-res-tiling')
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_argument('--silent')
            
            # Set Chrome binary location for Docker
            chrome_options.binary_location = "/usr/bin/google-chrome"
            
            # Create service
            service = Service(executable_path="/usr/local/bin/chromedriver")
            
            # Initialize driver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # CRITICAL: Hide webdriver property immediately
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            # Add more realistic navigator properties
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5], // Fake plugins array
                });
            """)
            
            # Set realistic timeouts (not too aggressive)
            self.driver.set_page_load_timeout(90)  # Longer like local
            self.driver.implicitly_wait(20)        # More patient like local
            
            print("✅ Selenium configured to mimic local VSCode environment")
            return True
            
        except Exception as e:
            print(f"❌ Local-style Selenium setup failed: {e}")
            return False
    
    def _setup_requests_like_local(self):
        """Setup requests session to mimic local development"""
        print("Setting up requests session to mimic local development...")
        self.session = requests.Session()
        
        # Mimic local developer browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            # Important: Add developer-like headers
            'Sec-CH-UA': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"Windows"',  # Specify Windows like VSCode
            # Add some realistic variations
            'sec-ch-ua-platform-version': '"10.0.0"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-model': '""',
        }
        
        self.session.headers.update(headers)
        self.session.timeout = 45  # More patient like local development
        print("✅ Requests session configured to mimic local development")
    
    def __del__(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def _mimic_local_behavior(self):
        """Simulate local development browsing patterns"""
        try:
            # Local developers often:
            
            # 1. Start by scrolling to see page content (like checking if page loaded)
            scroll_amount = random.randint(300, 800)
            self.driver.execute_script(f"window.scrollTo(0, {scroll_amount});")
            time.sleep(random.uniform(1.5, 3.0))  # Longer pauses like local testing
            
            # 2. Maybe check the console or inspect element (simulate with script)
            self.driver.execute_script("console.log('Checking page load...');")
            
            # 3. Scroll back up to work with content
            if random.random() > 0.6:
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(random.uniform(0.8, 1.5))
            
            # 4. Sometimes simulate clicking to test interactivity
            if random.random() > 0.7:
                try:
                    # Try to click a safe element like body
                    self.driver.execute_script("document.body.click();")
                except:
                    pass
            
            time.sleep(random.uniform(1, 2))  # Always take time like local testing
            
        except Exception as e:
            pass  # Ignore behavior simulation errors
    
    def search_products(self, category, max_products=10):
        """Search with Cincinnati store location"""
        print(f"🔍 Searching for products in Cincinnati: {category}")
        
        # Include location in search URL
        search_url = f"https://www.kroger.com/search?query={quote_plus(category)}"
        
        # Add store parameter if we have it
        if hasattr(self, 'cincinnati_store'):
            search_url += f"&storeId={self.cincinnati_store['store_id']}"
        
        start_time = time.time()
        max_search_time = 300  # 5 minutes
        
        try:
            if self.use_selenium:
                result = self._search_with_selenium_cincinnati(search_url, max_products, start_time, max_search_time)
            else:
                result = self._search_with_requests_cincinnati(search_url, max_products, start_time, max_search_time)
            
            return result
            
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return []
    
    def _search_with_selenium_cincinnati(self, search_url, max_products, start_time, max_time):

        try:
            print(f"Loading Cincinnati store search: {search_url}")
            
            if time.time() - start_time > max_time:
                return []
            
            # Navigate to search with location
            self.driver.get(search_url)
            time.sleep(5)
            
            print(f"✅ Page loaded. Title: {self.driver.title[:50]}...")
            
            # Verify we're shopping Cincinnati (look for store info)
            self._verify_cincinnati_location()
            
            # Continue with product search (using existing logic)
            return self._search_products_on_page(max_products, start_time, max_time)
            
        except Exception as e:
            print(f"❌ Cincinnati Selenium search failed: {e}")
            return []
    
    def _search_products_on_page(self, max_products, start_time, max_time):
        try:
            self._mimic_local_behavior()
            
            # Look for products with patience
            print("Looking for product elements...")
            
            local_selectors = [
                'a[href*="/p/"]',
                '[data-testid*="product"] a',
                '.ProductCard a',
                '.product-card a',
                'a[aria-label*="product"]',
                'a[href*="product"]',
                '.kds-Link[href*="/p/"]',
                'div[data-qa*="product"] a'
            ]
            
            products_found = []
            seen_urls = set()
            
            for selector in local_selectors:
                if time.time() - start_time > max_time:
                    break
                
                print(f"Trying selector: {selector}")              
                
                try:
                    self._smart_scroll_local()
                    
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    print(f"Found {len(elements)} elements with {selector}")
                    
                    if not elements:
                        continue
                    
                    for element in elements[:max_products * 3]:
                        try:
                            href = element.get_attribute('href')
                            if not href or href in seen_urls:
                                continue
                            
                            if not self._is_valid_kroger_product_url(href):
                                continue
                            
                            product_name = self._extract_product_name_local(element)
                            if not product_name or len(product_name) < 5:
                                continue
                            
                            full_url = href if href.startswith('http') else f"https://www.kroger.com{href}"
                            
                            products_found.append({
                                'name': product_name,
                                'url': full_url
                            })
                            seen_urls.add(href)
                            print(f"✅ Found: {product_name}")
                            
                            if len(products_found) >= max_products:
                                break
                                
                        except Exception as e:
                            continue
                
                    if products_found:
                        break
                        
                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue
            
            return self._clean_product_list(products_found)
            
        except Exception as e:
            print(f"❌ Product search on page failed: {e}")

    def _verify_cincinnati_location(self):
        """Verify we're shopping from Cincinnati location"""
        try:
            # Look for store location indicators
            location_indicators = [
                '.store-info',
                '.selected-store',
                '[data-testid*="store"]',
                '.header-store'
            ]
            
            for selector in location_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.lower()
                        if 'cincinnati' in text or self.cincinnati_store['zip_code'] in text:
                            print(f"✅ Confirmed Cincinnati location: {element.text[:50]}")
                            return True
                except:
                    continue
            
            # Check page source for location indicators
            page_source = self.driver.page_source.lower()
            if 'cincinnati' in page_source or self.cincinnati_store['zip_code'] in page_source:
                print("✅ Cincinnati location found in page source")
                return True
            
            print("⚠️ Could not verify Cincinnati location")
            return False
            
        except Exception as e:
            print(f"⚠️ Location verification failed: {e}")
            return False
    
    def _search_with_requests_cincinnati(self, search_url, max_products, start_time, max_time):
        """Requests search with Cincinnati location headers"""
        try:
            print(f"Making Cincinnati store request: {search_url}")
            
            if time.time() - start_time > max_time:
                return []
            
            # Add Cincinnati-specific headers
            headers = {
                'Referer': 'https://www.kroger.com/',
                'Origin': 'https://www.kroger.com',
                'X-Store-Id': self.cincinnati_store['store_id'],
                'X-Zip-Code': self.cincinnati_store['zip_code']
            }
            
            response = self.session.get(search_url, headers=headers, timeout=45)
            response.raise_for_status()
            
            print(f"✅ Cincinnati response received: {response.status_code}, length: {len(response.text)}")
            
            # Verify Cincinnati location in response
            if self.cincinnati_store['zip_code'] in response.text or 'cincinnati' in response.text.lower():
                print("✅ Confirmed Cincinnati location in response")
            
            # Parse products from response
            return self._parse_products_from_content(response.text, max_products)
            
        except Exception as e:
            print(f"❌ Cincinnati requests search failed: {e}")
            return []

    def _parse_products_from_content(self, content, max_products):
        try:
            # Look for JSON data structures (common in modern sites)
            json_patterns = [
                r'"href":"([^"]*\/p\/[^"]*)"[^}]*?"name":"([^"]*)"',
                r'"url":"([^"]*\/p\/[^"]*)"[^}]*?"title":"([^"]*)"',
                r'"link":"([^"]*\/p\/[^"]*)"[^}]*?"productName":"([^"]*)"'
            ]
            
            # Look for HTML patterns
            html_patterns = [
                r'<a[^>]+href="([^"]*\/p\/[^"]*)"[^>]*aria-label="([^"]*)"',
                r'<a[^>]+href="([^"]*\/p\/[^"]*)"[^>]*title="([^"]*)"',
                r'href="([^"]*\/p\/[^"]*)"[^>]*>([^<]+)</a>'
            ]
            
            products_found = []
            seen_urls = set()
            
            all_patterns = json_patterns + html_patterns
            
            for pattern in all_patterns:
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                print(f"Pattern found {len(matches)} matches")
                
                for href, name in matches:
                    if href in seen_urls or len(products_found) >= max_products:
                        continue
                    
                    if not self._is_valid_kroger_product_url(href):
                        continue
                    
                    # Clean up name
                    clean_name = re.sub(r'<[^>]+>', '', name).strip()
                    clean_name = re.sub(r'\s+', ' ', clean_name)
                    clean_name = re.sub(r'[^\w\s\-\.,&()%]', '', clean_name)
                    
                    if not self._looks_like_product_name(clean_name):
                        continue
                    
                    full_url = urljoin("https://www.kroger.com", href)
                    products_found.append({
                        'name': clean_name,
                        'url': full_url
                    })
                    seen_urls.add(href)
                    print(f"✅ Found: {clean_name}")
                
                if products_found:
                    break
            
            return self._clean_product_list(products_found)
            
        except Exception as e:
            print(f"❌ Content parsing failed: {e}")
            return []

    def _search_with_local_selenium(self, search_url, max_products, start_time, max_time):
        """Selenium search mimicking local VSCode development"""
        try:
            print(f"Loading page like local development: {search_url}")
            
            if time.time() - start_time > max_time:
                return []
            
            # Navigate like a developer testing locally
            self.driver.get(search_url)
            
            # Wait for page like local (developers are patient)
            time.sleep(5)  # Longer initial wait
            
#test hello


            print(f"✅ Page loaded in local-style. Title: {self.driver.title[:50]}...")
            
            # Mimic local developer behavior
            self._mimic_local_behavior()
            
            # Check if page looks normal (like developer would)
            page_height = self.driver.execute_script("return document.body.scrollHeight")
            if page_height < 1000:
                print("⚠️ Page seems too short, might be blocked")
            
            # Look for products with patience (like local testing)
            print("Looking for product elements...")
            
            # Try the exact selectors that worked locally
            local_selectors = [
                'a[href*="/p/"]',                    # Direct product links
                '[data-testid*="product"] a',       # Product card links  
                '.ProductCard a',                   # Product card class
                '.product-card a',                  # Alternative product card
                'a[aria-label*="product"]',         # Accessible product links
                'a[href*="product"]',               # Any product URLs
                '.kds-Link[href*="/p/"]',          # Kroger design system links
                'div[data-qa*="product"] a'        # QA attribute products
            ]
            
            products_found = []
            seen_urls = set()
            
            for selector in local_selectors:
                if time.time() - start_time > max_time:
                    break
                
                print(f"Trying selector: {selector}")
                
                try:
                    # Wait and scroll like local development
                    self._smart_scroll_local()
                    
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    print(f"Found {len(elements)} elements with {selector}")
                    
                    if not elements:
                        continue
                    
                    for element in elements[:max_products * 3]:
                        try:
                            href = element.get_attribute('href')
                            if not href or href in seen_urls:
                                continue
                            
                            # Validate URL like local testing
                            if not self._is_valid_kroger_product_url(href):
                                continue
                            
                            # Extract name carefully
                            product_name = self._extract_product_name_local(element)
                            if not product_name or len(product_name) < 5:
                                continue
                            
                            full_url = href if href.startswith('http') else f"https://www.kroger.com{href}"
                            
                            products_found.append({
                                'name': product_name,
                                'url': full_url
                            })
                            seen_urls.add(href)
                            print(f"✅ Found: {product_name}")
                            
                            if len(products_found) >= max_products:
                                break
                                
                        except Exception as e:
                            continue
                    
                    # If we found products, great!
                    if products_found:
                        break
                        
                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue
            
            return self._clean_product_list(products_found)
            
        except Exception as e:
            print(f"❌ Local-style Selenium search failed: {e}")
            return []
    
    def _smart_scroll_local(self):
        """Scroll like a local developer testing the page"""
        try:
            # Local developers often scroll to see different parts
            current_position = self.driver.execute_script("return window.pageYOffset")
            page_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Scroll down in realistic chunks
            for i in range(3):
                scroll_to = min(current_position + (i + 1) * 400, page_height - 500)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_to});")
                time.sleep(random.uniform(1, 2))  # Patient like local testing
                
                # Check if more content loaded
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height > page_height:
                    print("✅ Page loaded more content after scrolling")
                    page_height = new_height
                    
        except Exception as e:
            pass
    
    def _is_valid_kroger_product_url(self, url):
        """Validate Kroger product URLs like local testing would"""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Must be Kroger and contain product indicators
        if 'kroger.com' not in url_lower:
            return False
        
        # Look for actual product URL patterns
        valid_patterns = ['/p/', '/product/', '/item/']
        if not any(pattern in url_lower for pattern in valid_patterns):
            return False
        
        # Should not be navigation/utility pages
        invalid_patterns = [
            'search', 'category', 'department', 'help', 'account',
            'login', 'register', 'cart', 'checkout', 'store-locator',
            'recipe', 'coupon', 'deals', 'weekly-ad'
        ]
        
        for pattern in invalid_patterns:
            if pattern in url_lower:
                return False
        
        return True
    
    def _extract_product_name_local(self, element):
        """Extract product name like local testing (more thorough)"""
        try:
            # Try multiple strategies that work locally
            strategies = [
                # Most reliable: aria-label
                lambda e: e.get_attribute('aria-label'),
                lambda e: e.get_attribute('title'),
                
                # Text within the link
                lambda e: e.find_element(By.CSS_SELECTOR, 'h1, h2, h3, h4, h5').text.strip(),
                lambda e: e.find_element(By.CSS_SELECTOR, '[data-testid*="title"]').text.strip(),
                lambda e: e.find_element(By.CSS_SELECTOR, '.product-title').text.strip(),
                lambda e: e.find_element(By.CSS_SELECTOR, '[class*="title"]').text.strip(),
                
                # Image alt text
                lambda e: e.find_element(By.TAG_NAME, 'img').get_attribute('alt'),
                
                # Direct text content
                lambda e: e.text.strip()
            ]
            
            for strategy in strategies:
                try:
                    name = strategy(element)
                    if name and len(name.strip()) > 5:
                        # Clean up
                        clean_name = re.sub(r'\s+', ' ', name.strip())
                        clean_name = re.sub(r'[^\w\s\-\.,&()%]', '', clean_name)
                        
                        # Validate it looks like a product name
                        if self._looks_like_product_name(clean_name):
                            return clean_name
                except:
                    continue
            
            return ""
            
        except Exception as e:
            return ""
    
    def _looks_like_product_name(self, name):
        """Check if name looks like an actual product"""
        if not name or len(name) < 5:
            return False
        
        name_lower = name.lower()
        
        # Skip obvious UI elements
        ui_terms = [
            'search', 'filter', 'sort', 'view all', 'see more',
            'next', 'previous', 'page', 'results', 'loading',
            'menu', 'navigation', 'add to cart', 'quick view'
        ]
        
        for term in ui_terms:
            if term in name_lower:
                return False
        
        # Must look like product (has brand, size, or food words)
        product_indicators = [
            # Sizes and measurements
            'oz', 'lb', 'lbs', 'kg', 'gram', 'ml', 'liter',
            'pack', 'count', 'ct', 'piece', 'pc',
            
            # Food descriptors
            'organic', 'natural', 'fresh', 'frozen', 'low',
            'whole', 'skim', 'fat', 'free', 'gluten',
            'sugar', 'sodium', 'calorie',
            
            # Common brands (Kroger carries)
            'kroger', 'simple truth', 'private selection'
        ]
        
        # Must be reasonable length OR have indicators
        word_count = len(name.split())
        has_indicators = any(indicator in name_lower for indicator in product_indicators)
        
        return word_count >= 2 and (word_count <= 12 or has_indicators)
    
    def _search_with_local_requests(self, search_url, max_products, start_time, max_time):
        """Requests search mimicking local development"""
        try:
            print(f"Making request like local development: {search_url}")
            
            if time.time() - start_time > max_time:
                return []
            
            # Add referer like local browser
            headers = {
                'Referer': 'https://www.kroger.com/',
                'Origin': 'https://www.kroger.com'
            }
            
            response = self.session.get(search_url, headers=headers, timeout=45)
            response.raise_for_status()
            
            print(f"✅ Response received: {response.status_code}, length: {len(response.text)}")
            
            # Parse response like local development
            content = response.text
            
            # Look for JSON data structures (common in modern sites)
            json_patterns = [
                r'"href":"([^"]*\/p\/[^"]*)"[^}]*?"name":"([^"]*)"',
                r'"url":"([^"]*\/p\/[^"]*)"[^}]*?"title":"([^"]*)"',
                r'"link":"([^"]*\/p\/[^"]*)"[^}]*?"productName":"([^"]*)"'
            ]
            
            # Look for HTML patterns
            html_patterns = [
                r'<a[^>]+href="([^"]*\/p\/[^"]*)"[^>]*aria-label="([^"]*)"',
                r'<a[^>]+href="([^"]*\/p\/[^"]*)"[^>]*title="([^"]*)"',
                r'href="([^"]*\/p\/[^"]*)"[^>]*>([^<]+)</a>'
            ]
            
            products_found = []
            seen_urls = set()
            
            all_patterns = json_patterns + html_patterns
            
            for pattern in all_patterns:
                if time.time() - start_time > max_time:
                    break
                
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                print(f"Pattern found {len(matches)} matches")
                
                for href, name in matches:
                    if href in seen_urls or len(products_found) >= max_products:
                        continue
                    
                    if not self._is_valid_kroger_product_url(href):
                        continue
                    
                    # Clean up name
                    clean_name = re.sub(r'<[^>]+>', '', name).strip()
                    clean_name = re.sub(r'\s+', ' ', clean_name)
                    clean_name = re.sub(r'[^\w\s\-\.,&()%]', '', clean_name)
                    
                    if not self._looks_like_product_name(clean_name):
                        continue
                    
                    full_url = urljoin(search_url, href)
                    products_found.append({
                        'name': clean_name,
                        'url': full_url
                    })
                    seen_urls.add(href)
                    print(f"✅ Found: {clean_name}")
                
                if products_found:
                    break
            
            return self._clean_product_list(products_found)
            
        except Exception as e:
            print(f"❌ Local-style requests search failed: {e}")
            return []
    
    def _clean_product_list(self, products):
        """Clean and deduplicate product list"""
        seen_names = set()
        clean_products = []
        
        for product in products:
            # Create a normalized name for comparison
            norm_name = re.sub(r'[^\w\s]', '', product['name'].lower()).strip()
            
            if norm_name not in seen_names and len(norm_name) > 5:
                seen_names.add(norm_name)
                clean_products.append(product)
        
        return clean_products
    
    def scrape_product_reviews(self, product_url, max_reviews=20):
        """Mock reviews since review scraping is heavily blocked"""
        print(f"📝 Generating sample reviews for: {product_url}")
        
        # Generate realistic mock reviews for demonstration
        mock_reviews = [
            {"rating": 5, "text": "Great quality product! Very fresh and tasty.", "author": "LocalCustomer1", "datetime": datetime.now().isoformat()},
            {"rating": 4, "text": "Good value for the price. Would buy again.", "author": "LocalCustomer2", "datetime": datetime.now().isoformat()},
            {"rating": 5, "text": "Excellent! My family loves this product.", "author": "LocalCustomer3", "datetime": datetime.now().isoformat()},
            {"rating": 3, "text": "It's okay. Average quality for the price.", "author": "LocalCustomer4", "datetime": datetime.now().isoformat()},
            {"rating": 4, "text": "Pretty good. Fresh and well-packaged.", "author": "LocalCustomer5", "datetime": datetime.now().isoformat()},
            {"rating": 5, "text": "Perfect for our needs. Highly recommend!", "author": "LocalCustomer6", "datetime": datetime.now().isoformat()},
            {"rating": 2, "text": "Not what I expected. Could be better.", "author": "LocalCustomer7", "datetime": datetime.now().isoformat()},
            {"rating": 4, "text": "Good product overall. Meets expectations.", "author": "LocalCustomer8", "datetime": datetime.now().isoformat()}
        ]
        
        # Return random selection
        selected = random.sample(mock_reviews, min(max_reviews, len(mock_reviews)))
        print(f"✅ Generated {len(selected)} sample reviews")
        return selected
    
    # Include all other methods from the previous analyzer
    def analyze_category_by_products(self, category, max_products=10, max_reviews_per_product=20):
        """Main analysis method optimized for Cincinnati location"""
        print(f"🚀 Starting Cincinnati-based analysis for '{category}'")
        print(f"🏪 Using store: {self.cincinnati_store['name']} (ID: {self.cincinnati_store['store_id']})")
        
        products = self.search_products(category, max_products)
        
        if not products:
            print("❌ No products found")
            return None
        
        print(f"✅ Found {len(products)} products")
        
        product_analyses = []
        
        for i, product in enumerate(products):
            print(f"📊 Processing product {i+1}/{len(products)}: {product['name']}")
            
            try:
                reviews = self.scrape_product_reviews(product['url'], max_reviews_per_product)
                
                if reviews:
                    product_analysis = self.analyze_sentiment(reviews)
                    
                    if product_analysis and "error" not in product_analysis:
                        product_analysis['product_name'] = product['name']
                        product_analysis['product_url'] = product['url']
                        product_analysis['category'] = category
                        product_analyses.append(product_analysis)
                        print(f"✅ Added analysis for {product['name']}")
            
            except Exception as e:
                print(f"❌ Error processing {product['name']}: {e}")
                continue
            
            # Brief pause
            time.sleep(random.uniform(0.5, 1.5))
        
        if not product_analyses:
            print("❌ No valid product analyses generated")
            return None
        
        print(f"✅ Analysis complete: {len(product_analyses)} products processed")
        
        # Create summary
        summary_analysis = self._create_category_summary(product_analyses, category)
        
        return {
            'category': category,
            'summary': summary_analysis,
            'products': product_analyses,
            'total_products_analyzed': len(product_analyses),
            'store_info': self.cincinnati_store
        }
    
    
    # Include sentiment analysis and other helper methods from previous version
    def analyze_sentiment(self, reviews):
        """Analyze sentiment of reviews"""
        try:
            if not reviews:
                return {"error": "No reviews to analyze"}
            
            valid_reviews = []
            total_rating = 0
            rating_count = 0
            
            for review in reviews:
                if review.get('rating'):
                    total_rating += review['rating']
                    rating_count += 1
                
                if review.get('text') and len(review['text']) > 5:
                    valid_reviews.append(review)
            
            avg_rating = total_rating / rating_count if rating_count > 0 else 0
            
            # Analyze sentiment for text reviews
            sentiments = []
            positive_reviews = []
            negative_reviews = []
            neutral_reviews = []
            
            for review in valid_reviews:
                text = review.get('text', '')
                if text:
                    blob = TextBlob(text)
                    sentiment_score = blob.sentiment.polarity
                    sentiments.append(sentiment_score)
                    
                    if sentiment_score > 0.1:
                        positive_reviews.append(review)
                    elif sentiment_score < -0.1:
                        negative_reviews.append(review)
                    else:
                        neutral_reviews.append(review)
            
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
            
            # Extract themes
            all_text = ' '.join([review.get('text', '') for review in valid_reviews])
            themes = self._extract_themes(all_text)
            
            return {
                'average_rating': avg_rating,
                'total_reviews': len(reviews),
                'text_reviews': len(valid_reviews),
                'sentiment_score': avg_sentiment,
                'sentiment_label': self._get_sentiment_description(avg_sentiment),
                'positive_reviews': len(positive_reviews),
                'negative_reviews': len(negative_reviews),
                'neutral_reviews': len(neutral_reviews),
                'themes': themes,
                'sample_reviews': {
                    'positive': positive_reviews[:3],
                    'negative': negative_reviews[:3],
                    'neutral': neutral_reviews[:3]
                }
            }
            
        except Exception as e:
            print(f"Error in sentiment analysis: {e}")
            return {"error": str(e)}
    
    def _extract_themes(self, text):
        """Extract common themes from review text"""
        try:
            if not text or len(text) < 20:
                return []
            
            words = self._extract_meaningful_words(text)
            word_freq = Counter(words)
            common_words = word_freq.most_common(10)
            themes = [word for word, count in common_words if count >= 2]
            
            return themes[:5]
            
        except Exception as e:
            return []
    
    def _extract_meaningful_words(self, text):
        """Extract meaningful words from text"""
        try:
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
            
            stop_words = {
                'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
                'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
                'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this',
                'that', 'these', 'those', 'they', 'them', 'their', 'there', 'here',
                'when', 'where', 'why', 'how', 'what', 'who', 'which', 'very',
                'really', 'quite', 'just', 'only', 'also', 'even', 'still', 'more',
                'most', 'much', 'many', 'some', 'any', 'all', 'not', 'product'
            }
            
            return [word for word in words if word not in stop_words and len(word) > 3]
            
        except Exception as e:
            return []
    
    def _get_sentiment_description(self, score):
        """Convert sentiment score to description"""
        if score > 0.3:
            return "Very Positive"
        elif score > 0.1:
            return "Positive"
        elif score > -0.1:
            return "Neutral"
        elif score > -0.3:
            return "Negative"
        else:
            return "Very Negative"
    
    def _create_category_summary(self, product_analyses, category):
        """Create summary analysis for the entire category"""
        try:
            if not product_analyses:
                return None
            
            total_reviews = sum(p.get('total_reviews', 0) for p in product_analyses)
            total_text_reviews = sum(p.get('text_reviews', 0) for p in product_analyses)
            avg_rating = sum(p.get('average_rating', 0) for p in product_analyses) / len(product_analyses)
            avg_sentiment = sum(p.get('sentiment_score', 0) for p in product_analyses) / len(product_analyses)
            
            total_positive = sum(p.get('positive_reviews', 0) for p in product_analyses)
            total_negative = sum(p.get('negative_reviews', 0) for p in product_analyses)
            total_neutral = sum(p.get('neutral_reviews', 0) for p in product_analyses)
            
            all_themes = []
            for product in product_analyses:
                themes = product.get('themes', [])
                all_themes.extend(themes)
            
            theme_counts = Counter(all_themes)
            top_themes = [theme for theme, count in theme_counts.most_common(8)]
            
            best_product = max(product_analyses, key=lambda p: p.get('average_rating', 0))
            worst_product = min(product_analyses, key=lambda p: p.get('average_rating', 5))
            
            return {
                'category': category,
                'total_products': len(product_analyses),
                'total_reviews': total_reviews,
                'total_text_reviews': total_text_reviews,
                'average_rating': round(avg_rating, 2),
                'average_sentiment': round(avg_sentiment, 3),
                'sentiment_label': self._get_sentiment_description(avg_sentiment),
                'positive_reviews': total_positive,
                'negative_reviews': total_negative,
                'neutral_reviews': total_neutral,
                'top_themes': top_themes,
                'best_product': {
                    'name': best_product.get('product_name', ''),
                    'rating': best_product.get('average_rating', 0),
                    'url': best_product.get('product_url', '')
                },
                'worst_product': {
                    'name': worst_product.get('product_name', ''),
                    'rating': worst_product.get('average_rating', 0),
                    'url': worst_product.get('product_url', '')
                }
            }
            
        except Exception as e:
            print(f"Error creating category summary: {e}")
            return None
    
    def export_products_to_spreadsheet(self, analysis_data, filename=None):
        """Export analysis results to Excel spreadsheet"""
        try:
            if not analysis_data:
                print("No analysis data to export")
                return None
            
            if not filename:
                category = analysis_data.get('category', 'analysis')
                filename = f"{category.replace(' ', '_')}_analysis.xlsx"
            
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                self._write_category_summary_sheet(writer, analysis_data)
                self._write_products_overview_sheet(writer, analysis_data)
                self._write_all_reviews_sheet(writer, analysis_data)
            
            print(f"Analysis exported to: {filename}")
            return filename
            
        except Exception as e:
            print(f"Error exporting to spreadsheet: {e}")
            return None
    
    def _write_category_summary_sheet(self, writer, analysis_data):
        """Write category summary to Excel sheet"""
        try:
            summary = analysis_data.get('summary', {})
            
            summary_data = [
                ['Category', analysis_data.get('category', '')],
                ['Total Products Analyzed', summary.get('total_products', 0)],
                ['Total Reviews', summary.get('total_reviews', 0)],
                ['Total Text Reviews', summary.get('total_text_reviews', 0)],
                ['Average Rating', summary.get('average_rating', 0)],
                ['Average Sentiment Score', summary.get('average_sentiment', 0)],
                ['Overall Sentiment', summary.get('sentiment_label', '')],
                ['Positive Reviews', summary.get('positive_reviews', 0)],
                ['Neutral Reviews', summary.get('neutral_reviews', 0)],
                ['Negative Reviews', summary.get('negative_reviews', 0)],
                ['Top Themes', ', '.join(summary.get('top_themes', []))],
                ['Best Product', summary.get('best_product', {}).get('name', '')],
                ['Best Product Rating', summary.get('best_product', {}).get('rating', 0)],
                ['Worst Product', summary.get('worst_product', {}).get('name', '')],
                ['Worst Product Rating', summary.get('worst_product', {}).get('rating', 0)]
            ]
            
            df_summary = pd.DataFrame(summary_data, columns=['Metric', 'Value'])
            df_summary.to_excel(writer, sheet_name='Category Summary', index=False)
            
        except Exception as e:
            print(f"Error writing category summary: {e}")
    
    def _write_products_overview_sheet(self, writer, analysis_data):
        """Write products overview to Excel sheet"""
        try:
            products = analysis_data.get('products', [])
            
            products_data = []
            for product in products:
                products_data.append([
                    product.get('product_name', ''),
                    product.get('average_rating', 0),
                    product.get('total_reviews', 0),
                    product.get('text_reviews', 0),
                    product.get('sentiment_score', 0),
                    product.get('sentiment_label', ''),
                    product.get('positive_reviews', 0),
                    product.get('negative_reviews', 0),
                    product.get('neutral_reviews', 0),
                    ', '.join(product.get('themes', [])),
                    product.get('product_url', '')
                ])
            
            df_products = pd.DataFrame(products_data, columns=[
                'Product Name', 'Average Rating', 'Total Reviews', 'Text Reviews',
                'Sentiment Score', 'Sentiment Label', 'Positive Reviews',
                'Negative Reviews', 'Neutral Reviews', 'Top Themes', 'Product URL'
            ])
            
            df_products.to_excel(writer, sheet_name='Products Overview', index=False)
            
        except Exception as e:
            print(f"Error writing products overview: {e}")
    
    def _write_all_reviews_sheet(self, writer, analysis_data):
        """Write all reviews to Excel sheet"""
        try:
            all_reviews_data = []
            products = analysis_data.get('products', [])
            
            for product in products:
                product_name = product.get('product_name', '')
                sample_reviews = product.get('sample_reviews', {})
                
                # Add positive reviews
                for review in sample_reviews.get('positive', []):
                    all_reviews_data.append([
                        product_name,
                        'Positive',
                        review.get('rating', ''),
                        review.get('text', ''),
                        review.get('author', '')
                    ])
                
                # Add negative reviews
                for review in sample_reviews.get('negative', []):
                    all_reviews_data.append([
                        product_name,
                        'Negative',
                        review.get('rating', ''),
                        review.get('text', ''),
                        review.get('author', '')
                    ])
                
                # Add neutral reviews
                for review in sample_reviews.get('neutral', []):
                    all_reviews_data.append([
                        product_name,
                        'Neutral',
                        review.get('rating', ''),
                        review.get('text', ''),
                        review.get('author', '')
                    ])
            
            if all_reviews_data:
                df_reviews = pd.DataFrame(all_reviews_data, columns=[
                    'Product Name', 'Sentiment Category', 'Rating', 'Review Text', 'Author'
                ])
                df_reviews.to_excel(writer, sheet_name='All Reviews', index=False)
            
        except Exception as e:
            print(f"Error writing all reviews: {e}")

    # Add these methods to your kroger_analyzer.py file

    def _extract_review_data_selenium(self, element):
        """Enhanced review data extraction with datetime"""
        try:
            review_data = {}
            
            # Extract rating
            rating = self._extract_rating_enhanced(element)
            if rating:
                review_data['rating'] = rating
            
            # Extract review text
            review_text = self._extract_review_text_enhanced(element)
            if review_text:
                review_data['text'] = review_text
            
            # Extract author
            author = self._extract_author_enhanced(element)
            if author:
                review_data['author'] = author
            
            # Extract datetime - NEW
            datetime_stamp = self._extract_datetime(element)
            if datetime_stamp:
                review_data['datetime'] = datetime_stamp.isoformat()
            
            return review_data if review_data else None
                
        except Exception as e:
            print(f"Error extracting review data: {e}")
            return None

    def _extract_datetime(self, element):
        """Extract datetime from review element"""
        try:
            from datetime import datetime
            
            # Enhanced datetime selectors
            datetime_selectors = [
                '[data-testid*="date"]',
                '[data-testid*="time"]',
                '.review-date',
                '.date',
                '.timestamp',
                '[class*="date"]',
                '[class*="time"]',
                'time',
                '[datetime]',
                '.posted-date',
                '.review-timestamp'
            ]
            
            for selector in datetime_selectors:
                try:
                    datetime_elements = element.find_elements(By.CSS_SELECTOR, selector)
                    for datetime_element in datetime_elements:
                        
                        # Try datetime attribute first
                        datetime_attr = datetime_element.get_attribute('datetime')
                        if datetime_attr:
                            parsed_date = self._parse_datetime_string(datetime_attr)
                            if parsed_date:
                                return parsed_date
                        
                        # Try element text
                        datetime_text = datetime_element.text.strip()
                        if datetime_text:
                            parsed_date = self._parse_datetime_string(datetime_text)
                            if parsed_date:
                                return parsed_date
                                
                except:
                    continue
            
            # Try to find date patterns in parent element text
            element_text = element.text or ''
            parsed_date = self._parse_datetime_string(element_text)
            if parsed_date:
                return parsed_date
            
            # Return current datetime as fallback
            return datetime.now()
            
        except Exception as e:
            print(f"Error extracting datetime: {e}")
            from datetime import datetime
            return datetime.now()

    def _parse_datetime_string(self, date_string):
        try:
            if not date_string:
                return None
            
            # Common date patterns
            date_patterns = [
                # ISO format
                (r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', '%Y-%m-%dT%H:%M:%S'),
                (r'(\d{4}-\d{2}-\d{2})', '%Y-%m-%d'),
                # US format
                (r'(\d{1,2}/\d{1,2}/\d{4})', '%m/%d/%Y'),
                (r'(\d{1,2}-\d{1,2}-\d{4})', '%m-%d-%Y'),
                # Month day, year
                (r'([A-Za-z]+ \d{1,2}, \d{4})', '%B %d, %Y'),
                (r'([A-Za-z]{3} \d{1,2}, \d{4})', '%b %d, %Y'),
            ]
            
            # Handle relative dates first
            if 'ago' in date_string.lower():
                return self._parse_relative_date(date_string)
            elif 'yesterday' in date_string.lower():
                return datetime.now() - timedelta(days=1)
            elif 'today' in date_string.lower():
                return datetime.now()
            
            # Try absolute date patterns
            for pattern, date_format in date_patterns:
                matches = re.findall(pattern, date_string, re.IGNORECASE)
                if matches:
                    date_match = matches[0]
                    try:
                        return datetime.strptime(date_match, date_format)
                    except ValueError:
                        continue
        except Exception:
            return None

    def _parse_relative_date(self, date_string):
        """Parse relative date strings like '5 days ago'"""
        try:
            from datetime import datetime, timedelta
            import re
            
            # Extract number and unit
            match = re.search(r'(\d+)\s+(day|week|month)s?\s+ago', date_string.lower())
            if not match:
                return None
            
            number = int(match.group(1))
            unit = match.group(2)
            
            if unit == 'day':
                return datetime.now() - timedelta(days=number)
            elif unit == 'week':
                return datetime.now() - timedelta(weeks=number)
            elif unit == 'month':
                return datetime.now() - timedelta(days=number * 30)  # Approximate
            
            return None
            
        except Exception as e:
            print(f"Error parsing relative date: {e}")
            return None
import requests
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

class KrogerReviewAnalyzer:
    def __init__(self, use_selenium=True, headless=True):
        self.use_selenium = use_selenium
        self.headless = headless
        self.session = None
        self.driver = None
        
        # Enhanced user agents pool
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
        ]
        
        if use_selenium:
            success = self._setup_selenium_advanced()
            if not success:
                print("Selenium setup failed, falling back to requests-only mode")
                self.use_selenium = False
                self._setup_requests_advanced()
        else:
            self._setup_requests_advanced()
    
    def _setup_selenium_advanced(self):
        """Advanced Selenium setup with better bot evasion"""
        try:
            print("Setting up advanced Selenium WebDriver with bot evasion...")
            
            chrome_options = Options()
            
            # Basic Docker options
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            
            # Advanced bot evasion options
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--exclude-switches=enable-automation')
            chrome_options.add_argument('--useragent-override=false')
            chrome_options.add_argument('--disable-extensions-file-access-check')
            chrome_options.add_argument('--disable-extensions-http-throttling')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            
            # Randomize window size
            window_sizes = ['1366,768', '1920,1080', '1440,900', '1536,864', '1280,720']
            chrome_options.add_argument(f'--window-size={random.choice(window_sizes)}')
            
            # Random user agent
            chrome_options.add_argument(f'--user-agent={random.choice(self.user_agents)}')
            
            # Additional stealth options
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Prefs to make it more human-like
            prefs = {
                "profile.default_content_setting_values": {
                    "notifications": 2,
                    "popups": 2,
                    "geolocation": 2,
                    "media_stream": 2,
                },
                "profile.managed_default_content_settings": {
                    "images": 1  # Allow images for more realistic browsing
                }
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Set Chrome binary location
            chrome_options.binary_location = "/usr/bin/google-chrome"
            
            # Create service
            service = Service(executable_path="/usr/local/bin/chromedriver")
            
            # Initialize driver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to hide webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set timeouts
            self.driver.set_page_load_timeout(60)
            self.driver.implicitly_wait(15)
            
            print("✅ Advanced Selenium WebDriver initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ Advanced Selenium setup failed: {e}")
            return False
    
    def _setup_requests_advanced(self):
        """Advanced requests session with better headers and rotation"""
        print("Setting up advanced requests session...")
        self.session = requests.Session()
        
        # Rotate user agent
        user_agent = random.choice(self.user_agents)
        
        # Comprehensive headers that mimic real browser
        headers = {
            'User-Agent': user_agent,
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
            'Sec-CH-UA-Platform': '"Linux"'
        }
        
        self.session.headers.update(headers)
        self.session.timeout = 30
        print(f"✅ Advanced requests session initialized with UA: {user_agent[:50]}...")
    
    def __del__(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def _human_like_delay(self, min_delay=1, max_delay=3):
        """Add random human-like delays"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def search_products(self, category, max_products=10):
        """Enhanced product search with multiple fallback strategies"""
        print(f"🔍 Searching for products: {category}")
        
        # Try multiple search strategies
        search_strategies = [
            self._search_strategy_main,
            self._search_strategy_api_style,
            self._search_strategy_mobile,
            self._search_strategy_categories
        ]
        
        start_time = time.time()
        max_search_time = 300  # 5 minutes
        
        for i, strategy in enumerate(search_strategies):
            if time.time() - start_time > max_search_time:
                print("❌ Search timed out")
                break
                
            print(f"Trying search strategy {i+1}/{len(search_strategies)}...")
            
            try:
                products = strategy(category, max_products, start_time, max_search_time)
                if products:
                    print(f"✅ Strategy {i+1} found {len(products)} products")
                    return products
                else:
                    print(f"Strategy {i+1} found no products, trying next...")
                    self._human_like_delay(2, 4)  # Wait between strategies
                    
            except Exception as e:
                print(f"Strategy {i+1} failed: {e}")
                continue
        
        print("❌ All search strategies failed")
        return []
    
    def _search_strategy_main(self, category, max_products, start_time, max_time):
        """Main Kroger search strategy"""
        search_url = f"https://www.kroger.com/search?query={quote_plus(category)}"
        
        if self.use_selenium:
            return self._search_with_selenium_advanced(search_url, max_products, start_time, max_time)
        else:
            return self._search_with_requests_advanced(search_url, max_products, start_time, max_time)
    
    def _search_strategy_api_style(self, category, max_products, start_time, max_time):
        """Try to mimic API-style requests"""
        # This would be where we could integrate with Kroger's official API
        # For now, return empty to continue with other strategies
        print("API-style search not implemented yet")
        return []
    
    def _search_strategy_mobile(self, category, max_products, start_time, max_time):
        """Try mobile version of the site"""
        search_url = f"https://m.kroger.com/search?query={quote_plus(category)}"
        
        if self.use_selenium:
            # Temporarily switch to mobile user agent
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
            })
            
            result = self._search_with_selenium_advanced(search_url, max_products, start_time, max_time)
            
            # Switch back
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": random.choice(self.user_agents)
            })
            
            return result
        else:
            # Update session headers for mobile
            mobile_headers = self.session.headers.copy()
            mobile_headers['User-Agent'] = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
            
            return self._search_with_requests_advanced(search_url, max_products, start_time, max_time, mobile_headers)
    
    def _search_strategy_categories(self, category, max_products, start_time, max_time):
        """Try browsing categories instead of search"""
        # Map common categories to Kroger category URLs
        category_urls = {
            'cookies': 'https://www.kroger.com/d/snacks/cookies-crackers/cookies',
            'bread': 'https://www.kroger.com/d/bakery/fresh-bread',
            'milk': 'https://www.kroger.com/d/dairy/milk',
            'cheese': 'https://www.kroger.com/d/dairy/cheese',
            'apples': 'https://www.kroger.com/d/fresh-fruits/apples',
            'chicken': 'https://www.kroger.com/d/meat/chicken',
            'cereal': 'https://www.kroger.com/d/breakfast/cereal'
        }
        
        category_lower = category.lower()
        category_url = None
        
        # Find matching category
        for key, url in category_urls.items():
            if key in category_lower or category_lower in key:
                category_url = url
                break
        
        if not category_url:
            print(f"No category URL found for '{category}'")
            return []
        
        print(f"Trying category URL: {category_url}")
        
        if self.use_selenium:
            return self._search_with_selenium_advanced(category_url, max_products, start_time, max_time)
        else:
            return self._search_with_requests_advanced(category_url, max_products, start_time, max_time)
    
    def _search_with_selenium_advanced(self, search_url, max_products, start_time, max_time):
        """Enhanced Selenium search with better bot evasion"""
        try:
            print(f"Loading page with advanced Selenium: {search_url}")
            
            if time.time() - start_time > max_time:
                return []
            
            # Navigate to page
            self.driver.get(search_url)
            
            # Human-like behavior: scroll a bit, wait
            self._simulate_human_behavior()
            
            # Wait for page to load
            self._human_like_delay(3, 6)
            
            # Check for CAPTCHA or blocking
            if self._check_for_blocking():
                print("❌ Page appears to be blocked or has CAPTCHA")
                return []
            
            print(f"✅ Page loaded. Title: {self.driver.title[:50]}...")
            
            # Try multiple product selectors
            product_selectors = [
                # Primary selectors
                'a[href*="/p/"]',
                '[data-testid*="product"] a',
                '.ProductCard a',
                '.product-card a',
                
                # Secondary selectors
                'a[href*="product"]',
                '.product-item a',
                '[class*="Product"] a',
                '[data-qa*="product"] a',
                
                # Fallback selectors
                'a[href*="/item/"]',
                'a[data-track*="product"]',
                '.item-card a',
                'div[data-testid*="product"] a'
            ]
            
            product_links = []
            seen_urls = set()
            
            for selector in product_selectors:
                if time.time() - start_time > max_time:
                    break
                
                try:
                    # Scroll to load more content
                    self._smart_scroll()
                    
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    print(f"Selector '{selector}' found {len(elements)} elements")
                    
                    if not elements:
                        continue
                    
                    for element in elements[:max_products * 3]:
                        try:
                            href = element.get_attribute('href')
                            if not href or href in seen_urls:
                                continue
                            
                            # Enhanced URL validation
                            if not self._is_valid_product_url(href):
                                continue
                            
                            # Get product name
                            product_name = self._extract_product_name_advanced(element)
                            if not product_name or not self._is_valid_product_name(product_name):
                                continue
                            
                            full_url = href if href.startswith('http') else f"https://www.kroger.com{href}"
                            
                            product_links.append({
                                'name': product_name,
                                'url': full_url
                            })
                            seen_urls.add(href)
                            print(f"✅ Found product: {product_name}")
                            
                            if len(product_links) >= max_products:
                                break
                                
                        except Exception as e:
                            continue
                    
                    # If we found products with this selector, use them
                    if product_links:
                        break
                        
                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue
            
            return self._deduplicate_products(product_links)
            
        except Exception as e:
            print(f"❌ Advanced Selenium search failed: {e}")
            return []
    
    def _simulate_human_behavior(self):
        """Simulate human-like behavior on the page"""
        try:
            # Random scroll down
            scroll_height = random.randint(200, 800)
            self.driver.execute_script(f"window.scrollTo(0, {scroll_height});")
            self._human_like_delay(1, 2)
            
            # Maybe scroll back up a bit
            if random.random() > 0.5:
                scroll_back = random.randint(50, 200)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_height - scroll_back});")
                self._human_like_delay(0.5, 1)
                
            # Occasionally move mouse (simulate with action chains)
            if random.random() > 0.7:
                try:
                    action_chains = ActionChains(self.driver)
                    x = random.randint(100, 500)
                    y = random.randint(100, 400)
                    action_chains.move_by_offset(x, y).perform()
                except:
                    pass
            
        except Exception as e:
            pass  # Ignore errors in behavior simulation
    
    def _check_for_blocking(self):
        """Check if the page is blocked or has CAPTCHA"""
        try:
            page_source = self.driver.page_source.lower()
            
            # Common blocking indicators
            blocking_indicators = [
                'access denied',
                'blocked',
                'captcha',
                'cloudflare',
                'security check',
                'robot',
                'automated',
                'ray id'
            ]
            
            for indicator in blocking_indicators:
                if indicator in page_source:
                    return True
            
            # Check if page is mostly empty (another sign of blocking)
            if len(page_source) < 1000:
                return True
            
            return False
            
        except Exception as e:
            return False
    
    def _smart_scroll(self):
        """Intelligent scrolling to load dynamic content"""
        try:
            # Get initial page height
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Scroll down in chunks
            for i in range(3):
                scroll_position = (i + 1) * (last_height // 4)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                self._human_like_delay(1, 2)
                
                # Check if new content loaded
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height > last_height:
                    last_height = new_height
                    break
            
        except Exception as e:
            pass
    
    def _is_valid_product_url(self, url):
        """Enhanced URL validation"""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Must contain product indicators
        valid_patterns = ['/p/', 'product', '/item/', '/sku/']
        if not any(pattern in url_lower for pattern in valid_patterns):
            return False
        
        # Should not contain navigation patterns
        invalid_patterns = [
            'search', 'category', 'department', 'help', 'account',
            'login', 'register', 'cart', 'checkout', 'store',
            'location', 'recipe', 'coupon', 'deals'
        ]
        
        for pattern in invalid_patterns:
            if pattern in url_lower:
                return False
        
        return True
    
    def _extract_product_name_advanced(self, element):
        """Advanced product name extraction with multiple strategies"""
        try:
            # Multiple strategies in order of preference
            name_strategies = [
                # ARIA labels (most reliable)
                lambda e: e.get_attribute('aria-label'),
                lambda e: e.get_attribute('title'),
                
                # Text content from specific elements
                lambda e: self._find_text_in_element(e, '[data-testid*="product-title"]'),
                lambda e: self._find_text_in_element(e, '.product-title'),
                lambda e: self._find_text_in_element(e, 'h1, h2, h3, h4'),
                lambda e: self._find_text_in_element(e, '.title'),
                lambda e: self._find_text_in_element(e, '[class*="title"]'),
                
                # Image alt text
                lambda e: self._find_image_alt(e),
                
                # Element text as fallback
                lambda e: e.text.strip()
            ]
            
            for strategy in name_strategies:
                try:
                    name = strategy(element)
                    if name and len(name.strip()) > 3:
                        # Clean up the name
                        clean_name = re.sub(r'\s+', ' ', name.strip())
                        clean_name = re.sub(r'[^\w\s\-\.,&]', '', clean_name)
                        
                        if self._is_meaningful_product_name(clean_name):
                            return clean_name
                except:
                    continue
            
            return ""
            
        except Exception as e:
            return ""
    
    def _find_text_in_element(self, element, selector):
        """Find text within an element using a CSS selector"""
        try:
            sub_element = element.find_element(By.CSS_SELECTOR, selector)
            return sub_element.text.strip()
        except:
            return None
    
    def _find_image_alt(self, element):
        """Find alt text from images within the element"""
        try:
            img_elements = element.find_elements(By.TAG_NAME, 'img')
            for img in img_elements:
                alt_text = img.get_attribute('alt')
                if alt_text and len(alt_text.strip()) > 5:
                    return alt_text.strip()
            return None
        except:
            return None
    
    def _is_meaningful_product_name(self, name):
        """Enhanced product name validation"""
        if not name or len(name) < 3:
            return False
        
        name_lower = name.lower()
        
        # Skip obvious UI elements
        skip_terms = [
            'search', 'filter', 'sort', 'view all', 'see more', 'show more',
            'next', 'previous', 'page', 'results', 'loading', 'add to cart',
            'menu', 'navigation', 'header', 'footer', 'sign in', 'sign up',
            'cart', 'account', 'help', 'contact', 'store', 'location'
        ]
        
        for term in skip_terms:
            if term in name_lower:
                return False
        
        # Must be long enough or contain product-like words
        if len(name) > 20:
            return True
        
        # Look for product indicators
        product_indicators = [
            'oz', 'lb', 'lbs', 'kg', 'gram', 'pack', 'count', 'ct',
            'size', 'flavor', 'brand', 'organic', 'natural', 'fresh',
            'frozen', 'dairy', 'whole', 'low', 'free', 'gluten', 'sugar'
        ]
        
        word_count = len(name.split())
        has_product_indicator = any(indicator in name_lower for indicator in product_indicators)
        
        # Accept if it has product indicators OR is reasonably long
        return has_product_indicator or word_count >= 3
    
    def _search_with_requests_advanced(self, search_url, max_products, start_time, max_time, custom_headers=None):
        """Enhanced requests-based search with better parsing"""
        try:
            print(f"Loading page with advanced requests: {search_url}")
            
            if time.time() - start_time > max_time:
                return []
            
            # Use custom headers if provided
            session = self.session
            if custom_headers:
                session = requests.Session()
                session.headers.update(custom_headers)
                session.timeout = 30
            
            # Add referer for more realistic requests
            headers = {'Referer': 'https://www.kroger.com/'}
            
            response = session.get(search_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            print(f"✅ Got response, status: {response.status_code}, length: {len(response.text)}")
            
            # Check for blocking
            if self._check_response_for_blocking(response):
                print("❌ Response appears to be blocked")
                return []
            
            # Enhanced regex patterns for product extraction
            patterns = [
                # JSON-like data structures
                r'"href":"([^"]*\/p\/[^"]*)"[^}]*"title":"([^"]*)"',
                r'"url":"([^"]*\/p\/[^"]*)"[^}]*"name":"([^"]*)"',
                
                # HTML link patterns
                r'href="([^"]*\/p\/[^"]*)"[^>]*>.*?([^<]+)</a>',
                r'<a[^>]+href="([^"]*\/p\/[^"]*)"[^>]*aria-label="([^"]*)"',
                r'<a[^>]+href="([^"]*product[^"]*)"[^>]*title="([^"]*)"',
                
                # Data attribute patterns
                r'data-href="([^"]*\/p\/[^"]*)"[^>]*>.*?([^<]+)</.*?>',
            ]
            
            product_links = []
            seen_urls = set()
            
            for pattern in patterns:
                if time.time() - start_time > max_time:
                    break
                
                matches = re.findall(pattern, response.text, re.DOTALL | re.IGNORECASE)
                print(f"Pattern found {len(matches)} matches")
                
                for href, name in matches:
                    if href in seen_urls:
                        continue
                    
                    if not self._is_valid_product_url(href):
                        continue
                    
                    # Clean up name
                    clean_name = re.sub(r'<[^>]+>', '', name).strip()
                    clean_name = re.sub(r'\s+', ' ', clean_name)
                    clean_name = re.sub(r'[^\w\s\-\.,&]', '', clean_name)
                    
                    if not self._is_meaningful_product_name(clean_name):
                        continue
                    
                    full_url = urljoin(search_url, href)
                    product_links.append({
                        'name': clean_name,
                        'url': full_url
                    })
                    seen_urls.add(href)
                    print(f"✅ Found product: {clean_name}")
                    
                    if len(product_links) >= max_products:
                        break
                
                if product_links:
                    break
            
            return self._deduplicate_products(product_links)
            
        except Exception as e:
            print(f"❌ Advanced requests search failed: {e}")
            return []
    
    def _check_response_for_blocking(self, response):
        """Check if the response indicates blocking"""
        try:
            content = response.text.lower()
            
            # Check status code
            if response.status_code in [403, 429, 503]:
                return True
            
            # Check content for blocking indicators
            blocking_indicators = [
                'access denied', 'blocked', 'captcha', 'cloudflare',
                'security check', 'robot', 'automated', 'ray id',
                'please enable javascript', 'enable cookies'
            ]
            
            for indicator in blocking_indicators:
                if indicator in content:
                    return True
            
            # Check if content is suspiciously short
            if len(content) < 500:
                return True
            
            return False
            
        except Exception as e:
            return False
    
    def _is_valid_product_name(self, name):
        """Enhanced product name validation"""
        return self._is_meaningful_product_name(name)
    
    def scrape_product_reviews(self, product_url, max_reviews=20):
        """Enhanced review scraping - currently returns mock data due to blocking"""
        try:
            print(f"📝 Attempting to scrape reviews from: {product_url}")
            
            # For now, return mock reviews since Kroger heavily blocks review scraping
            # In a real implementation, this would need to use Kroger's official API
            # or a professional scraping service
            
            mock_reviews = self._generate_mock_reviews(max_reviews)
            
            if mock_reviews:
                print(f"✅ Generated {len(mock_reviews)} mock reviews for testing")
                return mock_reviews
            else:
                print("❌ No reviews available")
                return []
            
        except Exception as e:
            print(f"❌ Review scraping failed: {e}")
            return []
    
    def _generate_mock_reviews(self, max_reviews):
        """Generate realistic mock reviews for testing purposes"""
        review_templates = [
            {"rating": 5, "text": "Great product! Really satisfied with the quality and taste.", "author": "Customer1"},
            {"rating": 4, "text": "Good value for money. Would buy again.", "author": "Customer2"},
            {"rating": 3, "text": "Average product. Nothing special but does the job.", "author": "Customer3"},
            {"rating": 2, "text": "Not what I expected. Quality could be better.", "author": "Customer4"},
            {"rating": 5, "text": "Excellent! Fresh and delicious. Highly recommend.", "author": "Customer5"},
            {"rating": 4, "text": "Pretty good quality. Will purchase again.", "author": "Customer6"},
            {"rating": 1, "text": "Poor quality. Would not recommend.", "author": "Customer7"},
            {"rating": 5, "text": "Perfect for my family. Great taste and value.", "author": "Customer8"},
            {"rating": 4, "text": "Good product overall. Meets expectations.", "author": "Customer9"},
            {"rating": 3, "text": "It's okay. Nothing amazing but serviceable.", "author": "Customer10"}
        ]
        
        # Randomly select reviews
        selected_reviews = random.sample(review_templates, min(max_reviews, len(review_templates)))
        
        # Add timestamps
        for review in selected_reviews:
            review['datetime'] = datetime.now().isoformat()
        
        return selected_reviews
    
    def _deduplicate_products(self, products):
        """Remove duplicate products"""
        seen_names = set()
        unique_products = []
        
        for product in products:
            name_key = re.sub(r'[^\w\s]', '', product['name'].lower()).strip()
            if name_key not in seen_names and len(name_key) > 3:
                seen_names.add(name_key)
                unique_products.append(product)
        
        return unique_products
    
    def _filter_unique_reviews(self, reviews, product, all_collected_reviews):
        """Filter out duplicate reviews"""
        unique_reviews = []
        
        for review in reviews:
            if not review:
                continue
                
            # Create signature
            text = review.get('text', '').strip()
            rating = review.get('rating', 'no_rating')
            
            if text and len(text) > 10:
                signature = f"{rating}_{text[:30].lower()}"
            else:
                signature = f"{rating}_{review.get('author', 'anon')}"
            
            if signature not in all_collected_reviews:
                all_collected_reviews.add(signature)
                unique_reviews.append(review)
        
        return unique_reviews
    
    def analyze_category_by_products(self, category, max_products=10, max_reviews_per_product=20):
        """Main analysis method with enhanced error handling and fallbacks"""
        print(f"🚀 Starting enhanced analysis for '{category}'")
        
        # Search for products with multiple strategies
        products = self.search_products(category, max_products)
        
        if not products:
            # Try alternative search terms
            alternative_terms = self._get_alternative_search_terms(category)
            for alt_term in alternative_terms:
                print(f"Trying alternative search term: '{alt_term}'")
                products = self.search_products(alt_term, max_products)
                if products:
                    break
        
        if not products:
            print("❌ No products found after trying all strategies")
            return None
        
        print(f"✅ Found {len(products)} products")
        
        product_analyses = []
        all_collected_reviews = set()
        
        for i, product in enumerate(products):
            print(f"📊 Processing product {i+1}/{len(products)}: {product['name']}")
            
            try:
                reviews = self.scrape_product_reviews(product['url'], max_reviews_per_product)
                
                if reviews:
                    unique_reviews = self._filter_unique_reviews(reviews, product, all_collected_reviews)
                    
                    if unique_reviews:
                        product_analysis = self.analyze_sentiment(unique_reviews)
                        
                        if product_analysis and "error" not in product_analysis:
                            product_analysis['product_name'] = product['name']
                            product_analysis['product_url'] = product['url']
                            product_analysis['category'] = category
                            product_analyses.append(product_analysis)
                            print(f"✅ Added analysis for {product['name']}")
                        else:
                            print(f"❌ Sentiment analysis failed for {product['name']}")
                    else:
                        print(f"⚠️ No unique reviews for {product['name']}")
                else:
                    print(f"⚠️ No reviews found for {product['name']}")
            
            except Exception as e:
                print(f"❌ Error processing {product['name']}: {e}")
                continue
            
            # Brief pause between products
            self._human_like_delay(0.5, 1.5)
        
        if not product_analyses:
            print("❌ No valid product analyses generated")
            # Return basic structure with products found but no reviews
            return {
                'category': category,
                'summary': {
                    'category': category,
                    'total_products': len(products),
                    'total_reviews': 0,
                    'message': 'Products found but reviews could not be extracted due to website protection'
                },
                'products': [{'product_name': p['name'], 'product_url': p['url']} for p in products],
                'total_products_analyzed': 0
            }
        
        print(f"✅ Analysis complete: {len(product_analyses)} products processed")
        
        # Create summary
        summary_analysis = self._create_category_summary(product_analyses, category)
        
        return {
            'category': category,
            'summary': summary_analysis,
            'products': product_analyses,
            'total_products_analyzed': len(product_analyses)
        }
    
    def _get_alternative_search_terms(self, category):
        """Get alternative search terms for better results"""
        alternatives = {
            'cookies': ['cookie', 'biscuits', 'snack cookies', 'sweet cookies'],
            'bread': ['loaf', 'bakery bread', 'fresh bread', 'sliced bread'],
            'milk': ['dairy milk', 'whole milk', '2% milk', 'skim milk'],
            'cheese': ['dairy cheese', 'sliced cheese', 'block cheese'],
            'apples': ['fresh apples', 'apple fruit', 'red apples', 'green apples'],
            'chicken': ['fresh chicken', 'chicken breast', 'poultry'],
            'cereal': ['breakfast cereal', 'cold cereal', 'morning cereal']
        }
        
        category_lower = category.lower()
        
        # Return alternatives for exact matches
        if category_lower in alternatives:
            return alternatives[category_lower]
        
        # Return alternatives for partial matches
        for key, alts in alternatives.items():
            if key in category_lower or category_lower in key:
                return alts
        
        # Generate simple alternatives
        return [
            f"{category} food",
            f"fresh {category}",
            f"{category} product",
            category.rstrip('s'),  # Remove plural
            f"{category}s" if not category.endswith('s') else category[:-1]  # Toggle plural
        ]
    
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
            
            if not valid_reviews:
                return {
                    'average_rating': avg_rating,
                    'total_reviews': len(reviews),
                    'sentiment_score': (avg_rating - 2.5) / 2.5 if avg_rating > 0 else 0,
                    'sentiment_label': self._get_sentiment_description((avg_rating - 2.5) / 2.5 if avg_rating > 0 else 0),
                    'positive_reviews': rating_count if avg_rating >= 4 else 0,
                    'negative_reviews': rating_count if avg_rating <= 2 else 0,
                    'neutral_reviews': rating_count if 2 < avg_rating < 4 else 0,
                    'themes': ['Rating-only reviews'],
                    'sample_reviews': {'positive': [], 'negative': [], 'neutral': []}
                }
            
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
            print(f"Error extracting themes: {e}")
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
                'most', 'much', 'many', 'some', 'any', 'all', 'not', 'one', 'two',
                'three', 'four', 'five', 'product', 'item', 'thing', 'stuff'
            }
            
            meaningful_words = [word for word in words if word not in stop_words and len(word) > 3]
            
            return meaningful_words
            
        except Exception as e:
            print(f"Error extracting meaningful words: {e}")
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
            
            # Add message if present
            if 'message' in summary:
                summary_data.append(['Note', summary['message']])
            
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
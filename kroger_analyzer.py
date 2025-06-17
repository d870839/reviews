import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import time
import re
from textblob import TextBlob
import pandas as pd
from collections import Counter
import tempfile
import os
from urllib.parse import urljoin, quote_plus
from datetime import datetime, timedelta
import signal

class KrogerReviewAnalyzer:
    def __init__(self, use_selenium=True, headless=True):
        self.use_selenium = use_selenium
        self.headless = headless
        self.session = None
        self.driver = None
        
        if use_selenium:
            success = self._setup_selenium_docker()
            if not success:
                print("Selenium setup failed, falling back to requests-only mode")
                self.use_selenium = False
                self._setup_requests()
        else:
            self._setup_requests()
    
    def _setup_selenium_docker(self):
        """Set up Selenium WebDriver optimized for Docker environment"""
        try:
            print("Setting up Selenium WebDriver for Docker...")
            
            chrome_options = Options()
            
            # Docker-optimized Chrome options
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')  # Speed up loading
            chrome_options.add_argument('--window-size=1280,720')
            chrome_options.add_argument('--single-process')
            chrome_options.add_argument('--no-zygote')
            chrome_options.add_argument('--remote-debugging-port=9222')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            
            # User agent
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Set Chrome binary location (Docker specific)
            chrome_options.binary_location = "/usr/bin/google-chrome"
            
            # Create Chrome service with explicit chromedriver path
            service = Service(executable_path="/usr/local/bin/chromedriver")
            
            # Initialize the driver with timeout handling
            try:
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                
                # Set timeouts
                self.driver.set_page_load_timeout(45)
                self.driver.implicitly_wait(10)
                
                print("✅ Selenium WebDriver initialized successfully in Docker")
                return True
                
            except Exception as e:
                print(f"❌ Chrome driver initialization failed: {e}")
                return False
            
        except Exception as e:
            print(f"❌ Error setting up Selenium in Docker: {e}")
            return False
    
    def _setup_requests(self):
        """Set up requests session as fallback"""
        print("Setting up requests session...")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.timeout = 30
        print("✅ Requests session initialized")
    
    def __del__(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def search_products(self, category, max_products=10):
        """Search for products with simple timeout tracking"""
        search_url = f"https://www.kroger.com/search?query={quote_plus(category)}"
        
        print(f"🔍 Searching for products: {category}")
        print(f"Search URL: {search_url}")
        print(f"Using Selenium: {self.use_selenium}")
        
        start_time = time.time()
        max_search_time = 300  # 5 minutes
        
        try:
            if self.use_selenium:
                result = self._search_with_selenium(search_url, max_products, start_time, max_search_time)
            else:
                result = self._search_with_requests(search_url, max_products, start_time, max_search_time)
            
            return result
            
        except Exception as e:
            print(f"❌ Search failed: {e}")
            # Fallback to requests if Selenium fails
            if self.use_selenium:
                print("Falling back to requests method...")
                self.use_selenium = False
                self._setup_requests()
                return self._search_with_requests(search_url, max_products, start_time, max_search_time)
            else:
                return []
        
    def _get_product_name_safe(self, element):
        """Safely extract product name from element"""
        try:
            # Try different methods to get product name
            name_methods = [
                lambda e: e.get_attribute('aria-label'),
                lambda e: e.get_attribute('title'),
                lambda e: e.text.strip(),
                lambda e: e.find_element(By.TAG_NAME, 'img').get_attribute('alt') if e.find_elements(By.TAG_NAME, 'img') else None
            ]
            
            for method in name_methods:
                try:
                    name = method(element)
                    if name and len(name.strip()) > 3:
                        return name.strip()
                except:
                    continue
            
            return ""
        except:
            return ""
    def _search_with_selenium(self, search_url, max_products, start_time, max_time):
        """Enhanced Selenium search for Docker environment"""
        try:
            print(f"Loading search page with Selenium: {search_url}")
            
            # Check timeout
            if time.time() - start_time > max_time:
                print("❌ Search timed out")
                return []
            
            # Load page
            self.driver.get(search_url)
            print(f"✅ Page loaded. Title: {self.driver.title[:50]}...")
            
            # Wait for content to load
            time.sleep(5)
            
            # Check timeout again
            if time.time() - start_time > max_time:
                print("❌ Search timed out after page load")
                return []
            
            # Enhanced product selectors for Kroger
            product_selectors = [
                'a[href*="/p/"]',
                '[data-testid*="product"] a',
                '.ProductCard a',
                '.product-card a',
                'a[href*="product"]',
                '.product-item a',
                '[class*="Product"] a'
            ]
            
            product_links = []
            seen_urls = set()
            
            for selector in product_selectors:
                # Check timeout in loop
                if time.time() - start_time > max_time:
                    print("❌ Search timed out during product extraction")
                    break
                
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    print(f"Selector '{selector}' found {len(elements)} elements")
                    
                    for element in elements[:max_products * 3]:  # Get extra in case some are invalid
                        try:
                            href = element.get_attribute('href')
                            if not href or href in seen_urls:
                                continue
                            
                            # Enhanced URL validation
                            if not any(pattern in href.lower() for pattern in ['/p/', 'product', '/item/']):
                                continue
                            
                            # Get product name
                            product_name = self._extract_product_name_selenium(element)
                            if not product_name or len(product_name) < 3:
                                continue
                            
                            # Filter out navigation/UI elements
                            if self._is_valid_product_name(product_name):
                                product_links.append({
                                    'name': product_name,
                                    'url': href if href.startswith('http') else f"https://www.kroger.com{href}"
                                })
                                seen_urls.add(href)
                                print(f"✅ Found product: {product_name}")
                                
                                if len(product_links) >= max_products:
                                    break
                                    
                        except Exception as e:
                            continue
                    
                    if product_links:
                        break
                        
                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue
            
            print(f"✅ Found {len(product_links)} products total")
            return self._deduplicate_products(product_links)
            
        except Exception as e:
            print(f"❌ Selenium search failed: {e}")
            return []
    
    def _search_with_requests(self, search_url, max_products, start_time, max_time):
        """Enhanced requests-based search"""
        try:
            print(f"Loading search page with requests: {search_url}")
            
            # Check timeout
            if time.time() - start_time > max_time:
                print("❌ Requests search timed out")
                return []
            
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            
            print(f"✅ Got response, length: {len(response.text)}")
            
            # Enhanced regex patterns for product links
            patterns = [
                r'href="([^"]*\/p\/[^"]*)"[^>]*>([^<]+)',
                r'<a[^>]+href="([^"]*\/p\/[^"]*)"[^>]*>.*?([^<]+)</a>',
                r'href="([^"]*product[^"]*)"[^>]*>([^<]+)'
            ]
            
            product_links = []
            seen_urls = set()
            
            for pattern in patterns:
                # Check timeout
                if time.time() - start_time > max_time:
                    break
                
                matches = re.findall(pattern, response.text, re.DOTALL | re.IGNORECASE)
                print(f"Pattern found {len(matches)} matches")
                
                for href, name in matches:
                    if href in seen_urls:
                        continue
                    
                    clean_name = re.sub(r'<[^>]+>', '', name).strip()
                    if not self._is_valid_product_name(clean_name):
                        continue
                    
                    full_url = urljoin(search_url, href)
                    product_links.append({
                        'name': clean_name,
                        'url': full_url
                    })
                    seen_urls.add(href)
                    
                    if len(product_links) >= max_products:
                        break
                
                if product_links:
                    break
            
            print(f"✅ Found {len(product_links)} products with requests")
            return self._deduplicate_products(product_links)
            
        except Exception as e:
            print(f"❌ Requests search failed: {e}")
            return []
    
    def _extract_product_name(self, element):
        """Enhanced product name extraction"""
        try:
            # Kroger-specific name selectors
            name_selectors = [
                '[data-testid*="product-title"]',
                '[data-testid*="ProductTitle"]',
                '.ProductCard-title',
                '.product-title',
                '.product-name',
                'h2', 'h3', 'h4',
                '.title',
                '[class*="title"]',
                '[aria-label]'  # Sometimes product names are in aria-label
            ]
            
            for selector in name_selectors:
                try:
                    name_element = element.find_element(By.CSS_SELECTOR, selector)
                    name = name_element.text.strip()
                    if name and len(name) > 3:
                        return name
                except:
                    continue
            
            # Try aria-label as fallback
            aria_label = self._get_element_attribute(element, 'aria-label')
            if aria_label and len(aria_label) > 3:
                return aria_label.strip()
            
            # Try element text as last resort
            name = element.text.strip()
            if name and len(name) > 3:
                return name
            
            return ""
            
        except Exception as e:
            return ""

    def _is_meaningful_product_name(self, name):
        """Check if product name is meaningful"""
        if not name or len(name) < 3:
            return False
        
        name_lower = name.lower()
        
        # Skip common UI elements
        skip_terms = [
            'search', 'filter', 'sort', 'view all', 'see more',
            'next', 'previous', 'page', 'results', 'loading',
            'menu', 'navigation', 'header', 'footer', 'sign in',
            'cart', 'account', 'help', 'contact'
        ]
        
        for term in skip_terms:
            if term in name_lower:
                return False
        
        # Must be long enough or contain product indicators
        if len(name) > 15:
            return True
            
        product_indicators = [
            'oz', 'lb', 'pack', 'count', 'size', 'flavor',
            'brand', 'organic', 'natural', 'fresh', 'frozen'
        ]
        
        return any(indicator in name_lower for indicator in product_indicators)
    
    def _is_valid_product_name(self, name):
        """Enhanced product name validation"""
        if not name or len(name.strip()) < 3:
            return False
        
        name_lower = name.lower()
        
        # Skip common navigation elements
        skip_terms = [
            'search', 'filter', 'sort', 'view all', 'see more',
            'next', 'previous', 'page', 'results', 'loading',
            'menu', 'navigation', 'header', 'footer'
        ]
        
        for term in skip_terms:
            if term in name_lower:
                return False
        
        # Must contain some product-like words or be long enough
        if len(name) > 15:
            return True
        
        product_indicators = [
            'oz', 'lb', 'pack', 'count', 'size', 'flavor',
            'brand', 'organic', 'natural', 'fresh'
        ]
        
        return any(indicator in name_lower for indicator in product_indicators)


    def _extract_product_name_selenium(self, element):
        """Enhanced product name extraction for Selenium"""
        try:
            # Multiple strategies to get product name
            name_strategies = [
                lambda e: e.get_attribute('aria-label'),
                lambda e: e.get_attribute('title'),
                lambda e: e.find_element(By.CSS_SELECTOR, '[data-testid*="product-title"], .product-title, h2, h3, h4').text.strip(),
                lambda e: e.find_element(By.TAG_NAME, 'img').get_attribute('alt') if e.find_elements(By.TAG_NAME, 'img') else None,
                lambda e: e.text.strip()
            ]
            
            for strategy in name_strategies:
                try:
                    name = strategy(element)
                    if name and len(name.strip()) > 3:
                        # Clean up the name
                        clean_name = re.sub(r'\s+', ' ', name.strip())
                        if self._is_meaningful_product_name(clean_name):
                            return clean_name
                except:
                    continue
            
            return ""
            
        except Exception as e:
            return ""

    def _extract_simple_review_data(self, element):
        """Extract basic review data"""
        try:
            review_data = {}
            
            # Try to extract rating
            rating_text = element.text
            rating_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:star|out)', rating_text, re.IGNORECASE)
            if rating_match:
                review_data['rating'] = float(rating_match.group(1))
            
            # Try to extract text
            text = element.text.strip()
            if len(text) > 10:
                review_data['text'] = text
            
            # Add timestamp
            review_data['datetime'] = datetime.now().isoformat()
            
            return review_data if review_data else None
            
        except:
            return None
    def scrape_product_reviews(self, product_url, max_reviews=20):
        """Enhanced review scraping for Docker environment"""
        try:
            print(f"📝 Scraping reviews from: {product_url}")
            
            start_time = time.time()
            max_review_time = 120  # 2 minutes per product
            
            if self.use_selenium:
                reviews = self._scrape_reviews_selenium_docker(product_url, max_reviews, start_time, max_review_time)
            else:
                reviews = self._scrape_reviews_requests(product_url, max_reviews)
            
            # If no reviews found and using Selenium, try requests
            if not reviews and self.use_selenium:
                print("No reviews found with Selenium, trying requests...")
                reviews = self._scrape_reviews_requests(product_url, max_reviews)
            
            return reviews
            
        except Exception as e:
            print(f"❌ Review scraping failed: {e}")
            return []
        
    def _scrape_reviews_selenium(self, product_url, max_reviews):
        """Selenium review scraping with enhanced error handling"""
        try:
            self.driver.get(product_url)
            time.sleep(2)  # Reduced wait time
            
            # Simple review detection
            review_selectors = [
                '[class*="review"]',
                '[data-testid*="review"]',
                '.customer-review',
                '.user-review'
            ]
            
            reviews = []
            for selector in review_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements[:max_reviews]:
                    review_data = self._extract_simple_review_data(element)
                    if review_data:
                        reviews.append(review_data)
                
                if reviews:
                    break
            
            return reviews
            
        except Exception as e:
            print(f"Selenium review scraping failed: {e}")
            return []
            
        except Exception as e:
            print(f"Error scraping reviews from {product_url}: {e}")
            return []
    
    def _scrape_reviews_selenium_docker(self, product_url, max_reviews, start_time, max_time):
        """Docker-optimized Selenium review scraping"""
        try:
            # Check timeout
            if time.time() - start_time > max_time:
                print("❌ Review scraping timed out before starting")
                return []
            
            self.driver.get(product_url)
            time.sleep(3)
            
            # Enhanced review selectors for Kroger
            review_selectors = [
                '[data-testid*="review"]',
                '[data-testid*="Review"]',
                '.review-item',
                '.review-card',
                '.customer-review',
                '.user-review',
                '[class*="review"]',
                '[id*="review"]',
                '[data-qa*="review"]',
                '.review-content',
                '.ReviewItem'
            ]
            
            reviews = []
            
            for selector in review_selectors:
                # Check timeout in loop
                if time.time() - start_time > max_time:
                    print("❌ Review scraping timed out")
                    break
                
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"Selector '{selector}' found {len(elements)} elements")
                
                for element in elements[:max_reviews]:
                    review_data = self._extract_review_data_docker(element)
                    if review_data and self._is_valid_review_data(review_data):
                        reviews.append(review_data)
                        print(f"✅ Extracted review: {review_data.get('rating', 'N/A')} stars")
                
                if reviews:
                    break
            
            return reviews
            
        except Exception as e:
            print(f"❌ Selenium review scraping failed: {e}")
            return []

    def _scrape_reviews_requests(self, product_url, max_reviews):
        """Fallback requests-based review scraping"""
        try:
            response = self.session.get(product_url, timeout=30)
            response.raise_for_status()
            
            # For now, return empty list - can be enhanced later
            return []
            
        except Exception as e:
            print(f"Requests review scraping failed: {e}")
            return []
    
    def _parse_review_match(self, match):
        """Parse review data from regex match"""
        try:
            review_data = {}
            
            if isinstance(match, tuple):
                # Handle tuple matches
                for item in match:
                    if item and item.strip():
                        # Try to extract rating
                        rating_match = re.search(r'(\d+(?:\.\d+)?)', item)
                        if rating_match and not review_data.get('rating'):
                            potential_rating = float(rating_match.group(1))
                            if 1 <= potential_rating <= 5:
                                review_data['rating'] = potential_rating
                        
                        # Try to extract text (longer strings are likely review text)
                        clean_text = re.sub(r'<[^>]+>', '', item).strip()
                        if len(clean_text) > 10 and not review_data.get('text'):
                            review_data['text'] = clean_text
            else:
                # Handle single string match
                clean_text = re.sub(r'<[^>]+>', '', match).strip()
                if clean_text:
                    # Extract rating
                    rating_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:star|out of|/)', clean_text)
                    if rating_match:
                        review_data['rating'] = float(rating_match.group(1))
                    
                    # Extract review text (look for longer sentences)
                    sentences = re.split(r'[.!?]+', clean_text)
                    for sentence in sentences:
                        if len(sentence.strip()) > 15 and not sentence.strip().isdigit():
                            review_data['text'] = sentence.strip()
                            break
            
            return review_data if review_data else None
            
        except Exception as e:
            print(f"Error parsing review match: {e}")
            return None
        
    def _extract_review_data_docker(self, element):
        """Extract review data optimized for Docker environment"""
        try:
            review_data = {}
            
            # Extract rating
            rating = self._extract_rating_docker(element)
            if rating:
                review_data['rating'] = rating
            
            # Extract review text
            review_text = self._extract_review_text_docker(element)
            if review_text:
                review_data['text'] = review_text
            
            # Extract author
            author = self._extract_author_docker(element)
            if author:
                review_data['author'] = author
            
            # Add timestamp
            review_data['datetime'] = datetime.now().isoformat()
            
            return review_data if review_data else None
                
        except Exception as e:
            return None
    
    def _extract_rating_docker(self, element):
        """Extract rating from review element"""
        try:
            # Enhanced rating selectors
            rating_selectors = [
                '[data-testid*="rating"]',
                '[data-testid*="star"]',
                '.rating',
                '.stars',
                '[class*="rating"]',
                '[class*="star"]',
                '[aria-label*="star"]',
                '[aria-label*="rating"]'
            ]
            
            for selector in rating_selectors:
                try:
                    rating_elements = element.find_elements(By.CSS_SELECTOR, selector)
                    for rating_element in rating_elements:
                        
                        # Try aria-label first
                        aria_label = rating_element.get_attribute('aria-label') or ''
                        rating_match = re.search(r'(\d+(?:\.\d+)?)', aria_label)
                        if rating_match:
                            rating = float(rating_match.group(1))
                            if 1 <= rating <= 5:
                                return rating
                        
                        # Try element text
                        rating_text = rating_element.text.strip()
                        rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
                        if rating_match:
                            rating = float(rating_match.group(1))
                            if 1 <= rating <= 5:
                                return rating
                                
                except:
                    continue
            
            return None
            
        except Exception as e:
            return None
    
    def _extract_review_text_docker(self, element):
        """Extract review text from element"""
        try:
            # Enhanced text selectors
            text_selectors = [
                '[data-testid*="review-text"]',
                '[data-testid*="review-body"]',
                '.review-text',
                '.review-body',
                '.review-content',
                'p[class*="review"]',
                '.user-content'
            ]
            
            for selector in text_selectors:
                try:
                    text_elements = element.find_elements(By.CSS_SELECTOR, selector)
                    for text_element in text_elements:
                        text = text_element.text.strip()
                        
                        if self._is_valid_review_text(text):
                            return text
                        
                except:
                    continue
            
            # Try element text as fallback
            element_text = element.text.strip()
            if self._is_valid_review_text(element_text):
                return element_text
            
            return None
            
        except Exception as e:
            return None
    
    def _extract_author_docker(self, element):
        """Extract author from review element"""
        try:
            author_selectors = [
                '[data-testid*="author"]',
                '.review-author',
                '.author',
                '.reviewer',
                '.customer-name'
            ]
            
            for selector in author_selectors:
                try:
                    author_element = element.find_element(By.CSS_SELECTOR, selector)
                    author = author_element.text.strip()
                    if author and len(author) > 1:
                        return author
                except:
                    continue
            
            return None
            
        except Exception as e:
            return None
        
    def _extract_review_data_selenium(self, element):
        """Enhanced review data extraction with better text filtering"""
        try:
            review_data = {}
            
            # Extract rating with enhanced selectors
            rating = self._extract_rating_enhanced(element)
            if rating:
                review_data['rating'] = rating
            
            # Extract review text with enhanced filtering
            review_text = self._extract_review_text_enhanced(element)
            if review_text:
                review_data['text'] = review_text
            
            # Extract author
            author = self._extract_author_enhanced(element)
            if author:
                review_data['author'] = author
            
            return review_data if review_data else None
                
        except Exception as e:
            print(f"Error extracting review data: {e}")
            return None
    
    def _extract_rating_enhanced(self, element):
        """Enhanced rating extraction"""
        try:
            # Enhanced rating selectors
            rating_selectors = [
                '[data-testid*="rating"]',
                '[data-testid*="star"]',
                '.rating',
                '.stars',
                '[class*="rating"]',
                '[class*="star"]',
                '[aria-label*="star"]',
                '[aria-label*="rating"]',
                '.score',
                '[class*="score"]'
            ]
            
            for selector in rating_selectors:
                try:
                    rating_elements = element.find_elements(By.CSS_SELECTOR, selector)
                    for rating_element in rating_elements:
                        
                        # Try aria-label first
                        aria_label = rating_element.get_attribute('aria-label') or ''
                        rating_match = re.search(r'(\d+(?:\.\d+)?)', aria_label)
                        if rating_match:
                            rating = float(rating_match.group(1))
                            if 1 <= rating <= 5:
                                return rating
                        
                        # Try element text
                        rating_text = rating_element.text.strip()
                        rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
                        if rating_match:
                            rating = float(rating_match.group(1))
                            if 1 <= rating <= 5:
                                return rating
                                
                except:
                    continue
            
            # Try to find rating in parent element text
            element_text = element.text or ''
            rating_patterns = [
                r'(\d+(?:\.\d+)?)\s*(?:star|out of 5|/5)',
                r'rating:\s*(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*stars?'
            ]
            
            for pattern in rating_patterns:
                rating_match = re.search(pattern, element_text, re.IGNORECASE)
                if rating_match:
                    rating = float(rating_match.group(1))
                    if 1 <= rating <= 5:
                        return rating
            
            return None
            
        except Exception as e:
            return None
    
    def _extract_review_text_enhanced(self, element):
        """Enhanced review text extraction with better filtering"""
        try:
            # Enhanced text selectors
            text_selectors = [
                '[data-testid*="review-text"]',
                '[data-testid*="review-body"]',
                '[data-testid*="review-content"]',
                '.review-text',
                '.review-body',
                '.review-content',
                '.comment',
                '.feedback',
                'p[class*="review"]',
                'div[class*="review-text"]',
                'span[class*="review"]',
                '.user-content',
                '.customer-feedback'
            ]
            
            for selector in text_selectors:
                try:
                    text_elements = element.find_elements(By.CSS_SELECTOR, selector)
                    for text_element in text_elements:
                        text = text_element.text.strip()
                        
                        if self._is_valid_review_text_enhanced(text):
                            return text
                        
                except:
                    continue
            
            # Try child elements
            child_selectors = ['p', 'div', 'span']
            for child_selector in child_selectors:
                try:
                    child_elements = element.find_elements(By.TAG_NAME, child_selector)
                    for child in child_elements:
                        text = child.text.strip()
                        if self._is_valid_review_text_enhanced(text):
                            return text
                except:
                    continue
            
            # Last resort: try element text but with strict filtering
            element_text = element.text.strip()
            if element_text:
                # Split by lines and find the longest meaningful line
                lines = [line.strip() for line in element_text.split('\n') if line.strip()]
                
                for line in lines:
                    if self._is_valid_review_text_enhanced(line):
                        return line
            
            return None
            
        except Exception as e:
            return None
    
    def _is_valid_review_text_enhanced(self, text):
        """Enhanced validation for review text"""
        if not text or len(text) < 10:
            return False
        
        text_lower = text.lower().strip()
        
        # Enhanced junk patterns
        junk_patterns = [
            'kroger is not responsible',
            'terms and conditions',
            'customer ratings and reviews',
            'average customer rating',
            'how customer ratings',
            'reviews work',
            'write a review',
            'helpful',
            'not helpful',
            'report',
            'see all reviews',
            'sort by',
            'filter by',
            'verified purchase',
            'review guidelines',
            'community guidelines',
            'was this helpful',
            'yes no',
            'thumb up',
            'thumb down'
        ]
        
        # Check for junk patterns
        for pattern in junk_patterns:
            if pattern in text_lower:
                return False
        
        # Check if it's just numbers or dates
        if re.match(r'^[\d\s\-\/\.]+$', text):
            return False
        
        # Check for review-like content
        review_indicators = [
            'good', 'bad', 'great', 'terrible', 'amazing', 'awful',
            'love', 'hate', 'like', 'dislike', 'recommend', 'avoid',
            'delicious', 'tasty', 'flavor', 'taste', 'quality',
            'fresh', 'stale', 'crispy', 'soft', 'sweet', 'bitter',
            'bought', 'purchase', 'family', 'kids', 'enjoyed',
            'disappointed', 'satisfied', 'perfect', 'excellent',
            'price', 'value', 'expensive', 'cheap', 'worth',
            'favorite', 'best', 'worst'
        ]
        
        # Count review indicators
        indicator_count = sum(1 for indicator in review_indicators if indicator in text_lower)
        
        # Must have at least one review indicator for shorter texts
        if len(text) < 30 and indicator_count == 0:
            return False
        
        # Check for sentence structure
        has_sentence_structure = any(punct in text for punct in ['.', '!', '?'])
        
        return has_sentence_structure or indicator_count >= 2
    
    def _extract_author_enhanced(self, element):
        """Enhanced author extraction"""
        try:
            author_selectors = [
                '[data-testid*="author"]',
                '[data-testid*="reviewer"]',
                '.review-author',
                '.author',
                '.reviewer',
                '.customer-name',
                '.user-name',
                '[class*="author"]',
                '[class*="reviewer"]'
            ]
            
            for selector in author_selectors:
                try:
                    author_element = element.find_element(By.CSS_SELECTOR, selector)
                    author = author_element.text.strip()
                    if author and not self._is_junk_author(author):
                        return author
                except:
                    continue
            
            return None
            
        except Exception as e:
            return None
    
    def _is_valid_review_text(self, text):
        """Validate review text"""
        if not text or len(text) < 10:
            return False
        
        # Check for meaningful content
        meaningful_words = ['good', 'bad', 'great', 'love', 'hate', 'recommend', 'quality', 'taste', 'delicious']
        return any(word in text.lower() for word in meaningful_words)
    
    def _is_valid_review_data(self, review_data):
        """Validate complete review data"""
        if not review_data:
            return False
        
        has_rating = review_data.get('rating') is not None
        has_text = review_data.get('text') and len(review_data.get('text', '')) > 5
        
        return has_rating or has_text
    
    def _find_elements_safely(self, selector):
        """Safely find elements without throwing exceptions"""
        try:
            return self.driver.find_elements(By.CSS_SELECTOR, selector)
        except:
            return []
    
    def _get_element_attribute(self, element, attribute):
        """Safely get element attribute"""
        try:
            return element.get_attribute(attribute)
        except:
            return None
    
    def _is_valid_product_name(self, name):
        """Enhanced product name validation"""
        if not name or len(name.strip()) < 3:
            return False
        
        name_lower = name.lower()
        
        # Skip common navigation elements
        skip_terms = [
            'search', 'filter', 'sort', 'view all', 'see more',
            'next', 'previous', 'page', 'results', 'loading',
            'menu', 'navigation', 'header', 'footer'
        ]
        
        for term in skip_terms:
            if term in name_lower:
                return False
        
        # Must contain some product-like words
        product_indicators = [
            'oz', 'lb', 'pack', 'count', 'size', 'flavor',
            'brand', 'organic', 'natural', 'fresh'
        ]
        
        # If it's longer, it's probably a product name
        if len(name) > 15:
            return True
        
        # For shorter names, check for product indicators
        return any(indicator in name_lower for indicator in product_indicators)
    
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
    
    def _is_junk_author(self, author):
        """Check if author name is junk"""
        if not author:
            return True
            
        author_lower = author.lower()
        junk_terms = [
            'anonymous', 'guest', 'verified', 'customer',
            'review', 'rating', 'star', 'helpful', 'user'
        ]
        
        return any(term in author_lower for term in junk_terms)
    
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
        """Main analysis method optimized for Docker"""
        print(f"🚀 Starting Docker-optimized analysis for '{category}'")
        
        products = self.search_products(category, max_products)
        
        if not products:
            print("❌ No products found")
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
            
            except Exception as e:
                print(f"❌ Error processing {product['name']}: {e}")
                continue
            
            # Brief pause between products
            time.sleep(0.5)
        
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
            'total_products_analyzed': len(product_analyses)
        }
    
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
                    'sentiment_score': (avg_rating - 2.5) / 2.5,
                    'sentiment_label': self._get_sentiment_description((avg_rating - 2.5) / 2.5),
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
    # Enhanced review extraction methods to add to your kroger_analyzer.py

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
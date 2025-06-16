import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import re
from textblob import TextBlob
import pandas as pd
from collections import Counter
import tempfile
import os
from urllib.parse import urljoin, quote_plus
import webdriver_manager.chrome as chrome_manager

class KrogerReviewAnalyzer:
    def __init__(self, use_selenium=True, headless=True):
        self.use_selenium = use_selenium
        self.headless = headless
        self.session = None
        self.driver = None
        
        if use_selenium:
            self._setup_selenium()
        else:
            self._setup_requests()
    
    def _setup_selenium(self):
        """Set up Selenium WebDriver with Chrome"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                print("Selenium WebDriver initialized successfully")
                return
            except Exception as e:
                print(f"Chrome setup failed: {e}")
                chrome_manager.ChromeDriverManager().install()
                self.driver = webdriver.Chrome(options=chrome_options)
                print("Selenium WebDriver initialized with downloaded chromedriver")
            
        except Exception as e:
            print(f"Error setting up Selenium: {e}")
            self.use_selenium = False
            self._setup_requests()
    
    def _setup_requests(self):
        """Set up requests session"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def __del__(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def search_products(self, category, max_products=10):
        """Search for products in a category"""
        search_url = f"https://www.kroger.com/search?query={quote_plus(category)}"
        
        if self.use_selenium:
            return self._search_with_selenium(search_url, max_products)
        else:
            return self._search_with_requests(search_url, max_products)
    
    def _search_with_selenium(self, search_url, max_products):
        """Search using Selenium with improved product detection"""
        try:
            print(f"Loading search page: {search_url}")
            self.driver.get(search_url)
            time.sleep(5)
            
            print(f"Page loaded. Title: {self.driver.title}")
            print(f"Current URL: {self.driver.current_url}")
            
            # Enhanced product selectors for Kroger
            product_selectors = [
                # Kroger-specific selectors
                'a[data-testid*="product"]',
                'a[href*="/p/"]',
                '[data-testid="ProductCard"] a',
                '.ProductCard a',
                '.product-card a',
                '[class*="ProductCard"] a',
                '[class*="product-card"] a',
                # Generic product selectors
                'a[href*="product"]',
                '.product-item a',
                '[data-qa*="product"] a',
                'a[aria-label*="product"]'
            ]
            
            product_links = []
            seen_urls = set()
            
            for selector in product_selectors:
                elements = self._find_elements_safely(selector)
                print(f"Selector '{selector}' found {len(elements)} elements")
                
                for element in elements:
                    href = self._get_element_attribute(element, 'href')
                    if not href:
                        continue
                        
                    # More flexible URL validation
                    if not any(pattern in href.lower() for pattern in ['/p/', 'product', 'item']):
                        continue
                        
                    if href in seen_urls:
                        continue
                    
                    product_name = self._extract_product_name(element)
                    
                    if self._is_valid_product_name(product_name):
                        product_links.append({
                            'name': product_name,
                            'url': href if href.startswith('http') else f"https://www.kroger.com{href}"
                        })
                        seen_urls.add(href)
                        print(f"Added valid product: {product_name}")
                        
                        if len(product_links) >= max_products:
                            break
                
                if product_links:
                    break
            
            return self._deduplicate_products(product_links)
            
        except Exception as e:
            print(f"Error in Selenium search: {e}")
            return []
    
    def _search_with_requests(self, search_url, max_products):
        """Search using requests with improved regex patterns"""
        try:
            response = self.session.get(search_url)
            response.raise_for_status()
            
            product_links = []
            
            # Improved regex patterns for Kroger product links
            link_patterns = [
                r'href="([^"]*\/p\/[^"]*)"[^>]*(?:data-testid="[^"]*product[^"]*"|class="[^"]*product[^"]*")[^>]*>.*?([^<]+)',
                r'href="([^"]*product[^"]*)"[^>]*>.*?<[^>]*>([^<]+)',
                r'<a[^>]+href="([^"]*\/p\/[^"]*)"[^>]*>([^<]*(?:<[^>]*>[^<]*)*)</a>'
            ]
            
            seen_urls = set()
            for pattern in link_patterns:
                matches = re.findall(pattern, response.text, re.DOTALL | re.IGNORECASE)
                
                for href, name in matches:
                    if href in seen_urls:
                        continue
                    
                    full_url = urljoin(search_url, href)
                    clean_name = re.sub(r'<[^>]+>', '', name).strip()
                    
                    if self._is_valid_product_name(clean_name):
                        product_links.append({
                            'name': clean_name,
                            'url': full_url
                        })
                        seen_urls.add(href)
                        
                        if len(product_links) >= max_products:
                            break
                
                if product_links:
                    break
            
            return self._deduplicate_products(product_links)
            
        except Exception as e:
            print(f"Error in requests search: {e}")
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
    
    def scrape_product_reviews(self, product_url, max_reviews=20):
        """Enhanced review scraping with better pattern matching"""
        if self.use_selenium:
            return self._scrape_reviews_selenium(product_url, max_reviews)
        else:
            return self._scrape_reviews_requests(product_url, max_reviews)
    
    def _scrape_reviews_selenium(self, product_url, max_reviews):
        """Enhanced Selenium review scraping"""
        try:
            print(f"Loading product page: {product_url}")
            self.driver.get(product_url)
            time.sleep(3)
            
            # Try to find and click "Show Reviews" or similar buttons
            review_button_selectors = [
                'button[data-testid*="review"]',
                'button:contains("review")',
                'a[href*="review"]',
                '[data-testid*="show-reviews"]'
            ]
            
            for selector in review_button_selectors:
                try:
                    button = self._find_elements_safely(selector)
                    if button:
                        button[0].click()
                        time.sleep(2)
                        break
                except:
                    continue
            
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
                # Look for review containers
                '[data-qa*="review"]',
                '.review-content',
                '.ReviewItem'
            ]
            
            reviews = []
            
            for selector in review_selectors:
                elements = self._find_elements_safely(selector)
                print(f"Selector '{selector}' found {len(elements)} elements")
                
                for element in elements[:max_reviews]:
                    review_data = self._extract_review_data_selenium(element)
                    if review_data and self._is_valid_review_data(review_data):
                        reviews.append(review_data)
                        print(f"✓ Extracted valid review: Rating={review_data.get('rating', 'N/A')}, Text='{(review_data.get('text', '') or '')[:50]}...'")
                
                if reviews:
                    break
            
            print(f"Final review count: {len(reviews)}")
            return reviews
            
        except Exception as e:
            print(f"Error scraping reviews from {product_url}: {e}")
            return []
    
    def _scrape_reviews_requests(self, product_url, max_reviews):
        """Enhanced requests-based review scraping with better regex"""
        try:
            response = self.session.get(product_url)
            response.raise_for_status()
            
            reviews = []
            
            # Enhanced regex patterns for Kroger reviews
            review_patterns = [
                # Pattern for structured review data
                r'data-testid="[^"]*review[^"]*"[^>]*>.*?(?:rating[^>]*>([^<]+).*?)?(?:text[^>]*>([^<]+).*?)?</[^>]+>',
                # Pattern for review content blocks
                r'class="[^"]*review[^"]*"[^>]*>(.*?)</[^>]+>',
                # Pattern for JSON-LD review data
                r'"@type"\s*:\s*"Review"[^}]*"reviewBody"\s*:\s*"([^"]+)"[^}]*"ratingValue"\s*:\s*(\d+)',
                # Pattern for microdata reviews
                r'itemtype="[^"]*Review[^"]*"[^>]*>(.*?)</[^>]+>',
            ]
            
            for pattern in review_patterns:
                matches = re.findall(pattern, response.text, re.DOTALL | re.IGNORECASE)
                
                for match in matches[:max_reviews]:
                    review_data = self._parse_review_match(match)
                    if review_data and self._is_valid_review_data(review_data):
                        reviews.append(review_data)
                
                if reviews:
                    break
            
            return reviews
            
        except Exception as e:
            print(f"Error scraping reviews from {product_url}: {e}")
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
    
    def _is_valid_review_data(self, review_data):
        """Enhanced validation for complete review data"""
        if not review_data:
            return False
        
        has_rating = review_data.get('rating') is not None
        has_text = review_data.get('text') and len(review_data.get('text', '')) > 5
        
        # Accept if we have either a valid rating or valid text
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
        """Remove duplicate products with enhanced logic"""
        seen_names = set()
        unique_products = []
        
        for product in products:
            # Create a normalized name for comparison
            name_key = re.sub(r'\s+', ' ', product['name'].lower().strip())
            name_key = re.sub(r'[^\w\s]', '', name_key)  # Remove punctuation
            
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
        """Enhanced duplicate filtering"""
        unique_reviews = []
        
        for i, review in enumerate(reviews):
            if not review:
                continue
                
            # Create enhanced signature
            rating = review.get('rating', 'no_rating')
            text = review.get('text', '').strip()
            author = review.get('author', 'anonymous')
            
            # Create signature based on available data
            if text and len(text) > 10:
                # Use first 50 chars of text for signature
                text_signature = re.sub(r'\s+', ' ', text[:50].lower())
                signature = f"{rating}_{text_signature}"
            else:
                # For rating-only reviews
                signature = f"{rating}_{author}_{product['name'][:20]}"
            
            if signature in all_collected_reviews:
                continue
            
            # Enhanced validation
            is_valid = self._is_valid_review_data(review)
            
            if is_valid:
                all_collected_reviews.add(signature)
                unique_reviews.append(review)
        
        return unique_reviews
    
    # Keep all the existing analysis methods unchanged
    def analyze_category_by_products(self, category, max_products=10, max_reviews_per_product=20):
        """Main method to analyze products individually in a category"""
        print(f"Starting analyze_category_by_products for '{category}'")
        products = self.search_products(category, max_products)
        
        print(f"Search returned {len(products) if products else 0} products")
        if products:
            for i, product in enumerate(products):
                print(f"  Product {i+1}: {product['name']} | {product['url']}")
        
        if not products:
            print("No products found, returning None")
            return None
        
        product_analyses = []
        all_collected_reviews = set()
        
        for i, product in enumerate(products):
            print(f"\nScraping reviews for product {i+1}/{len(products)}: {product['name']}")
            print(f"Product URL: {product['url']}")
            
            try:
                reviews = self.scrape_product_reviews(product['url'], max_reviews_per_product)
                print(f"Scraped {len(reviews) if reviews else 0} reviews")
                
                if reviews:
                    unique_reviews = self._filter_unique_reviews(reviews, product, all_collected_reviews)
                    print(f"After filtering duplicates: {len(unique_reviews)} unique reviews")
                    
                    if unique_reviews:
                        product_analysis = self.analyze_sentiment(unique_reviews)
                        
                        if product_analysis and "error" not in product_analysis:
                            product_analysis['product_name'] = product['name']
                            product_analysis['product_url'] = product['url']
                            product_analysis['category'] = category
                            product_analyses.append(product_analysis)
                            print(f"Successfully added product analysis. Total so far: {len(product_analyses)}")
                        else:
                            print(f"Sentiment analysis failed: {product_analysis}")
                    
            except Exception as e:
                print(f"Error processing product {product['name']}: {e}")
            
            time.sleep(1)
        
        print(f"\nCompleted analysis. Found {len(product_analyses)} products with valid reviews")
        
        if not product_analyses:
            return None
        
        summary_analysis = self._create_category_summary(product_analyses, category)
        
        result = {
            'category': category,
            'summary': summary_analysis,
            'products': product_analyses,
            'total_products_analyzed': len(product_analyses)
        }
        
        return result
    
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
                    'sample_reviews': []
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
            
            # Extract meaningful words
            words = self._extract_meaningful_words(text)
            
            # Count word frequency
            word_freq = Counter(words)
            
            # Get most common themes
            common_words = word_freq.most_common(10)
            themes = [word for word, count in common_words if count >= 2]
            
            return themes[:5]  # Return top 5 themes
            
        except Exception as e:
            print(f"Error extracting themes: {e}")
            return []
    
    def _extract_meaningful_words(self, text):
        """Extract meaningful words from text"""
        try:
            # Convert to lowercase and extract words
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
            
            # Filter out stop words and common non-meaningful words
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
            
            # Aggregate metrics
            total_reviews = sum(p.get('total_reviews', 0) for p in product_analyses)
            total_text_reviews = sum(p.get('text_reviews', 0) for p in product_analyses)
            avg_rating = sum(p.get('average_rating', 0) for p in product_analyses) / len(product_analyses)
            avg_sentiment = sum(p.get('sentiment_score', 0) for p in product_analyses) / len(product_analyses)
            
            # Aggregate review counts
            total_positive = sum(p.get('positive_reviews', 0) for p in product_analyses)
            total_negative = sum(p.get('negative_reviews', 0) for p in product_analyses)
            total_neutral = sum(p.get('neutral_reviews', 0) for p in product_analyses)
            
            # Aggregate themes
            all_themes = []
            for product in product_analyses:
                themes = product.get('themes', [])
                all_themes.extend(themes)
            
            theme_counts = Counter(all_themes)
            top_themes = [theme for theme, count in theme_counts.most_common(8)]
            
            # Find best and worst products
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
            
            # Create Excel writer
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Write category summary
                self._write_category_summary_sheet(writer, analysis_data)
                
                # Write products overview
                self._write_products_overview_sheet(writer, analysis_data)
                
                # Write detailed reviews
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
    # Enhanced review extraction methods to add to your kroger_analyzer.py

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
                review_data['datetime'] = datetime_stamp
            
            return review_data if review_data else None
                
        except Exception as e:
            print(f"Error extracting review data: {e}")
            return None

    def _extract_datetime(self, element):
        """Extract datetime from review element"""
        try:
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
            
            return None
            
        except Exception as e:
            print(f"Error extracting datetime: {e}")
            return None

    def _parse_datetime_string(self, date_string):
        """Parse various datetime formats"""
        try:
            from datetime import datetime
            import re
            
            if not date_string:
                return None
            
            # Common date patterns
            date_patterns = [
                # ISO format
                r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
                r'(\d{4}-\d{2}-\d{2})',
                # US format
                r'(\d{1,2}/\d{1,2}/\d{4})',
                r'(\d{1,2}-\d{1,2}-\d{4})',
                # Month day, year
                r'([A-Za-z]+ \d{1,2}, \d{4})',
                # Relative dates
                r'(\d+) days? ago',
                r'(\d+) weeks? ago',
                r'(\d+) months? ago',
                r'yesterday',
                r'today'
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, date_string, re.IGNORECASE)
                if matches:
                    date_match = matches[0]
                    
                    # Handle relative dates
                    if 'ago' in date_string.lower():
                        return self._parse_relative_date(date_string)
                    elif 'yesterday' in date_string.lower():
                        from datetime import datetime, timedelta
                        return datetime.now() - timedelta(days=1)
                    elif 'today' in date_string.lower():
                        return datetime.now()
                    
                    # Try to parse absolute dates
                    date_formats = [
                        '%Y-%m-%dT%H:%M:%S',
                        '%Y-%m-%d',
                        '%m/%d/%Y',
                        '%m-%d-%Y',
                        '%B %d, %Y',
                        '%b %d, %Y'
                    ]
                    
                    for date_format in date_formats:
                        try:
                            return datetime.strptime(date_match, date_format)
                        except:
                            continue
            
            return None
            
        except Exception as e:
            print(f"Error parsing datetime string '{date_string}': {e}")
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
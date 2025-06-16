import requests
from bs4 import BeautifulSoup
import time
import re
from collections import Counter
from textblob import TextBlob
import pandas as pd
from urllib.parse import urljoin, urlparse
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import chromedriver_autoinstaller

class KrogerReviewAnalyzer:
    def __init__(self, use_selenium=True, headless=True):
        self.base_url = "https://www.kroger.com"
        self.reviews_data = []
        self.use_selenium = use_selenium
        
        if use_selenium:
            self._setup_selenium(headless)
        else:
            self._setup_requests()
    
    def _setup_selenium(self, headless):
        """Initialize Selenium WebDriver"""
        chromedriver_autoinstaller.install()
        
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
        except Exception as e:
            print(f"Error setting up Chrome driver: {e}")
            raise
    
    def _setup_requests(self):
        """Initialize requests session"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def __del__(self):
        """Clean up resources"""
        if hasattr(self, 'driver') and self.use_selenium:
            try:
                self.driver.quit()
            except:
                pass
        
    def search_products(self, category, max_products=20):
        """Search for products in a specific category"""
        search_url = f"{self.base_url}/search?query={category.replace(' ', '+')}"
        
        if self.use_selenium:
            return self._search_with_selenium(search_url, max_products)
        else:
            return self._search_with_requests(search_url, max_products)
    
    def _search_with_selenium(self, search_url, max_products):
        """Search using Selenium for JavaScript-heavy sites"""
        try:
            print(f"Loading search page: {search_url}")
            self.driver.get(search_url)
            time.sleep(5)  # Increased wait time
            
            # Debug: Check page title and URL
            print(f"Page loaded. Title: {self.driver.title}")
            print(f"Current URL: {self.driver.current_url}")
            
            product_selectors = [
                'a[href*="/p/"]',
                '[data-testid*="product"] a',
                '.ProductCard a',
                '.product-item a',
                '[class*="product"] a[href*="/p/"]',
                'a[href*="products"]'
            ]
            
            product_links = []
            seen_urls = set()
            
            # Debug: Check page source for basic content
            page_source = self.driver.page_source
            print(f"Page source length: {len(page_source)}")
            print(f"Contains 'cookie' text: {'cookie' in page_source.lower()}")
            print(f"Contains '/p/' links: {'/p/' in page_source}")
            
            # Try to find ANY links first
            all_links = self.driver.find_elements(By.TAG_NAME, 'a')
            print(f"Total links found on page: {len(all_links)}")
            
            # Check for common Kroger page elements
            kroger_elements = self.driver.find_elements(By.CSS_SELECTOR, '[class*="kroger"], [id*="kroger"]')
            print(f"Kroger-specific elements found: {len(kroger_elements)}")
            
            for selector in product_selectors:
                elements = self._find_elements_safely(selector)
                print(f"Selector '{selector}' found {len(elements)} elements")
                
                for element in elements:
                    href = self._get_element_attribute(element, 'href')
                    if not href:
                        continue
                        
                    print(f"Found link: {href}")
                    
                    if '/p/' not in href and 'product' not in href:
                        continue
                        
                    if href in seen_urls:
                        continue
                    
                    product_name = self._extract_product_name(element)
                    print(f"Extracted product name: '{product_name}'")
                    
                    if self._is_valid_product_name(product_name):
                        product_links.append({
                            'name': product_name,
                            'url': href
                        })
                        seen_urls.add(href)
                        print(f"Added valid product: {product_name}")
                        
                        if len(product_links) >= max_products:
                            break
                
                if product_links:
                    print(f"Found {len(product_links)} products with selector: {selector}")
                    break
                else:
                    print(f"No valid products found with selector: {selector}")
            
            # If still no products, try broader search
            if not product_links:
                print("No products found with standard selectors. Trying broader search...")
                
                # Look for any links containing product-like terms
                all_links = self.driver.find_elements(By.TAG_NAME, 'a')
                for link in all_links[:20]:  # Check first 20 links
                    href = self._get_element_attribute(link, 'href')
                    text = link.text.strip()
                    if href and ('product' in href.lower() or '/p/' in href or 'item' in href.lower()):
                        print(f"Potential product link: {href} | Text: {text[:50]}")
            
            result = self._deduplicate_products(product_links)
            print(f"Final result after deduplication: {len(result)} products")
            return result
            
        except Exception as e:
            print(f"Error in Selenium search: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _search_with_requests(self, search_url, max_products):
        """Search using requests (fallback)"""
        try:
            response = self.session.get(search_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            product_links = []
            product_elements = soup.find_all('a', href=re.compile(r'/p/'))
            
            for element in product_elements[:max_products]:
                href = element.get('href')
                if href:
                    full_url = urljoin(self.base_url, href)
                    product_name = element.get_text(strip=True) or "Unknown Product"
                    
                    if self._is_valid_product_name(product_name):
                        product_links.append({
                            'name': product_name,
                            'url': full_url
                        })
            
            return self._deduplicate_products(product_links)
            
        except Exception as e:
            print(f"Error searching for products: {e}")
            return []
    
    def _find_elements_safely(self, selector):
        """Safely find elements with error handling"""
        try:
            return self.driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            return []
    
    def _get_element_attribute(self, element, attribute):
        """Safely get element attribute"""
        try:
            return element.get_attribute(attribute)
        except Exception:
            return None
    
    def _extract_product_name(self, element):
        """Extract product name from various possible locations"""
        name_selectors = [
            '.product-title',
            '.ProductCard-title',
            '[data-testid*="title"]',
            'h2', 'h3', 'h4',
            '.title',
            '[class*="name"]',
            '[class*="title"]'
        ]
        
        # Try specific selectors first
        for selector in name_selectors:
            name = self._get_text_from_selector(element, selector)
            if name:
                return name
        
        # Fallback to element text
        try:
            text = element.text.strip()
            if text:
                return text
        except:
            pass
        
        # Extract from URL as last resort
        href = self._get_element_attribute(element, 'href')
        if href:
            match = re.search(r'/p/([^/]+)', href)
            if match:
                return match.group(1).replace('-', ' ').title()
        
        return "Unknown Product"
    
    def _get_text_from_selector(self, parent_element, selector):
        """Get text from a child element using CSS selector"""
        try:
            child_element = parent_element.find_element(By.CSS_SELECTOR, selector)
            return child_element.text.strip()
        except:
            return None
    
    def _is_valid_product_name(self, name):
        """Check if a product name seems valid"""
        if not name or name == "Unknown Product":
            return False
        
        invalid_patterns = [
            r'^\d+\s*more\s*flavors?$',
            r'^more\s*flavors?$',
            r'^view\s*all$',
            r'^see\s*more$',
            r'^load\s*more$',
            r'^show\s*more$',
            r'^\s*$',
            r'^\.+$',
            r'^-+$'
        ]
        
        name_lower = name.lower().strip()
        for pattern in invalid_patterns:
            if re.match(pattern, name_lower):
                return False
        
        return len(name.strip()) >= 3 and re.search(r'[a-zA-Z]', name)
    
    def _deduplicate_products(self, product_links):
        """Remove duplicate products based on name similarity"""
        if not product_links:
            return []
        
        unique_products = []
        seen_names = set()
        
        for product in product_links:
            normalized_name = re.sub(r'[^\w\s]', '', product['name'].lower().strip())
            normalized_name = ' '.join(normalized_name.split())
            
            is_duplicate = False
            for seen_name in seen_names:
                words1 = set(normalized_name.split())
                words2 = set(seen_name.split())
                if len(words1) > 0 and len(words2) > 0:
                    overlap = len(words1.intersection(words2)) / len(words1.union(words2))
                    if overlap > 0.8:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_products.append(product)
                seen_names.add(normalized_name)
        
        return unique_products
    
    def scrape_product_reviews(self, product_url, max_reviews=50):
        """Scrape reviews for a specific product"""
        if self.use_selenium:
            return self._scrape_reviews_selenium(product_url, max_reviews)
        else:
            return self._scrape_reviews_requests(product_url, max_reviews)
    
    def _scrape_reviews_selenium(self, product_url, max_reviews):
        """Scrape reviews using Selenium"""
        try:
            self.driver.get(product_url)
            time.sleep(3)
            
            review_selectors = [
                '[data-testid*="review"]',
                '.review',
                '.Review',
                '[class*="review"]',
                '[id*="review"]'
            ]
            
            reviews = []
            for selector in review_selectors:
                elements = self._find_elements_safely(selector)
                
                for element in elements[:max_reviews]:
                    review_data = self._extract_review_data_selenium(element)
                    if review_data:
                        reviews.append(review_data)
                
                if reviews:
                    break
            
            return reviews
            
        except Exception as e:
            print(f"Error scraping reviews from {product_url}: {e}")
            return []
    
    def _extract_review_data_selenium(self, element):
        """Extract review data from Selenium element"""
        review_data = {}
        
        # Extract rating
        rating = self._extract_rating(element)
        if rating:
            review_data['rating'] = rating
        
        # Extract text
        text = self._extract_review_text(element)
        if text:
            review_data['text'] = text
        
        # Extract author
        author = self._extract_author(element)
        if author:
            review_data['author'] = author
        
        return review_data if review_data else None
    
    def _extract_rating(self, element):
        """Extract rating from review element"""
        rating_selectors = [
            '[class*="star"]',
            '[class*="rating"]',
            '[data-testid*="rating"]',
            '.rating',
            '.stars'
        ]
        
        for selector in rating_selectors:
            try:
                rating_element = element.find_element(By.CSS_SELECTOR, selector)
                rating_text = rating_element.text or rating_element.get_attribute('aria-label') or ''
                rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
                if rating_match:
                    return float(rating_match.group(1))
            except:
                continue
        return None
    
    def _extract_review_text(self, element):
        """Extract review text from element"""
        text_selectors = [
            '[class*="review"] p',
            '.review-text',
            '[data-testid*="review-text"]',
            '.comment',
            'p'
        ]
        
        for selector in text_selectors:
            try:
                text_element = element.find_element(By.CSS_SELECTOR, selector)
                text = text_element.text.strip()
                
                if self._is_valid_review_text(text):
                    return text
            except:
                continue
        return None
    
    def _extract_author(self, element):
        """Extract author from review element"""
        author_selectors = [
            '[class*="author"]',
            '[class*="reviewer"]',
            '[data-testid*="author"]',
            '.name'
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
    
    def _is_valid_review_text(self, text):
        """Check if review text is valid (not junk)"""
        if not text or len(text.strip()) < 10:
            return False
        
        junk_patterns = [
            r'kroger is not responsible for the content',
            r'terms and conditions',
            r'opens in a new tab',
            r'for more information, visit',
            r'customer ratings and reviews',
            r'^\s*$',
            r'^\.+$',
            r'^-+$',
            r'^view\s*more$',
            r'^show\s*more$',
            r'^load\s*more$'
        ]
        
        text_lower = text.lower().strip()
        return not any(re.search(pattern, text_lower) for pattern in junk_patterns)
    
    def _is_junk_author(self, author):
        """Check if author name is junk"""
        if not author:
            return True
        
        junk_patterns = [
            r'^anonymous$',
            r'^kroger$',
            r'^admin$',
            r'^moderator$',
            r'^\s*$'
        ]
        
        author_lower = author.lower().strip()
        return any(re.match(pattern, author_lower) for pattern in junk_patterns)
    
    def _scrape_reviews_requests(self, product_url, max_reviews):
        """Scrape reviews using requests (fallback)"""
        try:
            if not hasattr(self, 'session'):
                self._setup_requests()
            
            response = self.session.get(product_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            reviews = []
            review_containers = soup.find_all(['div', 'section'], class_=re.compile(r'review|rating', re.I))
            
            for container in review_containers[:max_reviews]:
                review_data = self._extract_review_data_requests(container)
                if review_data:
                    reviews.append(review_data)
            
            return reviews
            
        except Exception as e:
            print(f"Error scraping reviews from {product_url}: {e}")
            return []
    
    def _extract_review_data_requests(self, container):
        """Extract review data from BeautifulSoup container"""
        review_data = {}
        
        # Extract rating
        rating_element = container.find(['span', 'div'], class_=re.compile(r'star|rating', re.I))
        if rating_element:
            rating_text = rating_element.get_text(strip=True)
            rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
            if rating_match:
                review_data['rating'] = float(rating_match.group(1))
        
        # Extract text
        text_element = container.find(['p', 'div', 'span'], class_=re.compile(r'review|comment|text', re.I))
        if text_element:
            text = text_element.get_text(strip=True)
            if self._is_valid_review_text(text):
                review_data['text'] = text
        
        # Extract author
        author_element = container.find(['span', 'div'], class_=re.compile(r'author|name|reviewer', re.I))
        if author_element:
            author = author_element.get_text(strip=True)
            if not self._is_junk_author(author):
                review_data['author'] = author
        
        return review_data if review_data else None
    
    def analyze_sentiment(self, reviews):
        """Analyze sentiment of reviews and extract insights"""
        if not reviews:
            return {"error": "No reviews to analyze"}
        
        valid_reviews = [r for r in reviews if r and r.get('rating') and r.get('text')]
        
        if not valid_reviews:
            return {"error": "No valid reviews found"}
        
        ratings = [r['rating'] for r in valid_reviews]
        avg_rating = sum(ratings) / len(ratings)
        
        all_text = " ".join([r['text'] for r in valid_reviews])
        blob = TextBlob(all_text)
        sentiment_polarity = blob.sentiment.polarity
        
        words = self._extract_meaningful_words(all_text)
        common_words = Counter(words).most_common(10)
        
        negative_reviews = [r['text'] for r in valid_reviews if r['rating'] <= 2]
        positive_reviews = [r['text'] for r in valid_reviews if r['rating'] >= 4]
        
        complaints = self._extract_themes(negative_reviews)
        praises = self._extract_themes(positive_reviews)
        
        return {
            "total_reviews": len(valid_reviews),
            "average_rating": round(avg_rating, 2),
            "sentiment_score": round(sentiment_polarity, 2),
            "sentiment_description": self._get_sentiment_description(sentiment_polarity),
            "common_words": common_words,
            "common_complaints": complaints,
            "common_praises": praises,
            "rating_distribution": Counter(ratings),
            "all_reviews": valid_reviews
        }
    
    def _extract_meaningful_words(self, text):
        """Extract meaningful words, excluding common stop words"""
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'were', 'will', 'with', 'you', 'your', 'i', 'me', 'my',
            'we', 'our', 'they', 'them', 'their', 'this', 'these', 'those',
            'but', 'or', 'so', 'if', 'when', 'where', 'why', 'how', 'what',
            'who', 'which', 'can', 'could', 'would', 'should', 'may', 'might',
            'do', 'does', 'did', 'have', 'had', 'been', 'being', 'get', 'got',
            'all', 'any', 'some', 'many', 'much', 'more', 'most', 'very',
            'just', 'only', 'also', 'even', 'still', 'too', 'up', 'out',
            'now', 'then', 'here', 'there', 'back', 'down', 'way', 'than'
        }
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return [word for word in words if word not in stop_words]
    
    def _extract_themes(self, texts):
        """Extract common themes from a list of texts"""
        if not texts:
            return []
        
        theme_keywords = {
            "taste": ["sweet", "salty", "bitter", "sour", "flavor", "taste", "delicious", "bland", "tasty"],
            "quality": ["quality", "fresh", "stale", "expired", "good", "bad", "poor", "excellent"],
            "price": ["expensive", "cheap", "price", "cost", "value", "money", "affordable"],
            "packaging": ["package", "packaging", "container", "box", "bag", "damaged", "broken"],
            "texture": ["soft", "hard", "chewy", "crunchy", "smooth", "rough", "texture", "crispy"]
        }
        
        themes = []
        combined_text = " ".join(texts).lower()
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in combined_text for keyword in keywords):
                sentences = self._extract_theme_sentences(texts, keywords)
                
                if sentences:
                    themes.append({
                        "theme": theme,
                        "examples": sentences[:3]
                    })
        
        return themes
    
    def _extract_theme_sentences(self, texts, keywords):
        """Extract sentences containing specific keywords"""
        sentences = []
        for text in texts:
            text_sentences = [s.strip() for s in text.split('.') if s.strip()]
            relevant_sentences = [s for s in text_sentences if any(kw in s.lower() for kw in keywords)]
            sentences.extend(relevant_sentences)
        
        # Remove duplicates while preserving order
        unique_sentences = []
        seen = set()
        for sentence in sentences:
            normalized = ' '.join(sentence.lower().split())
            if normalized not in seen and len(sentence) > 15:
                seen.add(normalized)
                unique_sentences.append(sentence)
        
        return unique_sentences
    
    def _get_sentiment_description(self, polarity):
        """Convert sentiment polarity to description"""
        if polarity > 0.3:
            return "Very Positive"
        elif polarity > 0.1:
            return "Positive"
        elif polarity > -0.1:
            return "Neutral"
        elif polarity > -0.3:
            return "Negative"
        else:
            return "Very Negative"
    
    def analyze_category_by_products(self, category, max_products=10, max_reviews_per_product=20):
        """Main method to analyze products individually in a category"""
        products = self.search_products(category, max_products)
        
        if not products:
            return None
        
        product_analyses = []
        all_collected_reviews = set()
        
        for product in products:
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
            
            time.sleep(1)  # Be respectful to the server
        
        if not product_analyses:
            return None
        
        summary_analysis = self._create_category_summary(product_analyses, category)
        
        return {
            'category': category,
            'summary': summary_analysis,
            'products': product_analyses,
            'total_products_analyzed': len(product_analyses)
        }
    
    def _filter_unique_reviews(self, reviews, product, all_collected_reviews):
        """Filter out duplicate reviews across products"""
        unique_reviews = []
        
        for review in reviews:
            if review is None:
                continue
            
            review_text = review.get('text', '') if review else ''
            if isinstance(review_text, str):
                review_text = review_text.strip()
            else:
                review_text = ''
            
            if review_text and review_text not in all_collected_reviews:
                review['product_name'] = product['name']
                review['product_url'] = product['url']
                unique_reviews.append(review)
                all_collected_reviews.add(review_text)
        
        return unique_reviews
    
    def _create_category_summary(self, product_analyses, category):
        """Create a summary analysis across all products in the category"""
        if not product_analyses:
            return None
        
        total_reviews = sum(p['total_reviews'] for p in product_analyses)
        all_ratings = []
        all_reviews_text = []
        
        for product in product_analyses:
            if 'all_reviews' in product:
                for review in product['all_reviews']:
                    if review.get('rating'):
                        all_ratings.append(review['rating'])
                    if review.get('text'):
                        all_reviews_text.append(review['text'])
        
        if not all_ratings:
            return None
        
        avg_rating = sum(all_ratings) / len(all_ratings)
        
        products_by_rating = sorted(product_analyses, 
                                  key=lambda x: x.get('average_rating', 0), 
                                  reverse=True)
        
        combined_text = " ".join(all_reviews_text)
        blob = TextBlob(combined_text)
        sentiment_polarity = blob.sentiment.polarity
        
        words = self._extract_meaningful_words(combined_text)
        common_words = Counter(words).most_common(10)
        
        return {
            'category': category,
            'total_products': len(product_analyses),
            'total_reviews': total_reviews,
            'average_rating_across_all': round(avg_rating, 2),
            'sentiment_score': round(sentiment_polarity, 2),
            'sentiment_description': self._get_sentiment_description(sentiment_polarity),
            'common_words': common_words,
            'top_rated_products': [
                {
                    'name': p['product_name'], 
                    'rating': p['average_rating'],
                    'review_count': p['total_reviews']
                } 
                for p in products_by_rating[:5]
            ],
            'rating_distribution': Counter(all_ratings)
        }
    
    def export_products_to_spreadsheet(self, analysis, filename=None):
        """Export product-level analysis results to Excel spreadsheet"""
        if not analysis or not analysis.get('products'):
            return None
        
        category = analysis['category']
        if filename is None:
            filename = f"{category.replace(' ', '_')}_products_analysis.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            self._write_category_summary_sheet(writer, analysis)
            self._write_products_overview_sheet(writer, analysis)
            self._write_all_reviews_sheet(writer, analysis)
        
        return filename
    
    def _write_category_summary_sheet(self, writer, analysis):
        """Write category summary sheet to Excel"""
        if not analysis.get('summary'):
            return
        
        summary = analysis['summary']
        summary_data = {
            'Metric': [
                'Category',
                'Total Products Analyzed',
                'Total Reviews',
                'Average Rating (All Products)',
                'Overall Sentiment Score',
                'Overall Sentiment Description'
            ],
            'Value': [
                analysis['category'],
                summary['total_products'],
                summary['total_reviews'],
                f"{summary['average_rating_across_all']}/5",
                summary['sentiment_score'],
                summary['sentiment_description']
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Category Summary', index=False)
        
        # Top rated products
        if summary.get('top_rated_products'):
            top_products_df = pd.DataFrame(summary['top_rated_products'])
            top_products_df.to_excel(writer, sheet_name='Top Rated Products', index=False)
        
        # Category common words
        if summary.get('common_words'):
            words_df = pd.DataFrame([
                {'Word': word, 'Mentions': count}
                for word, count in summary['common_words']
            ])
            words_df.to_excel(writer, sheet_name='Category Common Words', index=False)
    
    def _write_products_overview_sheet(self, writer, analysis):
        """Write products overview sheet to Excel"""
        products_summary = []
        for product in analysis['products']:
            products_summary.append({
                'Product Name': product['product_name'],
                'Average Rating': product['average_rating'],
                'Total Reviews': product['total_reviews'],
                'Sentiment Score': product['sentiment_score'],
                'Sentiment Description': product['sentiment_description'],
                'Top Complaints': ', '.join([theme['theme'].title() for theme in product.get('common_complaints', [])[:3]]),
                'Top Praises': ', '.join([theme['theme'].title() for theme in product.get('common_praises', [])[:3]])
            })
        
        products_df = pd.DataFrame(products_summary)
        products_df.to_excel(writer, sheet_name='Products Overview', index=False)
    
    def _write_all_reviews_sheet(self, writer, analysis):
        """Write all reviews sheet to Excel"""
        all_reviews_data = []
        for product in analysis['products']:
            if 'all_reviews' in product:
                for review in product['all_reviews']:
                    all_reviews_data.append({
                        'Product': product['product_name'],
                        'Rating': review.get('rating', ''),
                        'Review Text': review.get('text', ''),
                        'Author': review.get('author', 'Anonymous')
                    })
        
        if all_reviews_data:
            all_reviews_df = pd.DataFrame(all_reviews_data)
            all_reviews_df.to_excel(writer, sheet_name='All Reviews', index=False)
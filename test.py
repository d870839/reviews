#!/usr/bin/env python3
"""
Test script to verify Kroger website access and bot detection avoidance
"""

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import random

def test_requests_access():
    """Test basic requests access to Kroger"""
    print("🧪 Testing requests access to Kroger...")
    
    session = requests.Session()
    
    # Use realistic headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1'
    }
    
    session.headers.update(headers)
    
    try:
        # Test main page
        response = session.get('https://www.kroger.com/', timeout=30)
        print(f"Main page status: {response.status_code}")
        print(f"Content length: {len(response.text)}")
        
        if response.status_code == 200:
            content = response.text.lower()
            if 'access denied' in content or 'blocked' in content or 'captcha' in content:
                print("❌ Main page shows blocking indicators")
                return False
            else:
                print("✅ Main page accessible")
        
        # Test search page
        search_url = 'https://www.kroger.com/search?query=cookies'
        response = session.get(search_url, timeout=30)
        print(f"Search page status: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text.lower()
            if 'access denied' in content or 'blocked' in content or 'captcha' in content:
                print("❌ Search page shows blocking indicators")
                return False
            else:
                print("✅ Search page accessible")
                
                # Check if we can find product indicators
                product_indicators = ['/p/', 'product', 'href']
                found_indicators = sum(1 for indicator in product_indicators if indicator in content)
                print(f"Found {found_indicators}/{len(product_indicators)} product indicators")
                
                return found_indicators >= 2
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Requests test failed: {e}")
        return False

def test_selenium_access():
    """Test Selenium access to Kroger"""
    print("\n🧪 Testing Selenium access to Kroger...")
    
    try:
        chrome_options = Options()
        
        # Docker-optimized options
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        
        # Bot evasion options
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--exclude-switches=enable-automation')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument('--window-size=1920,1080')
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set binary location for Docker
        chrome_options.binary_location = "/usr/bin/google-chrome"
        
        # Create service
        service = Service(executable_path="/usr/local/bin/chromedriver")
        
        # Initialize driver
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Hide webdriver property
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver.set_page_load_timeout(60)
        
        # Test main page
        driver.get('https://www.kroger.com/')
        time.sleep(3)
        
        title = driver.title
        page_source = driver.page_source.lower()
        
        print(f"Page title: {title[:50]}...")
        print(f"Page source length: {len(page_source)}")
        
        # Check for blocking
        blocking_indicators = ['access denied', 'blocked', 'captcha', 'cloudflare', 'ray id']
        blocked = any(indicator in page_source for indicator in blocking_indicators)
        
        if blocked:
            print("❌ Page shows blocking indicators")
            driver.quit()
            return False
        else:
            print("✅ Main page accessible via Selenium")
        
        # Test search
        search_url = 'https://www.kroger.com/search?query=cookies'
        driver.get(search_url)
        time.sleep(5)
        
        # Simulate human behavior
        driver.execute_script("window.scrollTo(0, 300);")
        time.sleep(2)
        
        # Look for product links
        product_selectors = [
            'a[href*="/p/"]',
            '[data-testid*="product"] a',
            '.product-card a',
            'a[href*="product"]'
        ]
        
        total_products = 0
        for selector in product_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                total_products += len(elements)
                if elements:
                    print(f"Found {len(elements)} elements with selector: {selector}")
            except Exception as e:
                continue
        
        print(f"Total product elements found: {total_products}")
        
        driver.quit()
        return total_products > 0
        
    except Exception as e:
        print(f"❌ Selenium test failed: {e}")
        try:
            driver.quit()
        except:
            pass
        return False

def test_alternative_approaches():
    """Test alternative data sources"""
    print("\n🧪 Testing alternative approaches...")
    
    # Test if we can access category pages directly
    category_urls = [
        'https://www.kroger.com/d/snacks/cookies-crackers/cookies',
        'https://www.kroger.com/d/bakery/fresh-bread',
        'https://www.kroger.com/d/dairy/milk'
    ]
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    accessible_categories = 0
    
    for url in category_urls:
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 200:
                content = response.text.lower()
                if not any(indicator in content for indicator in ['access denied', 'blocked', 'captcha']):
                    accessible_categories += 1
                    print(f"✅ Category accessible: {url.split('/')[-1]}")
                else:
                    print(f"❌ Category blocked: {url.split('/')[-1]}")
            else:
                print(f"❌ Category error {response.status_code}: {url.split('/')[-1]}")
        except Exception as e:
            print(f"❌ Category failed: {url.split('/')[-1]} - {e}")
    
    print(f"Accessible categories: {accessible_categories}/{len(category_urls)}")
    
    return accessible_categories > 0

def main():
    """Run all tests"""
    print("🚀 Starting Kroger access tests...\n")
    
    results = {}
    
    # Test 1: Requests access
    results['requests'] = test_requests_access()
    
    # Test 2: Selenium access
    results['selenium'] = test_selenium_access()
    
    # Test 3: Alternative approaches
    results['alternatives'] = test_alternative_approaches()
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST RESULTS SUMMARY")
    print("="*50)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.capitalize():15} {status}")
    
    passed_tests = sum(results.values())
    total_tests = len(results)
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == 0:
        print("\n❌ All tests failed. Kroger has strong bot protection.")
        print("Recommendations:")
        print("1. Use Kroger's official API instead")
        print("2. Use a professional scraping service")
        print("3. Consider alternative data sources")
    elif passed_tests < total_tests:
        print(f"\n⚠️  Partial success. Some methods work.")
        print("The working methods can be used for data extraction.")
    else:
        print(f"\n✅ All tests passed! Bot evasion successful.")
    
    return results

if __name__ == '__main__':
    main()
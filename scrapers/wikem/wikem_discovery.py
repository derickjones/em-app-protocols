#!/usr/bin/env python3
"""
WikEM Discovery & Scale Analysis
Analyzes the full scope of WikEM before bulk scraping.

Usage:
    python wikem_discovery.py --sitemap    # Discover from sitemap.xml
    python wikem_discovery.py --categories # Discover from category pages
    python wikem_discovery.py --analyze    # Analyze discovered URLs
"""

import argparse
import json
import logging
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://wikem.org"
SITEMAP_URL = "https://www.wikem.org/w/sitemap.xml"
REQUEST_DELAY = 2.0  # Conservative rate limiting

OUTPUT_DIR = Path(__file__).parent / "discovery"
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WikEMDiscovery:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WikEM-Discovery/1.0 (Educational Medical Research; Contact: researcher@example.com)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def discover_from_sitemap(self):
        """Discover all pages from sitemap.xml"""
        logger.info("Fetching sitemap.xml...")
        
        try:
            response = self.session.get(SITEMAP_URL, timeout=30)
            response.raise_for_status()
            
            # Parse XML sitemap
            soup = BeautifulSoup(response.content, 'xml')
            urls = []
            
            for url_elem in soup.find_all('url'):
                loc = url_elem.find('loc')
                lastmod = url_elem.find('lastmod')
                
                if loc:
                    url = loc.text.strip()
                    lastmod_date = lastmod.text.strip() if lastmod else None
                    urls.append({
                        'url': url,
                        'lastmod': lastmod_date,
                        'source': 'sitemap'
                    })
            
            logger.info(f"Found {len(urls)} URLs in sitemap")
            return urls
            
        except Exception as e:
            logger.error(f"Failed to fetch sitemap: {e}")
            return []
    
    def discover_from_categories(self):
        """Discover pages from main medical categories"""
        logger.info("Discovering from category pages...")
        
        # Main medical categories on WikEM
        categories = [
            'Cardiology', 'Pulmonology', 'Neurology', 'Psychiatry',
            'Gastroenterology', 'Nephrology', 'Endocrinology', 'Hematology',
            'Oncology', 'Infectious_Disease', 'Dermatology', 'Ophthalmology',
            'ENT', 'Orthopedics', 'Rheumatology', 'Toxicology',
            'Pediatric_Emergency_Medicine', 'Procedures', 'Trauma'
        ]
        
        all_urls = []
        
        for category in categories:
            logger.info(f"Crawling category: {category}")
            category_url = f"{BASE_URL}/wiki/Category:{category}"
            
            try:
                response = self.session.get(category_url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find pages in this category
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if href.startswith('/wiki/') and ':' not in href.split('/')[-1]:
                        full_url = BASE_URL + href
                        all_urls.append({
                            'url': full_url,
                            'category': category,
                            'source': 'category_crawl'
                        })
                
                time.sleep(REQUEST_DELAY)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Failed to crawl category {category}: {e}")
        
        # Deduplicate
        unique_urls = {}
        for item in all_urls:
            url = item['url']
            if url not in unique_urls:
                unique_urls[url] = item
            else:
                # Merge categories
                if 'categories' not in unique_urls[url]:
                    unique_urls[url]['categories'] = [unique_urls[url].get('category', '')]
                unique_urls[url]['categories'].append(item['category'])
        
        logger.info(f"Found {len(unique_urls)} unique URLs from categories")
        return list(unique_urls.values())
    
    def classify_urls(self, urls):
        """Classify URLs by type and relevance"""
        logger.info("Classifying URLs...")
        
        classifications = {
            'clinical_topics': [],      # Main medical topics
            'procedures': [],           # Medical procedures  
            'medications': [],          # Drug information
            'administrative': [],       # User:, WikEM:, Help:, etc.
            'redirects': [],           # Redirect pages
            'disambiguations': [],     # Disambiguation pages
            'templates': [],           # Template: pages
            'talk_pages': [],          # Talk: pages
            'categories': [],          # Category: pages
            'other': []                # Everything else
        }
        
        stats = Counter()
        
        for item in urls:
            url = item['url']
            path = urlparse(url).path
            
            # Extract page title
            if '/wiki/' in path:
                title = unquote(path.split('/wiki/')[-1])
                item['title'] = title
                
                # Classify based on namespace and content patterns
                if ':' in title:
                    namespace = title.split(':', 1)[0]
                    if namespace in ['User', 'WikEM', 'Help', 'Project']:
                        classifications['administrative'].append(item)
                        stats['administrative'] += 1
                    elif namespace == 'Template':
                        classifications['templates'].append(item)
                        stats['templates'] += 1
                    elif namespace == 'Talk':
                        classifications['talk_pages'].append(item)
                        stats['talk_pages'] += 1
                    elif namespace == 'Category':
                        classifications['categories'].append(item)
                        stats['categories'] += 1
                    else:
                        classifications['other'].append(item)
                        stats['other'] += 1
                elif '(disambiguation)' in title.lower():
                    classifications['disambiguations'].append(item)
                    stats['disambiguations'] += 1
                elif any(proc_word in title.lower() for proc_word in 
                        ['injection', 'puncture', 'centesis', 'tube', 'catheter', 'biopsy']):
                    classifications['procedures'].append(item)
                    stats['procedures'] += 1
                elif any(med_word in title.lower() for med_word in 
                        ['mg', 'mcg', 'dose', 'dosing', 'medication']):
                    classifications['medications'].append(item)
                    stats['medications'] += 1
                else:
                    classifications['clinical_topics'].append(item)
                    stats['clinical_topics'] += 1
            else:
                classifications['other'].append(item)
                stats['other'] += 1
        
        return classifications, stats
    
    def sample_pages(self, classifications, sample_size=5):
        """Sample pages from each category to understand content quality"""
        logger.info("Sampling pages for content analysis...")
        
        samples = {}
        
        for category, items in classifications.items():
            if not items:
                continue
                
            logger.info(f"Sampling {min(sample_size, len(items))} pages from {category}")
            sample_items = items[:sample_size]
            samples[category] = []
            
            for item in sample_items:
                try:
                    response = self.session.get(item['url'], timeout=30)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Extract basic content metrics
                    content_div = soup.find('div', {'class': 'mw-parser-output'})
                    if content_div:
                        text_content = content_div.get_text(strip=True)
                        word_count = len(text_content.split())
                        
                        # Count sections
                        sections = content_div.find_all(['h2', 'h3', 'h4'])
                        section_count = len(sections)
                        
                        # Check for images
                        images = content_div.find_all('img')
                        image_count = len(images)
                        
                        sample_info = {
                            'url': item['url'],
                            'title': item.get('title', ''),
                            'word_count': word_count,
                            'section_count': section_count,
                            'image_count': image_count,
                            'has_content': word_count > 50,  # Basic quality threshold
                        }
                        
                        samples[category].append(sample_info)
                    
                    time.sleep(REQUEST_DELAY)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Failed to sample {item['url']}: {e}")
        
        return samples
    
    def analyze_and_report(self, urls, classifications, stats, samples):
        """Generate comprehensive analysis report"""
        logger.info("Generating analysis report...")
        
        report = {
            'discovery_date': datetime.now().isoformat(),
            'total_urls': len(urls),
            'classification_stats': dict(stats),
            'recommendations': {},
            'samples': samples
        }
        
        # Calculate recommendations
        clinical_count = stats['clinical_topics'] + stats['procedures'] + stats['medications']
        
        report['recommendations'] = {
            'recommended_for_scraping': {
                'clinical_topics': stats['clinical_topics'],
                'procedures': stats['procedures'], 
                'medications': stats['medications'],
                'total': clinical_count
            },
            'skip_categories': {
                'administrative': stats['administrative'],
                'templates': stats['templates'],
                'talk_pages': stats['talk_pages'],
                'categories': stats['categories'],
                'disambiguations': stats['disambiguations'],
                'total_skipped': (stats['administrative'] + stats['templates'] + 
                               stats['talk_pages'] + stats['categories'] + stats['disambiguations'])
            },
            'estimated_scraping_time': {
                'sequential_hours': round(clinical_count * REQUEST_DELAY / 3600, 1),
                'parallel_5_workers_hours': round(clinical_count * REQUEST_DELAY / (3600 * 5), 1)
            }
        }
        
        return report


def main():
    parser = argparse.ArgumentParser(description='Discover and analyze WikEM content scope')
    parser.add_argument('--sitemap', action='store_true', help='Discover from sitemap.xml')
    parser.add_argument('--categories', action='store_true', help='Discover from category pages')
    parser.add_argument('--analyze', action='store_true', help='Analyze previously discovered URLs')
    parser.add_argument('--output', type=str, default='wikem_discovery.json', 
                       help='Output file for results')
    
    args = parser.parse_args()
    
    if not any([args.sitemap, args.categories, args.analyze]):
        args.sitemap = True  # Default to sitemap
    
    discovery = WikEMDiscovery()
    
    if args.analyze:
        # Load previously discovered URLs
        discovery_file = OUTPUT_DIR / args.output
        if discovery_file.exists():
            with open(discovery_file, 'r') as f:
                data = json.load(f)
                urls = data.get('urls', [])
        else:
            logger.error(f"No discovery file found: {discovery_file}")
            return
    else:
        urls = []
        
        if args.sitemap:
            sitemap_urls = discovery.discover_from_sitemap()
            urls.extend(sitemap_urls)
        
        if args.categories:
            category_urls = discovery.discover_from_categories()
            urls.extend(category_urls)
    
    # Classify URLs
    classifications, stats = discovery.classify_urls(urls)
    
    # Sample pages for content analysis
    samples = discovery.sample_pages(classifications)
    
    # Generate final analysis
    report = discovery.analyze_and_report(urls, classifications, stats, samples)
    
    # Save results
    output_file = OUTPUT_DIR / args.output
    with open(output_file, 'w') as f:
        json.dump({
            'urls': urls,
            'classifications': classifications,
            'report': report
        }, f, indent=2)
    
    # Print summary
    print("\n" + "="*60)
    print("🏥 WIKEM DISCOVERY ANALYSIS")
    print("="*60)
    print(f"Total URLs discovered: {report['total_urls']:,}")
    print(f"\nRecommended for scraping:")
    for category, count in report['recommendations']['recommended_for_scraping'].items():
        if category != 'total':
            print(f"  {category}: {count:,}")
    print(f"  TOTAL: {report['recommendations']['recommended_for_scraping']['total']:,}")
    
    print(f"\nEstimated scraping time:")
    print(f"  Sequential: {report['recommendations']['estimated_scraping_time']['sequential_hours']} hours")
    print(f"  5 parallel workers: {report['recommendations']['estimated_scraping_time']['parallel_5_workers_hours']} hours")
    
    print(f"\nSkip categories:")
    for category, count in report['recommendations']['skip_categories'].items():
        if category != 'total_skipped':
            print(f"  {category}: {count:,}")
    
    print(f"\nResults saved to: {output_file}")
    print("="*60)


if __name__ == "__main__":
    main()
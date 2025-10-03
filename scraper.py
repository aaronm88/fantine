#!/usr/bin/env python3
"""
Fantine Web Scraper
A robust web scraping application designed to run on DigitalOcean droplets
"""

import asyncio
import aiohttp
import json
import logging
import os
import signal
import sys
import time
import boto3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import argparse
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/fantine/scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ScrapingConfig:
    """Configuration for scraping job"""
    target_urls: List[str]
    output_format: str = "json"
    max_pages: int = 100
    delay_seconds: float = 1.0
    timeout_seconds: int = 30
    max_concurrent: int = 5
    user_agent: str = "Fantine-Scraper/1.0 (+https://github.com/your-org/fantine)"

@dataclass
class ScrapedData:
    """Structure for scraped data"""
    url: str
    title: str
    content: str
    timestamp: str
    status_code: int
    response_time: float
    metadata: Dict[str, Any]

class FantineScraper:
    """Main scraper class"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.session = None
        self.results: List[ScrapedData] = []
        self.running = True
        self.start_time = datetime.now()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Create output directory
        self.output_dir = Path("/opt/fantine/results")
        self.output_dir.mkdir(exist_ok=True)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
        
    async def _create_session(self):
        """Create aiohttp session with proper configuration"""
        connector = aiohttp.TCPConnector(
            limit=self.config.max_concurrent,
            limit_per_host=2,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        
        headers = {
            'User-Agent': self.config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        
    async def _scrape_url(self, url: str) -> ScrapedData:
        """Scrape a single URL"""
        start_time = time.time()
        
        try:
            async with self.session.get(url) as response:
                content = await response.text()
                response_time = time.time() - start_time
                
                # Extract title from HTML
                title = self._extract_title(content)
                
                # Clean content (remove HTML tags, etc.)
                clean_content = self._clean_content(content)
                
                scraped_data = ScrapedData(
                    url=url,
                    title=title,
                    content=clean_content,
                    timestamp=datetime.now().isoformat(),
                    status_code=response.status,
                    response_time=response_time,
                    metadata={
                        'content_length': len(content),
                        'clean_content_length': len(clean_content),
                        'headers': dict(response.headers)
                    }
                )
                
                logger.info(f"Successfully scraped {url} (status: {response.status}, time: {response_time:.2f}s)")
                return scraped_data
                
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Failed to scrape {url}: {str(e)}")
            
            return ScrapedData(
                url=url,
                title="",
                content="",
                timestamp=datetime.now().isoformat(),
                status_code=0,
                response_time=response_time,
                metadata={'error': str(e)}
            )
    
    def _extract_title(self, html_content: str) -> str:
        """Extract title from HTML content"""
        import re
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            return title_match.group(1).strip()
        return "No title found"
    
    def _clean_content(self, html_content: str) -> str:
        """Clean HTML content and extract text"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
        except ImportError:
            # Fallback to simple regex if BeautifulSoup not available
            import re
            text = re.sub(r'<[^>]+>', '', html_content)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
    
    async def _save_results(self):
        """Save results to file and upload to DigitalOcean Spaces"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.config.output_format.lower() == "json":
            output_file = self.output_dir / f"scraped_data_{timestamp}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump([asdict(result) for result in self.results], f, indent=2, ensure_ascii=False)
        else:
            output_file = self.output_dir / f"scraped_data_{timestamp}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                for result in self.results:
                    f.write(f"URL: {result.url}\n")
                    f.write(f"Title: {result.title}\n")
                    f.write(f"Status: {result.status_code}\n")
                    f.write(f"Timestamp: {result.timestamp}\n")
                    f.write(f"Content: {result.content[:500]}...\n")
                    f.write("-" * 80 + "\n")
        
        logger.info(f"Results saved to {output_file}")
        
        # Upload to DigitalOcean Spaces
        await self._upload_to_spaces(output_file)
        
        return output_file
    
    async def _upload_to_spaces(self, file_path: Path):
        """Upload file to DigitalOcean Spaces"""
        try:
            # Get credentials from environment variables
            spaces_key = os.getenv('DO_SPACES_KEY')
            spaces_secret = os.getenv('DO_SPACES_SECRET')
            spaces_endpoint = os.getenv('DO_SPACES_ENDPOINT', 'https://nyc3.digitaloceanspaces.com')
            spaces_bucket = os.getenv('DO_SPACES_BUCKET', 'fantine-bucket')
            
            if not spaces_key or not spaces_secret:
                logger.warning("DigitalOcean Spaces credentials not found. Skipping upload.")
                return
            
            # Create S3 client for DigitalOcean Spaces
            session = boto3.session.Session()
            client = session.client('s3',
                                  region_name='nyc3',
                                  endpoint_url=spaces_endpoint,
                                  aws_access_key_id=spaces_key,
                                  aws_secret_access_key=spaces_secret)
            
            # Upload file
            key = f"scraped-data/{file_path.name}"
            client.upload_file(str(file_path), spaces_bucket, key)
            
            # Generate public URL
            public_url = f"{spaces_endpoint}/{spaces_bucket}/{key}"
            logger.info(f"File uploaded to DigitalOcean Spaces: {public_url}")
            
        except Exception as e:
            logger.error(f"Failed to upload to DigitalOcean Spaces: {str(e)}")
    
    async def run(self):
        """Main scraping loop"""
        logger.info("Starting Fantine scraper...")
        logger.info(f"Configuration: {asdict(self.config)}")
        
        await self._create_session()
        
        try:
            # Process URLs in batches
            semaphore = asyncio.Semaphore(self.config.max_concurrent)
            
            async def scrape_with_semaphore(url):
                async with semaphore:
                    return await self._scrape_url(url)
            
            # Create tasks for all URLs
            tasks = [scrape_with_semaphore(url) for url in self.config.target_urls[:self.config.max_pages]]
            
            # Process tasks with progress tracking
            completed = 0
            for task in asyncio.as_completed(tasks):
                if not self.running:
                    logger.info("Shutdown requested, stopping scraping...")
                    break
                    
                result = await task
                self.results.append(result)
                completed += 1
                
                logger.info(f"Progress: {completed}/{len(tasks)} URLs completed")
                
                # Add delay between requests
                if self.config.delay_seconds > 0:
                    await asyncio.sleep(self.config.delay_seconds)
            
            # Save results
            output_file = await self._save_results()
            
            # Log summary
            successful = sum(1 for r in self.results if r.status_code == 200)
            failed = len(self.results) - successful
            total_time = (datetime.now() - self.start_time).total_seconds()
            
            logger.info(f"Scraping completed!")
            logger.info(f"Total URLs: {len(self.results)}")
            logger.info(f"Successful: {successful}")
            logger.info(f"Failed: {failed}")
            logger.info(f"Total time: {total_time:.2f} seconds")
            logger.info(f"Results saved to: {output_file}")
            
        except Exception as e:
            logger.error(f"Scraping failed: {str(e)}")
            raise
        finally:
            if self.session:
                await self.session.close()

def load_config_from_env() -> ScrapingConfig:
    """Load configuration from environment variables"""
    return ScrapingConfig(
        target_urls=os.getenv('SCRAPING_TARGET_URLS', '').split(',') if os.getenv('SCRAPING_TARGET_URLS') else [],
        output_format=os.getenv('SCRAPING_OUTPUT_FORMAT', 'json'),
        max_pages=int(os.getenv('SCRAPING_MAX_PAGES', '100')),
        delay_seconds=float(os.getenv('SCRAPING_DELAY_SECONDS', '1.0')),
        timeout_seconds=int(os.getenv('SCRAPING_TIMEOUT_SECONDS', '30')),
        max_concurrent=int(os.getenv('SCRAPING_MAX_CONCURRENT', '5')),
    )

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Fantine Web Scraper')
    parser.add_argument('--config-file', help='Path to configuration file')
    parser.add_argument('--urls', nargs='+', help='URLs to scrape')
    parser.add_argument('--max-pages', type=int, default=100, help='Maximum pages to scrape')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests in seconds')
    parser.add_argument('--output-format', choices=['json', 'txt'], default='json', help='Output format')
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config_file and os.path.exists(args.config_file):
        with open(args.config_file, 'r') as f:
            config_data = json.load(f)
        config = ScrapingConfig(**config_data)
    elif args.urls:
        config = ScrapingConfig(
            target_urls=args.urls,
            max_pages=args.max_pages,
            delay_seconds=args.delay,
            output_format=args.output_format
        )
    else:
        config = load_config_from_env()
    
    if not config.target_urls:
        logger.error("No target URLs specified!")
        sys.exit(1)
    
    # Run scraper
    scraper = FantineScraper(config)
    
    try:
        asyncio.run(scraper.run())
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

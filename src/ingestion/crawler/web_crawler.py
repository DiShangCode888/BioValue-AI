# 网页爬虫
"""
异步网页爬虫，用于抓取创新药相关信息
"""

import asyncio
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
from pydantic import BaseModel, Field

from src.config import get_settings
from src.utils import get_logger

logger = get_logger(__name__)


class CrawlResult(BaseModel):
    """爬取结果"""
    url: str
    status_code: int
    content_type: str
    text: str = ""
    html: str = ""
    title: str = ""
    links: list[str] = Field(default_factory=list)
    error: str | None = None


class WebCrawler:
    """异步网页爬虫
    
    支持:
    - 并发爬取
    - 请求限速
    - 自动重试
    - 内容提取
    """
    
    def __init__(
        self,
        max_concurrent: int | None = None,
        request_delay: float | None = None,
        user_agent: str | None = None,
    ):
        settings = get_settings()
        crawler_config = settings.ingestion.crawler
        
        self.max_concurrent = max_concurrent or crawler_config.max_concurrent
        self.request_delay = request_delay or crawler_config.request_delay
        self.user_agent = user_agent or crawler_config.user_agent
        
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._session: aiohttp.ClientSession | None = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self.user_agent},
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session
    
    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def fetch(self, url: str, retries: int = 3) -> CrawlResult:
        """爬取单个 URL
        
        Args:
            url: 目标 URL
            retries: 重试次数
            
        Returns:
            CrawlResult: 爬取结果
        """
        async with self._semaphore:
            session = await self._get_session()
            
            for attempt in range(retries):
                try:
                    async with session.get(url) as response:
                        content_type = response.headers.get("Content-Type", "")
                        html = await response.text()
                        
                        # 提取纯文本和标题
                        text, title, links = self._extract_content(html, url)
                        
                        result = CrawlResult(
                            url=url,
                            status_code=response.status,
                            content_type=content_type,
                            text=text,
                            html=html,
                            title=title,
                            links=links,
                        )
                        
                        logger.debug(f"Fetched {url}: {response.status}")
                        
                        # 请求间隔
                        await asyncio.sleep(self.request_delay)
                        
                        return result
                        
                except aiohttp.ClientError as e:
                    logger.warning(f"Fetch error for {url} (attempt {attempt + 1}): {e}")
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)  # 指数退避
                    else:
                        return CrawlResult(
                            url=url,
                            status_code=0,
                            content_type="",
                            error=str(e),
                        )
                        
                except Exception as e:
                    logger.error(f"Unexpected error for {url}: {e}")
                    return CrawlResult(
                        url=url,
                        status_code=0,
                        content_type="",
                        error=str(e),
                    )
    
    async def fetch_many(self, urls: list[str]) -> list[CrawlResult]:
        """并发爬取多个 URL
        
        Args:
            urls: URL 列表
            
        Returns:
            list[CrawlResult]: 爬取结果列表
        """
        tasks = [self.fetch(url) for url in urls]
        return await asyncio.gather(*tasks)
    
    def _extract_content(
        self,
        html: str,
        base_url: str
    ) -> tuple[str, str, list[str]]:
        """从 HTML 提取内容
        
        Args:
            html: HTML 内容
            base_url: 基础 URL
            
        Returns:
            tuple: (纯文本, 标题, 链接列表)
        """
        try:
            from html.parser import HTMLParser
            
            class ContentExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self.title = ""
                    self.links = []
                    self.in_title = False
                    self.skip_tags = {"script", "style", "nav", "footer", "header"}
                    self.current_skip = 0
                
                def handle_starttag(self, tag, attrs):
                    if tag in self.skip_tags:
                        self.current_skip += 1
                    elif tag == "title":
                        self.in_title = True
                    elif tag == "a":
                        for name, value in attrs:
                            if name == "href" and value:
                                self.links.append(value)
                
                def handle_endtag(self, tag):
                    if tag in self.skip_tags:
                        self.current_skip = max(0, self.current_skip - 1)
                    elif tag == "title":
                        self.in_title = False
                
                def handle_data(self, data):
                    if self.in_title:
                        self.title = data.strip()
                    elif self.current_skip == 0:
                        text = data.strip()
                        if text:
                            self.text_parts.append(text)
            
            extractor = ContentExtractor()
            extractor.feed(html)
            
            # 处理链接为绝对路径
            links = []
            for link in extractor.links:
                if link.startswith(("http://", "https://")):
                    links.append(link)
                elif link.startswith("/"):
                    links.append(urljoin(base_url, link))
            
            text = " ".join(extractor.text_parts)
            
            return text, extractor.title, links[:50]  # 限制链接数量
            
        except Exception as e:
            logger.warning(f"Content extraction error: {e}")
            return "", "", []
    
    async def crawl_site(
        self,
        start_url: str,
        max_pages: int = 10,
        same_domain_only: bool = True,
    ) -> list[CrawlResult]:
        """爬取整个站点
        
        Args:
            start_url: 起始 URL
            max_pages: 最大页面数
            same_domain_only: 是否只爬取同域名
            
        Returns:
            list[CrawlResult]: 爬取结果列表
        """
        visited = set()
        to_visit = [start_url]
        results = []
        
        start_domain = urlparse(start_url).netloc
        
        while to_visit and len(results) < max_pages:
            url = to_visit.pop(0)
            
            if url in visited:
                continue
            
            visited.add(url)
            result = await self.fetch(url)
            results.append(result)
            
            # 添加新链接
            if result.links:
                for link in result.links:
                    if link not in visited and link not in to_visit:
                        if same_domain_only:
                            if urlparse(link).netloc == start_domain:
                                to_visit.append(link)
                        else:
                            to_visit.append(link)
        
        return results


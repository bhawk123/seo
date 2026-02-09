"""
Smart IP/Proxy Rotation.

Implements Critical Gap #6: Smart IP/proxy rotation.

Provides intelligent proxy management for avoiding rate limits and IP blocks:
- Multiple proxy types (HTTP, SOCKS4, SOCKS5)
- Rotation strategies (round-robin, random, weighted)
- Health checking with automatic failover
- Per-domain proxy assignment (sticky sessions)
- Rate limit detection and proxy retirement
- Proxy authentication support

Features ported from Spectrum per EPIC-SEO-INFRA-001.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ProxyType(str, Enum):
    """Supported proxy types."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class RotationStrategy(str, Enum):
    """Proxy rotation strategies."""
    ROUND_ROBIN = "round_robin"  # Cycle through proxies in order
    RANDOM = "random"  # Random selection
    WEIGHTED = "weighted"  # Weighted by success rate
    STICKY = "sticky"  # Stick to same proxy per domain
    LEAST_USED = "least_used"  # Prefer proxies with fewer recent uses


class ProxyHealth(str, Enum):
    """Proxy health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Occasional failures
    UNHEALTHY = "unhealthy"  # Too many failures
    RETIRED = "retired"  # Permanently removed


@dataclass
class ProxyConfig:
    """Configuration for a single proxy."""
    host: str
    port: int
    proxy_type: ProxyType = ProxyType.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    weight: float = 1.0  # Weight for weighted selection
    max_concurrent: int = 5  # Max concurrent connections
    region: Optional[str] = None  # Geographic region
    provider: Optional[str] = None  # Proxy provider name

    @property
    def url(self) -> str:
        """Get proxy URL."""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"

    @property
    def playwright_proxy(self) -> Dict[str, Any]:
        """Get proxy config for Playwright."""
        proxy = {
            "server": f"{self.proxy_type.value}://{self.host}:{self.port}"
        }
        if self.username and self.password:
            proxy["username"] = self.username
            proxy["password"] = self.password
        return proxy


@dataclass
class ProxyStats:
    """Statistics for a proxy."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0
    blocked_requests: int = 0
    total_response_time_ms: float = 0.0
    last_used: float = 0.0
    last_success: float = 0.0
    last_failure: float = 0.0
    consecutive_failures: int = 0
    current_connections: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 1.0  # Assume healthy until proven otherwise
        return self.successful_requests / self.total_requests

    @property
    def avg_response_time_ms(self) -> float:
        """Calculate average response time."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_response_time_ms / self.successful_requests


@dataclass
class ProxyEntry:
    """A proxy with its configuration and stats."""
    config: ProxyConfig
    stats: ProxyStats = field(default_factory=ProxyStats)
    health: ProxyHealth = ProxyHealth.HEALTHY

    def record_success(self, response_time_ms: float) -> None:
        """Record a successful request."""
        self.stats.total_requests += 1
        self.stats.successful_requests += 1
        self.stats.total_response_time_ms += response_time_ms
        self.stats.last_used = time.time()
        self.stats.last_success = time.time()
        self.stats.consecutive_failures = 0

        # Upgrade health if recovering
        if self.health == ProxyHealth.DEGRADED:
            if self.stats.success_rate > 0.9:
                self.health = ProxyHealth.HEALTHY

    def record_failure(self, is_rate_limit: bool = False, is_block: bool = False) -> None:
        """Record a failed request."""
        self.stats.total_requests += 1
        self.stats.failed_requests += 1
        self.stats.last_used = time.time()
        self.stats.last_failure = time.time()
        self.stats.consecutive_failures += 1

        if is_rate_limit:
            self.stats.rate_limited_requests += 1
        if is_block:
            self.stats.blocked_requests += 1

        # Degrade health based on consecutive failures
        if self.stats.consecutive_failures >= 5:
            self.health = ProxyHealth.UNHEALTHY
        elif self.stats.consecutive_failures >= 2:
            self.health = ProxyHealth.DEGRADED

        # Check for permanent retirement
        if self.stats.blocked_requests >= 3:
            self.health = ProxyHealth.RETIRED
            logger.warning(f"Proxy {self.config.host}:{self.config.port} retired due to repeated blocks")


@dataclass
class ProxyPoolConfig:
    """Configuration for the proxy pool."""
    rotation_strategy: RotationStrategy = RotationStrategy.WEIGHTED
    health_check_interval_seconds: float = 60.0
    max_consecutive_failures: int = 5
    min_success_rate: float = 0.7  # Below this, mark as degraded
    sticky_domain_ttl_seconds: float = 300.0  # How long to stick to a proxy per domain
    rate_limit_backoff_seconds: float = 30.0  # Backoff time after rate limit
    enable_health_checks: bool = True
    health_check_url: str = "https://httpbin.org/ip"
    fallback_to_direct: bool = False  # Use direct connection if all proxies fail


class ProxyPool:
    """
    Smart proxy pool with rotation and health management.

    Features:
    - Multiple rotation strategies
    - Automatic health checking
    - Per-domain sticky sessions
    - Rate limit detection and handling
    - Weighted selection by success rate
    """

    def __init__(self, config: Optional[ProxyPoolConfig] = None):
        self.config = config or ProxyPoolConfig()
        self._proxies: List[ProxyEntry] = []
        self._domain_assignments: Dict[str, tuple] = {}  # domain -> (proxy_index, timestamp)
        self._round_robin_index: int = 0
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False

    def add_proxy(self, proxy_config: ProxyConfig) -> None:
        """Add a proxy to the pool."""
        self._proxies.append(ProxyEntry(config=proxy_config))
        logger.debug(f"Added proxy: {proxy_config.host}:{proxy_config.port}")

    def add_proxies(self, proxy_configs: List[ProxyConfig]) -> None:
        """Add multiple proxies to the pool."""
        for config in proxy_configs:
            self.add_proxy(config)

    def add_proxy_from_url(self, url: str, **kwargs) -> None:
        """
        Add a proxy from URL string.

        Args:
            url: Proxy URL (e.g., "http://user:pass@host:port")
            **kwargs: Additional ProxyConfig options
        """
        parsed = urlparse(url)
        proxy_type = ProxyType(parsed.scheme) if parsed.scheme else ProxyType.HTTP

        config = ProxyConfig(
            host=parsed.hostname or "",
            port=parsed.port or 8080,
            proxy_type=proxy_type,
            username=parsed.username,
            password=parsed.password,
            **kwargs
        )
        self.add_proxy(config)

    @property
    def healthy_proxies(self) -> List[ProxyEntry]:
        """Get list of healthy proxies."""
        return [p for p in self._proxies if p.health in (ProxyHealth.HEALTHY, ProxyHealth.DEGRADED)]

    @property
    def pool_size(self) -> int:
        """Total proxies in pool."""
        return len(self._proxies)

    @property
    def available_count(self) -> int:
        """Count of healthy proxies."""
        return len(self.healthy_proxies)

    async def start(self) -> None:
        """Start the proxy pool and health checking."""
        self._running = True
        if self.config.enable_health_checks and self._proxies:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info(f"Proxy pool started with {self.pool_size} proxies")

    async def stop(self) -> None:
        """Stop the proxy pool."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Proxy pool stopped")

    async def get_proxy(self, url: Optional[str] = None) -> Optional[ProxyEntry]:
        """
        Get a proxy for a request.

        Args:
            url: Target URL (used for sticky sessions)

        Returns:
            ProxyEntry or None if no proxies available
        """
        async with self._lock:
            if not self._proxies:
                return None

            healthy = self.healthy_proxies
            if not healthy:
                if self.config.fallback_to_direct:
                    logger.warning("No healthy proxies, falling back to direct connection")
                    return None
                # Try to use degraded proxies
                healthy = [p for p in self._proxies if p.health != ProxyHealth.RETIRED]
                if not healthy:
                    logger.error("All proxies retired")
                    return None

            # Apply rotation strategy
            if self.config.rotation_strategy == RotationStrategy.STICKY and url:
                return self._get_sticky_proxy(url, healthy)
            elif self.config.rotation_strategy == RotationStrategy.ROUND_ROBIN:
                return self._get_round_robin_proxy(healthy)
            elif self.config.rotation_strategy == RotationStrategy.RANDOM:
                return self._get_random_proxy(healthy)
            elif self.config.rotation_strategy == RotationStrategy.WEIGHTED:
                return self._get_weighted_proxy(healthy)
            elif self.config.rotation_strategy == RotationStrategy.LEAST_USED:
                return self._get_least_used_proxy(healthy)
            else:
                return self._get_random_proxy(healthy)

    def _get_sticky_proxy(self, url: str, healthy: List[ProxyEntry]) -> ProxyEntry:
        """Get sticky proxy for domain."""
        domain = urlparse(url).netloc
        now = time.time()

        if domain in self._domain_assignments:
            proxy_idx, timestamp = self._domain_assignments[domain]
            if now - timestamp < self.config.sticky_domain_ttl_seconds:
                # Check if proxy is still healthy
                if proxy_idx < len(self._proxies):
                    proxy = self._proxies[proxy_idx]
                    if proxy in healthy:
                        return proxy

        # Assign new proxy
        proxy = self._get_weighted_proxy(healthy)
        self._domain_assignments[domain] = (self._proxies.index(proxy), now)
        return proxy

    def _get_round_robin_proxy(self, healthy: List[ProxyEntry]) -> ProxyEntry:
        """Get next proxy in round-robin order."""
        self._round_robin_index = (self._round_robin_index + 1) % len(healthy)
        return healthy[self._round_robin_index]

    def _get_random_proxy(self, healthy: List[ProxyEntry]) -> ProxyEntry:
        """Get random proxy."""
        return random.choice(healthy)

    def _get_weighted_proxy(self, healthy: List[ProxyEntry]) -> ProxyEntry:
        """Get proxy weighted by success rate and config weight."""
        weights = []
        for proxy in healthy:
            # Combine config weight with success rate
            weight = proxy.config.weight * proxy.stats.success_rate
            # Penalize proxies at max connections
            if proxy.stats.current_connections >= proxy.config.max_concurrent:
                weight *= 0.1
            weights.append(max(weight, 0.01))  # Ensure non-zero

        return random.choices(healthy, weights=weights)[0]

    def _get_least_used_proxy(self, healthy: List[ProxyEntry]) -> ProxyEntry:
        """Get least recently used proxy."""
        return min(healthy, key=lambda p: p.stats.last_used)

    async def record_result(
        self,
        proxy: ProxyEntry,
        success: bool,
        response_time_ms: float = 0.0,
        is_rate_limit: bool = False,
        is_block: bool = False
    ) -> None:
        """
        Record request result for a proxy.

        Args:
            proxy: The proxy used
            success: Whether request succeeded
            response_time_ms: Response time in milliseconds
            is_rate_limit: Whether failure was due to rate limiting
            is_block: Whether failure was due to IP block
        """
        async with self._lock:
            if success:
                proxy.record_success(response_time_ms)
            else:
                proxy.record_failure(is_rate_limit=is_rate_limit, is_block=is_block)

                # If rate limited, add backoff
                if is_rate_limit:
                    logger.info(f"Rate limit on {proxy.config.host}, backing off")
                    # Could implement backoff tracking here

    async def _health_check_loop(self) -> None:
        """Background task to check proxy health."""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval_seconds)
                await self._check_all_proxies()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _check_all_proxies(self) -> None:
        """Check health of all proxies."""
        import aiohttp

        for proxy in self._proxies:
            if proxy.health == ProxyHealth.RETIRED:
                continue

            try:
                start = time.time()
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.config.health_check_url,
                        proxy=proxy.config.url,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            elapsed_ms = (time.time() - start) * 1000
                            proxy.record_success(elapsed_ms)
                            logger.debug(f"Proxy {proxy.config.host} healthy ({elapsed_ms:.0f}ms)")
                        else:
                            proxy.record_failure()
            except Exception as e:
                proxy.record_failure()
                logger.debug(f"Proxy {proxy.config.host} health check failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "total_proxies": self.pool_size,
            "healthy_proxies": len([p for p in self._proxies if p.health == ProxyHealth.HEALTHY]),
            "degraded_proxies": len([p for p in self._proxies if p.health == ProxyHealth.DEGRADED]),
            "unhealthy_proxies": len([p for p in self._proxies if p.health == ProxyHealth.UNHEALTHY]),
            "retired_proxies": len([p for p in self._proxies if p.health == ProxyHealth.RETIRED]),
            "strategy": self.config.rotation_strategy.value,
            "proxies": [
                {
                    "host": p.config.host,
                    "port": p.config.port,
                    "health": p.health.value,
                    "success_rate": p.stats.success_rate,
                    "total_requests": p.stats.total_requests,
                    "avg_response_ms": p.stats.avg_response_time_ms,
                }
                for p in self._proxies
            ]
        }


def load_proxies_from_file(filepath: str) -> List[ProxyConfig]:
    """
    Load proxies from a file.

    Supports formats:
    - One URL per line: http://user:pass@host:port
    - CSV: host,port,type,username,password

    Args:
        filepath: Path to proxy file

    Returns:
        List of ProxyConfig objects
    """
    proxies = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if '://' in line:
                # URL format
                parsed = urlparse(line)
                proxy_type = ProxyType(parsed.scheme) if parsed.scheme else ProxyType.HTTP
                proxies.append(ProxyConfig(
                    host=parsed.hostname or "",
                    port=parsed.port or 8080,
                    proxy_type=proxy_type,
                    username=parsed.username,
                    password=parsed.password,
                ))
            elif ',' in line:
                # CSV format
                parts = line.split(',')
                if len(parts) >= 2:
                    proxies.append(ProxyConfig(
                        host=parts[0],
                        port=int(parts[1]),
                        proxy_type=ProxyType(parts[2]) if len(parts) > 2 else ProxyType.HTTP,
                        username=parts[3] if len(parts) > 3 else None,
                        password=parts[4] if len(parts) > 4 else None,
                    ))

    return proxies


def create_proxy_pool_from_env() -> ProxyPool:
    """
    Create proxy pool from environment variables.

    Environment variables:
    - PROXY_URLS: Comma-separated proxy URLs
    - PROXY_FILE: Path to proxy file
    - PROXY_ROTATION: Rotation strategy (round_robin, random, weighted, sticky)

    Returns:
        Configured ProxyPool
    """
    import os

    strategy = RotationStrategy(os.getenv("PROXY_ROTATION", "weighted"))
    pool = ProxyPool(ProxyPoolConfig(rotation_strategy=strategy))

    # Load from URLs
    proxy_urls = os.getenv("PROXY_URLS", "")
    if proxy_urls:
        for url in proxy_urls.split(","):
            url = url.strip()
            if url:
                pool.add_proxy_from_url(url)

    # Load from file
    proxy_file = os.getenv("PROXY_FILE", "")
    if proxy_file and os.path.exists(proxy_file):
        configs = load_proxies_from_file(proxy_file)
        pool.add_proxies(configs)

    return pool

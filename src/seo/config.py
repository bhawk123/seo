from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import json
import os

load_dotenv()  # Loads variables from .env file


class Settings:
    """
    Manages application settings loaded from environment variables.
    """
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    AHREFS_API_KEY = os.getenv("AHREFS_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///seo_data.db")  # Default to SQLite

    # Database backend configuration
    DB_BACKEND = os.getenv("DB_BACKEND", "local")  # 'local' or 'turso'
    TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")  # e.g., libsql://your-db.turso.io
    TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

    # LLM settings (moved from Config for consistency)
    LLM_API_KEY = os.getenv("LLM_API_KEY")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
    USER_AGENT = os.getenv("USER_AGENT", "SEO-Analyzer-Bot/1.0")


settings = Settings()


@dataclass
class Config:
    """Configuration for SEO Analyzer."""
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4"
    llm_provider: str = "openai"
    user_agent: str = "SEO-Analyzer-Bot/1.0"
    timeout: int = 30
    max_concurrent_requests: int = 10
    log_level: str = "INFO"

    # PageSpeed Insights API
    google_psi_api_key: Optional[str] = None
    psi_strategy: str = "mobile"  # 'mobile' or 'desktop'
    psi_locale: str = "en"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.

        Returns:
            Config: Configuration instance with values from environment
        """
        return cls(
            llm_api_key=os.getenv("LLM_API_KEY"),
            llm_model=os.getenv("LLM_MODEL", "gpt-4"),
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            user_agent=os.getenv("USER_AGENT", "SEO-Analyzer-Bot/1.0"),
            timeout=int(os.getenv("TIMEOUT", "30")),
            max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "10")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            # PageSpeed Insights
            google_psi_api_key=os.getenv("GOOGLE_PSI_API_KEY"),
            psi_strategy=os.getenv("PSI_STRATEGY", "mobile"),
            psi_locale=os.getenv("PSI_LOCALE", "en"),
        )


@dataclass
class AnalysisThresholds:
    """Configurable thresholds for SEO analysis."""

    # Technical SEO
    meta_description_min: int = 120
    meta_description_max: int = 160
    title_min: int = 30
    title_max: int = 60
    slow_page_seconds: float = 3.0
    thin_content_words: int = 300

    # Core Web Vitals (milliseconds for time-based, decimal for CLS)
    lcp_good: float = 2500
    lcp_poor: float = 4000
    inp_good: int = 200
    inp_poor: int = 500
    cls_good: float = 0.1
    cls_poor: float = 0.25
    fcp_good: int = 1800
    fcp_poor: int = 3000
    tbt_good: int = 200  # Total Blocking Time (ms)
    tbt_poor: int = 600
    fid_good: int = 100  # First Input Delay (ms)
    fid_poor: int = 300

    # Resource sizes (bytes)
    max_js_size: int = 500 * 1024  # 500KB
    max_css_size: int = 200 * 1024  # 200KB
    max_image_size: int = 1024 * 1024  # 1MB
    max_page_weight: int = 2 * 1024 * 1024  # 2MB
    max_font_size: int = 100 * 1024  # 100KB

    # URL structure
    max_url_length: int = 100
    max_url_depth: int = 4
    max_url_parameters: int = 3

    # Security
    hsts_min_max_age: int = 31536000  # 1 year in seconds

    # Content quality
    min_readability_score: float = 50.0
    keyword_stuffing_threshold: float = 3.0  # percentage

    # Images
    lazy_load_threshold: int = 3  # Images after this position should be lazy

    # Redirects
    redirect_ms_per_hop: int = 100  # Estimated ms per redirect hop
    redirect_long_chain_threshold: int = 3  # Chains >= this are "long"

    # Lab vs Field comparison
    lab_field_significant_gap: float = 20.0  # Percentage difference considered significant

    # Console errors
    console_error_top_count: int = 10  # Number of top errors to show
    console_pages_top_count: int = 20  # Number of top pages to show

    # Third-party
    third_party_high_percentage: float = 30.0  # % of page weight considered high
    third_party_high_requests: int = 20  # Requests per page considered high

    # Social meta
    social_og_coverage_target: float = 80.0  # Target OG coverage %
    social_twitter_coverage_target: float = 80.0  # Target Twitter coverage %

    # Human-like interaction simulation (Epic 9.2.4)
    human_sim_min_char_delay_ms: int = 50  # Minimum typing delay per character
    human_sim_max_char_delay_ms: int = 150  # Maximum typing delay per character
    human_sim_typo_rate: float = 0.05  # Probability of typo per character (0.0-1.0)
    human_sim_typo_correction_delay_ms: int = 100  # Delay before correcting typo
    human_sim_min_pause_seconds: float = 0.3  # Minimum thinking pause
    human_sim_max_pause_seconds: float = 1.5  # Maximum thinking pause
    human_sim_pre_click_delay_ms: int = 100  # Delay before clicking
    human_sim_max_click_offset_px: int = 3  # Random offset added to clicks
    human_sim_mouse_move_steps: int = 10  # Steps in mouse movement
    human_sim_mouse_move_jitter_px: int = 2  # Jitter added to mouse movement
    human_sim_fast_mode: bool = False  # Skip all human simulation when True

    @classmethod
    def from_env(cls) -> "AnalysisThresholds":
        """Load thresholds from environment variables.

        Environment variables should be prefixed with SEO_THRESHOLD_
        e.g., SEO_THRESHOLD_SLOW_PAGE_SECONDS=4.0

        Returns:
            AnalysisThresholds with values from environment
        """
        thresholds = cls()
        prefix = "SEO_THRESHOLD_"

        for field_name in thresholds.__dataclass_fields__:
            env_key = f"{prefix}{field_name.upper()}"
            env_value = os.getenv(env_key)

            if env_value is not None:
                field_type = thresholds.__dataclass_fields__[field_name].type
                try:
                    if field_type == int:
                        setattr(thresholds, field_name, int(env_value))
                    elif field_type == float:
                        setattr(thresholds, field_name, float(env_value))
                except ValueError:
                    pass  # Keep default if conversion fails

        return thresholds

    @classmethod
    def from_file(cls, path: str) -> "AnalysisThresholds":
        """Load thresholds from a JSON configuration file.

        Args:
            path: Path to JSON configuration file

        Returns:
            AnalysisThresholds with values from file
        """
        thresholds = cls()
        file_path = Path(path)

        if not file_path.exists():
            return thresholds

        with open(file_path, 'r') as f:
            config = json.load(f)

        threshold_config = config.get('thresholds', config)

        for field_name in thresholds.__dataclass_fields__:
            if field_name in threshold_config:
                setattr(thresholds, field_name, threshold_config[field_name])

        return thresholds

    def to_dict(self) -> dict:
        """Convert thresholds to dictionary.

        Returns:
            Dictionary of all threshold values
        """
        return {
            field_name: getattr(self, field_name)
            for field_name in self.__dataclass_fields__
        }

    def save_to_file(self, path: str) -> None:
        """Save current thresholds to a JSON file.

        Args:
            path: Path to save configuration
        """
        with open(path, 'w') as f:
            json.dump({'thresholds': self.to_dict()}, f, indent=2)


# Global default thresholds instance
default_thresholds = AnalysisThresholds()
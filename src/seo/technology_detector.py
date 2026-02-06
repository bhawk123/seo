"""Technology stack detection for websites.

Detects CMS, ecommerce platforms, frameworks, CDNs, analytics, fonts, and more.
Includes evidence capture for all detections to support audit trails.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Set, Any, Optional, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from seo.models import (
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)

try:
    from Wappalyzer import Wappalyzer, WebPage
    WAPPALYZER_AVAILABLE = True
except ImportError:
    WAPPALYZER_AVAILABLE = False
    logging.warning("python-Wappalyzer not installed. Technology detection will be limited.")

logger = logging.getLogger(__name__)


class TechnologyDetector:
    """Detects technologies used by a website."""

    # Technology categories
    CATEGORIES = {
        'CMS': ['WordPress', 'Drupal', 'Joomla', 'Wix', 'Squarespace', 'Webflow',
                'Contentful', 'Strapi', 'Ghost', 'Craft CMS', 'Umbraco', 'Sitecore',
                'Adobe Experience Manager', 'Kentico', 'DotCMS'],
        'Ecommerce': ['Shopify', 'WooCommerce', 'Magento/Adobe Commerce', 'BigCommerce', 'PrestaShop',
                      'OpenCart', 'Salesforce Commerce Cloud', 'SAP Commerce Cloud',
                      'Oracle ATG', 'commercetools', 'Shopware', 'Shopify Plus',
                      'Salesforce B2C Commerce', 'Salesforce Order Management',
                      'Demandware', 'Hybris', 'Vtex', 'Spryker', 'Elastic Path'],
        'JavaScript Frameworks': ['React', 'Vue.js', 'Angular', 'Svelte', 'Next.js',
                                   'Nuxt.js', 'Gatsby', 'Ember.js', 'Backbone.js',
                                   'Preact', 'Alpine.js', 'Solid.js', 'Qwik', 'Astro'],
        'JavaScript Libraries': ['jQuery', 'Lodash', 'Underscore.js', 'Moment.js',
                                'Day.js', 'Axios', 'RxJS', 'D3.js', 'Three.js',
                                'Chart.js', 'Leaflet', 'GSAP', 'Anime.js', 'Swiper',
                                'Slick', 'AOS', 'WOW.js', 'ScrollReveal', 'Isotope',
                                'Masonry', 'Parallax.js', 'Typed.js', 'CountUp.js'],
        'CSS Frameworks': ['Bootstrap', 'Tailwind CSS', 'Foundation', 'Bulma',
                           'Material-UI', 'Ant Design', 'Semantic UI', 'Chakra UI',
                           'Materialize', 'UIKit', 'Pure.css', 'Skeleton'],
        'Font Services': ['Google Font API', 'Adobe Fonts', 'Font Awesome', 'Typekit',
                         'Fonts.com', 'MyFonts', 'Cloud.typography', 'Fontstand'],
        'CDN': ['Cloudflare', 'Amazon CloudFront', 'Fastly', 'Akamai', 'CloudCDN',
                'jsDelivr', 'cdnjs', 'unpkg', 'StackPath', 'KeyCDN', 'BunnyCDN',
                'CloudFront', 'MaxCDN', 'Incapsula', 'Sucuri CDN'],
        'Analytics': ['Google Analytics', 'Google Tag Manager', 'Adobe Analytics',
                      'Hotjar', 'Mixpanel', 'Segment', 'Heap', 'Matomo', 'Piwik',
                      'Clicky', 'Fathom', 'Plausible', 'Amplitude', 'Kissmetrics',
                      'Crazy Egg', 'Mouseflow', 'FullStory', 'LogRocket',
                      'Coremetrics', 'IBM Digital Analytics', 'Webtrends'],
        'Advertising': ['Google Ads', 'Google AdSense', 'Google DoubleClick',
                       'Facebook Pixel', 'Twitter Ads', 'LinkedIn Insight Tag',
                       'Bing Ads', 'Taboola', 'Outbrain', 'Criteo', 'AdRoll',
                       'Perfect Audience', 'Quantcast', 'Media.net'],
        'Marketing Automation': ['HubSpot', 'Marketo', 'Pardot', 'Mailchimp', 'Klaviyo',
                                'Drift', 'Intercom', 'Zendesk', 'Eloqua', 'ActiveCampaign',
                                'Salesforce Marketing Cloud', 'Adobe Campaign',
                                'SendGrid', 'Campaign Monitor', 'Constant Contact',
                                'Omnisend', 'Drip', 'ConvertKit'],
        'Personalization': ['Optimizely', 'VWO', 'Adobe Target', 'Dynamic Yield',
                           'Monetate', 'Evergage', 'Qubit', 'Kameleoon', 'AB Tasty',
                           'Personyze', 'RichRelevance', 'Nosto', 'Barilliance'],
        'Search': ['Algolia', 'Elasticsearch', 'Apache Solr', 'Swiftype', 'Coveo',
                  'Searchspring', 'Klevu', 'Constructor.io', 'Bloomreach', 'Attraqt',
                  'InstantSearch.js', 'Doofinder', 'Site Search 360'],
        'Recommendation Engines': ['Nosto', 'Dynamic Yield', 'Monetate', 'Certona',
                                   'RichRelevance', 'Barilliance', 'Clerk.io',
                                   'LimeSpot', 'Reflektion', 'SALESmanago'],
        'Web Servers': ['Apache', 'Nginx', 'Microsoft IIS', 'LiteSpeed', 'Cloudflare',
                       'OpenResty', 'Caddy', 'Tomcat', 'Jetty', 'GlassFish'],
        'Programming Languages': ['PHP', 'Node.js', 'Python', 'Ruby', 'Java', 'ASP.NET',
                                 'Go', 'Rust', 'Scala', 'Elixir', 'Perl'],
        'Backend Frameworks': ['Express.js', 'Django', 'Flask', 'Ruby on Rails', 'Spring',
                              'Laravel', 'Symfony', 'FastAPI', 'NestJS', 'Koa'],
        'Caching': ['Varnish', 'Redis', 'Memcached', 'Cloudflare', 'Nginx Cache',
                   'W3 Total Cache', 'WP Super Cache', 'LiteSpeed Cache'],
        'Payment': ['Stripe', 'PayPal', 'Square', 'Braintree', 'Adyen', 'Authorize.Net',
                   'Worldpay', '2Checkout', 'Klarna', 'Afterpay', 'Affirm',
                   'Amazon Pay', 'Apple Pay', 'Google Pay', 'Venmo'],
        'Tag Managers': ['Google Tag Manager', 'Adobe Launch', 'Segment', 'Tealium',
                        'Ensighten', 'Signal', 'Piwik PRO Tag Manager'],
        'Video': ['YouTube', 'Vimeo', 'Wistia', 'Brightcove', 'JW Player',
                 'Vidyard', 'Kaltura', 'Sprout Video', 'Dailymotion'],
        'Live Chat': ['Intercom', 'Drift', 'Zendesk Chat', 'LiveChat', 'Olark',
                     'Tawk.to', 'Crisp', 'Freshchat', 'HubSpot Chat', 'Tidio'],
        'A/B Testing': ['Optimizely', 'VWO', 'Google Optimize', 'AB Tasty',
                       'Convert', 'Kameleoon', 'SplitIO', 'Unbounce'],
        'Accessibility': ['accessiBe', 'UserWay', 'AudioEye', 'EqualWeb', 'Recite Me'],
        'Security': ['Cloudflare', 'Sucuri', 'Wordfence', 'Imperva', 'PerimeterX',
                    'Distil Networks', 'DataDome', 'Akamai Bot Manager'],
        'API Technologies': ['GraphQL', 'Apollo', 'Relay', 'REST', 'gRPC'],
        'Hosting Platforms': ['Vercel', 'Netlify', 'AWS', 'Azure', 'Google Cloud',
                             'Heroku', 'DigitalOcean', 'Linode', 'Cloudflare Pages'],
        'Application Gateways': ['Varnish', 'HAProxy', 'Nginx Cache', 'Squid'],
    }

    def __init__(self):
        """Initialize technology detector."""
        self.wappalyzer = None
        # Evidence collection for current detection run
        self._evidence: Dict[str, EvidenceCollection] = {}

        if WAPPALYZER_AVAILABLE:
            try:
                self.wappalyzer = Wappalyzer.latest()
                logger.info("Wappalyzer initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Wappalyzer: {e}")
                self.wappalyzer = None

    def _add_evidence(
        self,
        tech_name: str,
        matched_string: str,
        pattern: str,
        source_type: EvidenceSourceType,
        source_location: Optional[str] = None,
    ) -> None:
        """Add evidence for a technology detection.

        Args:
            tech_name: Name of the detected technology
            matched_string: The actual string that was matched
            pattern: The regex pattern used
            source_type: Type of evidence source
            source_location: Where the match was found (URL, header name, etc.)
        """
        if tech_name not in self._evidence:
            self._evidence[tech_name] = EvidenceCollection(
                finding=tech_name,
                component_id='technology_detection',
            )

        record = EvidenceRecord.from_pattern_match(
            component_id='technology_detection',
            finding=tech_name,
            matched_string=matched_string,
            pattern=pattern,
            source_location=source_location or 'HTML content',
            source_type=source_type,
        )
        self._evidence[tech_name].add_record(record)

    def _detect_pattern(
        self,
        pattern: str,
        html: str,
        tech_name: str,
        source_type: EvidenceSourceType = EvidenceSourceType.HTML_CONTENT,
        source_location: Optional[str] = None,
        flags: int = 0,
    ) -> bool:
        """Detect a pattern and capture evidence if found.

        Args:
            pattern: Regex pattern to search for
            html: Content to search in
            tech_name: Technology name to associate with detection
            source_type: Type of evidence source
            source_location: Where the search is being performed
            flags: Regex flags (e.g., re.IGNORECASE)

        Returns:
            True if pattern was found, False otherwise
        """
        match = re.search(pattern, html, flags)
        if match:
            matched_string = match.group(0)
            self._add_evidence(
                tech_name=tech_name,
                matched_string=matched_string,
                pattern=pattern,
                source_type=source_type,
                source_location=source_location,
            )
            return True
        return False

    def detect(
        self,
        url: str,
        html: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Detect technologies used by a website.

        Args:
            url: The URL of the page
            html: HTML content of the page
            headers: HTTP response headers

        Returns:
            Dictionary with detected technologies organized by category,
            including evidence records for each detection
        """
        technologies = set()
        headers = headers or {}
        # Reset evidence collection for this detection run
        self._evidence = {}

        # Use Wappalyzer for main detection
        if self.wappalyzer:
            try:
                webpage = WebPage(url, html, headers)
                detected = self.wappalyzer.analyze(webpage)
                technologies.update(detected)
                # Add evidence for Wappalyzer detections
                for tech in detected:
                    if tech not in self._evidence:
                        self._evidence[tech] = EvidenceCollection(
                            finding=tech,
                            component_id='technology_detection',
                        )
                    record = EvidenceRecord(
                        component_id='technology_detection',
                        finding=tech,
                        evidence_string='Detected by Wappalyzer library',
                        confidence=ConfidenceLevel.HIGH,
                        timestamp=datetime.now(),
                        source='Wappalyzer',
                        source_type=EvidenceSourceType.PATTERN_MATCH,
                    )
                    self._evidence[tech].add_record(record)
                logger.debug(f"Wappalyzer detected: {detected}")
            except Exception as e:
                logger.warning(f"Wappalyzer detection failed: {e}")

        # Custom detection for additional technologies
        soup = BeautifulSoup(html, 'html.parser')
        custom_detected = self._custom_detection(url, html, soup, headers)
        technologies.update(custom_detected)

        # Organize by category
        categorized = self._categorize_technologies(technologies)

        # Get detailed info (enhanced with evidence)
        detailed = self._get_technology_details(technologies, url, html, soup, headers)

        # Build evidence summary
        evidence_summary = {
            tech: self._evidence[tech].to_dict()
            for tech in technologies
            if tech in self._evidence
        }

        return {
            'all_technologies': sorted(list(technologies)),
            'by_category': categorized,
            'details': detailed,
            'evidence': evidence_summary,
            'total_count': len(technologies),
        }

    def _custom_detection(
        self,
        url: str,
        html: str,
        soup: BeautifulSoup,
        headers: Dict[str, str]
    ) -> Set[str]:
        """Custom detection logic for technologies Wappalyzer might miss.

        All detections capture evidence including the matched pattern and string.

        Args:
            url: Page URL
            html: HTML content
            soup: BeautifulSoup parsed HTML
            headers: HTTP headers

        Returns:
            Set of detected technology names
        """
        detected = set()

        # CDN Detection from URLs (with evidence capture)
        cdn_patterns = {
            'Cloudflare': [r'cloudflare\.com', r'cdnjs\.cloudflare\.com', r'cf-ray'],
            'Akamai': [r'akamai\.net', r'akamaihd\.net', r'akamaized\.net'],
            'Amazon CloudFront': [r'cloudfront\.net'],
            'Fastly': [r'fastly\.net', r'fastlylb\.net'],
            'jsDelivr': [r'jsdelivr\.net'],
            'unpkg': [r'unpkg\.com'],
            'StackPath': [r'stackpath\.bootstrapcdn\.com'],
            'KeyCDN': [r'keycdn\.com'],
            'BunnyCDN': [r'bunnycdn\.com'],
        }

        for cdn, patterns in cdn_patterns.items():
            for pattern in patterns:
                if self._detect_pattern(pattern, html, cdn, flags=re.IGNORECASE):
                    detected.add(cdn)
                    break

        # Google Services (with evidence capture)
        if self._detect_pattern(r'fonts\.googleapis\.com', html, 'Google Font API'):
            detected.add('Google Font API')
        if self._detect_pattern(r'google-analytics\.com|ga\.js|analytics\.js', html, 'Google Analytics'):
            detected.add('Google Analytics')
        if self._detect_pattern(r'googletagmanager\.com|gtm\.js', html, 'Google Tag Manager'):
            detected.add('Google Tag Manager')
        if self._detect_pattern(r'googlesyndication\.com|adsbygoogle', html, 'Google AdSense'):
            detected.add('Google AdSense')
        if self._detect_pattern(r'doubleclick\.net|googleadservices\.com', html, 'Google DoubleClick'):
            detected.add('Google DoubleClick')
        if self._detect_pattern(r'googleadservices\.com|google\.com/ads', html, 'Google Ads'):
            detected.add('Google Ads')
        if self._detect_pattern(r'maps\.googleapis\.com|maps\.google\.com', html, 'Google Maps'):
            detected.add('Google Maps')
        if self._detect_pattern(r'recaptcha', html, 'Google reCAPTCHA', flags=re.IGNORECASE):
            detected.add('Google reCAPTCHA')
        if self._detect_pattern(r'optimize\.google\.com', html, 'Google Optimize'):
            detected.add('Google Optimize')

        # Font Services (with evidence capture for BeautifulSoup matches)
        adobe_link = soup.find('link', href=re.compile(r'fonts\.adobe\.com|typekit'))
        if adobe_link:
            href = adobe_link.get('href', '')
            self._add_evidence('Adobe Fonts', href, r'fonts\.adobe\.com|typekit',
                             EvidenceSourceType.LINK_HREF, f'link[href="{href}"]')
            detected.add('Adobe Fonts')

        fa_link = soup.find('link', href=re.compile(r'fontawesome\.com'))
        fa_icon = soup.find('i', class_=re.compile(r'fa-'))
        if fa_link:
            href = fa_link.get('href', '')
            self._add_evidence('Font Awesome', href, r'fontawesome\.com',
                             EvidenceSourceType.LINK_HREF, f'link[href="{href}"]')
            detected.add('Font Awesome')
        elif fa_icon:
            classes = ' '.join(fa_icon.get('class', []))
            self._add_evidence('Font Awesome', classes, r'fa-',
                             EvidenceSourceType.HTML_ATTRIBUTE, 'i[class*="fa-"]')
            detected.add('Font Awesome')
        elif self._detect_pattern(r'font-awesome', html, 'Font Awesome', flags=re.IGNORECASE):
            detected.add('Font Awesome')

        # Ecommerce Platforms (with evidence capture)
        if self._detect_pattern(r'shopify\.com|cdn\.shopify\.com|myshopify\.com', html, 'Shopify'):
            detected.add('Shopify')
        if self._detect_pattern(r'woocommerce', html, 'WooCommerce', flags=re.IGNORECASE):
            detected.add('WooCommerce')
        if self._detect_pattern(r'magento|mage\.js|mage/|varien/', html, 'Magento/Adobe Commerce', flags=re.IGNORECASE):
            detected.add('Magento/Adobe Commerce')
        if self._detect_pattern(r'bigcommerce\.com', html, 'BigCommerce'):
            detected.add('BigCommerce')
        if self._detect_pattern(r'demandware|dwanalytics|dw\.ac|dw\.engine', html, 'Salesforce Commerce Cloud', flags=re.IGNORECASE):
            detected.add('Salesforce Commerce Cloud')
        if self._detect_pattern(r'salesforce.*commerce|sfcc|demandware', html, 'Salesforce B2C Commerce', flags=re.IGNORECASE):
            detected.add('Salesforce B2C Commerce')
        if self._detect_pattern(r'commercetools|ctp\.com', html, 'commercetools', flags=re.IGNORECASE):
            detected.add('commercetools')
        if self._detect_pattern(r'hybris|/medias/_ui/|hac/platform', html, 'SAP Commerce Cloud', flags=re.IGNORECASE):
            detected.add('SAP Commerce Cloud')
        if self._detect_pattern(r'atg\.commerce|oracle.*atg|dynamo', html, 'Oracle ATG', flags=re.IGNORECASE):
            detected.add('Oracle ATG')
        if self._detect_pattern(r'vtex\.com|vteximg\.com|vtexassets\.com', html, 'Vtex', flags=re.IGNORECASE):
            detected.add('Vtex')
        if self._detect_pattern(r'spryker|yves|zed\.', html, 'Spryker', flags=re.IGNORECASE):
            detected.add('Spryker')

        # CMS Detection (with evidence capture)
        wp_meta = soup.find('meta', {'name': 'generator', 'content': re.compile(r'WordPress', re.I)})
        if wp_meta:
            content = wp_meta.get('content', '')
            self._add_evidence('WordPress', content, r'WordPress',
                             EvidenceSourceType.META_TAG, 'meta[name="generator"]')
            detected.add('WordPress')
        if self._detect_pattern(r'wp-content|wp-includes|/wp-json/', html, 'WordPress'):
            detected.add('WordPress')
        if self._detect_pattern(r'drupal|sites/default|sites/all', html, 'Drupal', flags=re.IGNORECASE):
            detected.add('Drupal')
        if self._detect_pattern(r'joomla', html, 'Joomla', flags=re.IGNORECASE):
            detected.add('Joomla')
        if self._detect_pattern(r'contentful\.com', html, 'Contentful', flags=re.IGNORECASE):
            detected.add('Contentful')
        if self._detect_pattern(r'strapi', html, 'Strapi', flags=re.IGNORECASE):
            detected.add('Strapi')
        if self._detect_pattern(r'ghost\.org|ghost\.io', html, 'Ghost', flags=re.IGNORECASE):
            detected.add('Ghost')
        if self._detect_pattern(r'sitecore', html, 'Sitecore', flags=re.IGNORECASE):
            detected.add('Sitecore')
        if self._detect_pattern(r'aem\.|\baem\b|adobe.*experience', html, 'Adobe Experience Manager', flags=re.IGNORECASE):
            detected.add('Adobe Experience Manager')

        # JavaScript Frameworks (with evidence capture)
        react_detected = self._detect_pattern(r'react(?:\.js)?|react-dom|__react', html, 'React', flags=re.IGNORECASE)
        react_root = soup.find('div', id='root')
        react_app = soup.find('div', id='app')
        if react_detected:
            detected.add('React')
        elif react_root:
            self._add_evidence('React', 'div#root', r'div#root',
                             EvidenceSourceType.HTML_ATTRIBUTE, 'div[id="root"]')
            detected.add('React')
        elif react_app:
            self._add_evidence('React', 'div#app', r'div#app',
                             EvidenceSourceType.HTML_ATTRIBUTE, 'div[id="app"]')
            detected.add('React')

        if self._detect_pattern(r'vue(?:\.js)?|vuejs|__vue', html, 'Vue.js', flags=re.IGNORECASE):
            detected.add('Vue.js')
        if self._detect_pattern(r'angular(?:\.js)?|ng-app|ng-controller', html, 'Angular', flags=re.IGNORECASE):
            detected.add('Angular')
        if self._detect_pattern(r'svelte', html, 'Svelte', flags=re.IGNORECASE):
            detected.add('Svelte')
        if self._detect_pattern(r'next(?:\.js)?|_next/static|__NEXT_DATA__', html, 'Next.js', flags=re.IGNORECASE):
            detected.add('Next.js')
        if self._detect_pattern(r'nuxt(?:\.js)?|__NUXT__', html, 'Nuxt.js', flags=re.IGNORECASE):
            detected.add('Nuxt.js')
        if self._detect_pattern(r'gatsby|___gatsby', html, 'Gatsby', flags=re.IGNORECASE):
            detected.add('Gatsby')
        if self._detect_pattern(r'ember(?:\.js)?', html, 'Ember.js', flags=re.IGNORECASE):
            detected.add('Ember.js')

        # JavaScript Libraries (with evidence capture)
        if self._detect_pattern(r'jquery(?:[.-]\d+)?\.(?:min\.)?js', html, 'jQuery', flags=re.IGNORECASE):
            detected.add('jQuery')
        if self._detect_pattern(r'lodash|underscore', html, 'Lodash', flags=re.IGNORECASE):
            detected.add('Lodash')
        if self._detect_pattern(r'moment(?:\.js)?', html, 'Moment.js', flags=re.IGNORECASE):
            detected.add('Moment.js')
        if self._detect_pattern(r'd3(?:\.js)?|d3\.v[0-9]', html, 'D3.js', flags=re.IGNORECASE):
            detected.add('D3.js')
        if self._detect_pattern(r'three(?:\.js)?|three\.min', html, 'Three.js', flags=re.IGNORECASE):
            detected.add('Three.js')
        if self._detect_pattern(r'chart(?:\.js)?', html, 'Chart.js', flags=re.IGNORECASE):
            detected.add('Chart.js')
        if self._detect_pattern(r'gsap|TweenMax|TimelineLite', html, 'GSAP', flags=re.IGNORECASE):
            detected.add('GSAP')
        if self._detect_pattern(r'swiper', html, 'Swiper', flags=re.IGNORECASE):
            detected.add('Swiper')
        if self._detect_pattern(r'slick(?:-carousel)?', html, 'Slick', flags=re.IGNORECASE):
            detected.add('Slick')

        # CSS Frameworks (with evidence capture)
        if self._detect_pattern(r'bootstrap(?:\.min)?\.css|bootstrap\.css', html, 'Bootstrap', flags=re.IGNORECASE):
            detected.add('Bootstrap')
        if self._detect_pattern(r'tailwind', html, 'Tailwind CSS', flags=re.IGNORECASE):
            detected.add('Tailwind CSS')
        if self._detect_pattern(r'foundation\.css|zurb', html, 'Foundation', flags=re.IGNORECASE):
            detected.add('Foundation')
        if self._detect_pattern(r'bulma', html, 'Bulma', flags=re.IGNORECASE):
            detected.add('Bulma')
        if self._detect_pattern(r'material-ui|mui', html, 'Material-UI', flags=re.IGNORECASE):
            detected.add('Material-UI')

        # Analytics & Marketing (with evidence capture)
        if self._detect_pattern(r'hotjar', html, 'Hotjar', flags=re.IGNORECASE):
            detected.add('Hotjar')
        if self._detect_pattern(r'mixpanel', html, 'Mixpanel', flags=re.IGNORECASE):
            detected.add('Mixpanel')
        if self._detect_pattern(r'segment\.com|analytics\.js', html, 'Segment'):
            detected.add('Segment')
        if self._detect_pattern(r'amplitude', html, 'Amplitude', flags=re.IGNORECASE):
            detected.add('Amplitude')
        if self._detect_pattern(r'heap', html, 'Heap', flags=re.IGNORECASE):
            detected.add('Heap')
        if self._detect_pattern(r'matomo|piwik', html, 'Matomo', flags=re.IGNORECASE):
            detected.add('Matomo')
        if self._detect_pattern(r'adobe.*analytics|omniture|s_code\.js', html, 'Adobe Analytics', flags=re.IGNORECASE):
            detected.add('Adobe Analytics')
        if self._detect_pattern(r'coremetrics|cmcreate|eluminate', html, 'Coremetrics', flags=re.IGNORECASE):
            detected.add('Coremetrics')
        if self._detect_pattern(r'crazyegg', html, 'Crazy Egg', flags=re.IGNORECASE):
            detected.add('Crazy Egg')
        if self._detect_pattern(r'fullstory', html, 'FullStory', flags=re.IGNORECASE):
            detected.add('FullStory')
        if self._detect_pattern(r'logrocket', html, 'LogRocket', flags=re.IGNORECASE):
            detected.add('LogRocket')

        # Advertising (with evidence capture)
        if self._detect_pattern(r'facebook.*pixel|fbevents\.js|fbq\(', html, 'Facebook Pixel', flags=re.IGNORECASE):
            detected.add('Facebook Pixel')
        if self._detect_pattern(r'linkedin\.com/in/px/|_linkedin_partner_id', html, 'LinkedIn Insight Tag', flags=re.IGNORECASE):
            detected.add('LinkedIn Insight Tag')
        if self._detect_pattern(r'bing\.com/uet|bat\.bing\.com', html, 'Bing Ads', flags=re.IGNORECASE):
            detected.add('Bing Ads')
        if self._detect_pattern(r'taboola', html, 'Taboola', flags=re.IGNORECASE):
            detected.add('Taboola')
        if self._detect_pattern(r'outbrain', html, 'Outbrain', flags=re.IGNORECASE):
            detected.add('Outbrain')
        if self._detect_pattern(r'criteo', html, 'Criteo', flags=re.IGNORECASE):
            detected.add('Criteo')
        if self._detect_pattern(r'adroll', html, 'AdRoll', flags=re.IGNORECASE):
            detected.add('AdRoll')

        # Marketing Automation (with evidence capture)
        if self._detect_pattern(r'hubspot|hs-analytics|_hsp', html, 'HubSpot', flags=re.IGNORECASE):
            detected.add('HubSpot')
        if self._detect_pattern(r'marketo|munchkin', html, 'Marketo', flags=re.IGNORECASE):
            detected.add('Marketo')
        if self._detect_pattern(r'pardot', html, 'Pardot', flags=re.IGNORECASE):
            detected.add('Pardot')
        if self._detect_pattern(r'mailchimp', html, 'Mailchimp', flags=re.IGNORECASE):
            detected.add('Mailchimp')
        if self._detect_pattern(r'klaviyo', html, 'Klaviyo', flags=re.IGNORECASE):
            detected.add('Klaviyo')
        if self._detect_pattern(r'eloqua', html, 'Eloqua', flags=re.IGNORECASE):
            detected.add('Eloqua')
        if self._detect_pattern(r'sendgrid', html, 'SendGrid', flags=re.IGNORECASE):
            detected.add('SendGrid')
        if self._detect_pattern(r'salesforce.*marketing|exacttarget', html, 'Salesforce Marketing Cloud', flags=re.IGNORECASE):
            detected.add('Salesforce Marketing Cloud')

        # Search Solutions (with evidence capture)
        if self._detect_pattern(r'algolia|algoliasearch', html, 'Algolia', flags=re.IGNORECASE):
            detected.add('Algolia')
        if self._detect_pattern(r'elasticsearch|elastic\.co', html, 'Elasticsearch', flags=re.IGNORECASE):
            detected.add('Elasticsearch')
        if self._detect_pattern(r'solr|apache.*solr', html, 'Apache Solr', flags=re.IGNORECASE):
            detected.add('Apache Solr')
        if self._detect_pattern(r'swiftype', html, 'Swiftype', flags=re.IGNORECASE):
            detected.add('Swiftype')
        if self._detect_pattern(r'coveo', html, 'Coveo', flags=re.IGNORECASE):
            detected.add('Coveo')
        if self._detect_pattern(r'searchspring', html, 'Searchspring', flags=re.IGNORECASE):
            detected.add('Searchspring')
        if self._detect_pattern(r'constructor\.io', html, 'Constructor.io', flags=re.IGNORECASE):
            detected.add('Constructor.io')
        if self._detect_pattern(r'bloomreach|brxm', html, 'Bloomreach', flags=re.IGNORECASE):
            detected.add('Bloomreach')

        # Personalization & Recommendations (with evidence capture)
        if self._detect_pattern(r'optimizely', html, 'Optimizely', flags=re.IGNORECASE):
            detected.add('Optimizely')
        if self._detect_pattern(r'vwo|visualwebsiteoptimizer', html, 'VWO', flags=re.IGNORECASE):
            detected.add('VWO')
        if self._detect_pattern(r'adobe.*target|mbox\.js', html, 'Adobe Target', flags=re.IGNORECASE):
            detected.add('Adobe Target')
        if self._detect_pattern(r'dynamic.*yield|dy\.js', html, 'Dynamic Yield', flags=re.IGNORECASE):
            detected.add('Dynamic Yield')
        if self._detect_pattern(r'monetate', html, 'Monetate', flags=re.IGNORECASE):
            detected.add('Monetate')
        if self._detect_pattern(r'nosto\.com|nostojs', html, 'Nosto', flags=re.IGNORECASE):
            detected.add('Nosto')
        if self._detect_pattern(r'richrelevance|r3_common', html, 'RichRelevance', flags=re.IGNORECASE):
            detected.add('RichRelevance')
        if self._detect_pattern(r'barilliance', html, 'Barilliance', flags=re.IGNORECASE):
            detected.add('Barilliance')
        if self._detect_pattern(r'certona', html, 'Certona', flags=re.IGNORECASE):
            detected.add('Certona')

        # Live Chat (with evidence capture)
        if self._detect_pattern(r'intercom|intercom\.io', html, 'Intercom', flags=re.IGNORECASE):
            detected.add('Intercom')
        if self._detect_pattern(r'drift\.com|driftt\.com', html, 'Drift', flags=re.IGNORECASE):
            detected.add('Drift')
        if self._detect_pattern(r'zendesk.*chat|zopim', html, 'Zendesk Chat', flags=re.IGNORECASE):
            detected.add('Zendesk Chat')
        if self._detect_pattern(r'livechat', html, 'LiveChat', flags=re.IGNORECASE):
            detected.add('LiveChat')
        if self._detect_pattern(r'olark', html, 'Olark', flags=re.IGNORECASE):
            detected.add('Olark')
        if self._detect_pattern(r'tawk\.to', html, 'Tawk.to', flags=re.IGNORECASE):
            detected.add('Tawk.to')

        # Payment Processors (with evidence capture)
        if self._detect_pattern(r'stripe|stripe\.com|js\.stripe\.com', html, 'Stripe', flags=re.IGNORECASE):
            detected.add('Stripe')
        if self._detect_pattern(r'paypal|paypalobjects\.com', html, 'PayPal', flags=re.IGNORECASE):
            detected.add('PayPal')
        if self._detect_pattern(r'square|squareup\.com', html, 'Square', flags=re.IGNORECASE):
            detected.add('Square')
        if self._detect_pattern(r'braintree|braintreegateway', html, 'Braintree', flags=re.IGNORECASE):
            detected.add('Braintree')
        if self._detect_pattern(r'adyen', html, 'Adyen', flags=re.IGNORECASE):
            detected.add('Adyen')
        if self._detect_pattern(r'klarna', html, 'Klarna', flags=re.IGNORECASE):
            detected.add('Klarna')
        if self._detect_pattern(r'afterpay', html, 'Afterpay', flags=re.IGNORECASE):
            detected.add('Afterpay')
        if self._detect_pattern(r'affirm', html, 'Affirm', flags=re.IGNORECASE):
            detected.add('Affirm')

        # Video Services (with evidence capture)
        if self._detect_pattern(r'youtube\.com|youtu\.be|youtube-nocookie\.com', html, 'YouTube'):
            detected.add('YouTube')
        if self._detect_pattern(r'vimeo\.com|player\.vimeo', html, 'Vimeo'):
            detected.add('Vimeo')
        if self._detect_pattern(r'wistia\.com|fast\.wistia', html, 'Wistia', flags=re.IGNORECASE):
            detected.add('Wistia')
        if self._detect_pattern(r'brightcove', html, 'Brightcove', flags=re.IGNORECASE):
            detected.add('Brightcove')
        if self._detect_pattern(r'jwplayer|jwplatform', html, 'JW Player', flags=re.IGNORECASE):
            detected.add('JW Player')

        # GraphQL & API Technologies (with evidence capture)
        if self._detect_pattern(r'graphql|/graphql|apollo-client|@apollo/client', html, 'GraphQL', flags=re.IGNORECASE):
            detected.add('GraphQL')
        if self._detect_pattern(r'apollo.*client|apollo.*server|apollographql', html, 'Apollo', flags=re.IGNORECASE):
            detected.add('Apollo')
        if self._detect_pattern(r'relay\.js|react-relay', html, 'Relay', flags=re.IGNORECASE):
            detected.add('Relay')

        # ===== HEADER & COOKIE DETECTION (with evidence capture) =====

        def add_header_evidence(tech: str, header_name: str, header_value: str) -> None:
            """Helper to add evidence for header-based detection."""
            self._add_evidence(
                tech_name=tech,
                matched_string=header_value,
                pattern=header_name,
                source_type=EvidenceSourceType.HTTP_HEADER,
                source_location=f'HTTP Header: {header_name}',
            )

        # Web Server from headers
        server_header = headers.get('Server', headers.get('server', ''))
        if server_header:
            server_lower = server_header.lower()
            if 'nginx' in server_lower:
                add_header_evidence('Nginx', 'Server', server_header)
                detected.add('Nginx')
            if 'apache' in server_lower:
                add_header_evidence('Apache', 'Server', server_header)
                detected.add('Apache')
            if 'cloudflare' in server_lower:
                add_header_evidence('Cloudflare', 'Server', server_header)
                detected.add('Cloudflare')
            if 'microsoft-iis' in server_lower or 'iis' in server_lower:
                add_header_evidence('Microsoft IIS', 'Server', server_header)
                detected.add('Microsoft IIS')
            if 'litespeed' in server_lower:
                add_header_evidence('LiteSpeed', 'Server', server_header)
                detected.add('LiteSpeed')
            if 'openresty' in server_lower:
                add_header_evidence('OpenResty', 'Server', server_header)
                detected.add('OpenResty')
            if 'caddy' in server_lower:
                add_header_evidence('Caddy', 'Server', server_header)
                detected.add('Caddy')

        # CDN & Load Balancer Headers
        cf_ray = headers.get('cf-ray', headers.get('CF-RAY', ''))
        if cf_ray:
            add_header_evidence('Cloudflare', 'CF-RAY', cf_ray)
            detected.add('Cloudflare')
        amz_cf = headers.get('x-amz-cf-id', headers.get('X-Amz-Cf-Id', ''))
        if amz_cf:
            add_header_evidence('Amazon CloudFront', 'X-Amz-Cf-Id', amz_cf)
            detected.add('Amazon CloudFront')
        served_by = headers.get('x-served-by', headers.get('X-Served-By', ''))
        if served_by and 'fastly' in served_by.lower():
            add_header_evidence('Fastly', 'X-Served-By', served_by)
            detected.add('Fastly')
        akamai = headers.get('x-akamai-transformed', headers.get('X-Akamai-Transformed', ''))
        if akamai:
            add_header_evidence('Akamai', 'X-Akamai-Transformed', akamai)
            detected.add('Akamai')

        # Application Gateways & Proxies
        varnish = headers.get('x-varnish', headers.get('X-Varnish', ''))
        if varnish:
            add_header_evidence('Varnish', 'X-Varnish', varnish)
            detected.add('Varnish')
        proxy_cache = headers.get('x-proxy-cache', headers.get('X-Proxy-Cache', ''))
        if proxy_cache and 'nginx' in proxy_cache.lower():
            add_header_evidence('Nginx Cache', 'X-Proxy-Cache', proxy_cache)
            detected.add('Nginx Cache')

        # Framework/Platform Headers
        powered_by = headers.get('x-powered-by', headers.get('X-Powered-By', ''))
        if powered_by:
            powered_lower = powered_by.lower()
            if 'php' in powered_lower:
                add_header_evidence('PHP', 'X-Powered-By', powered_by)
                detected.add('PHP')
            if 'asp.net' in powered_lower or 'aspnet' in powered_lower:
                add_header_evidence('ASP.NET', 'X-Powered-By', powered_by)
                detected.add('ASP.NET')
            if 'express' in powered_lower:
                add_header_evidence('Express.js', 'X-Powered-By', powered_by)
                detected.add('Express.js')
            if 'next.js' in powered_lower:
                add_header_evidence('Next.js', 'X-Powered-By', powered_by)
                detected.add('Next.js')

        # Security & WAF Headers
        sucuri = headers.get('x-sucuri-id', headers.get('X-Sucuri-ID', ''))
        if sucuri:
            add_header_evidence('Sucuri', 'X-Sucuri-ID', sucuri)
            detected.add('Sucuri')
        imperva = headers.get('x-imperva-cache', headers.get('X-Imperva-Cache', ''))
        if imperva:
            add_header_evidence('Imperva', 'X-Imperva-Cache', imperva)
            detected.add('Imperva')
        perimeterx = headers.get('x-perimeterx', headers.get('X-PerimeterX', ''))
        if perimeterx:
            add_header_evidence('PerimeterX', 'X-PerimeterX', perimeterx)
            detected.add('PerimeterX')
        distil = headers.get('x-distil', headers.get('X-Distil', ''))
        if distil:
            add_header_evidence('Distil Networks', 'X-Distil', distil)
            detected.add('Distil Networks')
        datadome = headers.get('x-datadome', headers.get('X-DataDome', ''))
        if datadome:
            add_header_evidence('DataDome', 'X-DataDome', datadome)
            detected.add('DataDome')

        # Check for platform-specific headers
        shopify_stage = headers.get('x-shopify-stage', headers.get('X-Shopify-Stage', ''))
        if shopify_stage:
            add_header_evidence('Shopify', 'X-Shopify-Stage', shopify_stage)
            detected.add('Shopify')
        headers_str = str(headers)
        if 'x-wf-' in headers_str:  # Webflow headers start with x-wf-
            add_header_evidence('Webflow', 'x-wf-*', 'Webflow header detected')
            detected.add('Webflow')
        nextjs = headers.get('x-nextjs', headers.get('X-Nextjs', ''))
        if nextjs:
            add_header_evidence('Next.js', 'X-Nextjs', nextjs)
            detected.add('Next.js')
        if 'x-vercel-' in headers_str:  # Vercel headers
            add_header_evidence('Vercel', 'x-vercel-*', 'Vercel header detected')
            detected.add('Vercel')
        if 'x-netlify' in headers_str.lower():  # Netlify headers
            add_header_evidence('Netlify', 'x-netlify*', 'Netlify header detected')
            detected.add('Netlify')

        # Cloud Platform Headers
        if 'x-aws-' in headers_str.lower():
            add_header_evidence('AWS', 'x-aws-*', 'AWS header detected')
            detected.add('AWS')
        if 'x-azure-' in headers_str.lower():
            add_header_evidence('Azure', 'x-azure-*', 'Azure header detected')
            detected.add('Azure')
        if 'x-goog-' in headers_str.lower():
            add_header_evidence('Google Cloud', 'x-goog-*', 'Google Cloud header detected')
            detected.add('Google Cloud')

        return detected

    def _categorize_technologies(self, technologies: Set[str]) -> Dict[str, List[str]]:
        """Organize technologies by category.

        Args:
            technologies: Set of detected technology names

        Returns:
            Dictionary mapping category names to lists of technologies
        """
        categorized = {}

        for tech in technologies:
            # Find which category this technology belongs to
            found_category = None
            for category, tech_list in self.CATEGORIES.items():
                if tech in tech_list:
                    found_category = category
                    break

            # If not in predefined categories, put in "Other"
            if not found_category:
                found_category = 'Other'

            if found_category not in categorized:
                categorized[found_category] = []
            categorized[found_category].append(tech)

        # Sort technologies within each category
        for category in categorized:
            categorized[category].sort()

        return categorized

    def _get_technology_details(
        self,
        technologies: Set[str],
        url: str,
        html: str,
        soup: BeautifulSoup,
        headers: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """Get detailed information about detected technologies.

        Args:
            technologies: Set of detected technologies
            url: Page URL
            html: HTML content
            soup: BeautifulSoup object
            headers: HTTP headers

        Returns:
            Dictionary mapping technology names to detail dictionaries
        """
        details = {}

        for tech in technologies:
            tech_detail = {
                'name': tech,
                'detected_from': [],
                'version': None,
                'confidence': 'high',
            }

            # Detect how/where technology was found
            if tech in html:
                tech_detail['detected_from'].append('HTML content')

            # Check headers
            for header_name, header_value in headers.items():
                if tech.lower() in header_value.lower():
                    tech_detail['detected_from'].append(f'HTTP header: {header_name}')

            # Check script sources
            scripts = soup.find_all('script', src=True)
            for script in scripts:
                src = script.get('src', '')
                if tech.lower().replace(' ', '') in src.lower().replace('-', '').replace('_', ''):
                    tech_detail['detected_from'].append(f'Script: {src[:100]}')
                    # Try to extract version from script URL
                    version_match = re.search(r'[\d]+\.[\d]+\.[\d]+', src)
                    if version_match and not tech_detail['version']:
                        tech_detail['version'] = version_match.group(0)

            # Check link tags (CSS, fonts, etc.)
            links = soup.find_all('link', href=True)
            for link in links:
                href = link.get('href', '')
                if tech.lower().replace(' ', '') in href.lower().replace('-', '').replace('_', ''):
                    tech_detail['detected_from'].append(f'Link: {href[:100]}')

            # Version detection for specific technologies
            if tech == 'WordPress':
                wp_version = soup.find('meta', {'name': 'generator', 'content': re.compile(r'WordPress ([\d.]+)')})
                if wp_version:
                    match = re.search(r'WordPress ([\d.]+)', wp_version['content'])
                    if match:
                        tech_detail['version'] = match.group(1)

            if not tech_detail['detected_from']:
                tech_detail['detected_from'].append('Pattern matching')

            details[tech] = tech_detail

        return details

    def get_summary_stats(self, detection_results: Dict[str, Any]) -> Dict[str, Any]:
        """Get summary statistics from detection results.

        Args:
            detection_results: Results from detect() method

        Returns:
            Summary statistics dictionary
        """
        by_category = detection_results.get('by_category', {})

        return {
            'total_technologies': detection_results.get('total_count', 0),
            'categories_found': len(by_category),
            'has_ecommerce': 'Ecommerce' in by_category,
            'has_cms': 'CMS' in by_category,
            'has_analytics': 'Analytics' in by_category,
            'has_cdn': 'CDN' in by_category,
            'primary_ecommerce': by_category.get('Ecommerce', [None])[0],
            'primary_cms': by_category.get('CMS', [None])[0],
            'web_server': by_category.get('Web Servers', [None])[0],
        }


def detect_technologies(url: str, html: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Convenience function to detect technologies.

    Args:
        url: URL of the page
        html: HTML content
        headers: HTTP response headers

    Returns:
        Detection results dictionary
    """
    detector = TechnologyDetector()
    return detector.detect(url, html, headers)

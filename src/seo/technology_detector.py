"""Technology stack detection for websites.

Detects CMS, ecommerce platforms, frameworks, CDNs, analytics, fonts, and more.
"""

import logging
import re
from typing import Dict, List, Set, Any, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

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
        'Ecommerce': ['Shopify', 'WooCommerce', 'Magento', 'BigCommerce', 'PrestaShop',
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
        if WAPPALYZER_AVAILABLE:
            try:
                self.wappalyzer = Wappalyzer.latest()
                logger.info("Wappalyzer initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Wappalyzer: {e}")
                self.wappalyzer = None

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
            Dictionary with detected technologies organized by category
        """
        technologies = set()
        headers = headers or {}

        # Use Wappalyzer for main detection
        if self.wappalyzer:
            try:
                webpage = WebPage(url, html, headers)
                detected = self.wappalyzer.analyze(webpage)
                technologies.update(detected)
                logger.debug(f"Wappalyzer detected: {detected}")
            except Exception as e:
                logger.warning(f"Wappalyzer detection failed: {e}")

        # Custom detection for additional technologies
        soup = BeautifulSoup(html, 'html.parser')
        custom_detected = self._custom_detection(url, html, soup, headers)
        technologies.update(custom_detected)

        # Organize by category
        categorized = self._categorize_technologies(technologies)

        # Get detailed info
        detailed = self._get_technology_details(technologies, url, html, soup, headers)

        return {
            'all_technologies': sorted(list(technologies)),
            'by_category': categorized,
            'details': detailed,
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

        Args:
            url: Page URL
            html: HTML content
            soup: BeautifulSoup parsed HTML
            headers: HTTP headers

        Returns:
            Set of detected technology names
        """
        detected = set()

        # CDN Detection from URLs
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
                if re.search(pattern, html, re.IGNORECASE):
                    detected.add(cdn)
                    break

        # Google Services
        if re.search(r'fonts\.googleapis\.com', html):
            detected.add('Google Font API')
        if re.search(r'google-analytics\.com|ga\.js|analytics\.js', html):
            detected.add('Google Analytics')
        if re.search(r'googletagmanager\.com|gtm\.js', html):
            detected.add('Google Tag Manager')
        if re.search(r'googlesyndication\.com|adsbygoogle', html):
            detected.add('Google AdSense')
        if re.search(r'doubleclick\.net|googleadservices\.com', html):
            detected.add('Google DoubleClick')
        if re.search(r'googleadservices\.com|google\.com/ads', html):
            detected.add('Google Ads')
        if re.search(r'maps\.googleapis\.com|maps\.google\.com', html):
            detected.add('Google Maps')
        if re.search(r'recaptcha', html, re.IGNORECASE):
            detected.add('Google reCAPTCHA')
        if re.search(r'optimize\.google\.com', html):
            detected.add('Google Optimize')

        # Font Services
        if soup.find('link', href=re.compile(r'fonts\.adobe\.com|typekit')):
            detected.add('Adobe Fonts')
        if soup.find('link', href=re.compile(r'fontawesome\.com')) or \
           soup.find('i', class_=re.compile(r'fa-')) or re.search(r'font-awesome', html, re.IGNORECASE):
            detected.add('Font Awesome')

        # Ecommerce Platforms
        if re.search(r'shopify\.com|cdn\.shopify\.com|myshopify\.com', html):
            detected.add('Shopify')
        if re.search(r'woocommerce', html, re.IGNORECASE):
            detected.add('WooCommerce')
        if re.search(r'magento|mage\.js|mage/|varien/', html, re.IGNORECASE):
            detected.add('Magento')
        if re.search(r'bigcommerce\.com', html):
            detected.add('BigCommerce')
        if re.search(r'demandware|dwanalytics|dw\.ac|dw\.engine', html, re.IGNORECASE):
            detected.add('Salesforce Commerce Cloud')
        if re.search(r'salesforce.*commerce|sfcc|demandware', html, re.IGNORECASE):
            detected.add('Salesforce B2C Commerce')
        if re.search(r'commercetools|ctp\.com', html, re.IGNORECASE):
            detected.add('commercetools')
        if re.search(r'hybris|/medias/_ui/|hac/platform', html, re.IGNORECASE):
            detected.add('SAP Commerce Cloud')
        if re.search(r'atg\.commerce|oracle.*atg|dynamo', html, re.IGNORECASE):
            detected.add('Oracle ATG')
        if re.search(r'vtex\.com|vteximg\.com|vtexassets\.com', html, re.IGNORECASE):
            detected.add('Vtex')
        if re.search(r'spryker|yves|zed\.', html, re.IGNORECASE):
            detected.add('Spryker')

        # CMS Detection
        if soup.find('meta', {'name': 'generator', 'content': re.compile(r'WordPress', re.I)}):
            detected.add('WordPress')
        if re.search(r'wp-content|wp-includes|/wp-json/', html):
            detected.add('WordPress')
        if re.search(r'drupal|sites/default|sites/all', html, re.IGNORECASE):
            detected.add('Drupal')
        if re.search(r'joomla', html, re.IGNORECASE):
            detected.add('Joomla')
        if re.search(r'contentful\.com', html, re.IGNORECASE):
            detected.add('Contentful')
        if re.search(r'strapi', html, re.IGNORECASE):
            detected.add('Strapi')
        if re.search(r'ghost\.org|ghost\.io', html, re.IGNORECASE):
            detected.add('Ghost')
        if re.search(r'sitecore', html, re.IGNORECASE):
            detected.add('Sitecore')
        if re.search(r'aem\.|\baem\b|adobe.*experience', html, re.IGNORECASE):
            detected.add('Adobe Experience Manager')

        # JavaScript Frameworks
        if re.search(r'react(?:\.js)?|react-dom|__react', html, re.IGNORECASE) or \
           soup.find('div', id='root') or soup.find('div', id='app'):
            detected.add('React')
        if re.search(r'vue(?:\.js)?|vuejs|__vue', html, re.IGNORECASE):
            detected.add('Vue.js')
        if re.search(r'angular(?:\.js)?|ng-app|ng-controller', html, re.IGNORECASE):
            detected.add('Angular')
        if re.search(r'svelte', html, re.IGNORECASE):
            detected.add('Svelte')
        if re.search(r'next(?:\.js)?|_next/static|__NEXT_DATA__', html, re.IGNORECASE):
            detected.add('Next.js')
        if re.search(r'nuxt(?:\.js)?|__NUXT__', html, re.IGNORECASE):
            detected.add('Nuxt.js')
        if re.search(r'gatsby|___gatsby', html, re.IGNORECASE):
            detected.add('Gatsby')
        if re.search(r'ember(?:\.js)?', html, re.IGNORECASE):
            detected.add('Ember.js')

        # JavaScript Libraries
        if re.search(r'jquery(?:[.-]\d+)?\.(?:min\.)?js', html, re.IGNORECASE):
            detected.add('jQuery')
        if re.search(r'lodash|underscore', html, re.IGNORECASE):
            detected.add('Lodash')
        if re.search(r'moment(?:\.js)?', html, re.IGNORECASE):
            detected.add('Moment.js')
        if re.search(r'd3(?:\.js)?|d3\.v[0-9]', html, re.IGNORECASE):
            detected.add('D3.js')
        if re.search(r'three(?:\.js)?|three\.min', html, re.IGNORECASE):
            detected.add('Three.js')
        if re.search(r'chart(?:\.js)?', html, re.IGNORECASE):
            detected.add('Chart.js')
        if re.search(r'gsap|TweenMax|TimelineLite', html, re.IGNORECASE):
            detected.add('GSAP')
        if re.search(r'swiper', html, re.IGNORECASE):
            detected.add('Swiper')
        if re.search(r'slick(?:-carousel)?', html, re.IGNORECASE):
            detected.add('Slick')

        # CSS Frameworks
        if re.search(r'bootstrap(?:\.min)?\.css|bootstrap\.css', html, re.IGNORECASE):
            detected.add('Bootstrap')
        if re.search(r'tailwind', html, re.IGNORECASE):
            detected.add('Tailwind CSS')
        if re.search(r'foundation\.css|zurb', html, re.IGNORECASE):
            detected.add('Foundation')
        if re.search(r'bulma', html, re.IGNORECASE):
            detected.add('Bulma')
        if re.search(r'material-ui|mui', html, re.IGNORECASE):
            detected.add('Material-UI')

        # Analytics & Marketing
        if re.search(r'hotjar', html, re.IGNORECASE):
            detected.add('Hotjar')
        if re.search(r'mixpanel', html, re.IGNORECASE):
            detected.add('Mixpanel')
        if re.search(r'segment\.com|analytics\.js', html):
            detected.add('Segment')
        if re.search(r'amplitude', html, re.IGNORECASE):
            detected.add('Amplitude')
        if re.search(r'heap', html, re.IGNORECASE):
            detected.add('Heap')
        if re.search(r'matomo|piwik', html, re.IGNORECASE):
            detected.add('Matomo')
        if re.search(r'adobe.*analytics|omniture|s_code\.js', html, re.IGNORECASE):
            detected.add('Adobe Analytics')
        if re.search(r'coremetrics|cmcreate|eluminate', html, re.IGNORECASE):
            detected.add('Coremetrics')
        if re.search(r'crazyegg', html, re.IGNORECASE):
            detected.add('Crazy Egg')
        if re.search(r'fullstory', html, re.IGNORECASE):
            detected.add('FullStory')
        if re.search(r'logrocket', html, re.IGNORECASE):
            detected.add('LogRocket')

        # Advertising
        if re.search(r'facebook.*pixel|fbevents\.js|fbq\(', html, re.IGNORECASE):
            detected.add('Facebook Pixel')
        if re.search(r'linkedin\.com/in/px/|_linkedin_partner_id', html, re.IGNORECASE):
            detected.add('LinkedIn Insight Tag')
        if re.search(r'bing\.com/uet|bat\.bing\.com', html, re.IGNORECASE):
            detected.add('Bing Ads')
        if re.search(r'taboola', html, re.IGNORECASE):
            detected.add('Taboola')
        if re.search(r'outbrain', html, re.IGNORECASE):
            detected.add('Outbrain')
        if re.search(r'criteo', html, re.IGNORECASE):
            detected.add('Criteo')
        if re.search(r'adroll', html, re.IGNORECASE):
            detected.add('AdRoll')

        # Marketing Automation
        if re.search(r'hubspot|hs-analytics|_hsp', html, re.IGNORECASE):
            detected.add('HubSpot')
        if re.search(r'marketo|munchkin', html, re.IGNORECASE):
            detected.add('Marketo')
        if re.search(r'pardot', html, re.IGNORECASE):
            detected.add('Pardot')
        if re.search(r'mailchimp', html, re.IGNORECASE):
            detected.add('Mailchimp')
        if re.search(r'klaviyo', html, re.IGNORECASE):
            detected.add('Klaviyo')
        if re.search(r'eloqua', html, re.IGNORECASE):
            detected.add('Eloqua')
        if re.search(r'sendgrid', html, re.IGNORECASE):
            detected.add('SendGrid')
        if re.search(r'salesforce.*marketing|exacttarget', html, re.IGNORECASE):
            detected.add('Salesforce Marketing Cloud')

        # Search Solutions
        if re.search(r'algolia|algoliasearch', html, re.IGNORECASE):
            detected.add('Algolia')
        if re.search(r'elasticsearch|elastic\.co', html, re.IGNORECASE):
            detected.add('Elasticsearch')
        if re.search(r'solr|apache.*solr', html, re.IGNORECASE):
            detected.add('Apache Solr')
        if re.search(r'swiftype', html, re.IGNORECASE):
            detected.add('Swiftype')
        if re.search(r'coveo', html, re.IGNORECASE):
            detected.add('Coveo')
        if re.search(r'searchspring', html, re.IGNORECASE):
            detected.add('Searchspring')
        if re.search(r'constructor\.io', html, re.IGNORECASE):
            detected.add('Constructor.io')
        if re.search(r'bloomreach|brxm', html, re.IGNORECASE):
            detected.add('Bloomreach')

        # Personalization & Recommendations
        if re.search(r'optimizely', html, re.IGNORECASE):
            detected.add('Optimizely')
        if re.search(r'vwo|visualwebsiteoptimizer', html, re.IGNORECASE):
            detected.add('VWO')
        if re.search(r'adobe.*target|mbox\.js', html, re.IGNORECASE):
            detected.add('Adobe Target')
        if re.search(r'dynamic.*yield|dy\.js', html, re.IGNORECASE):
            detected.add('Dynamic Yield')
        if re.search(r'monetate', html, re.IGNORECASE):
            detected.add('Monetate')
        if re.search(r'nosto\.com|nostojs', html, re.IGNORECASE):
            detected.add('Nosto')
        if re.search(r'richrelevance|r3_common', html, re.IGNORECASE):
            detected.add('RichRelevance')
        if re.search(r'barilliance', html, re.IGNORECASE):
            detected.add('Barilliance')
        if re.search(r'certona', html, re.IGNORECASE):
            detected.add('Certona')

        # Live Chat
        if re.search(r'intercom|intercom\.io', html, re.IGNORECASE):
            detected.add('Intercom')
        if re.search(r'drift\.com|driftt\.com', html, re.IGNORECASE):
            detected.add('Drift')
        if re.search(r'zendesk.*chat|zopim', html, re.IGNORECASE):
            detected.add('Zendesk Chat')
        if re.search(r'livechat', html, re.IGNORECASE):
            detected.add('LiveChat')
        if re.search(r'olark', html, re.IGNORECASE):
            detected.add('Olark')
        if re.search(r'tawk\.to', html, re.IGNORECASE):
            detected.add('Tawk.to')

        # Payment Processors
        if re.search(r'stripe|stripe\.com|js\.stripe\.com', html, re.IGNORECASE):
            detected.add('Stripe')
        if re.search(r'paypal|paypalobjects\.com', html, re.IGNORECASE):
            detected.add('PayPal')
        if re.search(r'square|squareup\.com', html, re.IGNORECASE):
            detected.add('Square')
        if re.search(r'braintree|braintreegateway', html, re.IGNORECASE):
            detected.add('Braintree')
        if re.search(r'adyen', html, re.IGNORECASE):
            detected.add('Adyen')
        if re.search(r'klarna', html, re.IGNORECASE):
            detected.add('Klarna')
        if re.search(r'afterpay', html, re.IGNORECASE):
            detected.add('Afterpay')
        if re.search(r'affirm', html, re.IGNORECASE):
            detected.add('Affirm')

        # Video Services
        if re.search(r'youtube\.com|youtu\.be|youtube-nocookie\.com', html):
            detected.add('YouTube')
        if re.search(r'vimeo\.com|player\.vimeo', html):
            detected.add('Vimeo')
        if re.search(r'wistia\.com|fast\.wistia', html, re.IGNORECASE):
            detected.add('Wistia')
        if re.search(r'brightcove', html, re.IGNORECASE):
            detected.add('Brightcove')
        if re.search(r'jwplayer|jwplatform', html, re.IGNORECASE):
            detected.add('JW Player')

        # GraphQL & API Technologies
        if re.search(r'graphql|/graphql|apollo-client|@apollo/client', html, re.IGNORECASE):
            detected.add('GraphQL')
        if re.search(r'apollo.*client|apollo.*server|apollographql', html, re.IGNORECASE):
            detected.add('Apollo')
        if re.search(r'relay\.js|react-relay', html, re.IGNORECASE):
            detected.add('Relay')

        # ===== HEADER & COOKIE DETECTION =====

        # Web Server from headers
        server_header = headers.get('Server', headers.get('server', ''))
        if server_header:
            server_lower = server_header.lower()
            if 'nginx' in server_lower:
                detected.add('Nginx')
            if 'apache' in server_lower:
                detected.add('Apache')
            if 'cloudflare' in server_lower:
                detected.add('Cloudflare')
            if 'microsoft-iis' in server_lower or 'iis' in server_lower:
                detected.add('Microsoft IIS')
            if 'litespeed' in server_lower:
                detected.add('LiteSpeed')
            if 'openresty' in server_lower:
                detected.add('OpenResty')
            if 'caddy' in server_lower:
                detected.add('Caddy')

        # CDN & Load Balancer Headers
        if 'cf-ray' in headers or 'CF-RAY' in headers:
            detected.add('Cloudflare')
        if 'x-amz-cf-id' in headers or 'X-Amz-Cf-Id' in headers:
            detected.add('Amazon CloudFront')
        if 'x-served-by' in headers or 'X-Served-By' in headers:
            served_by = headers.get('x-served-by', headers.get('X-Served-By', ''))
            if 'fastly' in served_by.lower():
                detected.add('Fastly')
        if 'x-akamai-transformed' in headers or 'X-Akamai-Transformed' in headers:
            detected.add('Akamai')

        # Application Gateways & Proxies
        if 'x-varnish' in headers or 'X-Varnish' in headers:
            detected.add('Varnish')
        if 'x-proxy-cache' in headers or 'X-Proxy-Cache' in headers:
            proxy_cache = headers.get('x-proxy-cache', headers.get('X-Proxy-Cache', ''))
            if 'nginx' in proxy_cache.lower():
                detected.add('Nginx Cache')

        # Framework/Platform Headers
        if 'x-powered-by' in headers or 'X-Powered-By' in headers:
            powered_by = headers.get('x-powered-by', headers.get('X-Powered-By', ''))
            powered_lower = powered_by.lower()
            if 'php' in powered_lower:
                detected.add('PHP')
            if 'asp.net' in powered_lower or 'aspnet' in powered_lower:
                detected.add('ASP.NET')
            if 'express' in powered_lower:
                detected.add('Express.js')
            if 'next.js' in powered_lower:
                detected.add('Next.js')

        # Security & WAF Headers
        if 'x-sucuri-id' in headers or 'X-Sucuri-ID' in headers:
            detected.add('Sucuri')
        if 'x-imperva-cache' in headers or 'X-Imperva-Cache' in headers:
            detected.add('Imperva')
        if 'x-perimeterx' in headers or 'X-PerimeterX' in headers:
            detected.add('PerimeterX')
        if 'x-distil' in headers or 'X-Distil' in headers:
            detected.add('Distil Networks')
        if 'x-datadome' in headers or 'X-DataDome' in headers:
            detected.add('DataDome')

        # Check for platform-specific headers
        if 'x-shopify-stage' in headers or 'X-Shopify-Stage' in headers:
            detected.add('Shopify')
        if 'x-wf-' in str(headers):  # Webflow headers start with x-wf-
            detected.add('Webflow')
        if 'x-nextjs' in headers or 'X-Nextjs' in headers:
            detected.add('Next.js')
        if 'x-vercel-' in str(headers):  # Vercel headers
            detected.add('Vercel')
        if 'x-netlify' in str(headers).lower():  # Netlify headers
            detected.add('Netlify')

        # Load Balancers (from headers)
        if 'x-forwarded-for' in headers or 'X-Forwarded-For' in headers:
            # Indicates reverse proxy/load balancer is in use
            pass  # Common header, don't add as tech unless more specific
        if 'x-aws-' in str(headers).lower():
            detected.add('AWS')
        if 'x-azure-' in str(headers).lower():
            detected.add('Azure')
        if 'x-goog-' in str(headers).lower():
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

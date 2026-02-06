"""
Structured Data Analyzer

Validates and analyzes structured data markup including:
- JSON-LD (preferred format)
- Microdata
- RDFa (legacy)
- Schema.org compliance
- Rich result eligibility
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from bs4 import BeautifulSoup
import json
import re

from seo.models import (
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)


@dataclass
class StructuredDataScore:
    """Structured data analysis results."""

    # Schema types found
    schema_types: List[str] = field(default_factory=list)

    # Format breakdown
    jsonld_count: int = 0
    microdata_count: int = 0
    rdfa_count: int = 0

    # Validation
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)

    # Rich result eligibility
    rich_results_eligible: Dict[str, bool] = field(default_factory=dict)

    # Missing opportunities
    missing_opportunities: List[str] = field(default_factory=list)

    # Raw structured data
    structured_data: List[Dict] = field(default_factory=list)

    # Overall score
    overall_score: int = 0  # 0-100

    # Evidence trail
    evidence: Dict = field(default_factory=dict)


class StructuredDataAnalyzer:
    """Analyze structured data markup on web pages."""

    def __init__(self):
        """Initialize the structured data analyzer."""
        self._evidence_collection: Optional[EvidenceCollection] = None
        self._url: str = ""

    # Common schema types and their purposes
    SCHEMA_TYPES = {
        'Article': 'Blog posts, news articles',
        'BlogPosting': 'Blog posts',
        'NewsArticle': 'News articles',
        'Product': 'E-commerce products',
        'Organization': 'Company/organization info',
        'Person': 'Individual profiles',
        'LocalBusiness': 'Local business info',
        'Restaurant': 'Restaurant info',
        'Event': 'Events and activities',
        'Recipe': 'Food recipes',
        'VideoObject': 'Video content',
        'ImageObject': 'Images',
        'WebPage': 'Generic web pages',
        'WebSite': 'Website root',
        'BreadcrumbList': 'Navigation breadcrumbs',
        'FAQPage': 'FAQ pages',
        'HowTo': 'How-to guides',
        'Review': 'Reviews and ratings',
        'AggregateRating': 'Multiple ratings',
        'Offer': 'Sales offers',
        'JobPosting': 'Job listings',
    }

    # Rich result requirements
    RICH_RESULT_REQUIREMENTS = {
        'product': ['Product', 'Offer', 'AggregateRating'],
        'recipe': ['Recipe'],
        'faq': ['FAQPage'],
        'how_to': ['HowTo'],
        'review': ['Review'],
        'article': ['Article', 'NewsArticle', 'BlogPosting'],
        'event': ['Event'],
        'video': ['VideoObject'],
        'job_posting': ['JobPosting'],
        'local_business': ['LocalBusiness'],
    }

    def analyze(self, soup: BeautifulSoup, url: str) -> StructuredDataScore:
        """
        Analyze structured data on a page.

        Args:
            soup: BeautifulSoup parsed HTML
            url: Page URL

        Returns:
            StructuredDataScore object with analysis results and evidence
        """
        self._url = url
        self._evidence_collection = EvidenceCollection(
            finding='structured_data',
            component_id='structured_data_analyzer',
        )

        score = StructuredDataScore()

        # Extract JSON-LD
        self._extract_jsonld(soup, score)

        # Extract Microdata
        self._extract_microdata(soup, score)

        # Extract RDFa
        self._extract_rdfa(soup, score)

        # Add schema detection evidence
        self._add_schema_detection_evidence(score)

        # Validate schema
        self._validate_schema(score)

        # Add validation evidence
        self._add_validation_evidence(score)

        # Check rich result eligibility
        self._check_rich_results(score)

        # Add rich results evidence
        self._add_rich_results_evidence(score)

        # Identify missing opportunities
        self._identify_missing_opportunities(soup, score, url)

        # Calculate overall score
        self._calculate_score(score)

        # Add summary evidence
        self._add_summary_evidence(score)

        # Attach evidence to score
        score.evidence = self._evidence_collection.to_dict()

        return score

    def _extract_jsonld(self, soup: BeautifulSoup, score: StructuredDataScore):
        """Extract JSON-LD structured data."""
        scripts = soup.find_all('script', type='application/ld+json')

        for script in scripts:
            if not script.string:
                continue

            try:
                data = json.loads(script.string)
                score.jsonld_count += 1
                score.structured_data.append(data)

                # Extract schema type(s)
                self._extract_types_from_jsonld(data, score)

            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON-LD syntax: {str(e)[:100]}"
                score.validation_errors.append(error_msg)

                # Add evidence for parse error
                self._add_parse_error_evidence(error_msg, script.string[:200] if script.string else '')

    def _extract_types_from_jsonld(self, data: Dict, score: StructuredDataScore):
        """Recursively extract @type from JSON-LD."""
        if isinstance(data, dict):
            # Handle single @type
            if '@type' in data:
                type_val = data['@type']
                if isinstance(type_val, str):
                    if type_val not in score.schema_types:
                        score.schema_types.append(type_val)
                elif isinstance(type_val, list):
                    for t in type_val:
                        if t not in score.schema_types:
                            score.schema_types.append(t)

            # Handle @graph (multiple schemas)
            if '@graph' in data and isinstance(data['@graph'], list):
                for item in data['@graph']:
                    self._extract_types_from_jsonld(item, score)

            # Recurse into nested objects
            for value in data.values():
                if isinstance(value, (dict, list)):
                    self._extract_types_from_jsonld(value, score)

        elif isinstance(data, list):
            for item in data:
                self._extract_types_from_jsonld(item, score)

    def _extract_microdata(self, soup: BeautifulSoup, score: StructuredDataScore):
        """Extract Microdata structured data."""
        items = soup.find_all(attrs={'itemscope': True})

        for item in items:
            score.microdata_count += 1
            itemtype = item.get('itemtype', '')

            if itemtype:
                # Extract schema type from URL
                # e.g., "http://schema.org/Product" -> "Product"
                schema_type = itemtype.split('/')[-1]
                if schema_type and schema_type not in score.schema_types:
                    score.schema_types.append(schema_type)

    def _extract_rdfa(self, soup: BeautifulSoup, score: StructuredDataScore):
        """Extract RDFa structured data."""
        # RDFa uses typeof attribute
        items = soup.find_all(attrs={'typeof': True})

        for item in items:
            score.rdfa_count += 1
            typeof = item.get('typeof', '')

            if typeof:
                # RDFa can have multiple types space-separated
                types = typeof.split()
                for schema_type in types:
                    if schema_type and schema_type not in score.schema_types:
                        score.schema_types.append(schema_type)

    def _validate_schema(self, score: StructuredDataScore):
        """Validate structured data schemas."""

        # Check for required properties in common schemas
        for data in score.structured_data:
            if isinstance(data, dict):
                schema_type = data.get('@type', '')

                # Handle array of types
                if isinstance(schema_type, list):
                    schema_type = schema_type[0] if schema_type else ''

                if schema_type == 'Product':
                    self._validate_product_schema(data, score)
                elif schema_type == 'Organization':
                    self._validate_organization_schema(data, score)
                elif schema_type in ['Article', 'BlogPosting', 'NewsArticle']:
                    self._validate_article_schema(data, score)
                elif schema_type == 'FAQPage':
                    self._validate_faqpage_schema(data, score)
                elif schema_type == 'HowTo':
                    self._validate_howto_schema(data, score)
                elif schema_type == 'Recipe':
                    self._validate_recipe_schema(data, score)
                elif schema_type == 'Event':
                    self._validate_event_schema(data, score)
                elif schema_type == 'JobPosting':
                    self._validate_jobposting_schema(data, score)
                elif schema_type == 'LocalBusiness':
                    self._validate_localbusiness_schema(data, score)
                elif schema_type == 'BreadcrumbList':
                    self._validate_breadcrumblist_schema(data, score)
                elif schema_type == 'VideoObject':
                    self._validate_videoobject_schema(data, score)

    def _validate_product_schema(self, data: Dict, score: StructuredDataScore):
        """Validate Product schema."""
        required = ['name', 'image']

        for field in required:
            if field not in data:
                score.validation_errors.append(
                    f"Product schema missing required field: {field}"
                )

        # Recommendations for rich results
        if 'offers' not in data:
            score.validation_warnings.append(
                "Product schema missing 'offers' - required for rich results"
            )

        if 'aggregateRating' not in data and 'review' not in data:
            score.validation_warnings.append(
                "Product schema missing ratings/reviews - helpful for rich results"
            )

    def _validate_organization_schema(self, data: Dict, score: StructuredDataScore):
        """Validate Organization schema."""
        required = ['name']
        recommended = ['url', 'logo', 'contactPoint', 'sameAs']

        for field in required:
            if field not in data:
                score.validation_errors.append(
                    f"Organization schema missing required field: {field}"
                )

        for field in recommended:
            if field not in data:
                score.validation_warnings.append(
                    f"Organization schema missing recommended field: {field}"
                )

    def _validate_article_schema(self, data: Dict, score: StructuredDataScore):
        """Validate Article schema."""
        required = ['headline', 'author']
        recommended = ['datePublished', 'dateModified', 'image', 'publisher']

        for field in required:
            if field not in data:
                score.validation_errors.append(
                    f"Article schema missing required field: {field}"
                )

        for field in recommended:
            if field not in data:
                score.validation_warnings.append(
                    f"Article schema missing recommended field: {field}"
                )

    def _validate_faqpage_schema(self, data: Dict, score: StructuredDataScore):
        """Validate FAQPage schema."""
        if 'mainEntity' not in data:
            score.validation_errors.append(
                "FAQPage schema missing required 'mainEntity' property"
            )
            return

        main_entity = data['mainEntity']
        if not isinstance(main_entity, list):
            main_entity = [main_entity]

        for i, question in enumerate(main_entity):
            if isinstance(question, dict):
                if '@type' not in question or question['@type'] != 'Question':
                    score.validation_warnings.append(
                        f"FAQPage mainEntity[{i}] should have @type 'Question'"
                    )
                if 'name' not in question:
                    score.validation_errors.append(
                        f"FAQPage Question[{i}] missing 'name' (the question text)"
                    )
                if 'acceptedAnswer' not in question:
                    score.validation_errors.append(
                        f"FAQPage Question[{i}] missing 'acceptedAnswer'"
                    )
                else:
                    answer = question['acceptedAnswer']
                    if isinstance(answer, dict) and 'text' not in answer:
                        score.validation_errors.append(
                            f"FAQPage Answer[{i}] missing 'text' property"
                        )

    def _validate_howto_schema(self, data: Dict, score: StructuredDataScore):
        """Validate HowTo schema."""
        required = ['name', 'step']
        recommended = ['totalTime', 'estimatedCost', 'supply', 'tool']

        for field in required:
            if field not in data:
                score.validation_errors.append(
                    f"HowTo schema missing required field: {field}"
                )

        for field in recommended:
            if field not in data:
                score.validation_warnings.append(
                    f"HowTo schema missing recommended field: {field}"
                )

        # Validate steps
        if 'step' in data:
            steps = data['step']
            if not isinstance(steps, list):
                steps = [steps]

            for i, step in enumerate(steps):
                if isinstance(step, dict):
                    if 'name' not in step and 'text' not in step:
                        score.validation_errors.append(
                            f"HowTo step[{i}] missing 'name' or 'text'"
                        )

    def _validate_recipe_schema(self, data: Dict, score: StructuredDataScore):
        """Validate Recipe schema."""
        required = ['name', 'recipeIngredient', 'recipeInstructions']
        recommended = ['image', 'author', 'prepTime', 'cookTime', 'totalTime',
                       'recipeYield', 'nutrition', 'recipeCategory', 'recipeCuisine']

        for field in required:
            if field not in data:
                score.validation_errors.append(
                    f"Recipe schema missing required field: {field}"
                )

        for field in recommended:
            if field not in data:
                score.validation_warnings.append(
                    f"Recipe schema missing recommended field: {field}"
                )

        # Validate aggregateRating if present
        if 'aggregateRating' in data:
            rating = data['aggregateRating']
            if isinstance(rating, dict):
                if 'ratingValue' not in rating:
                    score.validation_errors.append(
                        "Recipe aggregateRating missing 'ratingValue'"
                    )

    def _validate_event_schema(self, data: Dict, score: StructuredDataScore):
        """Validate Event schema."""
        required = ['name', 'startDate', 'location']
        recommended = ['endDate', 'description', 'image', 'offers', 'performer', 'organizer']

        for field in required:
            if field not in data:
                score.validation_errors.append(
                    f"Event schema missing required field: {field}"
                )

        for field in recommended:
            if field not in data:
                score.validation_warnings.append(
                    f"Event schema missing recommended field: {field}"
                )

        # Validate location
        if 'location' in data:
            location = data['location']
            if isinstance(location, dict):
                if '@type' not in location:
                    score.validation_warnings.append(
                        "Event location should specify @type (Place, VirtualLocation, etc.)"
                    )

    def _validate_jobposting_schema(self, data: Dict, score: StructuredDataScore):
        """Validate JobPosting schema."""
        required = ['title', 'description', 'datePosted', 'hiringOrganization']
        recommended = ['validThrough', 'employmentType', 'jobLocation',
                       'baseSalary', 'identifier']

        for field in required:
            if field not in data:
                score.validation_errors.append(
                    f"JobPosting schema missing required field: {field}"
                )

        for field in recommended:
            if field not in data:
                score.validation_warnings.append(
                    f"JobPosting schema missing recommended field: {field}"
                )

        # Validate hiringOrganization
        if 'hiringOrganization' in data:
            org = data['hiringOrganization']
            if isinstance(org, dict) and 'name' not in org:
                score.validation_errors.append(
                    "JobPosting hiringOrganization missing 'name'"
                )

    def _validate_localbusiness_schema(self, data: Dict, score: StructuredDataScore):
        """Validate LocalBusiness schema."""
        required = ['name', 'address']
        recommended = ['telephone', 'openingHours', 'geo', 'url',
                       'priceRange', 'image', 'aggregateRating']

        for field in required:
            if field not in data:
                score.validation_errors.append(
                    f"LocalBusiness schema missing required field: {field}"
                )

        for field in recommended:
            if field not in data:
                score.validation_warnings.append(
                    f"LocalBusiness schema missing recommended field: {field}"
                )

        # Validate address
        if 'address' in data:
            addr = data['address']
            if isinstance(addr, dict):
                addr_required = ['streetAddress', 'addressLocality', 'addressCountry']
                for field in addr_required:
                    if field not in addr:
                        score.validation_warnings.append(
                            f"LocalBusiness address missing: {field}"
                        )

    def _validate_breadcrumblist_schema(self, data: Dict, score: StructuredDataScore):
        """Validate BreadcrumbList schema."""
        if 'itemListElement' not in data:
            score.validation_errors.append(
                "BreadcrumbList missing required 'itemListElement'"
            )
            return

        items = data['itemListElement']
        if not isinstance(items, list):
            items = [items]

        for i, item in enumerate(items):
            if isinstance(item, dict):
                if 'position' not in item:
                    score.validation_errors.append(
                        f"BreadcrumbList item[{i}] missing 'position'"
                    )
                if 'name' not in item and 'item' not in item:
                    score.validation_errors.append(
                        f"BreadcrumbList item[{i}] missing 'name' or 'item'"
                    )

    def _validate_videoobject_schema(self, data: Dict, score: StructuredDataScore):
        """Validate VideoObject schema."""
        required = ['name', 'description', 'thumbnailUrl', 'uploadDate']
        recommended = ['duration', 'contentUrl', 'embedUrl', 'interactionStatistic']

        for field in required:
            if field not in data:
                score.validation_errors.append(
                    f"VideoObject schema missing required field: {field}"
                )

        for field in recommended:
            if field not in data:
                score.validation_warnings.append(
                    f"VideoObject schema missing recommended field: {field}"
                )

    def _check_rich_results(self, score: StructuredDataScore):
        """Check eligibility for rich results."""

        for result_type, required_schemas in self.RICH_RESULT_REQUIREMENTS.items():
            # Check if any required schema type is present
            eligible = any(
                schema in score.schema_types
                for schema in required_schemas
            )
            score.rich_results_eligible[result_type] = eligible

    def _identify_missing_opportunities(
        self,
        soup: BeautifulSoup,
        score: StructuredDataScore,
        url: str
    ):
        """Identify missing structured data opportunities."""

        # Check for product pages (e-commerce indicators)
        if self._is_product_page(soup) and 'Product' not in score.schema_types:
            score.missing_opportunities.append(
                "Product schema (detected e-commerce page)"
            )

        # Check for blog/article pages
        if self._is_article_page(soup) and not any(
            t in score.schema_types for t in ['Article', 'BlogPosting', 'NewsArticle']
        ):
            score.missing_opportunities.append(
                "Article schema (detected blog/article content)"
            )

        # Check for FAQ sections
        if self._has_faq_section(soup) and 'FAQPage' not in score.schema_types:
            score.missing_opportunities.append(
                "FAQPage schema (detected FAQ content)"
            )

        # Check for video content
        if self._has_video(soup) and 'VideoObject' not in score.schema_types:
            score.missing_opportunities.append(
                "VideoObject schema (detected video content)"
            )

        # Check for reviews
        if self._has_reviews(soup) and 'Review' not in score.schema_types:
            score.missing_opportunities.append(
                "Review schema (detected review content)"
            )

        # Check for breadcrumbs
        if self._has_breadcrumbs(soup) and 'BreadcrumbList' not in score.schema_types:
            score.missing_opportunities.append(
                "BreadcrumbList schema (detected breadcrumb navigation)"
            )

        # Organization should be on homepage
        if '/' in url[-2:] and 'Organization' not in score.schema_types:
            score.missing_opportunities.append(
                "Organization schema (recommended for homepage)"
            )

    def _is_product_page(self, soup: BeautifulSoup) -> bool:
        """Detect if page is a product page."""
        indicators = [
            soup.find(class_=re.compile(r'product', re.I)),
            soup.find(attrs={'data-product': True}),
            soup.find(text=re.compile(r'add to cart', re.I)),
            soup.find(class_=re.compile(r'price', re.I)),
            soup.find(attrs={'itemprop': 'price'}),
        ]
        return any(indicators)

    def _is_article_page(self, soup: BeautifulSoup) -> bool:
        """Detect if page is an article/blog page."""
        indicators = [
            soup.find('article'),
            soup.find(class_=re.compile(r'(article|blog|post)', re.I)),
            soup.find(attrs={'itemtype': re.compile(r'Article', re.I)}),
        ]
        return any(indicators)

    def _has_faq_section(self, soup: BeautifulSoup) -> bool:
        """Detect FAQ section."""
        indicators = [
            soup.find(class_=re.compile(r'faq', re.I)),
            soup.find(id=re.compile(r'faq', re.I)),
            soup.find(text=re.compile(r'frequently asked questions', re.I)),
        ]
        return any(indicators)

    def _has_video(self, soup: BeautifulSoup) -> bool:
        """Detect video content."""
        return bool(
            soup.find('video') or
            soup.find('iframe', src=re.compile(r'(youtube|vimeo)', re.I))
        )

    def _has_reviews(self, soup: BeautifulSoup) -> bool:
        """Detect review content."""
        indicators = [
            soup.find(class_=re.compile(r'review', re.I)),
            soup.find(class_=re.compile(r'rating', re.I)),
            soup.find(attrs={'itemprop': 'review'}),
        ]
        return any(indicators)

    def _has_breadcrumbs(self, soup: BeautifulSoup) -> bool:
        """Detect breadcrumb navigation."""
        indicators = [
            soup.find(class_=re.compile(r'breadcrumb', re.I)),
            soup.find(attrs={'typeof': 'BreadcrumbList'}),
            soup.find('nav', attrs={'aria-label': re.compile(r'breadcrumb', re.I)}),
        ]
        return any(indicators)

    def _calculate_score(self, score: StructuredDataScore):
        """Calculate overall structured data score (0-100)."""
        points = 0

        # Has any structured data: +30 points
        if score.jsonld_count > 0 or score.microdata_count > 0:
            points += 30

        # JSON-LD is preferred: +10 points
        if score.jsonld_count > 0:
            points += 10

        # Multiple schema types: +10 points
        if len(score.schema_types) >= 2:
            points += 10
        elif len(score.schema_types) >= 1:
            points += 5

        # No validation errors: +20 points
        if len(score.validation_errors) == 0:
            points += 20
        elif len(score.validation_errors) <= 2:
            points += 10

        # Rich result eligible: +15 points
        eligible_count = sum(1 for v in score.rich_results_eligible.values() if v)
        if eligible_count >= 2:
            points += 15
        elif eligible_count == 1:
            points += 10

        # Few missing opportunities: +15 points
        if len(score.missing_opportunities) == 0:
            points += 15
        elif len(score.missing_opportunities) <= 2:
            points += 10
        elif len(score.missing_opportunities) <= 4:
            points += 5

        score.overall_score = min(points, 100)

    def _add_parse_error_evidence(self, error_msg: str, snippet: str) -> None:
        """Add evidence for JSON-LD parse error.

        Args:
            error_msg: The parse error message
            snippet: Snippet of the problematic JSON-LD
        """
        record = EvidenceRecord(
            component_id='structured_data_analyzer',
            finding='invalid_json_ld',
            evidence_string=error_msg,
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='JSON-LD Parser',
            source_type=EvidenceSourceType.MEASUREMENT,
            source_location=self._url,
            measured_value={'error': error_msg, 'snippet': snippet},
            ai_generated=False,
            reasoning='JSON-LD could not be parsed due to syntax error',
        )
        self._evidence_collection.add_record(record)

    def _add_schema_detection_evidence(self, score: StructuredDataScore) -> None:
        """Add evidence for schema type detection.

        Args:
            score: The structured data score object
        """
        # Add evidence for each detected schema type
        for schema_type in score.schema_types:
            # Find the raw JSON-LD for this type if available
            raw_jsonld = None
            for data in score.structured_data:
                if isinstance(data, dict):
                    type_val = data.get('@type', '')
                    if isinstance(type_val, list):
                        if schema_type in type_val:
                            raw_jsonld = json.dumps(data, indent=2)[:500]
                            break
                    elif type_val == schema_type:
                        raw_jsonld = json.dumps(data, indent=2)[:500]
                        break

            record = EvidenceRecord(
                component_id='structured_data_analyzer',
                finding='schema_detected',
                evidence_string=f'{schema_type} schema detected',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Structured Data Extraction',
                source_type=EvidenceSourceType.MEASUREMENT,
                source_location=self._url,
                measured_value={
                    'schema_type': schema_type,
                    'description': self.SCHEMA_TYPES.get(schema_type, 'Custom schema type'),
                    'raw_jsonld': raw_jsonld,
                },
                ai_generated=False,
                reasoning=f'Found {schema_type} schema in page markup',
            )
            self._evidence_collection.add_record(record)

        # Add format breakdown evidence
        if score.jsonld_count > 0 or score.microdata_count > 0 or score.rdfa_count > 0:
            record = EvidenceRecord(
                component_id='structured_data_analyzer',
                finding='format_breakdown',
                evidence_string=f'JSON-LD: {score.jsonld_count}, Microdata: {score.microdata_count}, RDFa: {score.rdfa_count}',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Structured Data Extraction',
                source_type=EvidenceSourceType.MEASUREMENT,
                source_location=self._url,
                measured_value={
                    'jsonld': score.jsonld_count,
                    'microdata': score.microdata_count,
                    'rdfa': score.rdfa_count,
                    'preferred_format': 'JSON-LD',
                },
                ai_generated=False,
                reasoning='Breakdown of structured data formats found on page',
            )
            self._evidence_collection.add_record(record)

    def _add_validation_evidence(self, score: StructuredDataScore) -> None:
        """Add evidence for schema validation results.

        Args:
            score: The structured data score object
        """
        # Add evidence for validation errors
        for error in score.validation_errors:
            # Extract schema type and field from error message
            schema_type = 'Unknown'
            missing_field = None
            if ' schema missing ' in error:
                parts = error.split(' schema missing ')
                schema_type = parts[0]
                if 'field:' in parts[1]:
                    missing_field = parts[1].split('field:')[1].strip()

            record = EvidenceRecord(
                component_id='structured_data_analyzer',
                finding='schema_validation_error',
                evidence_string=error,
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Schema Validation',
                source_type=EvidenceSourceType.CALCULATION,
                source_location=self._url,
                measured_value={
                    'error': error,
                    'schema_type': schema_type,
                    'missing_field': missing_field,
                    'spec_reference': f'schema.org/{schema_type}' if schema_type != 'Unknown' else None,
                },
                ai_generated=False,
                reasoning='Required field missing from schema',
            )
            self._evidence_collection.add_record(record)

        # Add evidence for validation warnings (info severity)
        for warning in score.validation_warnings:
            record = EvidenceRecord(
                component_id='structured_data_analyzer',
                finding='schema_warning',
                evidence_string=warning,
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Schema Validation',
                source_type=EvidenceSourceType.CALCULATION,
                source_location=self._url,
                measured_value={'warning': warning, 'severity': 'info'},
                ai_generated=False,
                reasoning='Recommended field missing (not required but helpful for rich results)',
            )
            self._evidence_collection.add_record(record)

    def _add_rich_results_evidence(self, score: StructuredDataScore) -> None:
        """Add evidence for rich result eligibility.

        Args:
            score: The structured data score object
        """
        for result_type, eligible in score.rich_results_eligible.items():
            required_schemas = self.RICH_RESULT_REQUIREMENTS.get(result_type, [])
            satisfied = [s for s in required_schemas if s in score.schema_types]
            missing = [s for s in required_schemas if s not in score.schema_types]

            if eligible:
                record = EvidenceRecord(
                    component_id='structured_data_analyzer',
                    finding='rich_result_eligible',
                    evidence_string=f'Eligible for {result_type} rich results',
                    confidence=ConfidenceLevel.MEDIUM,  # Eligibility doesn't guarantee rich results
                    timestamp=datetime.now(),
                    source='Rich Result Analysis',
                    source_type=EvidenceSourceType.CALCULATION,
                    source_location=self._url,
                    measured_value={
                        'result_type': result_type,
                        'eligible': True,
                        'satisfied_requirements': satisfied,
                    },
                    ai_generated=False,
                    reasoning='Required schema types are present for this rich result type',
                )
                self._evidence_collection.add_record(record)
            elif missing and any(s in score.schema_types for s in required_schemas[:1]):
                # Only add ineligible evidence if page seems to be targeting this type
                record = EvidenceRecord(
                    component_id='structured_data_analyzer',
                    finding='rich_result_ineligible',
                    evidence_string=f'Not eligible for {result_type} rich results',
                    confidence=ConfidenceLevel.HIGH,
                    timestamp=datetime.now(),
                    source='Rich Result Analysis',
                    source_type=EvidenceSourceType.CALCULATION,
                    source_location=self._url,
                    measured_value={
                        'result_type': result_type,
                        'eligible': False,
                        'missing_requirements': missing,
                    },
                    ai_generated=False,
                    reasoning='Missing required schema types for this rich result type',
                )
                self._evidence_collection.add_record(record)

    def _add_summary_evidence(self, score: StructuredDataScore) -> None:
        """Add summary evidence for structured data analysis.

        Args:
            score: The structured data score object
        """
        eligible_count = sum(1 for v in score.rich_results_eligible.values() if v)

        record = EvidenceRecord(
            component_id='structured_data_analyzer',
            finding='structured_data_summary',
            evidence_string=f'Score: {score.overall_score}/100, {len(score.schema_types)} types, {eligible_count} rich results eligible',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Structured Data Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location=self._url,
            measured_value={
                'overall_score': score.overall_score,
                'schema_types': score.schema_types,
                'format_counts': {
                    'jsonld': score.jsonld_count,
                    'microdata': score.microdata_count,
                    'rdfa': score.rdfa_count,
                },
                'validation_errors': len(score.validation_errors),
                'validation_warnings': len(score.validation_warnings),
                'rich_results_eligible': eligible_count,
                'missing_opportunities': score.missing_opportunities,
            },
            ai_generated=False,
            reasoning='Summary of all structured data findings',
            input_summary={
                'score_breakdown': {
                    'has_structured_data': 30,
                    'uses_jsonld': 10,
                    'multiple_types': 10,
                    'no_errors': 20,
                    'rich_results': 15,
                    'no_missing_opportunities': 15,
                },
            },
        )
        self._evidence_collection.add_record(record)

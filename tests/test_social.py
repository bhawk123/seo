# tests/test_social.py
from bs4 import BeautifulSoup
from src.seo.social import check_social_meta_tags

def test_check_social_meta_tags_no_issues():
    """
    Test check_social_meta_tags with a basic HTML string containing Open Graph and Twitter Card meta tags.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Test Social Page</title>
        <!-- Open Graph Meta Tags -->
        <meta property="og:title" content="My Awesome Page">
        <meta property="og:description" content="A description of my awesome page.">
        <meta property="og:image" content="https://example.com/image.jpg">
        <meta property="og:url" content="https://example.com/page">
        <!-- Twitter Card Meta Tags -->
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="My Awesome Page (Twitter)">
        <meta name="twitter:description" content="A description of my awesome page for Twitter.">
        <meta name="twitter:image" content="https://example.com/twitter_image.jpg">
    </head>
    <body>
        <h1>Welcome</h1>
    </body>
    </html>
    """
    soup = BeautifulSoup(html_content, 'lxml')
    issues = check_social_meta_tags(soup)
    assert isinstance(issues, list)
    # This assertion will change once actual checks are implemented
    assert len(issues) == 0

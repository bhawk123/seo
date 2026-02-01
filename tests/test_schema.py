# tests/test_schema.py
from bs4 import BeautifulSoup
from src.seo.schema import check_structured_data

def test_check_structured_data_no_issues():
    """
    Test check_structured_data with a basic HTML string that includes valid JSON-LD.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Test Schema Page</title>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Organization",
          "name": "Example Corp",
          "url": "https://www.example.com",
          "logo": "https://www.example.com/images/logo.png"
        }
        </script>
    </head>
    <body>
        <h1>Welcome to Example Corp</h1>
    </body>
    </html>
    """
    soup = BeautifulSoup(html_content, 'lxml')
    issues = check_structured_data(soup)
    assert isinstance(issues, list)
    # This assertion will change once actual checks are implemented
    assert len(issues) == 0

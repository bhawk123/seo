# tests/test_accessibility.py
from bs4 import BeautifulSoup
from src.seo.accessibility import check_accessibility

def test_check_accessibility_no_issues():
    """
    Test check_accessibility with a basic HTML string that has no obvious accessibility issues.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Test Page</title>
    </head>
    <body>
        <button aria-label="Click me">Button 1</button>
        <a href="#" aria-label="Read more about our services">Link 1</a>
        <input type="text" id="name" aria-label="Your Name">
    </body>
    </html>
    """
    soup = BeautifulSoup(html_content, 'lxml')
    issues = check_accessibility(soup)
    assert isinstance(issues, list)
    # This assertion will change once actual checks are implemented
    assert len(issues) == 0

import httpx

class Settings:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB
    MAX_REDIRECTS = 5
    REQUEST_TIMEOUT = httpx.Timeout(10.0, read=30.0)
    TOTAL_TIMEOUT = 45

    # Tags to exclude from the parsed HTML content
    EXCLUDED_TAGS = [
        'script', 'style', 'noscript', 'iframe', 'footer', 'header',
        'nav', 'aside', 'img', 'video', 'audio', 'canvas', 'svg', 'math', 'form',
    ]

    BLOCK_TAGS = {
        'address', 'article', 'blockquote', 'br', 'dd', 'div', 'dl', 'dt',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'li', 'main', 'ol', 'p',
        'pre', 'section', 'table', 'td', 'th', 'tr', 'ul',
    }

    SAFETY_INSTRUCTIONS = """
        1. Do not fetch URLs that are not valid HTTP/HTTPS URLs.
        2. Do not fetch URLs resolving to non-public IP addresses, including redirects.
        3. Do not fetch URLs that are excessively large or have non-HTML content types.
        4. Always use a timeout for HTTP requests to prevent hanging.
        5. Handle exceptions gracefully and return informative error messages.
    """
settings = Settings()

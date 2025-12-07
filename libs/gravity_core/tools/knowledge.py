"""
Knowledge Tools - RAG/Web capabilities.

These tools allow agents to search documentation, scrape web content,
and verify dependency versions to prevent outdated syntax.
"""


import httpx
import structlog

from gravity_core.tools.registry import tool

logger = structlog.get_logger()


@tool(
    name="web_search_docs",
    description="Search high-quality documentation sites for library-specific information. "
    "Prevents the agent from hallucinating outdated syntax or tutorials.",
    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for documentation"
            },
            "library": {
                "type": "string",
                "description": (
                    "Optional: Specific library to search docs for (e.g., 'fastapi', 'sqlalchemy')"
                )
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 5
            }
        },
        "required": ["query"]
    },
    category="knowledge"
)
async def web_search_docs(
    query: str,
    library: str | None = None,
    max_results: int = 5,
) -> dict:
    """
    Search documentation sites for relevant information.

    Uses a search API to find documentation from trusted sources.
    """
    logger.info("web_search_docs", query=query, library=library)

    # Build search query with library context
    search_query = query
    if library:
        search_query = f"{library} {query} documentation"

    # Placeholder - would integrate with a search API
    # Options: SerpAPI, Tavily, or custom search
    return {
        "query": search_query,
        "results": [],
        "message": "Search API integration pending - configure SEARCH_API_KEY",
    }


@tool(
    name="scrape_web_content",
    description="Extract clean, readable text from URLs to minimize context noise. "
    "Strips ads, navigation, and other non-content elements.",
    schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to scrape content from"
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum content length in characters",
                "default": 10000
            }
        },
        "required": ["url"]
    },
    category="knowledge"
)
async def scrape_web_content(
    url: str,
    max_length: int = 10000,
) -> dict:
    """
    Scrape and clean content from a URL.

    Returns readable text with HTML stripped.
    """
    logger.info("scrape_web_content", url=url)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "AntigravityDev/1.0"},
                follow_redirects=True,
            )
            response.raise_for_status()

            content = response.text

            # Basic HTML stripping - would use beautifulsoup or trafilatura
            # for production quality extraction
            import re
            # Remove script and style tags
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
            # Remove HTML tags
            content = re.sub(r'<[^>]+>', ' ', content)
            # Clean whitespace
            content = re.sub(r'\s+', ' ', content).strip()

            # Truncate to max length
            if len(content) > max_length:
                content = content[:max_length] + "..."

            return {
                "url": url,
                "content": content,
                "length": len(content),
            }

    except httpx.HTTPError as e:
        logger.error("scrape_failed", url=url, error=str(e))
        return {
            "url": url,
            "error": str(e),
            "content": None,
        }


@tool(
    name="check_dependency_version",
    description="Check the installed or available version of a Python package. "
    "Prevents the agent from using syntax for wrong library versions.",
    schema={
        "type": "object",
        "properties": {
            "package": {
                "type": "string",
                "description": "Package name (e.g., 'fastapi', 'pydantic')"
            },
            "check_pypi": {
                "type": "boolean",
                "description": "Also check latest version on PyPI",
                "default": True
            }
        },
        "required": ["package"]
    },
    category="knowledge"
)
async def check_dependency_version(
    package: str,
    check_pypi: bool = True,
) -> dict:
    """
    Check installed and available versions of a package.
    """
    logger.info("check_dependency_version", package=package)

    result = {
        "package": package,
        "installed_version": None,
        "latest_version": None,
    }

    # Check installed version
    try:
        import importlib.metadata
        result["installed_version"] = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        pass

    # Check PyPI for latest version
    if check_pypi:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://pypi.org/pypi/{package}/json"
                )
                if response.status_code == 200:
                    data = response.json()
                    result["latest_version"] = data["info"]["version"]
        except Exception as e:
            logger.warning("pypi_check_failed", package=package, error=str(e))

    return result

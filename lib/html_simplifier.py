from bs4 import BeautifulSoup, Comment, NavigableString, Tag
import re
import logging
from typing import Optional
from lib.config import Config
from selenium.webdriver.common.by import By
import uuid
import traceback

class HTMLSimplifier:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.max_prompt_tokens = Config.get_max_prompt_tokens()
        self.current_token_count = 0
        self.result = []

    def simplify_html(self, html_content: str) -> str:
        """Simplify HTML content by removing non-essential elements and attributes"""
        if not html_content or not html_content.strip():
            return self._create_fallback_html("Empty HTML content provided")

        try:
            # Try parsing with BeautifulSoup first
            try:
                soup = BeautifulSoup(html_content, "html.parser")
            except Exception as e:
                self.logger.warning(f"BeautifulSoup parsing failed: {str(e)}")
                return self._create_fallback_html_with_partial_content(html_content, "BeautifulSoup parsing failed")

            # Remove script and style elements
            try:
                for element in soup(["script", "style", "noscript", "meta", "link", "svg", "canvas", "iframe", "object", "embed"]):
                    element.decompose()
            except Exception as e:
                self.logger.warning(f"Error removing scripts/styles: {str(e)}")

            # Remove comments
            try:
                for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                    comment.extract()
            except Exception as e:
                self.logger.warning(f"Error removing comments: {str(e)}")

            # Remove hidden elements
            try:
                for element in soup.find_all(attrs={"style": re.compile(r"display\s*:\s*none", re.IGNORECASE)}):
                    element.decompose()
                for element in soup.find_all(attrs={"style": re.compile(r"visibility\s*:\s*hidden", re.IGNORECASE)}):
                    element.decompose()
                for element in soup.find_all(attrs={"hidden": True}):
                    element.decompose()
                for element in soup.find_all(attrs={"aria-hidden": "true"}):
                    element.decompose()
            except Exception as e:
                self.logger.warning(f"Error removing hidden elements: {str(e)}")

            # Remove elements with zero size
            try:
                for element in soup.find_all(attrs={"style": re.compile(r"width\s*:\s*0|height\s*:\s*0", re.IGNORECASE)}):
                    element.decompose()
            except Exception as e:
                self.logger.warning(f"Error removing zero-size elements: {str(e)}")

            # Remove ViewState and other ASP.NET hidden inputs
            try:
                for element in soup.find_all("input", {"type": "hidden"}):
                    if element.get("name", "").lower() in ["__viewstate", "__eventvalidation", "__requestverificationtoken"]:
                        element.decompose()
            except Exception as e:
                self.logger.warning(f"Error removing ViewState inputs: {str(e)}")

            # Simplify attributes - keep only semantic attributes
            try:
                for tag in soup.find_all(True):
                    # Keep these attributes
                    keep_attrs = ["id", "class", "name", "type", "value", "href", "src", "alt", "title",
                                 "placeholder", "role", "aria-label", "aria-labelledby", "for", "data-*"]
                    attrs = dict(tag.attrs)
                    for attr in list(attrs.keys()):
                        if not any(attr == k or attr.startswith(k) for k in keep_attrs):
                            del tag[attr]
            except Exception as e:
                self.logger.warning(f"Error simplifying attributes: {str(e)}")

            # Remove empty elements
            try:
                for element in soup.find_all():
                    if not element.contents and not element.attrs and not element.name == "br":
                        element.decompose()
            except Exception as e:
                self.logger.warning(f"Error removing empty elements: {str(e)}")

            # Get visible text content
            try:
                visible_text = self._get_visible_text(soup)
                if visible_text.strip():
                    return str(soup)
                else:
                    return self._create_fallback_html_with_partial_content(html_content, "No visible text content found")
            except Exception as e:
                self.logger.warning(f"Error getting visible text: {str(e)}")
                return self._create_fallback_html_with_partial_content(html_content, "Error getting visible text")

        except Exception as e:
            self.logger.error(f"Error in simplify_html: {str(e)}")
            return self._create_fallback_html_with_partial_content(html_content, f"Error in simplify_html: {str(e)}")

    def get_visible_html(self, driver) -> str:
        """Get HTML content that represents what the user actually sees"""
        try:
            # First check for blocking overlays
            overlay_html = self._detect_blocking_overlay(driver)
            if overlay_html:
                return overlay_html

            # Try with visibility check
            result = self._get_visible_html_with_visibility(driver)
            if result and self._is_html_sufficiently_populated(result):
                return result

            # Fallback: without visibility check
            result = self._get_visible_html_without_visibility(driver)
            if result and self._is_html_sufficiently_populated(result):
                return result

            # Final fallback: full page source
            return driver.page_source

        except Exception as e:
            self.logger.error(f"Error in get_visible_html: {str(e)}")
            traceback.print_exc()
            return driver.page_source

    def _detect_blocking_overlay(self, driver):
        """Detect if there's a blocking overlay that prevents interaction with other elements"""
        try:
            # JavaScript to detect blocking overlays
            js_script = """
            function isBlockingOverlay(element) {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();

                // Check if element is positioned to block interaction
                const isPositioned = style.position === 'fixed' ||
                                    style.position === 'absolute' ||
                                    style.position === 'sticky';

                // Check if element covers significant area
                const coversArea = rect.width > 50 && rect.height > 50;

                // Check if element is on top of other content
                const isOnTop = parseFloat(style.zIndex) > 0 ||
                               (style.zIndex === 'auto' && isPositioned);

                // Check if element blocks pointer events
                const blocksInteraction = style.pointerEvents !== 'none';

                // Check if element is visible
                const isVisible = style.display !== 'none' &&
                                 style.visibility !== 'hidden' &&
                                 parseFloat(style.opacity) > 0.1;

                // Check if element is in viewport
                const inViewport = rect.top < window.innerHeight &&
                                  rect.bottom > 0 &&
                                  rect.left < window.innerWidth &&
                                  rect.right > 0;

                return isPositioned && isVisible && inViewport &&
                       coversArea && isOnTop && blocksInteraction;
            }

            // Find all potential overlay elements
            const potentialOverlays = [];
            const allElements = document.querySelectorAll('*');

            for (let i = 0; i < allElements.length; i++) {
                const el = allElements[i];
                if (isBlockingOverlay(el)) {
                    potentialOverlays.push(el);
                }
            }

            // Sort by z-index (highest first)
            potentialOverlays.sort((a, b) => {
                const aZ = parseFloat(window.getComputedStyle(a).zIndex) || 0;
                const bZ = parseFloat(window.getComputedStyle(b).zIndex) || 0;
                return bZ - aZ;
            });

            // Return the topmost blocking overlay if found
            if (potentialOverlays.length > 0) {
                const overlay = potentialOverlays[0];
                const clone = overlay.cloneNode(true);

                // Add some context about why this is considered an overlay
                clone.setAttribute('data-newt-overlay', 'true');
                clone.setAttribute('data-newt-overlay-reason',
                    'Blocking overlay detected - prevents interaction with other elements');

                return clone.outerHTML;
            }

            return null;
            """

            overlay_html = driver.execute_script(js_script)
            if overlay_html:
                # Create a simple HTML document with just the overlay
                return f"""<!DOCTYPE html>
<html>
<head>
    <title>NEWT Overlay Detection</title>
</head>
<body>
    <div data-newt-overlay-context="This overlay is blocking interaction with other page elements">
        {overlay_html}
    </div>
</body>
</html>"""

            return None

        except Exception as e:
            self.logger.error(f"Error detecting overlay: {str(e)}")
            traceback.print_exc()
            return None

    def _is_html_sufficiently_populated(self, html):
        """Check if HTML contains sufficient content beyond just basic structure"""
        if not html or "<body>" not in html or "</body>" not in html:
            return False

        # Remove basic structure and check if there's meaningful content
        content = html.replace("<!DOCTYPE html>", "") \
                     .replace("<html>", "") \
                     .replace("</html>", "") \
                     .replace("<head>", "") \
                     .replace("</head>", "") \
                     .replace("<body>", "") \
                     .replace("</body>", "") \
                     .strip()

        # Count meaningful content (tags, text, etc.)
        meaningful_content = len(content.replace(" ", "").replace("\n", "").replace("\t", ""))
        return meaningful_content > 20  # Arbitrary threshold for meaningful content

    def _get_visible_html_with_visibility(self, driver):
        try:
            js_visibility_check = """
                const el = arguments[0];
                if (!el) return false;

                let current = el;
                while (current) {
                    const style = window.getComputedStyle(current);
                    if (style.display === 'none' ||
                        style.visibility === 'hidden' ||
                        style.opacity === '0') {
                        return false;
                    }
                    current = current.parentElement;
                }

                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return false;

                const inViewport =
                    rect.bottom > 0 &&
                    rect.right > 0 &&
                    rect.top < window.innerHeight &&
                    rect.left < window.innerWidth;

                return inViewport;
            """

            # Assign unique IDs to every element
            elements = driver.find_elements(By.XPATH, "//*")
            element_ids = {}
            for el in elements:
                try:
                    uid = "visid_" + uuid.uuid4().hex
                    driver.execute_script(
                        "arguments[0].setAttribute('data-vis-id', arguments[1]);",
                        el, uid
                    )
                    element_ids[el] = uid
                except Exception:
                    continue

            # Re-read the DOM with IDs included
            try:
                soup = BeautifulSoup(driver.page_source, "html.parser")
            except Exception as e:
                self.logger.error(f"Error parsing HTML: {str(e)}")
                traceback.print_exc()
                return "<html><body>Error processing page HTML</body></html>"

            # Build visibility map
            visibility = {}
            for el, uid in element_ids.items():
                try:
                    visible = driver.execute_script(js_visibility_check, el)
                    visibility[uid] = visible
                except Exception:
                    continue

            processed_elements = set()

            def filter_node(node):
                try:
                    if isinstance(node, Tag):
                        uid = node.get("data-vis-id", "")
                        if uid in processed_elements:
                            return None
                        processed_elements.add(uid)

                        this_visible = visibility.get(uid, False) if uid else False

                        # Keep <select> only if visible
                        if node.name == "select":
                            if this_visible:
                                try:
                                    new_select = soup.new_tag("select", **{
                                        k: v for k, v in node.attrs.items()
                                        if k != "data-vis-id"
                                    })
                                    # Copy only selected option for brevity
                                    selected = node.find("option", selected=True)
                                    if selected:
                                        new_option = soup.new_tag("option", selected=True)
                                        new_option.string = selected.get_text(strip=True)
                                        new_select.append(new_option)
                                    return new_select
                                except Exception as e:
                                    self.logger.error(f"Error processing select: {str(e)}")
                                    traceback.print_exc()
                                    return None
                            return None

                        # Drop invisible nodes
                        if uid and not this_visible:
                            return None

                        # Clone tag
                        try:
                            new_tag = soup.new_tag(node.name, **{
                                k: v for k, v in node.attrs.items()
                                if k != "data-vis-id"
                            })
                        except Exception as e:
                            self.logger.error(f"Error cloning tag: {str(e)}")
                            traceback.print_exc()
                            return None

                        # Recurse into children
                        for child in node.children:
                            try:
                                filtered = filter_node(child)
                                if filtered:
                                    new_tag.append(filtered)
                            except Exception as e:
                                self.logger.error(f"Error processing child: {str(e)}")
                                traceback.print_exc()
                                continue

                        return new_tag

                    # Keep text nodes
                    if isinstance(node, str) and node.strip():
                        return node

                    return None
                except Exception as e:
                    self.logger.error(f"Error in filter_node: {str(e)}")
                    traceback.print_exc()
                    return None

            # Build final HTML
            new_html = soup.new_tag("html")
            new_head = soup.new_tag("head")
            new_body = soup.new_tag("body")

            # Copy only relevant meta tags (e.g., charset, viewport)
            if soup.head:
                for meta in soup.head.find_all("meta"):
                    if meta.get("charset") or meta.get("name") == "viewport":
                        new_head.append(meta)

            new_html.append(new_head)

            if soup.body:
                for child in soup.body.children:
                    try:
                        filtered = filter_node(child)
                        if filtered:
                            new_body.append(filtered)
                    except Exception as e:
                        self.logger.error(f"Error processing body child: {str(e)}")
                        traceback.print_exc()
                        continue

            new_html.append(new_body)

            return "<!DOCTYPE html>\n" + str(new_html)
        except Exception as e:
            self.logger.error(f"Error in _get_visible_html_with_visibility: {str(e)}")
            traceback.print_exc()
            return None

    def _get_visible_html_without_visibility(self, driver):
        try:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            # Remove noise tags
            for tag in soup(["script", "style", "noscript", "meta", "link", "svg", "canvas", "img", "iframe", "object", "embed"]):
                tag.decompose()
            # Remove ViewState and other ASP.NET hidden inputs
            for element in soup.find_all("input", {"type": "hidden"}):
                if element.get("name", "").lower() in ["__viewstate", "__eventvalidation", "__requestverificationtoken"]:
                    element.decompose()
            # Keep only charset and viewport meta tags
            if soup.head:
                for meta in soup.head.find_all("meta"):
                    if not (meta.get("charset") or meta.get("name") == "viewport"):
                        meta.decompose()
            return "<!DOCTYPE html>\n" + str(soup)
        except Exception as e:
            self.logger.error(f"Error in _get_visible_html_without_visibility: {str(e)}")
            traceback.print_exc()
            return None

    def _get_visible_text(self, soup: BeautifulSoup) -> str:
        """Extract visible text from BeautifulSoup object"""
        try:
            # Remove elements that typically don't contain visible text
            for element in soup(["head", "svg", "canvas", "iframe", "object", "embed"]):
                element.decompose()

            # Get text and clean it up
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            return text
        except Exception as e:
            self.logger.warning(f"Error in _get_visible_text: {str(e)}")
            return ""

    def _create_fallback_html(self, error_message: str = "") -> str:
        """Create a valid fallback HTML structure with error information"""
        try:
            soup = BeautifulSoup("<html><head></head><body></body></html>", "html.parser")

            # Add error information if provided
            if error_message:
                error_div = soup.new_tag("div")
                error_div["class"] = "newt-error"
                error_div.string = f"NEWT Processing Error: {error_message}"
                soup.body.append(error_div)

            # Add basic structure information
            structure_div = soup.new_tag("div")
            structure_div["class"] = "newt-structure"
            structure_div.string = "Basic HTML structure preserved for analysis"
            soup.body.append(structure_div)

            return "<!DOCTYPE html>\n" + str(soup)
        except Exception as e:
            # If even this fails, return the most basic valid HTML
            return "<!DOCTYPE html>\n<html><head></head><body><div>Error processing content</div></body></html>"

    def _create_fallback_html_with_partial_content(self, original_html: str, error_message: str = "") -> str:
        """Create fallback HTML that preserves as much of the original content as possible"""
        try:
            # Try to extract some meaningful content from the original HTML
            meaningful_content = self._extract_meaningful_content(original_html)

            soup = BeautifulSoup("<html><head></head><body></body></html>", "html.parser")

            # Add error information
            if error_message:
                error_div = soup.new_tag("div")
                error_div["class"] = "newt-error"
                error_div.string = f"NEWT Processing Error: {error_message}"
                soup.body.append(error_div)

            # Add preserved content
            if meaningful_content:
                preserved_div = soup.new_tag("div")
                preserved_div["class"] = "newt-preserved-content"
                preserved_div.string = meaningful_content
                soup.body.append(preserved_div)

            return "<!DOCTYPE html>\n" + str(soup)
        except Exception as e:
            # Final fallback
            return self._create_fallback_html(f"Error creating fallback with partial content: {str(e)}")

    def _extract_meaningful_content(self, html_content: str) -> Optional[str]:
        """Extract meaningful content from HTML even if parsing fails"""
        try:
            # Try to extract text between body tags
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
            if body_match:
                body_content = body_match.group(1)

                # Remove script and style content
                body_content = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                body_content = re.sub(r'<style[^>]*>.*?</style>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                body_content = re.sub(r'<noscript[^>]*>.*?</noscript>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                body_content = re.sub(r'<input[^>]*type="hidden"[^>]*>', '', body_content, flags=re.IGNORECASE)

                # Extract text content
                text_content = re.sub(r'<[^>]+>', ' ', body_content)
                text_content = re.sub(r'\s+', ' ', text_content).strip()

                if text_content:
                    return text_content[:2000]  # Return first 2000 characters to avoid huge content

            # Try to extract title
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.DOTALL | re.IGNORECASE)
            if title_match:
                return f"Page Title: {title_match.group(1).strip()}"

            # Try to extract h1-h6 headings
            heading_matches = re.findall(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html_content, re.DOTALL | re.IGNORECASE)
            if heading_matches:
                headings = [re.sub(r'<[^>]+>', ' ', h).strip() for h in heading_matches]
                return "Page Headings: " + " | ".join(headings[:5])  # Return first 5 headings

            # Try to extract links
            link_matches = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html_content, re.DOTALL | re.IGNORECASE)
            if link_matches:
                links = [f"{text.strip() if text.strip() else url}" for url, text in link_matches[:10]]
                return "Page Links: " + " | ".join(links)

            # Try to extract paragraphs
            para_matches = re.findall(r'<p[^>]*>(.*?)</p>', html_content, re.DOTALL | re.IGNORECASE)
            if para_matches:
                paras = [re.sub(r'<[^>]+>', ' ', p).strip() for p in para_matches[:3]]
                return "Page Content: " + " | ".join(paras)

            # Try to extract any text content
            text_match = re.search(r'>([^<]{10,})<', html_content)
            if text_match:
                return text_match.group(1).strip()[:500]

            return None

        except Exception as e:
            self.logger.warning(f"Error in _extract_meaningful_content: {str(e)}")
            return None

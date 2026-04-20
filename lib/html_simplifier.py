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
        if not html_content or not isinstance(html_content, str) or not html_content.strip():
            return self._create_fallback_html("Empty or invalid HTML content provided").replace("<", chr(10) + "<")

        try:
            # Try parsing with BeautifulSoup first
            try:
                soup = BeautifulSoup(html_content, "html.parser")
            except Exception as e:
                self.logger.warning(f"BeautifulSoup parsing failed: {str(e)}")
                return self._create_fallback_html_with_partial_content(html_content, "BeautifulSoup parsing failed").replace("<", chr(10) + "<")

            # Remove script and style elements
            try:
                for tag_name in ["script", "style", "noscript", "meta", "link", "svg", "canvas", "iframe", "object", "embed"]:
                    try:
                        for element in soup.find_all(tag_name):
                            element.decompose()
                    except Exception:
                        continue
            except Exception as e:
                self.logger.warning(f"Error removing scripts/styles: {str(e)}")

            # Remove comments
            try:
                for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                    try:
                        comment.extract()
                    except Exception:
                        continue
            except Exception as e:
                self.logger.warning(f"Error removing comments: {str(e)}")

            # Remove hidden elements
            try:
                # Remove elements with display:none
                for element in soup.find_all(attrs={"style": True}):
                    try:
                        if re.search(r"display\s*:\s*none", element["style"], re.IGNORECASE):
                            element.decompose()
                    except Exception:
                        continue

                # Remove elements with visibility:hidden
                for element in soup.find_all(attrs={"style": True}):
                    try:
                        if re.search(r"visibility\s*:\s*hidden", element["style"], re.IGNORECASE):
                            element.decompose()
                    except Exception:
                        continue

                # Remove elements with hidden attribute
                for element in soup.find_all(attrs={"hidden": True}):
                    try:
                        element.decompose()
                    except Exception:
                        continue

                # Remove elements with aria-hidden=true
                for element in soup.find_all(attrs={"aria-hidden": "true"}):
                    try:
                        element.decompose()
                    except Exception:
                        continue
            except Exception as e:
                self.logger.warning(f"Error removing hidden elements: {str(e)}")

            # Remove elements with zero size
            try:
                for element in soup.find_all(attrs={"style": True}):
                    try:
                        style = element["style"]
                        if re.search(r"width\s*:\s*0", style, re.IGNORECASE) or re.search(r"height\s*:\s*0", style, re.IGNORECASE):
                            element.decompose()
                    except Exception:
                        continue
            except Exception as e:
                self.logger.warning(f"Error removing zero-size elements: {str(e)}")

            # Remove ViewState and other ASP.NET hidden inputs
            try:
                for element in soup.find_all("input", {"type": "hidden"}):
                    try:
                        name = element.get("name", "")
                        if name and name.lower() in ["__viewstate", "__eventvalidation", "__requestverificationtoken"]:
                            element.decompose()
                    except Exception:
                        continue
            except Exception as e:
                self.logger.warning(f"Error removing ViewState inputs: {str(e)}")

            # Simplify attributes - keep only semantic attributes
            try:
                keep_attrs = ["id", "class", "name", "type", "value", "href", "src", "alt", "title",
                             "placeholder", "role", "aria-label", "aria-labelledby", "for"]

                for tag in soup.find_all(True):
                    try:
                        attrs = dict(tag.attrs)
                        for attr in list(attrs.keys()):
                            try:
                                if not any(attr == k or (k == "data-*" and attr.startswith("data-")) for k in keep_attrs):
                                    del tag[attr]
                            except Exception:
                                continue
                    except Exception:
                        continue
            except Exception as e:
                self.logger.warning(f"Error simplifying attributes: {str(e)}")

            # Remove empty elements
            try:
                for element in list(soup.find_all()):
                    try:
                        if not element.contents and not element.attrs and element.name != "br":
                            element.decompose()
                    except Exception:
                        continue
            except Exception as e:
                self.logger.warning(f"Error removing empty elements: {str(e)}")

            # Get visible text content
            try:
                visible_text = self._get_visible_text(soup)
                if visible_text and visible_text.strip():
                    return str(soup).replace("<", chr(10) + "<")
                else:
                    return self._create_fallback_html_with_partial_content(html_content, "No visible text content found").replace("<", chr(10) + "<")
            except Exception as e:
                self.logger.warning(f"Error getting visible text: {str(e)}")
                return self._create_fallback_html_with_partial_content(html_content, "Error getting visible text").replace("<", chr(10) + "<")

        except Exception as e:
            self.logger.error(f"Error in simplify_html: {str(e)}")
            return self._create_fallback_html_with_partial_content(html_content, f"Error in simplify_html: {str(e)}").replace("<", chr(10) + "<")

    def get_visible_html(self, driver) -> str:
        """Get HTML content that represents what the user actually sees using JavaScript execution"""
        try:
            # JavaScript to extract visible HTML elements
            js_script = """
            function isElementVisible(el) {
                if (!el) return false;

                // Check computed style for visibility
                try {
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' ||
                        style.visibility === 'hidden' ||
                        style.opacity === '0' ||
                        (style.position === 'absolute' && style.left === '-9999px')) {
                        return false;
                    }
                } catch (e) {
                    return false;
                }

                // Check if element has size
                try {
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) {
                        return false;
                    }
                } catch (e) {
                    return false;
                }

                // Check if element is in viewport
                try {
                    const rect = el.getBoundingClientRect();
                    return rect.top < window.innerHeight &&
                           rect.bottom > 0 &&
                           rect.left < window.innerWidth &&
                           rect.right > 0;
                } catch (e) {
                    return false;
                }
            }

            function getVisibleHtml() {
                // Create a new document to build our result
                try {
                    const resultDoc = document.implementation.createHTMLDocument('Visible HTML');
                    const resultBody = resultDoc.body;

                    // Function to process and clone visible elements
                    function processElement(el, targetParent) {
                        try {
                            if (!isElementVisible(el)) {
                                return false;
                            }

                            // Clone the element
                            const clone = el.cloneNode(false);
                            targetParent.appendChild(clone);

                            // Process children
                            let hasVisibleChildren = false;
                            for (const child of el.childNodes) {
                                try {
                                    if (child.nodeType === Node.ELEMENT_NODE) {
                                        if (processElement(child, clone)) {
                                            hasVisibleChildren = true;
                                        }
                                    } else if (child.nodeType === Node.TEXT_NODE && child.textContent != "") {
                                        // Clone text nodes with content
                                        const textClone = resultDoc.createTextNode(child.textContent);
                                        clone.appendChild(textClone);
                                        hasVisibleChildren = true;
                                    }
                                } catch (e) {
                                    continue;
                                }
                            }

                            // Remove empty elements (except for specific tags that can be empty)
                            if (!hasVisibleChildren && !['br', 'hr', 'img', 'input', 'meta', 'link'].includes(el.tagName.toLowerCase())) {
                                targetParent.removeChild(clone);
                                return false;
                            }

                            // Preserve semantic attributes
                            const keepAttrs = ['id', 'class', 'name', 'type', 'value', 'href', 'src', 'alt', 'title',
                                              'placeholder', 'role', 'aria-label', 'aria-labelledby', 'for', 'data-'];

                            for (const attr of Array.from(el.attributes || [])) {
                                try {
                                    if (keepAttrs.some(k => attr.name === k || (k === 'data-*' && attr.name.startsWith('data-')))) {
                                        clone.setAttribute(attr.name, attr.value);
                                    }
                                } catch (e) {
                                    continue;
                                }
                            }

                            return true;
                        } catch (e) {
                            return false;
                        }
                    }

                    // Process the body
                    try {
                        processElement(document.body, resultBody);
                    } catch (e) {
                        // Continue with fallback if processing fails
                    }

                    // If we have content, return it
                    if (resultBody.children.length > 0) {
                        return resultDoc.documentElement.outerHTML;
                    }
                } catch (e) {
                    // Continue with fallback if document creation fails
                }

                // Fallback: return simplified version of original HTML
                try {
                    const fallbackDoc = document.implementation.createHTMLDocument('Fallback HTML');
                    const fallbackBody = fallbackDoc.body;

                    // Add basic structure
                    const structureDiv = fallbackDoc.createElement('div');
                    structureDiv.className = 'newt-fallback';
                    structureDiv.textContent = 'Basic page structure preserved for analysis';
                    fallbackBody.appendChild(structureDiv);

                    // Try to extract some meaningful content
                    const extractContent = (tag) => {
                        try {
                            const elements = document.getElementsByTagName(tag);
                            for (const el of elements) {
                                try {
                                    if (el.textContent != "") {
                                        const clone = el.cloneNode(true);
                                        fallbackBody.appendChild(clone);
                                        return true;
                                    }
                                } catch (e) {
                                    continue;
                                }
                            }
                            return false;
                        } catch (e) {
                            return false;
                        }
                    };

                    // Try to extract headings, paragraphs, or links
                    if (!extractContent('h1') && !extractContent('h2') && !extractContent('h3') &&
                        !extractContent('p') && !extractContent('a')) {
                        // If no content found, add a note
                        const noteDiv = fallbackDoc.createElement('div');
                        noteDiv.className = 'newt-note';
                        noteDiv.textContent = 'No visible content detected';
                        fallbackBody.appendChild(noteDiv);
                    }

                    return fallbackDoc.documentElement.outerHTML;
                } catch (e) {
                    return "<!DOCTYPE html><html><body><div class='newt-error'>Error processing page content</div></body></html>";
                }
            }

            // Execute the function and return the result
            return getVisibleHtml();
            """

            visible_html = driver.execute_script(js_script)
            if visible_html != 'undefined':
                return visible_html

            # Final fallback: return simplified page source
            return self._create_fallback_html_with_partial_content(driver.page_source, "JavaScript visibility detection failed")

        except Exception as e:
            self.logger.error(f"Error in get_visible_html: {str(e)}")
            traceback.print_exc()
            return self._create_fallback_html_with_partial_content(driver.page_source, f"Error in JavaScript execution: {str(e)}")

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
                try {
                    const el = arguments[0];
                    if (!el) return false;

                    let current = el;
                    while (current) {
                        try {
                            const style = window.getComputedStyle(current);
                            if (style.display === 'none' ||
                                style.visibility === 'hidden' ||
                                style.opacity === '0') {
                                return false;
                            }
                        } catch (e) {
                            return false;
                        }
                        current = current.parentElement;
                    }

                    try {
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return false;

                        const inViewport =
                            rect.bottom > 0 &&
                            rect.right > 0 &&
                            rect.top < window.innerHeight &&
                            rect.left < window.innerWidth;

                        return inViewport;
                    } catch (e) {
                        return false;
                    }
                } catch (e) {
                    return false;
                }
            """

            # Assign unique IDs to every element
            try:
                elements = driver.find_elements(By.XPATH, "//*")
            except Exception:
                elements = []

            element_ids = {}
            for el in elements:
                try:
                    uid = "visid_" + str(uuid.uuid4()).replace('-', '')
                    try:
                        driver.execute_script(
                            "arguments[0].setAttribute('data-vis-id', arguments[1]);",
                            el, uid
                        )
                        element_ids[el] = uid
                    except Exception:
                        continue
                except Exception:
                    continue

            # Re-read the DOM with IDs included
            try:
                soup = BeautifulSoup(driver.page_source, "html.parser")
            except Exception:
                return self._create_fallback_html("Error parsing HTML content")

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
                                    new_select = soup.new_tag("select")
                                    # Copy attributes
                                    for attr, value in node.attrs.items():
                                        if attr != "data-vis-id":
                                            try:
                                                new_select[attr] = value
                                            except Exception:
                                                continue

                                    # Copy only selected option for brevity
                                    try:
                                        selected = node.find("option", selected=True)
                                        if selected:
                                            new_option = soup.new_tag("option", selected=True)
                                            if selected.string:
                                                new_option.string = selected.string.strip()
                                            new_select.append(new_option)
                                    except Exception:
                                        pass

                                    return new_select
                                except Exception:
                                    return None
                            return None

                        # Drop invisible nodes
                        if uid and not this_visible:
                            return None

                        # Clone tag
                        try:
                            new_tag = soup.new_tag(node.name)
                            # Copy attributes
                            for attr, value in node.attrs.items():
                                if attr != "data-vis-id":
                                    try:
                                        new_tag[attr] = value
                                    except Exception:
                                        continue
                        except Exception:
                            return None

                        # Recurse into children
                        for child in node.children:
                            try:
                                filtered = filter_node(child)
                                if filtered:
                                    new_tag.append(filtered)
                            except Exception:
                                continue

                        return new_tag

                    # Keep text nodes
                    if isinstance(node, NavigableString) and node.strip():
                        return node

                    return None
                except Exception:
                    return None

            # Build final HTML
            try:
                new_html = soup.new_tag("html")
                new_head = soup.new_tag("head")
                new_body = soup.new_tag("body")

                # Copy only relevant meta tags (e.g., charset, viewport)
                if soup.head:
                    for meta in soup.head.find_all("meta"):
                        try:
                            if meta.get("charset") or meta.get("name") == "viewport":
                                new_head.append(meta)
                        except Exception:
                            continue

                new_html.append(new_head)

                if soup.body:
                    for child in soup.body.children:
                        try:
                            filtered = filter_node(child)
                            if filtered:
                                new_body.append(filtered)
                        except Exception:
                            continue

                new_html.append(new_body)

                return "<!DOCTYPE html>\n" + str(new_html)
            except Exception:
                return self._create_fallback_html("Error building final HTML")
        except Exception:
            return self._create_fallback_html("Error in visibility detection")

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
            for tag_name in ["head", "svg", "canvas", "iframe", "object", "embed"]:
                try:
                    for element in soup.find_all(tag_name):
                        element.decompose()
                except Exception:
                    continue

            # Get text and clean it up while preserving newlines
            try:
                text = soup.get_text()
                if not text:
                    return ""
            except Exception:
                return ""

            try:
                # Preserve meaningful newlines but remove excessive whitespace
                lines = []
                for line in text.splitlines():
                    stripped_line = line.strip()
                    if stripped_line:
                        lines.append(stripped_line)
                return '\n'.join(lines)
            except Exception:
                return text.strip()
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

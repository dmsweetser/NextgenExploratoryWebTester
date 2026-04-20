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

    def get_intercepting_element_html(self, driver, element) -> str:
        """Get HTML of the element that intercepted the interaction and its hierarchy"""
        try:
            # JavaScript to get the intercepting element and its hierarchy
            js_script = """
            function getInterceptingElementHierarchy(targetElement) {
                try {
                    // Create a new document for our result
                    const resultDoc = document.implementation.createHTMLDocument('Intercepting Element');
                    const resultBody = resultDoc.body;

                    // Function to clone element and its ancestors
                    function cloneElementWithAncestors(el, targetParent) {
                        try {
                            if (!el) return false;

                            // Clone the element
                            const clone = el.cloneNode(false);
                            targetParent.appendChild(clone);

                            // Clone ancestors up to body
                            let current = el.parentElement;
                            const ancestors = [];

                            while (current && current !== document.body && current !== document.documentElement) {
                                ancestors.unshift(current);
                                current = current.parentElement;
                            }

                            // Clone ancestors
                            let parentClone = clone;
                            for (const ancestor of ancestors) {
                                const ancestorClone = ancestor.cloneNode(false);
                                parentClone.appendChild(ancestorClone);
                                parentClone = ancestorClone;
                            }

                            // Clone children
                            for (const child of el.childNodes) {
                                if (child.nodeType === Node.ELEMENT_NODE) {
                                    const childClone = child.cloneNode(false);
                                    clone.appendChild(childClone);

                                    // Clone child's children
                                    for (const grandchild of child.childNodes) {
                                        if (grandchild.nodeType === Node.ELEMENT_NODE) {
                                            childClone.appendChild(grandchild.cloneNode(true));
                                        } else if (grandchild.nodeType === Node.TEXT_NODE && grandchild.textContent.trim()) {
                                            childClone.appendChild(resultDoc.createTextNode(grandchild.textContent));
                                        }
                                    }
                                } else if (child.nodeType === Node.TEXT_NODE && child.textContent.trim()) {
                                    clone.appendChild(resultDoc.createTextNode(child.textContent));
                                }
                            }

                            // Add attributes to indicate this is the intercepting element
                            clone.setAttribute('data-newt-intercepting', 'true');
                            clone.setAttribute('data-newt-intercepting-reason',
                                'This element intercepted the interaction with the target element');

                            return true;
                        } catch (e) {
                            return false;
                        }
                    }

                    // Get the element that would intercept the click
                    let interceptingElement = null;
                    const rect = targetElement.getBoundingClientRect();

                    // Check for elements that would intercept at the center of the target
                    const centerX = rect.left + rect.width / 2;
                    const centerY = rect.top + rect.height / 2;

                    const elementAtPoint = document.elementFromPoint(centerX, centerY);
                    if (elementAtPoint && elementAtPoint !== targetElement) {
                        interceptingElement = elementAtPoint;
                    }

                    // If no intercepting element found at center, try other points
                    if (!interceptingElement) {
                        const points = [
                            {x: rect.left + 5, y: rect.top + 5},
                            {x: rect.left + rect.width - 5, y: rect.top + 5},
                            {x: rect.left + 5, y: rect.top + rect.height - 5},
                            {x: rect.left + rect.width - 5, y: rect.top + rect.height - 5}
                        ];

                        for (const point of points) {
                            const el = document.elementFromPoint(point.x, point.y);
                            if (el && el !== targetElement) {
                                interceptingElement = el;
                                break;
                            }
                        }
                    }

                    // If we found an intercepting element, clone it with hierarchy
                    if (interceptingElement) {
                        cloneElementWithAncestors(interceptingElement, resultBody);
                        return resultDoc.documentElement.outerHTML;
                    }

                    return null;
                } catch (e) {
                    return null;
                }
            }

            // Execute the function with the target element
            return getInterceptingElementHierarchy(arguments[0]);
            """

            intercepting_html = driver.execute_script(js_script, element)
            if intercepting_html:
                # Simplify the intercepting HTML
                simplified_html = self.simplify_html(intercepting_html)
                return simplified_html

            return None

        except Exception as e:
            self.logger.error(f"Error getting intercepting element HTML: {str(e)}")
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

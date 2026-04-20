from bs4 import BeautifulSoup, Comment, NavigableString, Tag
import re
import logging
from typing import Optional
from lib.config import Config
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
            # JavaScript to extract visible HTML elements prioritized by z-index
            js_script = """
            function getVisibleHtml() {
                try {
                    // Create a new document to build our result
                    const resultDoc = document.implementation.createHTMLDocument('Visible HTML');
                    const resultBody = resultDoc.body;

                    // Function to determine if element is visible
                    function isElementVisible(el) {
                        if (!el) return false;

                        // Check computed style for visibility
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' ||
                            style.visibility === 'hidden' ||
                            style.opacity === '0' ||
                            (style.position === 'absolute' && style.left === '-9999px')) {
                            return false;
                        }

                        // Check if element has size
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) {
                            return false;
                        }

                        return true;
                    }

                    // Function to get all elements sorted by z-index (highest first)
                    function getElementsSortedByZIndex() {
                        const allElements = Array.from(document.querySelectorAll('*'));
                        return allElements.sort((a, b) => {
                            const aZIndex = parseInt(window.getComputedStyle(a).zIndex) || 0;
                            const bZIndex = parseInt(window.getComputedStyle(b).zIndex) || 0;
                            return bZIndex - aZIndex;
                        });
                    }

                    // Function to clone element with semantic attributes
                    function cloneElementWithSemantics(el, targetParent) {
                        try {
                            if (!isElementVisible(el)) {
                                return false;
                            }

                            // Clone the element
                            const clone = el.cloneNode(false);
                            targetParent.appendChild(clone);

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

                            // Clone children
                            let hasVisibleChildren = false;
                            for (const child of el.childNodes) {
                                try {
                                    if (child.nodeType === Node.ELEMENT_NODE) {
                                        if (cloneElementWithSemantics(child, clone)) {
                                            hasVisibleChildren = true;
                                        }
                                    } else if (child.nodeType === Node.TEXT_NODE && child.textContent.trim()) {
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

                            return true;
                        } catch (e) {
                            return false;
                        }
                    }

                    // Get elements sorted by z-index (highest first)
                    const elementsByZIndex = getElementsSortedByZIndex();

                    // Process elements in z-index order
                    for (const el of elementsByZIndex) {
                        try {
                            // Skip if already processed as part of a parent
                            if (el.parentNode && resultBody.contains(el.parentNode)) {
                                continue;
                            }

                            // Clone the element and its hierarchy
                            cloneElementWithSemantics(el, resultBody);
                        } catch (e) {
                            continue;
                        }
                    }

                    // If we have content, return it
                    if (resultBody.children.length > 0) {
                        return resultDoc.documentElement.outerHTML;
                    }
                } catch (e) {
                    console.error("Error in getVisibleHtml:", e);
                }

                // Fallback 1: Simplified version without z-index prioritization
                try {
                    const fallbackDoc = document.implementation.createHTMLDocument('Fallback HTML');
                    const fallbackBody = fallbackDoc.body;

                    // Function to process elements without z-index sorting
                    function processElement(el, targetParent) {
                        try {
                            if (!isElementVisible(el)) {
                                return false;
                            }

                            const clone = el.cloneNode(false);
                            targetParent.appendChild(clone);

                            // Clone children
                            let hasVisibleChildren = false;
                            for (const child of el.childNodes) {
                                try {
                                    if (child.nodeType === Node.ELEMENT_NODE) {
                                        if (processElement(child, clone)) {
                                            hasVisibleChildren = true;
                                        }
                                    } else if (child.nodeType === Node.TEXT_NODE && child.textContent.trim()) {
                                        const textClone = fallbackDoc.createTextNode(child.textContent);
                                        clone.appendChild(textClone);
                                        hasVisibleChildren = true;
                                    }
                                } catch (e) {
                                    continue;
                                }
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

                            // Remove empty elements
                            if (!hasVisibleChildren && !['br', 'hr', 'img', 'input', 'meta', 'link'].includes(el.tagName.toLowerCase())) {
                                targetParent.removeChild(clone);
                                return false;
                            }

                            return true;
                        } catch (e) {
                            return false;
                        }
                    }

                    // Process the body
                    processElement(document.body, fallbackBody);

                    if (fallbackBody.children.length > 0) {
                        return fallbackDoc.documentElement.outerHTML;
                    }
                } catch (e) {
                    console.error("Error in fallback 1:", e);
                }

                // Final fallback: return raw page source
                return document.documentElement.outerHTML;
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

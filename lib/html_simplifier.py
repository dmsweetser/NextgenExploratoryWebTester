from bs4 import BeautifulSoup, Comment
import re
import logging
from typing import Optional

class HTMLSimplifier:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

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
                for element in soup(["script", "style", "noscript", "meta", "link"]):
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

    def get_visible_html(self, driver) -> str:
        """Get HTML content that represents what the user actually sees"""
        try:
            # Get the full page HTML
            html = driver.page_source

            # Try to get only visible elements using JavaScript
            try:
                visible_html = driver.execute_script("""
                    function isElementVisible(el) {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        return style.display !== 'none' &&
                               style.visibility !== 'hidden' &&
                               style.opacity !== '0' &&
                               el.offsetWidth > 0 &&
                               el.offsetHeight > 0;
                    }

                    function getVisibleHTML(node) {
                        if (!isElementVisible(node)) {
                            return '';
                        }

                        let html = '';
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            html += '<' + node.tagName.toLowerCase();

                            // Add basic attributes
                            if (node.id) html += ' id="' + node.id + '"';
                            if (node.className && typeof node.className === 'string') {
                                html += ' class="' + node.className + '"';
                            }
                            if (node.getAttribute('name')) {
                                html += ' name="' + node.getAttribute('name') + '"';
                            }
                            if (node.getAttribute('type')) {
                                html += ' type="' + node.getAttribute('type') + '"';
                            }
                            if (node.getAttribute('value')) {
                                html += ' value="' + node.getAttribute('value') + '"';
                            }
                            if (node.getAttribute('href')) {
                                html += ' href="' + node.getAttribute('href') + '"';
                            }
                            if (node.getAttribute('src')) {
                                html += ' src="' + node.getAttribute('src') + '"';
                            }
                            if (node.getAttribute('alt')) {
                                html += ' alt="' + node.getAttribute('alt') + '"';
                            }
                            if (node.getAttribute('title')) {
                                html += ' title="' + node.getAttribute('title') + '"';
                            }
                            if (node.getAttribute('placeholder')) {
                                html += ' placeholder="' + node.getAttribute('placeholder') + '"';
                            }
                            if (node.getAttribute('role')) {
                                html += ' role="' + node.getAttribute('role') + '"';
                            }
                            if (node.getAttribute('aria-label')) {
                                html += ' aria-label="' + node.getAttribute('aria-label') + '"';
                            }

                            html += '>';

                            // Process children
                            for (let i = 0; i < node.childNodes.length; i++) {
                                html += getVisibleHTML(node.childNodes[i]);
                            }

                            html += '</' + node.tagName.toLowerCase() + '>';
                        } else if (node.nodeType === Node.TEXT_NODE) {
                            const text = node.textContent.trim();
                            if (text) {
                                html += text;
                            }
                        }
                        return html;
                    }

                    return getVisibleHTML(document.body);
                """)
                if visible_html and visible_html.strip():
                    return visible_html
            except Exception as e:
                self.logger.warning(f"JavaScript visible HTML extraction failed: {str(e)}")

            # Fallback to full HTML if JavaScript extraction fails
            return html

        except Exception as e:
            self.logger.error(f"Error in get_visible_html: {str(e)}")
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

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
import re
import logging
from typing import Optional
from lib.config import Config
import uuid

class HTMLSimplifier:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.max_prompt_tokens = Config.get_max_prompt_tokens()

    def simplify_html(self, html_content: str) -> str:
        """Simplify HTML content by removing non-essential elements and attributes"""
        if not html_content or not isinstance(html_content, str) or not html_content.strip():
            return self._create_fallback_html("Empty or invalid HTML content provided").replace("<", chr(10) + "<")

        try:
            soup = self._parse_html(html_content)
            if not soup:
                return self._create_fallback_html_with_partial_content(html_content, "HTML parsing failed").replace("<", chr(10) + "<")

            self._remove_non_essential_elements(soup)
            visible_text = self._get_visible_text(soup)

            if visible_text and visible_text.strip():
                return self._clean_html_output(str(soup))
            else:
                return self._create_fallback_html_with_partial_content(html_content, "No visible text content found").replace("<", chr(10) + "<")

        except Exception as e:
            self.logger.error(f"Error in simplify_html: {str(e)}")
            return self._create_fallback_html_with_partial_content(html_content, f"Error in simplify_html: {str(e)}").replace("<", chr(10) + "<")

    def get_visible_html(self, driver) -> str:
        """Get HTML content that represents what the user actually sees using JavaScript execution"""
        try:
            js_script = """
            function getVisibleHtml() {
                try {
                    const resultDoc = document.implementation.createHTMLDocument('Visible HTML');
                    const resultBody = resultDoc.body;

                    function isElementVisible(el) {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                            return false;
                        }

                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    }

                    function cloneElementWithSemantics(el, targetParent) {
                        try {
                            if (!isElementVisible(el)) return false;

                            const clone = el.cloneNode(false);
                            targetParent.appendChild(clone);

                            const keepAttrs = ['id', 'class', 'name', 'type', 'value', 'href', 'src', 'alt', 'title',
                                              'placeholder', 'role', 'aria-label', 'aria-labelledby', 'for', 'data-'];

                            for (const attr of Array.from(el.attributes || [])) {
                                try {
                                    if (keepAttrs.some(k => attr.name === k || (k === 'data-' && attr.name.startsWith('data-')))) {
                                        clone.setAttribute(attr.name, attr.value);
                                    }
                                } catch (e) {
                                    continue;
                                }
                            }

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

                            if (!hasVisibleChildren && !['br', 'hr', 'img', 'input', 'meta', 'link'].includes(el.tagName.toLowerCase())) {
                                targetParent.removeChild(clone);
                                return false;
                            }

                            return true;
                        } catch (e) {
                            return false;
                        }
                    }

                    const elements = Array.from(document.querySelectorAll('*'));
                    for (const el of elements) {
                        try {
                            if (!el.parentNode || !resultBody.contains(el.parentNode)) {
                                cloneElementWithSemantics(el, resultBody);
                            }
                        } catch (e) {
                            continue;
                        }
                    }

                    return resultBody.children.length > 0 ? resultDoc.documentElement.outerHTML : document.documentElement.outerHTML;
                } catch (e) {
                    console.error("Error in getVisibleHtml:", e);
                    return document.documentElement.outerHTML;
                }
            }

            return getVisibleHtml();
            """

            visible_html = driver.execute_script(js_script)
            if visible_html != 'undefined':
                return visible_html

            return self._create_fallback_html_with_partial_content(driver.page_source, "JavaScript visibility detection failed")

        except Exception as e:
            self.logger.error(f"Error in get_visible_html: {str(e)}")
            return self._create_fallback_html_with_partial_content(driver.page_source, f"Error in JavaScript execution: {str(e)}")

    def _parse_html(self, html_content: str) -> Optional[BeautifulSoup]:
        """Parse HTML content with BeautifulSoup"""
        try:
            return BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            self.logger.warning(f"BeautifulSoup parsing failed: {str(e)}")
            return None

    def _remove_non_essential_elements(self, soup: BeautifulSoup) -> None:
        """Remove non-essential elements from the HTML"""
        try:
            for tag_name in ["script", "style", "noscript", "meta", "link", "svg", "canvas", "iframe", "object", "embed"]:
                for element in soup.find_all(tag_name):
                    element.decompose()

            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
        except Exception as e:
            self.logger.warning(f"Error removing non-essential elements: {str(e)}")

    def _get_visible_text(self, soup: BeautifulSoup) -> str:
        """Extract visible text from BeautifulSoup object"""
        try:
            for tag_name in ["head", "svg", "canvas", "iframe", "object", "embed"]:
                for element in soup.find_all(tag_name):
                    element.decompose()

            text = soup.get_text()
            if not text:
                return ""

            lines = []
            for line in text.splitlines():
                stripped_line = line.strip()
                if stripped_line:
                    lines.append(stripped_line)
            return '\n'.join(lines)
        except Exception as e:
            self.logger.warning(f"Error in _get_visible_text: {str(e)}")
            return ""

    def _clean_html_output(self, html: str) -> str:
        """Clean HTML output to prevent duplicate content"""
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Remove duplicate html/body tags
            for tag in soup.find_all(['html', 'body']):
                if len(tag.find_all(['html', 'body'])) > 0:
                    tag.unwrap()

            # Remove duplicate content
            seen = set()
            for tag in soup.find_all():
                tag_str = str(tag)
                if tag_str in seen:
                    tag.decompose()
                else:
                    seen.add(tag_str)

            return str(soup).replace("<", chr(10) + "<")
        except Exception as e:
            self.logger.warning(f"Error cleaning HTML output: {str(e)}")
            return html.replace("<", chr(10) + "<")

    def _create_fallback_html(self, error_message: str = "") -> str:
        """Create a valid fallback HTML structure with error information"""
        try:
            soup = BeautifulSoup("<html><head></head><body></body></html>", "html.parser")

            if error_message:
                error_div = soup.new_tag("div")
                error_div["class"] = "newt-error"
                error_div.string = f"NEWT Processing Error: {error_message}"
                soup.body.append(error_div)

            structure_div = soup.new_tag("div")
            structure_div["class"] = "newt-structure"
            structure_div.string = "Basic HTML structure preserved for analysis"
            soup.body.append(structure_div)

            return "<!DOCTYPE html>\n" + str(soup)
        except Exception:
            return "<!DOCTYPE html>\n<html><head></head><body><div>Error processing content</div></body></html>"

    def _create_fallback_html_with_partial_content(self, original_html: str, error_message: str = "") -> str:
        """Create fallback HTML that preserves as much of the original content as possible"""
        try:
            meaningful_content = self._extract_meaningful_content(original_html)
            soup = BeautifulSoup("<html><head></head><body></body></html>", "html.parser")

            if error_message:
                error_div = soup.new_tag("div")
                error_div["class"] = "newt-error"
                error_div.string = f"NEWT Processing Error: {error_message}"
                soup.body.append(error_div)

            if meaningful_content:
                preserved_div = soup.new_tag("div")
                preserved_div["class"] = "newt-preserved-content"
                preserved_div.string = meaningful_content
                soup.body.append(preserved_div)

            return "<!DOCTYPE html>\n" + str(soup)
        except Exception as e:
            return self._create_fallback_html(f"Error creating fallback with partial content: {str(e)}")

    def _extract_meaningful_content(self, html_content: str) -> Optional[str]:
        """Extract meaningful content from HTML even if parsing fails"""
        try:
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
            if body_match:
                body_content = body_match.group(1)
                body_content = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                body_content = re.sub(r'<style[^>]*>.*?</style>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                body_content = re.sub(r'<noscript[^>]*>.*?</noscript>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                body_content = re.sub(r'<input[^>]*type="hidden"[^>]*>', '', body_content, flags=re.IGNORECASE)

                text_content = re.sub(r'<[^>]+>', ' ', body_content)
                text_content = re.sub(r'\s+', ' ', text_content).strip()

                if text_content:
                    return text_content[:2000]

            title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.DOTALL | re.IGNORECASE)
            if title_match:
                return f"Page Title: {title_match.group(1).strip()}"

            heading_matches = re.findall(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html_content, re.DOTALL | re.IGNORECASE)
            if heading_matches:
                headings = [re.sub(r'<[^>]+>', ' ', h).strip() for h in heading_matches]
                return "Page Headings: " + " | ".join(headings[:5])

            link_matches = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html_content, re.DOTALL | re.IGNORECASE)
            if link_matches:
                links = [f"{text.strip() if text.strip() else url}" for url, text in link_matches[:10]]
                return "Page Links: " + " | ".join(links)

            para_matches = re.findall(r'<p[^>]*>(.*?)</p>', html_content, re.DOTALL | re.IGNORECASE)
            if para_matches:
                paras = [re.sub(r'<[^>]+>', ' ', p).strip() for p in para_matches[:3]]
                return "Page Content: " + " | ".join(paras)

            text_match = re.search(r'>([^<]{10,})<', html_content)
            if text_match:
                return text_match.group(1).strip()[:500]

            return None

        except Exception as e:
            self.logger.warning(f"Error in _extract_meaningful_content: {str(e)}")
            return None

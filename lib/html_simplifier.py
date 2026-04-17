from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from lib.config import Config
from selenium.webdriver.common.by import By
import uuid
import traceback

class HTMLSimplifier:
    def __init__(self):
        self.max_prompt_tokens = Config.get_max_prompt_tokens()
        self.current_token_count = 0
        self.result = []

    def get_visible_html(self, driver):
        try:
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
            print(f"Error in get_visible_html: {str(e)}")
            traceback.print_exc()
            return driver.page_source

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
                print(f"Error parsing HTML: {str(e)}")
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
                                    print(f"Error processing select: {str(e)}")
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
                            print(f"Error cloning tag: {str(e)}")
                            traceback.print_exc()
                            return None

                        # Recurse into children
                        for child in node.children:
                            try:
                                filtered = filter_node(child)
                                if filtered:
                                    new_tag.append(filtered)
                            except Exception as e:
                                print(f"Error processing child: {str(e)}")
                                traceback.print_exc()
                                continue

                        return new_tag

                    # Keep text nodes
                    if isinstance(node, str) and node.strip():
                        return node

                    return None
                except Exception as e:
                    print(f"Error in filter_node: {str(e)}")
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
                        print(f"Error processing body child: {str(e)}")
                        traceback.print_exc()
                        continue

            new_html.append(new_body)

            return "<!DOCTYPE html>\n" + str(new_html)
        except Exception as e:
            print(f"Error in _get_visible_html_with_visibility: {str(e)}")
            traceback.print_exc()
            return None

    def _get_visible_html_without_visibility(self, driver):
        try:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            # Remove noise tags
            for tag in soup(["script", "style", "noscript", "meta", "link", "svg", "canvas", "img", "iframe", "object", "embed"]):
                tag.decompose()
            # Keep only charset and viewport meta tags
            if soup.head:
                for meta in soup.head.find_all("meta"):
                    if not (meta.get("charset") or meta.get("name") == "viewport"):
                        meta.decompose()
            return "<!DOCTYPE html>\n" + str(soup)
        except Exception as e:
            print(f"Error in _get_visible_html_without_visibility: {str(e)}")
            traceback.print_exc()
            return None

    def simplify_html(self, html: str) -> str:
        """
        Simplifies HTML by removing noise, comments, styling, and non-semantic classes.
        Outputs a valid, stripped-down HTML page optimized for LLM consumption.
        """
        try:
            if not html or not html.strip():
                print("Error: Input HTML is empty or None.")
                return "<html><body>Error: Input HTML is empty.</body></html>"

            soup = BeautifulSoup(html, "html.parser")

            # --- Step 1: Remove comments ---
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            # --- Step 2: Remove noise tags ---
            for tag in soup(["script", "style", "noscript", "svg", "canvas", "img", "iframe", "object", "embed"]):
                tag.decompose()

            # --- Step 3: Keep only essential meta tags ---
            if soup.head:
                for meta in soup.head.find_all("meta"):
                    if not (meta.get("charset") or meta.get("name") == "viewport"):
                        meta.decompose()

            # --- Step 4: Remove hidden/invisible elements ---
            for tag in soup.find_all(True):
                # Remove by style
                style = tag.get("style", "").lower()
                if "display:none" in style or "visibility:hidden" in style:
                    tag.decompose()
                # Remove by class
                classes = tag.get("class", [])
                if any(cls in ["hidden", "invisible", "zero-size"] for cls in classes):
                    tag.decompose()

            # --- Step 5: Clean up attributes ---
            for tag in soup.find_all(True):
                attrs = dict(tag.attrs)
                for attr in list(attrs.keys()):
                    try:
                        # Remove empty aria-label
                        if attr == "aria-label" and not tag.get(attr, "").strip():
                            del tag[attr]
                        # Remove style attributes
                        elif attr == "style":
                            del tag[attr]
                        # Remove empty or non-semantic classes
                        elif attr == "class":
                            classes = tag.get("class", [])
                            # Keep only semantic classes (e.g., "error", "hidden")
                            semantic_classes = [cls for cls in classes if cls in ["error", "hidden", "bug-section"]]
                            if not semantic_classes:
                                del tag[attr]
                            else:
                                tag["class"] = semantic_classes
                        # Remove data-* attributes except data-label
                        elif attr.startswith("data-") and attr != "data-label":
                            del tag[attr]
                        # Simplify boolean attributes (e.g., required="", selected="True" -> required, selected)
                        elif attr in ["required", "selected", "disabled", "readonly"]:
                            if tag.get(attr, "").lower() in ["true", ""]:
                                tag[attr] = None  # BeautifulSoup will render as just the attribute name
                    except Exception as e:
                        print(f"Error processing attribute {attr}: {str(e)}")
                        continue

            # --- Step 6: Remove empty tags (except structural ones) ---
            for tag in soup.find_all(True):
                if tag.name not in ["div", "span", "p", "body", "html", "head", "form", "ul", "ol", "li", "button", "label", "input", "select", "option"]:
                    if not tag.contents and not tag.attrs:
                        tag.decompose()
                # Remove empty divs/spans if they have no semantic meaning
                elif tag.name in ["div", "span"] and not tag.contents and not any(attr in tag.attrs for attr in ["id", "class", "role", "data-label"]):
                    tag.decompose()

            # --- Step 7: Fix duplicate DOCTYPE ---
            html_str = str(soup)
            html_str = html_str.replace("<!DOCTYPE html><!DOCTYPE html>", "<!DOCTYPE html>")

            return html_str
        except Exception as e:
            print(f"Error in simplify_html: {str(e)}")
            import traceback
            traceback.print_exc()
            return "<html><body>Error simplifying HTML: " + str(e) + "</body></html>"
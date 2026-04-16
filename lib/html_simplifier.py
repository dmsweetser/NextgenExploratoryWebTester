from bs4 import BeautifulSoup, NavigableString, Tag
from lib.config import Config
from selenium.webdriver.common.by import By
import uuid


class HTMLSimplifier:
    def __init__(self):
        self.max_prompt_tokens = Config.get_max_prompt_tokens()
        self.current_token_count = 0
        self.result = []


    def get_visible_html(self, driver):
        try:
            # JS visibility logic
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

            # STEP 1 — Assign unique IDs to every element
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

            # STEP 2 — Re-read the DOM with IDs included
            try:
                soup = BeautifulSoup(driver.page_source, "html.parser")
            except Exception:
                return "<html><body>Error processing page HTML</body></html>"

            # STEP 3 — Build visibility map keyed by data-vis-id
            visibility = {}
            for el, uid in element_ids.items():
                try:
                    visible = driver.execute_script(js_visibility_check, el)
                    visibility[uid] = visible
                except Exception:
                    continue

            # Track processed elements to prevent duplicates
            processed_elements = set()

            # STEP 4 — Recursively filter DOM with error handling
            def filter_node(node):
                try:
                    if isinstance(node, Tag):
                        uid = node.get("data-vis-id", "")
                        if uid in processed_elements:
                            return None
                        processed_elements.add(uid)

                        this_visible = visibility.get(uid, False) if uid else False

                        # SPECIAL CASE: keep <select> ONLY if the select itself is visible
                        if node.name == "select":
                            if this_visible:
                                try:
                                    selected = node.find("option", selected=True)
                                    new_select = soup.new_tag("select", **{
                                        k: v for k, v in node.attrs.items()
                                        if k != "data-vis-id"
                                    })
                                    if selected:
                                        new_option = soup.new_tag("option", selected=True)
                                        new_option.string = selected.get_text(strip=True)
                                        new_select.append(new_option)
                                    return new_select
                                except Exception:
                                    return None
                            return None  # invisible select → drop it

                        # Normal visibility rule: drop invisible nodes
                        if uid and not this_visible:
                            return None

                        # Clone tag with error handling
                        try:
                            new_tag = soup.new_tag(node.name, **{
                                k: v for k, v in node.attrs.items()
                                if k != "data-vis-id"
                            })
                        except Exception:
                            return None

                        # Recurse into children with error handling
                        for child in node.children:
                            try:
                                filtered = filter_node(child)
                                if filtered:
                                    new_tag.append(filtered)
                            except Exception:
                                continue

                        return new_tag

                    # Keep text nodes
                    if isinstance(node, str) and node.strip():
                        return node

                    return None
                except Exception:
                    return None

            # STEP 5 — Build final HTML document with error handling
            new_html = soup.new_tag("html")
            new_body = soup.new_tag("body")

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
        except Exception as e:
            self.logger.error(f"Error in get_visible_html: {str(e)}")
            return "<html><body>Error processing page HTML</body></html>"

    def simplify_html(self, html: str) -> str:
        self.max_prompt_tokens = Config.get_max_prompt_tokens()
        self.current_token_count = 0
        self.result = []

        soup = BeautifulSoup(html, "html.parser")

        # Remove noise tags (even if visible)
        for tag in soup([
            "script", "style", "noscript", "meta", "link",
            "svg", "canvas", "img", "iframe", "object", "embed"
        ]):
            tag.decompose()

        # --- Direct text only ---
        def direct_text(el):
            return "".join(
                child.strip()
                for child in el.children
                if isinstance(child, NavigableString)
            )

        # --- Short selector (tag + id + classes) ---
        def short_selector(el):
            if el.name == "[document]":
                return "[document]"

            tag = el.name

            if el.has_attr("id"):
                return f"{tag}#{el['id']}"

            classes = "".join(f".{c}" for c in el.get("class", []) if c)
            return f"{tag}{classes}"

        # --- Relevant attributes ---
        def relevant_attrs(el):
            attrs = []

            # Inputs
            if el.name == "input":
                attrs.append(f"[type='{el.get('type', 'text')}']")
                if el.get("placeholder"):
                    attrs.append(f"[placeholder='{el['placeholder']}']")

            # Buttons and links
            elif el.name in ["button", "a"]:
                if el.name == "button" and el.get("type"):
                    attrs.append(f"[type='{el['type']}']")
                if el.name == "a" and el.get("href"):
                    attrs.append(f"[href='{el['href']}']")

            # Selects
            elif el.name == "select" and el.get("id"):
                selected = el.find("option", selected=True)
                if selected:
                    return f" > option: '{selected.get_text(strip=True)}'"

            # Data attributes
            if el.get("data-label"):
                attrs.append(f"[data-label='{el['data-label']}']")
            if el.get("data-bs-toggle"):
                attrs.append(f"[data-bs-toggle='{el['data-bs-toggle']}']")

            return " ".join(attrs) if attrs else ""

        # --- Label consolidation ---
        def consolidate_label(el):
            if el.name == "label" and el.get("for"):
                input_id = el["for"]
                input_tag = soup.find(attrs={"id": input_id})
                if input_tag:
                    label_text = el.get_text(strip=True)
                    if label_text:
                        input_tag["data-label"] = label_text
                    return True
            return False

        # --- Process element ---
        def process(el):
            if isinstance(el, NavigableString):
                return

            # Consolidate labels (still useful)
            if consolidate_label(el):
                return

            sel = short_selector(el)
            attrs = relevant_attrs(el)
            text = direct_text(el)

            # Skip empty containers
            if el.name in ["div", "span", "li"] and not attrs and not text:
                return

            # Text-bearing tags
            if el.name in [
                "h1", "h2", "h3", "h4", "h5", "h6",
                "p", "span", "li", "strong", "em", "b", "i", "div"
            ]:
                if text:
                    line = f"{sel}: '{text}'"
                elif attrs:
                    line = f"{sel} {attrs}"
                else:
                    line = sel
                self._add_line(line)
                return

            # Links
            if el.name == "a":
                if text:
                    line = f"{sel} {attrs}: '{text}'"
                else:
                    line = f"{sel} {attrs}"
                self._add_line(line)
                return

            # Buttons
            if el.name == "button":
                if text:
                    line = f"{sel} {attrs}: '{text}'"
                else:
                    line = f"{sel} {attrs}"
                self._add_line(line)
                return

            # Inputs
            if el.name == "input":
                line = f"{sel} {attrs}"
                self._add_line(line)
                return

            # Selects
            if el.name == "select":
                line = f"{sel} {attrs}"
                self._add_line(line)
                return

            # Fallback
            if attrs:
                self._add_line(f"{sel} {attrs}")
            else:
                self._add_line(sel)

        # --- Process DOM ---
        for el in soup.body.descendants if soup.body else soup.descendants:
            if el.name == "option":
                continue
            process(el)
            if self.current_token_count > self.max_prompt_tokens:
                break

        return "".join(self.result)

    # --- Add line with token check ---
    def _add_line(self, line):
        line += "\n"
        line_length = len(line)
        if self.current_token_count + line_length > self.max_prompt_tokens:
            if "# [TRUNCATED BY NEWT] HTML content reduced to fit token limit" not in self.result:
                self.result.append("# [TRUNCATED BY NEWT] HTML content reduced to fit token limit")
            return False
        self.result.append(line)
        self.current_token_count += line_length
        return True

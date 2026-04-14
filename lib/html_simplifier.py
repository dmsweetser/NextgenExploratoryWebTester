from bs4 import BeautifulSoup, NavigableString
from lib.config import Config

class HTMLSimplifier:
    def __init__(self):
        self.max_prompt_tokens = Config.get_max_prompt_tokens()
        self.current_token_count = 0
        self.result = []

    def simplify_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise tags entirely
        for tag in soup([
            "script", "style", "noscript", "meta", "link",
            "svg", "canvas", "img", "iframe", "object", "embed"
        ]):
            tag.decompose()

        # ---------------------------------------
        # Check if element is visible to user
        # ---------------------------------------
        def is_visible(el):
            if not hasattr(el, "name"):
                return False
            if el.has_attr("hidden"):
                return False
            if el.has_attr("style") and any(
                s in el["style"] for s in ["display: none", "visibility: hidden", "opacity: 0"]
            ):
                return False
            parent = el.parent
            while parent:
                if parent.name and (parent.has_attr("hidden") or
                                   (parent.has_attr("style") and any(
                                       s in parent["style"] for s in ["display: none", "visibility: hidden", "opacity: 0"]
                                   ))):
                    return False
                parent = parent.parent
            return True

        # ---------------------------------------
        # Build a full selector including parents
        # ---------------------------------------
        def full_selector(el):
            """Returns the shortest useful selector for the element."""
            if el.name == "[document]":
                return "[document]"
            if el.has_attr("id"):
                return f"#{el['id']}"
            if el.name == "body":
                return "body"
            classes = "".join(f".{c}" for c in el.get("class", []) if c)
            return f"{el.name}{classes}"

        # ---------------------------------------
        # Convert attributes to a readable string - only include relevant attributes
        # ---------------------------------------
        def attr_string(el):
            """Returns only the most relevant attributes for interaction."""
            relevant = []
            if el.name == "a" and el.get("href"):
                relevant.append(f"[href='{el['href']}']")
            if el.name == "input" and el.get("type") != "hidden":
                relevant.append(f"[type='{el.get('type', 'text')}']")
            if el.name in ["button", "input", "select", "textarea"] and el.get("name"):
                relevant.append(f"[name='{el['name']}']")
            if el.get("data-label"):
                relevant.append(f"[data-label='{el['data-label']}']")
            return " ".join(relevant)

        # ---------------------------------------
        # Get immediate text (not nested text)
        # ---------------------------------------
        def immediate_text(el):
            text = ""
            for child in el.children:
                if isinstance(child, NavigableString):
                    text += child.strip()
                elif hasattr(child, "name"):
                    break
            return text.strip()

        # ---------------------------------------
        # Consolidate labels and inputs
        # ---------------------------------------
        def consolidate_label_input(el):
            if el.name == "label" and el.get("for"):
                input_id = el["for"]
                input_tag = soup.find(attrs={"id": input_id})
                if input_tag and is_visible(input_tag):
                    label_text = immediate_text(el)
                    if label_text:
                        input_tag["data-label"] = label_text
                    return True
            return False

        # ---------------------------------------
        # Process each element in DOM order
        # ---------------------------------------
        def process(el):
            # Skip text nodes and invisible elements
            if isinstance(el, NavigableString) or not is_visible(el):
                return

            # Consolidate label and input
            if consolidate_label_input(el):
                return

            tag = el.name
            sel = full_selector(el)
            attrs = attr_string(el)

            # TEXT‑BEARING TAGS
            if tag in ["h1","h2","h3","h4","h5","h6","p","span","li","strong","em","b","i","div"]:
                text = immediate_text(el)
                if text:
                    self._add_line(f"{sel}: '{text}'", attrs)
                elif attrs:
                    self._add_line(sel, attrs)
                return

            # LINKS
            if tag == "a" and el.get("href"):
                text = immediate_text(el)
                href = el["href"]
                base = f"{sel} [{attrs}]" if attrs else sel
                if text:
                    self._add_line(f"{base}: '{text}' ({href})")
                else:
                    self._add_line(f"{base} ({href})")
                return

            # GENERIC ELEMENTS
            if tag not in ["input", "select", "textarea"]:
                if attrs:
                    self._add_line(f"{sel} [{attrs}]")
                else:
                    self._add_line(sel)
                return

            # INPUT
            if tag == "input":
                input_type = el.get("type", "text")
                if input_type in ["hidden", "file"]:
                    return
                if "data-label" in el.attrs:
                    attrs = attr_string(el).replace("data-label", "")
                    self._add_line(f"{sel} [{attrs}]: '{el['data-label']}'")
                else:
                    if attrs:
                        self._add_line(f"{sel} [{attrs}]")
                    else:
                        self._add_line(sel)
                return

            # SELECT
            if tag == "select":
                if attrs:
                    self._add_line(f"{sel} [{attrs}]")
                else:
                    self._add_line(sel)
                options = el.find_all("option")
                selected = next((opt for opt in options if opt.has_attr("selected")), None)
                if selected:
                    self._add_line(f"{sel} > option: '{immediate_text(selected)}'  <!-- {len(options)} total -->")
                return

            # TEXTAREA
            if tag == "textarea":
                text = immediate_text(el)
                if "data-label" in el.attrs:
                    attrs = attr_string(el).replace("data-label", "")
                    self._add_line(f"{sel} [{attrs}]: '{el['data-label']}': '{text}'")
                else:
                    if text:
                        if attrs:
                            self._add_line(f"{sel} [{attrs}]: '{text}'")
                        else:
                            self._add_line(f"{sel}: '{text}'")
                    else:
                        if attrs:
                            self._add_line(f"{sel} [{attrs}]")
                        else:
                            self._add_line(sel)
                return

        # ---------------------------------------
        # DOM‑ORDER WALK
        # ---------------------------------------
        for el in soup.body.descendants if soup.body else soup.descendants:
            if el.name == "option":
                continue
            process(el)
            if self.current_token_count > self.max_prompt_tokens:
                break

        return "".join(self.result)
    
    # ---------------------------------------
    # Helper to add a line and check token count
    # ---------------------------------------
    def _add_line(self, selector_part, attrs_part=""):
        line = f"{selector_part} [{attrs_part}]" if attrs_part else selector_part
        line += "\n"
        line_length = len(line)
        if self.current_token_count + line_length > self.max_prompt_tokens:
            self.result.append("# [TRUNCATED] HTML content reduced to fit token limit")
            return False
        self.result.append(line)
        self.current_token_count += line_length
        return True
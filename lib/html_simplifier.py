from bs4 import BeautifulSoup, NavigableString
from lib.config import Config

class HTMLSimplifier:
    def __init__(self):
        self.max_prompt_tokens = Config.get_max_prompt_tokens()
        self.current_token_count = 0
        self.result = []

    def simplify_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise tags
        for tag in soup([
            "script", "style", "noscript", "meta", "link",
            "svg", "canvas", "img", "iframe", "object", "embed"
        ]):
            tag.decompose()

        # --- Visibility check ---
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

        # --- Direct text only ---
        def direct_text(el):
            return "".join(
                child.strip()
                for child in el.children
                if isinstance(child, NavigableString)
            )

        # --- Short selector (now includes tag + ID) ---
        def short_selector(el):
            if el.name == "[document]":
                return "[document]"

            tag = el.name

            # ID takes priority but keeps tag name
            if el.has_attr("id"):
                return f"{tag}#{el['id']}"

            # Otherwise use tag + classes
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
            # Labels and data attributes
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
                if input_tag and is_visible(input_tag):
                    label_text = el.get_text(strip=True)
                    if label_text:
                        input_tag["data-label"] = label_text
                    return True
            return False

        # --- Process element ---
        def process(el):
            if isinstance(el, NavigableString) or not is_visible(el):
                return
            if consolidate_label(el):
                return

            sel = short_selector(el)
            attrs = relevant_attrs(el)
            text = direct_text(el)

            # Skip empty containers with no direct text and no attributes
            if el.name in ["div", "span", "li"] and not attrs and not text:
                return

            # Text-bearing tags (direct text only)
            if el.name in ["h1", "h2", "h3", "h4", "h5", "h6",
                           "p", "span", "li", "strong", "em", "b", "i", "div"]:
                if text:
                    line = f"{sel}: '{text}'"
                elif attrs:
                    line = f"{sel} {attrs}"
                else:
                    line = sel
                self._add_line(line)
                return

            # Links
            if el.name == "a" and el.get("href"):
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

            # Generic fallback
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
            self.result.append("# [TRUNCATED] HTML content reduced to fit token limit")
            return False
        self.result.append(line)
        self.current_token_count += line_length
        return True

from bs4 import BeautifulSoup


class HTMLSimplifier:
    # Elements the bot may interact with
    INTERACTIVE_TAGS = {
        "input", "select", "option", "textarea", "button", "a"
    }

    # Semantic and structural context
    CONTEXT_TAGS = {
        "label", "form", "fieldset", "legend",
        "p", "span", "div",
        "ul", "ol", "li",
        "table", "thead", "tbody", "tr", "td", "th",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "section", "article", "header", "footer", "nav", "main"
    }

    WHITELIST_TAGS = INTERACTIVE_TAGS | CONTEXT_TAGS

    # Attributes needed for JS selectors or meaning
    WHITELIST_ATTRS = {
        "id", "name", "type", "value",
        "checked", "selected", "href",
        "placeholder", "for",
        "role", "title",
        "aria-label", "aria-labelledby", "aria-describedby"
    }

    def simplify_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        # ---------------------------------------------------------
        # 1. Remove obvious noise
        # ---------------------------------------------------------
        for tag in soup([
            "script", "style", "noscript", "meta", "link",
            "svg", "canvas", "img", "iframe", "object", "embed"
        ]):
            tag.decompose()

        # ---------------------------------------------------------
        # 2. Preserve inner text for interactive elements
        #    BEFORE destructive operations
        # ---------------------------------------------------------
        self._preserve_interactive_inner_text(soup)

        # ---------------------------------------------------------
        # 3. Remove non-whitelisted tags but keep their text
        # ---------------------------------------------------------
        for tag in soup.find_all(True):
            if tag.name not in self.WHITELIST_TAGS:
                tag.unwrap()

        # ---------------------------------------------------------
        # 4. Strip attributes aggressively
        # ---------------------------------------------------------
        for tag in soup.find_all(True):
            attrs = dict(tag.attrs)
            for attr in list(attrs.keys()):
                if attr not in self.WHITELIST_ATTRS:
                    # Keep class ONLY for interactive elements
                    if attr == "class" and tag.name in self.INTERACTIVE_TAGS:
                        continue
                    del tag.attrs[attr]

        # ---------------------------------------------------------
        # 5. Normalize input elements
        # ---------------------------------------------------------
        self._normalize_inputs(soup)

        # ---------------------------------------------------------
        # 6. Normalize selects (keep only selected option)
        # ---------------------------------------------------------
        self._normalize_selects(soup)

        # ---------------------------------------------------------
        # 7. Remove empty containers
        # ---------------------------------------------------------
        self._remove_empty_containers(soup)

        # ---------------------------------------------------------
        # 8. Collapse whitespace
        # ---------------------------------------------------------
        simplified = " ".join(str(soup).split())

        return simplified

    # ============================================================
    # Helpers
    # ============================================================

    def _preserve_interactive_inner_text(self, soup):
        """
        Extracts inner text from interactive elements and injects it
        as plain text before simplification removes nested tags.
        """
        for tag in soup.find_all(True):
            if tag.name in self.INTERACTIVE_TAGS:
                text = tag.get_text(" ", strip=True)
                if text:
                    tag.insert(0, text + " ")

    def _normalize_inputs(self, soup):
        for input_tag in soup.find_all("input"):
            t = (input_tag.get("type") or "text").lower()

            if t == "text":
                input_tag["value"] = input_tag.get("value", "")
            elif t in ("checkbox", "radio"):
                if input_tag.has_attr("checked"):
                    input_tag["checked"] = "checked"
                else:
                    input_tag.attrs.pop("checked", None)
            elif t in ("submit", "button", "reset"):
                pass
            else:
                # Remove irrelevant input types
                input_tag.decompose()

    def _normalize_selects(self, soup):
        for select_tag in soup.find_all("select"):
            options = select_tag.find_all("option")
            if not options:
                continue

            selected = next((o for o in options if o.has_attr("selected")), None)
            if not selected:
                selected = options[0]

            # Keep only the selected option
            for option in options:
                if option is not selected:
                    option.decompose()

            selected["selected"] = "selected"

    def _remove_empty_containers(self, soup):
        """
        Remove non-interactive tags that have no text and no children.
        """
        changed = True
        while changed:
            changed = False
            for tag in list(soup.find_all(True)):
                if tag.name in self.INTERACTIVE_TAGS:
                    continue

                has_text = bool(tag.get_text(strip=True))
                has_children = bool(tag.find(True))

                if not has_text and not has_children:
                    tag.decompose()
                    changed = True

from bs4 import BeautifulSoup, NavigableString

class HTMLSimplifier:
    # Elements Selenium can interact with or that provide meaningful context
    INTERACTIVE_TAGS = {
        "input", "select", "option", "textarea", "button", "a"
    }

    # Elements that provide semantic structure or text context
    CONTEXT_TAGS = {
        "label", "form", "fieldset", "legend",
        "p", "span", "div",
        "ul", "ol", "li",
        "table", "thead", "tbody", "tr", "td", "th",
        "h1", "h2", "h3", "h4", "h5", "h6"
    }

    WHITELIST_TAGS = INTERACTIVE_TAGS | CONTEXT_TAGS

    # Attributes Selenium may rely on
    WHITELIST_ATTRS = {
        "type", "value", "checked", "selected", "name",
        "href", "placeholder", "for", "id"
    }

    def simplify_html(self, html):
        soup = BeautifulSoup(html, "html.parser")

        # Remove obvious noise
        for tag in soup(["script", "style", "noscript", "meta", "link", "svg", "canvas", "img", "iframe", "object", "embed"]):
            tag.decompose()

        # Remove all non-whitelisted tags but keep their text
        for tag in soup.find_all(True):
            if tag.name not in self.WHITELIST_TAGS:
                tag.unwrap()

        # Strip attributes aggressively
        for tag in soup.find_all(True):
            attrs = dict(tag.attrs)
            for attr in list(attrs.keys()):
                if not any(attr == allowed or attr.startswith("data-") for allowed in self.WHITELIST_ATTRS):
                    del tag.attrs[attr]

        # Normalize input elements
        for input_tag in soup.find_all("input"):
            t = input_tag.get("type", "text")

            if t == "text":
                input_tag["value"] = input_tag.get("value", "")
            elif t in ("checkbox", "radio"):
                if input_tag.has_attr("checked"):
                    input_tag["checked"] = "checked"
                else:
                    input_tag.attrs.pop("checked", None)
            elif t in ("submit", "button"):
                pass  # keep
            else:
                # Remove irrelevant input types (file, hidden, color, date, etc.)
                input_tag.decompose()

        # Normalize select elements
        for select_tag in soup.find_all("select"):
            options = select_tag.find_all("option")
            selected = None

            for option in options:
                if option.has_attr("selected"):
                    selected = option
                    break

            if not selected and options:
                selected = options[0]

            # Remove all other options
            for option in options:
                if option is not selected:
                    option.decompose()

            select_tag["data-has-options"] = "true"

        # Remove empty containers
        for tag in soup.find_all(True):
            if tag.name not in self.INTERACTIVE_TAGS:
                if not tag.text.strip() and not tag.find(True):
                    tag.decompose()

        # Collapse whitespace
        simplified = " ".join(str(soup).split())

        return simplified

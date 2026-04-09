from bs4 import BeautifulSoup

class HTMLSimplifier:
    def simplify_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise tags entirely
        for tag in soup([
            "script", "style", "noscript", "meta", "link",
            "svg", "canvas", "img", "iframe", "object", "embed"
        ]):
            tag.decompose()

        result = []

        # ---------------------------------------
        # Build a full selector including parents
        # ---------------------------------------
        def full_selector(el):
            parts = []
            node = el
            while node and hasattr(node, "name"):
                tag = node.name
                el_id = node.get("id")
                el_class = node.get("class", [])

                seg = tag
                if el_id:
                    seg += f"#{el_id}"
                if el_class:
                    seg += "." + ".".join(el_class)

                parts.append(seg)
                node = node.parent

            return " > ".join(reversed(parts))

        # ---------------------------------------
        # Convert attributes to a readable string
        # ---------------------------------------
        def attr_string(el):
            attrs = []
            for key, value in el.attrs.items():
                # Normalize class lists
                if key == "class":
                    value = " ".join(value)
                attrs.append(f"{key}='{value}'")
            return " ".join(attrs) if attrs else ""

        # ---------------------------------------
        # Process each element in DOM order
        # ---------------------------------------
        def process(el):
            tag = el.name
            sel = full_selector(el)
            attrs = attr_string(el)

            # TEXT‑BEARING TAGS (including div)
            if tag in [
                "h1","h2","h3","h4","h5","h6",
                "p","span","li","strong","em","b","i",
                "div"
            ]:
                text = el.get_text(strip=True)
                if text:
                    if attrs:
                        result.append(f"{sel} [{attrs}]: '{text}'")
                    else:
                        result.append(f"{sel}: '{text}'")
                else:
                    if attrs:
                        result.append(f"{sel} [{attrs}]")
                return

            # LINKS
            if tag == "a" and el.get("href"):
                text = el.get_text(strip=True)
                href = el.get("href")
                if attrs:
                    base = f"{sel} [{attrs}]"
                else:
                    base = sel

                if text:
                    result.append(f"{base}: '{text}' ({href})")
                else:
                    result.append(f"{base} ({href})")
                return

            # GENERIC ELEMENTS (including form, button, label, etc.)
            # Inputs, selects, textareas get special handling below
            if tag not in ["input", "select", "textarea"]:
                if attrs:
                    result.append(f"{sel} [{attrs}]")
                else:
                    result.append(sel)
                return

            # INPUT
            if tag == "input":
                input_type = el.get("type", "text")
                if input_type in ["hidden", "file"]:
                    return

                text = ""
                if attrs:
                    result.append(f"{sel} [{attrs}]")
                else:
                    result.append(sel)
                return

            # SELECT
            if tag == "select":
                if attrs:
                    result.append(f"{sel} [{attrs}]")
                else:
                    result.append(sel)

                options = el.find_all("option")
                selected = None
                for opt in options:
                    if opt.has_attr("selected"):
                        selected = opt.get_text(strip=True)
                        break

                if selected:
                    result.append(
                        f"{sel} > option: '{selected}'  <!-- {len(options)} total -->"
                    )
                return

            # TEXTAREA
            if tag == "textarea":
                text = el.get_text(strip=True)
                if attrs:
                    if text:
                        result.append(f"{sel} [{attrs}]: '{text}'")
                    else:
                        result.append(f"{sel} [{attrs}]")
                else:
                    if text:
                        result.append(f"{sel}: '{text}'")
                    else:
                        result.append(sel)
                return

        # ---------------------------------------
        # DOM‑ORDER WALK (including text inside forms/links)
        # ---------------------------------------
        for el in soup.body.descendants if soup.body else soup.descendants:
            if not hasattr(el, "name"):
                continue
            process(el)

        return "\n".join(result)

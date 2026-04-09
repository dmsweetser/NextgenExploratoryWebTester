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
        # Process each element in DOM order
        # ---------------------------------------
        def process(el):
            tag = el.name

            # TEXT‑BEARING TAGS
            if tag in ["h1","h2","h3","h4","h5","h6","p","span","li","strong","em","b","i"]:
                text = el.get_text(strip=True)
                if text:
                    result.append(f"{full_selector(el)}: '{text}'")
                return

            # LINKS
            if tag == "a" and el.get("href"):
                text = el.get_text(strip=True)
                href = el.get("href")
                if text:
                    result.append(f"{full_selector(el)}: '{text}' ({href})")
                else:
                    result.append(f"{full_selector(el)} ({href})")
                return

            # FORMS
            if tag == "form":
                result.append(full_selector(el))
                return

            # INPUTS
            if tag == "input":
                input_type = el.get("type", "text")
                if input_type in ["hidden", "file"]:
                    return

                sel = full_selector(el)
                name = el.get("name")
                placeholder = el.get("placeholder")
                value = el.get("value")

                line = f"{sel} [type={input_type}]"
                if name:
                    line += f" [name={name}]"
                if placeholder:
                    line += f" placeholder='{placeholder}'"
                if value:
                    line += f" value='{value}'"

                result.append(line)
                return

            # SELECT
            if tag == "select":
                sel = full_selector(el)
                result.append(sel)

                options = el.find_all("option")
                selected = None
                for opt in options:
                    if opt.has_attr("selected"):
                        selected = opt.get_text(strip=True)
                        break

                if selected:
                    result.append(f"{sel} > option: '{selected}'  <!-- {len(options)} total -->")
                return

            # TEXTAREA
            if tag == "textarea":
                sel = full_selector(el)
                text = el.get_text(strip=True)
                placeholder = el.get("placeholder")

                if placeholder:
                    result.append(f"{sel} placeholder='{placeholder}'")
                elif text:
                    result.append(f"{sel}: '{text}'")
                else:
                    result.append(sel)
                return

            # BUTTON
            if tag == "button":
                sel = full_selector(el)
                text = el.get_text(strip=True)
                btn_type = el.get("type", "button")

                if text:
                    result.append(f"{sel} [type={btn_type}]: '{text}'")
                else:
                    result.append(f"{sel} [type={btn_type}]")
                return

            # LABEL
            if tag == "label":
                sel = full_selector(el)
                text = el.get_text(strip=True)
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

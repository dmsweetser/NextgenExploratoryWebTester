from bs4 import BeautifulSoup, NavigableString

from lib.config import Config

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
        # Check if element is visible to user
        # ---------------------------------------
        def is_visible(el):
            if not hasattr(el, "name"):
                return False

            # Check for display: none
            if el.has_attr("style") and "display: none" in el["style"]:
                return False

            # Check for visibility: hidden
            if el.has_attr("style") and "visibility: hidden" in el["style"]:
                return False

            # Check for opacity: 0
            if el.has_attr("style") and "opacity: 0" in el["style"]:
                return False

            # Check for hidden attribute
            if el.has_attr("hidden"):
                return False

            # Check if parent is hidden
            parent = el.parent
            while parent:
                if parent.name and (parent.has_attr("hidden") or
                                   (parent.has_attr("style") and ("display: none" in parent["style"] or
                                                                 "visibility: hidden" in parent["style"] or
                                                                 "opacity: 0" in parent["style"]))):
                    return False
                parent = parent.parent

            return True

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
        # Convert attributes to a readable string - only include relevant attributes
        # ---------------------------------------
        def attr_string(el):
            relevant_attrs = ['id', 'name', 'type', 'value', 'href', 'placeholder', 'disabled', 'readonly', 'required', 'checked', 'selected']
            attrs = []
            for key, value in el.attrs.items():
                if key in relevant_attrs or key.startswith('data-'):
                    if key == "class":
                        # Only include classes that affect display/accessibility
                        display_classes = [c for c in value if c in ['active', 'disabled', 'hidden', 'visible', 'show', 'hide', 'collapsed', 'expanded']]
                        if display_classes:
                            value = " ".join(display_classes)
                            attrs.append(f"{key}='{value}'")
                    else:
                        if isinstance(value, list):
                            value = " ".join(value)
                        attrs.append(f"{key}='{value}'")
            return " ".join(attrs) if attrs else ""

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
        # Process each element in DOM order
        # ---------------------------------------
        def process(el):
            # Skip text nodes safely
            if isinstance(el, NavigableString):
                return

            # Skip if not visible
            if not is_visible(el):
                return

            tag = el.name
            sel = full_selector(el)
            attrs = attr_string(el)

            # TEXT‑BEARING TAGS (including div)
            if tag in [
                "h1","h2","h3","h4","h5","h6",
                "p","span","li","strong","em","b","i",
                "div"
            ]:
                text = immediate_text(el)
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
                text = immediate_text(el)
                href = el.get("href")
                base = f"{sel} [{attrs}]" if attrs else sel

                if text:
                    result.append(f"{base}: '{text}' ({href})")
                else:
                    result.append(f"{base} ({href})")
                return

            # GENERIC ELEMENTS (form, div, button, label, etc.)
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
                        selected = immediate_text(opt)
                        break

                if selected:
                    result.append(
                        f"{sel} > option: '{selected}'  <!-- {len(options)} total -->"
                    )
                return

            # TEXTAREA
            if tag == "textarea":
                text = immediate_text(el)
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
        # Estimate token count and truncate if needed
        # ---------------------------------------
        def estimate_token_count(text):
            """Simple approximation: 1 token ~ 4 characters"""
            return len(text) / 4

        def truncate_html(simplified_lines, max_tokens=8000):
            """Truncate HTML representation to stay within token limit"""
            current_count = estimate_token_count(chr(10).join(simplified_lines))

            if current_count <= max_tokens:
                return simplified_lines

            # Truncate by removing less important elements
            truncated = []
            important_tags = ['input', 'button', 'form', 'select', 'textarea', 'a']

            for line in simplified_lines:
                # Keep important interactive elements
                if any(tag in line for tag in important_tags):
                    truncated.append(line)
                # Keep short lines (likely headers, labels, etc.)
                elif len(line) < 100:
                    truncated.append(line)

            # If still too long, truncate further
            if estimate_token_count(chr(10).join(truncated)) > max_tokens:
                # Keep only first 80% and add truncation notice
                cutoff = int(len(truncated) * 0.8)
                truncated = truncated[:cutoff]
                truncated.append("# [TRUNCATED] HTML content reduced to fit token limit")
                truncated.append("# Use GET_SELECT_OPTIONS to get detailed select element information")

            return truncated

        # ---------------------------------------
        # DOM‑ORDER WALK (safe for text nodes)
        # ---------------------------------------
        for el in soup.body.descendants if soup.body else soup.descendants:
            if el.name == "option":
                continue
            process(el)

        # Truncate if needed
        max_prompt_tokens = Config.get_max_prompt_tokens()
        simplified_lines = truncate_html(result, max_prompt_tokens)

        return chr(10).join(simplified_lines)

from bs4 import BeautifulSoup

class HTMLSimplifier:
    def simplify_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, and other noise
        for tag in soup([
            "script", "style", "noscript", "meta", "link",
            "svg", "canvas", "img", "iframe", "object", "embed"
        ]):
            tag.decompose()

        result = []

        # ---------- Helpers ----------

        def build_selector(element, fallback_tag: str) -> str:
            """
            Build a CSS-like selector for a generic element using id, class, and other attributes.
            """
            selector_parts = []
            el_id = element.get("id", "")
            el_class = element.get("class", [])

            if el_id:
                selector_parts.append(f"#{el_id}")
            elif el_class:
                selector_parts.append(f".{' '.join(el_class)}")
            else:
                selector_parts.append(fallback_tag)

            return " ".join(selector_parts) if selector_parts else fallback_tag

        # ---------- Forms and form controls ----------

        for form in soup.find_all("form"):
            form_id = form.get("id", "")
            form_class = form.get("class", [])
            form_selector = f"form{'#' + form_id if form_id else ''}{'.' + '.'.join(form_class) if form_class else ''}"

            form_elements = []

            for element in form.find_all(["input", "select", "textarea", "button", "label"]):
                if element.name == "input":
                    input_id = element.get("id", "")
                    input_name = element.get("name", "")
                    input_type = element.get("type", "text")
                    input_value = element.get("value", "")
                    input_placeholder = element.get("placeholder", "")

                    # Skip hidden and file inputs
                    if input_type in ["hidden", "file"]:
                        continue

                    selector_parts = []
                    if input_id:
                        selector_parts.append(f"#{input_id}")
                    else:
                        classes = element.get("class", [])
                        if classes:
                            selector_parts.append(f".{' '.join(classes)}")
                        selector_parts.append(f"[type='{input_type}']")

                    if input_name:
                        selector_parts.append(f"[name='{input_name}']")

                    if element.has_attr("checked"):
                        selector_parts.append("[checked]")
                    if element.has_attr("selected"):
                        selector_parts.append("[selected]")

                    selector = " ".join(selector_parts) if selector_parts else "input"

                    # Associated label
                    label_text = ""
                    label_for = element.get("id")
                    if label_for:
                        label = soup.find("label", attrs={"for": label_for})
                        if label:
                            label_text = label.get_text(strip=True)

                    if label_text:
                        form_elements.append(f"  label[for='{label_for}']: '{label_text}'")
                    # Include placeholder/value if present
                    if input_placeholder:
                        form_elements.append(f"  {selector} placeholder: '{input_placeholder}'")
                    elif input_value:
                        form_elements.append(f"  {selector} value: '{input_value}'")
                    else:
                        form_elements.append(f"  {selector}")

                elif element.name == "select":
                    select_id = element.get("id", "")
                    select_name = element.get("name", "")
                    select_class = element.get("class", [])

                    selector_parts = []
                    if select_id:
                        selector_parts.append(f"#{select_id}")
                    else:
                        if select_class:
                            selector_parts.append(f".{' '.join(select_class)}")
                        if select_name:
                            selector_parts.append(f"[name='{select_name}']")

                    selector = " ".join(selector_parts) if selector_parts else "select"

                    selected_option = ""
                    all_options = element.find_all("option")
                    for option in all_options:
                        if option.has_attr("selected"):
                            selected_option = option.get_text(strip=True)
                            break

                    form_elements.append(f"  {selector}")
                    if selected_option:
                        form_elements.append(
                            f"    option: '{selected_option}' <!-- {len(all_options)} other options are present but omitted here for brevity -->"
                        )

                elif element.name == "textarea":
                    textarea_id = element.get("id", "")
                    textarea_name = element.get("name", "")
                    textarea_class = element.get("class", [])
                    textarea_placeholder = element.get("placeholder", "")
                    textarea_value = element.get_text(strip=True)

                    selector_parts = []
                    if textarea_id:
                        selector_parts.append(f"#{textarea_id}")
                    else:
                        if textarea_class:
                            selector_parts.append(f".{' '.join(textarea_class)}")
                        if textarea_name:
                            selector_parts.append(f"[name='{textarea_name}']")

                    selector = " ".join(selector_parts) if selector_parts else "textarea"

                    label_text = ""
                    label_for = element.get("id")
                    if label_for:
                        label = soup.find("label", attrs={"for": label_for})
                        if label:
                            label_text = label.get_text(strip=True)

                    if label_text:
                        form_elements.append(f"  label[for='{label_for}']: '{label_text}'")

                    if textarea_placeholder:
                        form_elements.append(f"  {selector} placeholder: '{textarea_placeholder}'")
                    elif textarea_value:
                        form_elements.append(f"  {selector}: '{textarea_value}'")
                    else:
                        form_elements.append(f"  {selector}")

                elif element.name == "button":
                    button_id = element.get("id", "")
                    button_type = element.get("type", "button")
                    button_text = element.get_text(strip=True)
                    button_class = element.get("class", [])

                    selector_parts = []
                    if button_id:
                        selector_parts.append(f"#{button_id}")
                    else:
                        if button_class:
                            selector_parts.append(f".{' '.join(button_class)}")
                        if button_type:
                            selector_parts.append(f"[type='{button_type}']")

                    selector = " ".join(selector_parts) if selector_parts else "button"

                    if button_text:
                        form_elements.append(f"  {selector}: '{button_text}'")
                    else:
                        form_elements.append(f"  {selector}")

                elif element.name == "label":
                    label_for = element.get("for", "")
                    label_text = element.get_text(strip=True)
                    if label_for:
                        form_elements.append(f"  label[for='{label_for}']: '{label_text}'")
                    elif label_text:
                        form_elements.append(f"  label: '{label_text}'")

            if form_elements:
                result.append(form_selector)
                result.extend(form_elements)
                result.append("")

        # ---------- Links ----------

        for link in soup.find_all("a", href=True):
            link_text = link.get_text(strip=True)
            link_href = link.get("href")

            selector_parts = []
            link_id = link.get("id")
            link_class = link.get("class", [])

            if link_id:
                selector_parts.append(f"#{link_id}")
            elif link_class:
                selector_parts.append(f".{' '.join(link_class)}")
            else:
                selector_parts.append("a")

            selector = " ".join(selector_parts) if selector_parts else "a"

            if link_text:
                result.append(f"{selector}: '{link_text}' ({link_href})")
            else:
                result.append(f"{selector} ({link_href})")

        # ---------- Textual content elements (headings, paragraphs, spans, etc.) ----------

        text_tags = [
            "h1", "h2", "h3", "h4", "h5", "h6",
            "p", "span", "li", "strong", "em", "b", "i"
        ]

        for el in soup.find_all(text_tags):
            text = el.get_text(strip=True)
            if not text:
                continue

            # Skip if this is inside a form control or link already captured
            if el.find_parent(["form", "a"]):
                continue

            selector = build_selector(el, el.name)
            result.append(f"{selector}: '{text}'")

        return "\n".join(result)

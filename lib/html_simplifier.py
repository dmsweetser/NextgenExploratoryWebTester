from bs4 import BeautifulSoup

class HTMLSimplifier:
    def simplify_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, and other noise
        for tag in soup(["script", "style", "noscript", "meta", "link", "svg", "canvas", "img", "iframe", "object", "embed"]):
            tag.decompose()

        # Extract interactive elements with their context
        result = []

        # Find all forms and their contents
        for form in soup.find_all("form"):
            form_id = form.get("id", "")
            form_class = form.get("class", [])
            form_selector = f"form{'#' + form_id if form_id else ''}{'.' + '.'.join(form_class) if form_class else ''}"

            # Process form elements
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

                    # Build selector - use CSS selector format
                    selector_parts = []
                    if input_id:
                        selector_parts.append(f"#{input_id}")
                    else:
                        # If no ID, try to build a more specific selector
                        classes = element.get("class", [])
                        if classes:
                            selector_parts.append(f".{' '.join(classes)}")
                        # Fallback to type selector
                        selector_parts.append(f"[type='{input_type}']")

                    # Add name attribute if available for more specificity
                    if input_name:
                        selector_parts.append(f"[name='{input_name}']")

                    # Add checked/selected attributes
                    if element.has_attr("checked"):
                        selector_parts.append("[checked]")
                    if element.has_attr("selected"):
                        selector_parts.append("[selected]")

                    # Join with spaces for CSS selector
                    selector = ' '.join(selector_parts) if selector_parts else "input"

                    # Get associated label
                    label_text = ""
                    label_for = element.get("id")
                    if label_for:
                        label = soup.find("label", attrs={"for": label_for})
                        if label:
                            label_text = label.get_text(strip=True)

                    # Add to form elements
                    if label_text:
                        form_elements.append(f"  label[for='{label_for}']")
                    form_elements.append(f"  {selector}")

                elif element.name == "select":
                    select_id = element.get("id", "")
                    select_name = element.get("name", "")
                    select_class = element.get("class", [])

                    # Build selector
                    selector_parts = []
                    if select_id:
                        selector_parts.append(f"#{select_id}")
                    else:
                        # If no ID, use class or name
                        if select_class:
                            selector_parts.append(f".{' '.join(select_class)}")
                        if select_name:
                            selector_parts.append(f"[name='{select_name}']")

                    selector = ' '.join(selector_parts) if selector_parts else "select"

                    # Get selected option
                    selected_option = ""
                    all_options = element.find_all("option")
                    for option in all_options:
                        if option.has_attr("selected"):
                            selected_option = option.get_text(strip=True)
                            break

                    form_elements.append(f"  {selector}")
                    if selected_option:
                        form_elements.append(f"    option: '{selected_option}' <!-- {len(all_options)} other options are present but ommitted here for brevity -->")

                elif element.name == "textarea":
                    textarea_id = element.get("id", "")
                    textarea_name = element.get("name", "")
                    textarea_class = element.get("class", [])
                    textarea_placeholder = element.get("placeholder", "")
                    textarea_value = element.get_text(strip=True)

                    # Build selector
                    selector_parts = []
                    if textarea_id:
                        selector_parts.append(f"#{textarea_id}")
                    else:
                        # If no ID, use class or name
                        if textarea_class:
                            selector_parts.append(f".{' '.join(textarea_class)}")
                        if textarea_name:
                            selector_parts.append(f"[name='{textarea_name}']")

                    selector = ' '.join(selector_parts) if selector_parts else "textarea"

                    # Get associated label
                    label_text = ""
                    label_for = element.get("id")
                    if label_for:
                        label = soup.find("label", attrs={"for": label_for})
                        if label:
                            label_text = label.get_text(strip=True)

                    if label_text:
                        form_elements.append(f"  label[for='{label_for}']")
                    form_elements.append(f"  {selector}")

                elif element.name == "button":
                    button_id = element.get("id", "")
                    button_type = element.get("type", "button")
                    button_text = element.get_text(strip=True)
                    button_class = element.get("class", [])

                    # Build selector
                    selector_parts = []
                    if button_id:
                        selector_parts.append(f"#{button_id}")
                    else:
                        # If no ID, use class
                        if button_class:
                            selector_parts.append(f".{' '.join(button_class)}")
                        # Add type for more specificity
                        if button_type:
                            selector_parts.append(f"[type='{button_type}']")

                    selector = ' '.join(selector_parts) if selector_parts else "button"

                    if button_text:
                        form_elements.append(f"  {selector}: '{button_text}'")
                    else:
                        form_elements.append(f"  {selector}")

                elif element.name == "label":
                    label_for = element.get("for", "")
                    label_text = element.get_text(strip=True)

                    if label_for:
                        form_elements.append(f"  label[for='{label_for}']")

            if form_elements:
                result.append(form_selector)
                result.extend(form_elements)
                result.append("")

        # Find all links
        for link in soup.find_all("a", href=True):
            link_text = link.get_text(strip=True)
            link_href = link.get("href")

            selector_parts = []
            link_id = link.get("id")
            link_class = link.get("class", [])

            if link_id:
                selector_parts.append(f"#{link_id}")
            else:
                # If no ID, use class
                if link_class:
                    selector_parts.append(f".{' '.join(link_class)}")

            selector = ' '.join(selector_parts) if selector_parts else "a"

            if link_text:
                result.append(f"{selector}: '{link_text}'")
            else:
                result.append(f"{selector}")

        # Return as formatted string
        return chr(10).join(result)

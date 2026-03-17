from bs4 import BeautifulSoup
import json

class HTMLSimplifier:
    def simplify_html(self, html):
        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for script in soup(['script', 'style', 'noscript', 'meta', 'link']):
            script.decompose()

        # Simplify input elements
        for input_tag in soup.find_all('input'):
            if input_tag.get('type') == 'text':
                input_tag['value'] = input_tag.get('value', '')
            elif input_tag.get('type') == 'checkbox':
                input_tag['checked'] = 'checked' if input_tag.get('checked') else None
            elif input_tag.get('type') == 'radio':
                input_tag['checked'] = 'checked' if input_tag.get('checked') else None

        # Simplify select elements - only keep selected option
        for select_tag in soup.find_all('select'):
            selected_option = None
            for option in select_tag.find_all('option'):
                if option.get('selected'):
                    selected_option = option
                    break

            # Keep only the selected option or first option if none selected
            if selected_option:
                # Keep the selected option
                for option in select_tag.find_all('option'):
                    if option != selected_option:
                        option.decompose()
            else:
                # Keep only the first option
                options = select_tag.find_all('option')
                if len(options) > 1:
                    for option in options[1:]:
                        option.decompose()

            # Add data attribute for all options (will be retrieved on demand)
            select_tag['data-has-options'] = 'true'

        return str(soup)

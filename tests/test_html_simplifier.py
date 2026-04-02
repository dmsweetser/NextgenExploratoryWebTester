import unittest
from lib.html_simplifier import HTMLSimplifier

class TestHTMLSimplifier(unittest.TestCase):
    def setUp(self):
        self.simplifier = HTMLSimplifier()

    def test_simplify_html(self):
        html = """
        <html>
            <head><script>alert('test')</script></head>
            <body>
                <div class="container">
                    <h1>Title</h1>
                    <p>Paragraph with <span class="highlight">highlighted</span> text</p>
                    <form>
                        <input type="text" id="username" value="user">
                        <button type="submit">Submit</button>
                    </form>
                    <div class="noise">This should be removed</div>
                </div>
            </body>
        </html>
        """
        simplified = self.simplifier.simplify_html(html)
        self.assertNotIn('<script>', simplified)
        self.assertNotIn('alert', simplified)
        self.assertIn('<h1>Title</h1>', simplified)
        self.assertIn('<p>Paragraph with <span class="highlight">highlighted</span> text</p>', simplified)
        self.assertIn('<input type="text" id="username" value="user"', simplified)
        self.assertIn('<button type="submit">Submit</button>', simplified)

    def test_simplify_select_elements(self):
        html = """
        <select id="country">
            <option value="">Select...</option>
            <option value="us" selected>United States</option>
            <option value="uk">United Kingdom</option>
            <option value="ca">Canada</option>
        </select>
        """
        simplified = self.simplifier.simplify_html(html)
        self.assertIn('<select id="country" data-has-options="true">', simplified)
        # Should only have one option (the selected one)
        option_count = simplified.count('<option')
        self.assertEqual(option_count, 1)

    def test_simplify_input_elements(self):
        html = """
        <input type="text" id="name" value="John">
        <input type="checkbox" id="agree" checked>
        <input type="hidden" id="token" value="abc123">
        <input type="file" id="upload">
        """
        simplified = self.simplifier.simplify_html(html)
        self.assertIn('<input type="text" id="name" value="John"', simplified)
        self.assertIn('<input type="checkbox" id="agree" checked="checked"', simplified)
        self.assertNotIn('<input type="hidden"', simplified)
        self.assertNotIn('<input type="file"', simplified)

    def test_remove_empty_containers(self):
        html = """
        <div>
            <div class="empty"></div>
            <div>Content</div>
            <div class="another-empty"></div>
        </div>
        """
        simplified = self.simplifier.simplify_html(html)
        self.assertNotIn('<div class="empty"></div>', simplified)
        self.assertNotIn('<div class="another-empty"></div>', simplified)
        self.assertIn('<div>Content</div>', simplified)

    def test_preserve_whitespace(self):
        html = """
        <div>
            <p>Line 1</p>
            <p>Line 2</p>
        </div>
        """
        simplified = self.simplifier.simplify_html(html)
        self.assertIn('<p>Line 1</p>', simplified)
        self.assertIn('<p>Line 2</p>', simplified)

if __name__ == '__main__':
    unittest.main()

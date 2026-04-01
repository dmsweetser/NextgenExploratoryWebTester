import unittest
from unittest.mock import patch, MagicMock
from lib.llm_integration import LLMFactory, LocalLlama, AzureFoundry, extract_line_based_content
from lib.config import Config

class TestLLMIntegration(unittest.TestCase):
    def test_extract_line_based_content(self):
        content = """
[test_start]
Content here
[test_end]
More content
"""
        result = extract_line_based_content(content, "[test_start]", "[test_end]")
        self.assertEqual(result, "Content here")

    def test_extract_line_based_content_missing_markers(self):
        content = "No markers here"
        result = extract_line_based_content(content, "[test_start]", "[test_end]")
        self.assertEqual(result, "")

    def test_llm_factory_local(self):
        with patch('lib.llm_integration.Config.use_local_model', return_value=True):
            factory = LLMFactory()
            llm = factory.create_llm()
            self.assertIsInstance(llm, LocalLlama)

    def test_llm_factory_azure(self):
        with patch('lib.llm_integration.Config.use_local_model', return_value=False):
            factory = LLMFactory()
            llm = factory.create_llm()
            self.assertIsInstance(llm, AzureFoundry)

    @patch('subprocess.Popen')
    def test_local_llama_get_action(self, mock_popen):
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        mock_process.stdout.read.sideeffect = ['[action]click[/action]', '']
        mock_process.wait.return_value = 0

        with patch('lib.llm_integration.os.path.isfile', return_value=True):
            llm = LocalLlama()
            result = llm.get_action("test prompt")

        self.assertIn('[action]click[/action]', result)

    @patch('lib.llm_integration.ChatCompletionsClient')
    def test_azure_foundry_get_action(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.complete.return_value = [
            MagicMock(choices=[{'delta': {'content': 'test'}}]),
            MagicMock(choices=[])
        ]

        with patch('lib.llm_integration.Config.get_endpoint', return_value='endpoint'), \
             patch('lib.llm_integration.Config.get_api_key', return_value='key'), \
             patch('lib.llm_integration.Config.get_model_name', return_value='model'):
            llm = AzureFoundry()
            result = llm.get_action("test prompt")

        self.assertEqual(result, 'test')

if __name__ == '__main__':
    unittest.main()

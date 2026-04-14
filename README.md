# NEWT - Next-gen Exploratory Web Tester

NEWT (Next-gen Exploratory Web Tester) is an advanced automated web testing system that uses AI-driven exploratory testing to identify bugs, usability issues, and other problems on websites. Unlike traditional automated testing tools that follow predefined scripts, NEWT uses a Large Language Model (LLM) to make intelligent decisions about what to test and how to interact with web applications.

## Features

- **AI-Driven Exploratory Testing**: The NEWT bot uses an LLM to make intelligent decisions about what actions to take, what to test, and when to report bugs.
- **Smart Bug Detection**: The NEWT bot analyzes pages for malfunctions, logical blocking, typos, and other issues, rather than relying on simple keyword matching.
- **Comprehensive Reporting**: Detailed bug reports with screenshots, execution steps, and technical analysis.
- **Multi-Model Support**: Works with both local LLMs (via llama.cpp) and Azure AI models.
- **Self-Testing**: Built-in test website to verify NEWT functionality.
- **Email Notifications**: Automatic bug notifications with severity levels.
- **Web Interface**: User-friendly dashboard to create, monitor, and manage test bots.

## Installation

### Prerequisites

- Python 3.8+
- Git
- CMake (for building llama.cpp)
- Chrome/Chromium browser
- WKHTMLTOPDF - https://wkhtmltopdf.org/downloads.html

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/newt.git
   cd newt
   ```

2. **Install dependencies:**
   - On Windows:
     ```batch
     install.bat
     ```
   - On Linux/macOS:
     ```bash
     ./install.sh
     ```

3. **Configure settings:**
   Copy `.env.example` to `.env` and update the configuration:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your preferred settings (local model or Azure AI).

4. **Download a model (if using local mode):**
   Place your GGUF model file in the `models/` directory.

## Usage

1. **Start the NEWT application:**
   ```bash
   python app.py
   ```
   or use the convenience scripts:
   ```bash
   ./run.sh
   ```
   (Windows: `run.bat`)

2. **Access the web interface:**
   Open your browser to `http://localhost:6329`

3. **Create a new NEWT bot:**
   - Provide a name for your test
   - Enter the start URL
   - Define your testing directive (what should the bot test?)

4. **Monitor results:**
   - View execution steps in real-time
   - Review detected bugs
   - Export detailed reports

## Configuration

### Local Model Configuration

Edit `.env` to use a local LLM:
```
USE_LOCAL_MODEL=true
MODEL_PATH=models/your_model.gguf
MODEL_CONTEXT=131072
MODEL_THREADS=4
MODEL_BATCH=512
MODEL_GPU_LAYERS=0
```

### Azure AI Configuration

Edit `.env` to use Azure AI:
```
USE_LOCAL_MODEL=false
AZURE_ENDPOINT=https://your-resource.azure.ai
AZURE_API_KEY=your-api-key
AZURE_MODEL_NAME=gpt-35-turbo
```

### Model Parameters

Adjust LLM parameters in `.env`:
```
OUTPUT_TOKENS=32768
TEMPERATURE=0.9
TOP_P=0.8
TOP_K=20
MIN_P=0.0
```

### Email Notifications

Configure SMTP settings:
```
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=your-email@yourprovider.com
SMTP_PASSWORD=your-password
SMTP_FROM=newt@yourdomain.com
BUG_NOTIFICATION_EMAILS=team1@company.com,team2@company.com
```

### Application Settings

Additional settings:
```
DEBUG=false
HEADLESS=true
LOG_PROMPTS=true
DEFAULT_WAIT=10
```

## Self-Test

NEWT includes a built-in test website to verify functionality:
1. Click "NEWT Self Test" in the sidebar
2. The NEWT bot will navigate through the test website
3. It should detect the known bug (error message display)
4. Results appear in the bot dashboard

## Running Unit Tests

To run the unit tests:
```bash
python -m unittest discover tests
```

Or run specific test files:
```bash
python -m unittest tests/test_app.py
python -m unittest tests/test_database.py
python -m unittest tests/test_bot_manager.py
```

## Technical Details

### How NEWT Works

1. **Initialization**: The NEWT bot loads the specified page and analyzes its structure.
2. **Action Decision**: The LLM examines the page and decides what action to take next (click, fill, select, etc.). The bot is programmed to be curious and try edge cases within the bounds of its directive.
3. **Execution**: The bot performs the action and captures a screenshot.
4. **Bug Detection**: The LLM analyzes the result to determine if a bug exists, looking for malfunctions, logical blocking, typos, unexpected behaviors, and edge case failures.
5. **Completion Check**: The LLM evaluates whether the testing directive has been satisfied and if all edge cases have been explored.
6. **Reporting**: Bugs are recorded with detailed analysis and screenshots.
7. **Error Handling**: The bot is resilient to failures and can continue testing even if parts of the process fail.

NEWT is designed to be an exploratory tester, meaning it goes beyond just following a script. It tries to:
- Test edge cases and unusual scenarios
- Attempt to break the system within the bounds of its directive
- Explore multiple paths and approaches
- Try invalid inputs and unusual combinations
- Poke and prod the application to find hidden issues

### Bug Detection Logic

NEWT uses a sophisticated approach to bug detection:
- **Malfunctions**: Error messages, exceptions, or unexpected page states
- **Logical Blocking**: Interactive elements that should work but don't
- **Typos**: Incorrect or misspelled text that indicates problems
- **Unexpected Behaviors**: Actions that don't produce the expected results
- **Edge Cases**: Issues that occur with unusual inputs or combinations
- **Cross-Path Issues**: Problems that arise when following non-standard user paths

The bot is specifically designed to be curious and exploratory, trying edge cases and unusual scenarios to uncover hidden bugs that might not be found with standard testing approaches.

## Architecture

### Core Components

- **app.py**: Main Flask application with routes and web interface
- **lib/database.py**: SQLite database for storing bots, steps, and bugs
- **lib/bot_thread.py**: Threaded bot that performs testing actions
- **lib/bot_manager.py**: Manages active bot threads
- **lib/html_simplifier.py**: Simplifies HTML for LLM processing
- **lib/llm_integration.py**: Handles communication with LLM models
- **lib/screenshot_capturer.py**: Captures screenshots during testing
- **lib/bug_reporter.py**: Sends email notifications for bugs
- **lib/config.py**: Configuration management from environment variables

### Database Schema

The application uses SQLite with the following tables:
- **bots**: Stores bot configurations and status
- **steps**: Records each action taken by a bot
- **bugs**: Tracks detected bugs with status
- **bug_knowledge**: Stores detailed knowledge about each bug

## License

NEWT is released under the MIT License. See [LICENSE](LICENSE) for details.

## Support

For issues and questions, please open an issue on the GitHub repository.

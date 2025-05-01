# autobloggerai
# AutoBlogger AI - an AI-powered article writing solution for WordPress.

AutoBlogger is a Python tool designed to automate content generation and WordPress publishing. It reads article titles from a spreadsheet, uses AI language models to generate articles, inserts image placeholders, and publishes the content to a WordPress site. It includes both a graphical user interface (GUI) and command-line interface for flexibility.

## Features

- Modern GUI interface for easy use
- Reads article titles from CSV or Excel spreadsheets
- Generates full articles using multiple LLM options:
  - Local LLM via LM Studio or similar local API servers
  - Google Gemini API
- Inserts image placeholders at configurable intervals
- Automatically publishes to WordPress using XML-RPC API
- Tracks used titles to avoid duplication
- Configurable posting options (draft/publish, categories, etc.)
- Optional future post scheduling
- Comprehensive logging system
- Ability to save and load custom configurations
- Customizable prompt templates
- Packages as a standalone executable for easy distribution

## Prerequisites

- Python 3.10 or higher
- One of the following LLM options:
  - LM Studio or a similar local API server running locally
  - Google Gemini API key
- WordPress site with XML-RPC enabled

## Installation

### Running from Source

1. Clone or download this repository

2. Install required dependencies:

```bash
pip install -r requirements.txt
```

3. Launch the GUI application:

```bash
python wp_poster_gui.py
```

4. Configure the application settings through the GUI

5. Prepare your titles spreadsheet (CSV or Excel format)

### Using Pre-built Executable (Windows)

1. Download the latest release from the releases page

2. Run the installer or extract the executable

3. Launch the application and configure settings through the GUI

## Configuration

### GUI Configuration

The application can be fully configured through the intuitive GUI interface:

1. **General Settings:** Configure spreadsheet location, sheet name, column names, and generation options
2. **Article Generation:** Customize the prompt template for AI-generated content
3. **WordPress Settings:** Set WordPress connection details and posting preferences
4. **LLM Settings:** Choose between local LLM or Google Gemini, and configure API options
5. **Logs:** View real-time logs and application progress

### Manual Configuration

Settings are stored in `config.json` which can also be edited manually if needed:

```json
{
    "input": {
        "file_path": "titles.xlsx",        // Path to your spreadsheet
        "sheet_name": "Sheet1",           // Sheet name for Excel files
        "title_column": "Title",         // Column containing article titles
        "used_column": "Used"            // Column to track used titles
    },
    "wordpress": {
        "url": "https://your-wordpress-site.com",  // WordPress site URL
        "username": "your_username",               // WordPress username
        "password": "your_password",               // WordPress password
        "use_application_password": false,         // Use WP application password
        "category": "Blog",                        // Category to assign posts
        "post_status": "draft",                    // "draft" or "publish"
        "future_scheduling": false                 // Schedule posts in the future
    },
    "mode": "local",                             // "local" or "gemini"
    "local": {
        "endpoint": "http://localhost:1234/v1/chat/completions", // Local LLM API endpoint
        "model": "local-model",                   // Model name
        "temperature": 0.7,                       // Creativity parameter (0.0-1.0)
        "max_tokens": 6000                        // Maximum tokens for generated content
    },
    "gemini": {
        "api_key": "your-gemini-api-key",         // Google Gemini API key
        "model": "gemini-1.5-flash",              // Gemini model name
        "temperature": 0.7,                       // Creativity parameter
        "max_output_tokens": 4096                // Max tokens for generated content
    },
    "generation": {
        "post_template": "Write a 4000-word SEO-optimized article...", // Prompt template
        "posts_per_day": 1,                       // Number of posts to generate per run
        "randomize_selection": true,              // Randomize which titles to use
        "image_placeholder_frequency": 600        // Insert image every ~600 words
    },
    "logging": {
        "log_folder": "logs"                      // Folder for log files
    }
}
```

## Spreadsheet Format

Your spreadsheet should have at least two columns:

1. A column for article titles (default: "Title")
2. A column to track usage status (default: "Used") with values "Yes" or "No"

Example:

| ID | Title                                      | Used |
|----|--------------------------------------------| ---- |
| 1  | How AI is Transforming VFX and CGI in Films | No   |
| 2  | Why Filmmakers Are Switching to Virtual Production | No   |
| 3  | 5 Reasons Your Business Needs CGI Advertisement | No   |

## Usage

### GUI Mode (Recommended)

Run the application with:

```bash
python wp_poster_gui.py
```

Or simply double-click on the executable if using the pre-built version.

1. Configure all settings through the GUI tabs
2. Test your WordPress and LLM connections using the test buttons
3. Click "Generate Articles" to start the process
4. View progress in the Logs tab



## Setting Up LLM Providers

### Local LLM (LM Studio or similar)

1. Download and install LM Studio from [lmstudio.ai](https://lmstudio.ai/) or use any compatible local LLM server
2. Load your preferred model
3. Start the local server (make note of the port number)
4. Enter the endpoint URL and other settings in the LLM Settings tab of the GUI

### Google Gemini API

1. Get a Google Gemini API key from the [Google AI Studio](https://ai.google.dev/)
2. Select "Google Gemini API" in the LLM Settings tab of the GUI
3. Enter your API key in the settings field
4. Select your preferred model (gemini-1.5-flash, gemini-1.5-pro, etc.)

## Automating Execution

### With GUI Application


Common issues:

- **LLM Connection Error**: 
  - Local LLM: Ensure your LLM server is running and the endpoint is correct
  - Gemini: Verify your API key is valid and that you have internet connectivity
- **WordPress Connection Error**: Verify WordPress URL, username, password, and that XML-RPC is enabled
- **Spreadsheet Errors**: Make sure your spreadsheet format matches what's expected in the configuration
- **GUI Display Issues**: If the GUI doesn't display properly, try adjusting your screen scaling

## License

This project is licensed under the MIT License.

## Credits

AutoBlogger AI was created to help content creators automate the process of generating and publishing high-quality content to WordPress sites.
Regards,
Umair Fareed
SUZA Productions




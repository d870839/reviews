# Kroger Review Analyzer - Flask Web App

A web application that scrapes and analyzes customer reviews from Kroger.com to provide detailed sentiment analysis and product insights.

## Features

- 🔍 **Product Search**: Search any product category on Kroger.com
- 📊 **Sentiment Analysis**: Analyze customer sentiment using TextBlob
- 🏆 **Product Ranking**: Compare products by average rating
- 📈 **Theme Extraction**: Identify common complaints and praises
- 📑 **Excel Export**: Download detailed analysis as Excel spreadsheet
- 🎯 **Individual Product Analysis**: Each product analyzed separately
- 🚀 **Real-time Progress**: Live updates during analysis

## Live Demo

Deploy to Render: [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

## Local Development

### Prerequisites

- Python 3.9+
- Chrome browser (for Selenium)

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd kroger-review-analyzer
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Run the application**
```bash
python app.py
```

4. **Open in browser**
```
http://localhost:5000
```

## Deployment to Render

### Method 1: One-Click Deploy

1. Click the "Deploy to Render" button above
2. Connect your GitHub account
3. Configure environment variables if needed
4. Deploy!

### Method 2: Manual Deploy

1. **Create a new Web Service on Render**
2. **Connect your GitHub repository**
3. **Configure the service:**
   - **Build Command**: 
     ```bash
     pip install -r requirements.txt && python -c "import chromedriver_autoinstaller; chromedriver_autoinstaller.install()"
     ```
   - **Start Command**: `gunicorn app:app`
   - **Environment**: `Python 3`

4. **Set Environment Variables:**
   - `SECRET_KEY`: Generate a random secret key
   - `PYTHON_VERSION`: `3.9`

5. **Deploy**

## File Structure

```
kroger-review-analyzer/
├── app.py                 # Flask application
├── kroger_analyzer.py     # Core analysis logic
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment config
├── README.md             # This file
└── templates/
    ├── index.html        # Main form page
    └── progress.html     # Analysis progress page
```

## How It Works

1. **User Input**: Users enter a search category and set parameters
2. **Product Search**: Selenium scrapes Kroger.com for matching products
3. **Review Extraction**: Individual product pages are scraped for reviews
4. **Data Cleaning**: Duplicate reviews and junk content are filtered out
5. **Sentiment Analysis**: TextBlob analyzes sentiment and themes
6. **Excel Generation**: Results are compiled into a detailed spreadsheet
7. **Download**: Users receive the analysis file automatically

## Analysis Output

The Excel file contains multiple sheets:

- **Category Summary**: Overall statistics across all products
- **Top Rated Products**: Products ranked by average rating
- **Products Overview**: Side-by-side comparison of all products
- **Individual Product Sheets**: Detailed analysis for each product
- **All Reviews**: Complete dataset of all collected reviews

## Configuration

### Environment Variables

- `SECRET_KEY`: Flask secret key for sessions
- `PYTHON_VERSION`: Python version (default: 3.9)

### Analysis Parameters

- **Max Products**: 1-20 products to analyze
- **Max Reviews**: 1-50 reviews per product
- **Categories**: Any product category (cookies, bread, etc.)

## Limitations

- **Rate Limiting**: Respects Kroger's servers with delays between requests
- **Review Availability**: Limited to products that have customer reviews
- **Processing Time**: Analysis takes 2-5 minutes depending on parameters
- **Headless Chrome**: Requires sufficient memory for browser automation

## Technical Details

### Web Scraping
- **Selenium WebDriver**: Handles JavaScript-heavy pages
- **Chrome Headless**: Optimized for server environments
- **Smart Selectors**: Multiple fallback CSS selectors
- **Duplicate Detection**: Prevents same reviews across products

### Data Processing
- **Stop Words Filtering**: Removes common English words
- **Theme Extraction**: Groups feedback by categories (taste, price, quality)
- **Sentiment Scoring**: -1 (very negative) to +1 (very positive)
- **Statistical Analysis**: Averages, distributions, percentages

### Performance Optimizations
- **Background Processing**: Analysis runs in separate threads
- **Progress Updates**: Real-time status via AJAX polling
- **Temporary Files**: Automatic cleanup of generated files
- **Memory Management**: Efficient Chrome options for low memory

## API Endpoints

- `GET /`: Main form page
- `POST /analyze`: Start new analysis
- `GET /status/<job_id>`: Check analysis progress
- `GET /download/<job_id>`: Download results
- `GET /cleanup`: Clean up old jobs (internal)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues or questions:
1. Check the logs for error messages
2. Verify Chrome is installed on the server
3. Ensure sufficient memory for Selenium
4. Check Kroger.com accessibility

## Disclaimer

This tool is for educational and research purposes. Please respect Kroger's terms of service and use responsibly with appropriate delays between requests.
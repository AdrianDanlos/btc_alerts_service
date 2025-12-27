# Bitcoin Indicator Emailer

A Python script that fetches Bitcoin indicators (Puell Multiple, MVRV Z-Score, AHR999) and sends investment recommendations via email based on flash signals.

## Features

- Fetches three Bitcoin indicators from ChartInspect and CoinGecko APIs
- Detects "flash" signals when indicators drop below thresholds
- Calculates investment recommendations based on flash count (0-3 indicators)
- Sends formatted HTML email reports with current BTC price and indicator values
- Configurable via environment variables

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
# Required: Email configuration
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECIPIENT_EMAIL=recipient@gmail.com

# Required: ChartInspect API key
CHARTINSPECT_API_KEY=your_api_key

# Optional: SMTP configuration (defaults to Gmail)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

**Gmail App Password Setup:**
1. Enable 2-Step Verification on your Google account
2. Go to: https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail"
4. Use that 16-character password as `SENDER_PASSWORD`

## Usage

Run the script:
```bash
python btc_indicator_emailer.py
```

## How It Works

The script:
1. Fetches the minimum values of three indicators over the last 7 days
2. Checks if any indicators "flashed" (dropped below thresholds):
   - MVRV Z-Score: < 0
   - Puell Multiple: < 0.5
   - AHR999: < 0.45
3. Calculates investment recommendation based on flash count:
   - 0 flashes: €0
   - 1 flash: €550
   - 2 flashes: €1,100
   - 3 flashes: €2,100
4. Sends an email with indicator values, current BTC price, and investment recommendation

## Scheduling

The script can be scheduled using:
- **GitHub Actions**: Create a workflow file in `.github/workflows/`
- **Cron** (Linux/Mac): Add to crontab
- **Task Scheduler** (Windows): Schedule as daily task
- **Any cloud scheduler**: PythonAnywhere, AWS Lambda, etc.

Make sure environment variables are set in your scheduler environment.

## License

Free to use and modify.

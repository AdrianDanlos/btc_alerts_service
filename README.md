# Bitcoin Indicator Emailer

A Python 3 script that automatically fetches Bitcoin indicators (Puell Multiple, MVRV Z-Score, AHR999x) and sends them via email.

## Features

- Fetches three Bitcoin indicators with placeholder functions ready for API integration
- Sends formatted email reports via SMTP
- Modular, well-documented code
- Exception handling for robust operation
- Configurable via environment variables or direct code modification

## Setup

### 1. Install Dependencies

No external dependencies required! Uses only Python standard library:
- `smtplib` (email sending)
- `email.mime` (email formatting)
- `os` (environment variables)
- `typing` (type hints)

### 2. Configure Email Credentials

**Option A: Environment Variables (Recommended for Security)**

```bash
# Windows PowerShell
$env:SENDER_EMAIL="your_email@gmail.com"
$env:SENDER_PASSWORD="your_app_password"
$env:RECIPIENT_EMAIL="recipient@gmail.com"

# Windows CMD
set SENDER_EMAIL=your_email@gmail.com
set SENDER_PASSWORD=your_app_password
set RECIPIENT_EMAIL=recipient@gmail.com

# Linux/Mac
export SENDER_EMAIL="your_email@gmail.com"
export SENDER_PASSWORD="your_app_password"
export RECIPIENT_EMAIL="recipient@gmail.com"
```

**Option B: Edit the Script**

Edit the `main()` function in `btc_indicator_emailer.py` and replace the default values:
```python
SENDER_EMAIL = 'your_email@gmail.com'
SENDER_PASSWORD = 'your_app_password'
RECIPIENT_EMAIL = 'recipient@gmail.com'
```

### 3. Gmail App Password Setup

For Gmail, you need to use an App Password (not your regular password):

1. Enable 2-Step Verification on your Google account
2. Go to: https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail"
4. Use that 16-character password in the script

### 4. Replace Placeholder API Functions

Edit the following functions in `btc_indicator_emailer.py`:
- `get_puell()` - Replace with actual API call for Puell Multiple
- `get_mvrv_z()` - Replace with actual API call for MVRV Z-Score
- `get_ahr999x()` - Replace with actual API call for AHR999x

Example API sources:
- **Glassnode API**: https://docs.glassnode.com/
- **Alternative APIs**: Search for Bitcoin indicator APIs

## Usage

Run the script directly:
```bash
python btc_indicator_emailer.py
```

## Scheduling

### PythonAnywhere

1. Upload the script to your PythonAnywhere account
2. Go to the "Tasks" tab
3. Create a scheduled task:
   - Command: `python3 /home/yourusername/btc_indicator_emailer.py`
   - Schedule: Daily at your preferred time (e.g., "at 09:00")
4. Set environment variables in the "Files" tab → `.bashrc`:
   ```bash
   export SENDER_EMAIL="your_email@gmail.com"
   export SENDER_PASSWORD="your_app_password"
   export RECIPIENT_EMAIL="recipient@gmail.com"
   ```

### GitHub Actions

1. Create `.github/workflows/btc-indicators.yml`:
```yaml
name: BTC Indicator Emailer

on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM UTC
  workflow_dispatch:  # Allow manual runs

jobs:
  send-indicators:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.x'
      - name: Run script
        env:
          SENDER_EMAIL: ${{ secrets.SENDER_EMAIL }}
          SENDER_PASSWORD: ${{ secrets.SENDER_PASSWORD }}
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
        run: python btc_indicator_emailer.py
```

2. Add secrets in GitHub repository settings:
   - `SENDER_EMAIL`
   - `SENDER_PASSWORD`
   - `RECIPIENT_EMAIL`

### Replit

1. Upload the script to your Replit project
2. Go to "Tools" → "Scheduled Jobs"
3. Create a new scheduled job:
   - Command: `python btc_indicator_emailer.py`
   - Schedule: Daily/Weekly as needed
4. Set environment variables in "Secrets" tab

### Linux/Mac Cron

1. Edit crontab: `crontab -e`
2. Add line (runs daily at 9 AM):
```bash
0 9 * * * cd /path/to/script && /usr/bin/python3 btc_indicator_emailer.py
```

3. Set environment variables in your shell profile (`.bashrc`, `.zshrc`, etc.)

### Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (daily/weekly)
4. Action: Start a program
   - Program: `python`
   - Arguments: `C:\path\to\btc_indicator_emailer.py`
   - Start in: `C:\path\to\`
5. For environment variables, create a batch file wrapper:
```batch
@echo off
set SENDER_EMAIL=your_email@gmail.com
set SENDER_PASSWORD=your_app_password
set RECIPIENT_EMAIL=recipient@gmail.com
python C:\path\to\btc_indicator_emailer.py
```

## Email Provider Configuration

### Gmail
- SMTP Server: `smtp.gmail.com`
- Port: `587` (TLS) or `465` (SSL)
- Requires App Password

### Outlook
- SMTP Server: `smtp-mail.outlook.com`
- Port: `587`
- Use your regular password

### Yahoo
- SMTP Server: `smtp.mail.yahoo.com`
- Port: `587`
- May require App Password

## Troubleshooting

**Authentication Error:**
- For Gmail: Make sure you're using an App Password, not your regular password
- Check that 2-Step Verification is enabled

**Connection Error:**
- Check your internet connection
- Verify SMTP server and port settings
- Some networks block SMTP ports; try a different network

**API Fetch Errors:**
- Check that placeholder functions are replaced with real API calls
- Verify API endpoints are correct
- Check API rate limits and authentication

## License

Free to use and modify as needed.


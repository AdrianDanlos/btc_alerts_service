#!/usr/bin/env python3
"""
Bitcoin Indicator Emailer

This script fetches three Bitcoin indicators
(Puell Multiple, MVRV Z-Score, AHR999)
and sends them via email on a scheduled basis.

Schedule using GitHub Actions.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import Dict, Optional, Tuple
import requests
from datetime import datetime, timedelta
import math

# Constants
DAYS_TO_FETCH = 7
DCA_WINDOW_DAYS = 200
BITCOIN_GENESIS = datetime(2009, 1, 3)
CHARTINSPECT_BASE_URL = "https://chartinspect.com/api/v1/onchain"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
REQUEST_TIMEOUT = 30

# Flash thresholds
FLASH_THRESHOLDS = {
    "MVRV Z-Score": 0,
    "Puell Multiple": 0.5,
    "AHR999": 0.45,
}

# Investment amounts based on flash count
INVESTMENT_AMOUNTS = {0: 0, 1: 750, 2: 1500, 3: 3000}


def _get_date_from_item(item: dict) -> Optional[str]:
    """Extracts date from API response item."""
    return item.get("formattedDate") or item.get("date")


def _fetch_chartinspect_indicator(
    endpoint: str, value_key: str
) -> Tuple[float, list[float], str, str]:
    """
    Generic function to fetch ChartInspect indicator data.

    Args:
        endpoint: API endpoint (e.g., "puell-multiple", "mvrv-z-score")
        value_key: Key to extract value from response items

    Returns:
        tuple: (minimum_value, list_of_all_values, min_date, last_date)
    """
    api_key = os.getenv("CHARTINSPECT_API_KEY")
    if not api_key:
        raise ValueError("CHARTINSPECT_API_KEY environment variable not set")

    url = f"{CHARTINSPECT_BASE_URL}/{endpoint}"
    params = {"days": DAYS_TO_FETCH}
    headers = {"X-API-Key": api_key}

    response = requests.get(
        url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    data = response.json()

    if not data.get("success") or not data.get("data"):
        raise ValueError("No data returned from ChartInspect API")

    # Find minimum value and its date
    min_value = float("inf")
    min_date = None
    values = []

    for item in data["data"]:
        value = item[value_key]
        values.append(value)
        if value < min_value:
            min_value = value
            min_date = _get_date_from_item(item)

    if not values:
        raise ValueError("Invalid data format from ChartInspect API")

    # Get the last date (most recent data point)
    last_date = _get_date_from_item(data["data"][-1])

    return (min_value, values, min_date, last_date)


def get_puell() -> Tuple[float, list[float], str, str]:
    """
    Fetches Puell Multiple from ChartInspect API for last 7 days.

    Returns:
        tuple: (minimum_value, list_of_all_values, min_date, last_date)
            - minimum_value: Lowest Puell Multiple in last 7 days
            - list_of_all_values: All values for flash detection
            - min_date: Date when minimum value occurred (YYYY-MM-DD)
            - last_date: Last available date (YYYY-MM-DD format)

    Raises:
        Exception: If API call fails or returns invalid data
    """
    return _fetch_chartinspect_indicator("puell-multiple", "puell_multiple")


def get_mvrv_z() -> Tuple[float, list[float], str, str]:
    """
    Fetches MVRV Z-Score from ChartInspect API for last 7 days.

    Returns:
        tuple: (minimum_value, list_of_all_values, min_date, last_date)
            - minimum_value: Lowest MVRV Z-Score in last 7 days
            - list_of_all_values: All values for flash detection
            - min_date: Date when minimum value occurred (YYYY-MM-DD)
            - last_date: Last available date (YYYY-MM-DD format)

    Raises:
        Exception: If API call fails or returns invalid data
    """
    return _fetch_chartinspect_indicator("mvrv-z-score", "z_score")


def get_ahr999() -> Tuple[float, list[float], str, str]:
    """
    Calculates AHR999 indicator using CoinGecko API for last 7 days.

    Formula: AHR999 = (Price / 200-day DCA Cost) × (Price / Growth Valuation)

    Returns:
        tuple: (minimum_value, list_of_all_values, min_date, last_date)
            - minimum_value: Lowest AHR999 in last 7 days
            - list_of_all_values: All values for flash detection
            - min_date: Date when minimum value occurred (YYYY-MM-DD)
            - last_date: Last available date (YYYY-MM-DD format)

    Raises:
        Exception: If API call fails or calculation fails
    """
    # Get 7 days of historical prices plus 200 days for DCA calculation
    end_date = datetime.now()
    start_date = end_date - timedelta(days=DAYS_TO_FETCH + DCA_WINDOW_DAYS)
    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())

    historical_url = (
        f"{COINGECKO_BASE_URL}/coins/bitcoin"
        f"/market_chart/range?vs_currency=usd"
        f"&from={start_timestamp}&to={end_timestamp}"
    )
    response = requests.get(historical_url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    historical_data = response.json()

    # Extract prices from historical data
    price_points = historical_data.get("prices", [])
    if not price_points:
        raise ValueError("No price data returned from CoinGecko API")

    # Get prices for last 7 days (for AHR999 calculation)
    seven_days_ago = end_date - timedelta(days=DAYS_TO_FETCH)
    seven_days_timestamp = int(seven_days_ago.timestamp())

    ahr999_values = []
    ahr999_with_dates = []  # List of (value, date) tuples

    # Group prices by day to calculate once per day
    daily_prices = {}
    for point in price_points:
        point_timestamp = point[0] / 1000
        point_date = datetime.fromtimestamp(point_timestamp)
        date_key = point_date.strftime("%Y-%m-%d")

        # Only process last 7 days
        if point_timestamp < seven_days_timestamp:
            continue

        # Use the last price of each day
        if date_key not in daily_prices or point_timestamp > daily_prices[date_key][0]:
            daily_prices[date_key] = (point_timestamp, point[1], point_date)

    # Calculate AHR999 for each day
    for date_key in sorted(daily_prices.keys()):
        _, current_price, point_date = daily_prices[date_key]
        point_timestamp = point_date.timestamp()

        # Get 200 days of prices before this point for DCA calculation
        point_start = point_date - timedelta(days=DCA_WINDOW_DAYS)
        point_start_ts = int(point_start.timestamp())

        # Find prices in the 200-day window before this point
        prices_200d = [
            p[1]
            for p in price_points
            if point_start_ts <= p[0] / 1000 < point_timestamp
        ]

        if not prices_200d:
            # Fallback: use all available prices before this point
            prices_200d = [p[1] for p in price_points if p[0] / 1000 < point_timestamp]

        # Calculate 200-day DCA cost (average of prices)
        if prices_200d:
            dca_cost = sum(prices_200d) / len(prices_200d)
        else:
            dca_cost = current_price

        # Calculate exponential growth valuation
        # Standard AHR999 formula: 10^(5.84 × log10(Bitcoin Age) - 17.01)
        days_since_genesis = (point_date - BITCOIN_GENESIS).days

        if days_since_genesis > 0:
            # Use the standard AHR999 growth valuation formula
            log10_days = math.log10(days_since_genesis)
            growth_valuation = 10 ** (5.84 * log10_days - 17.01)
        else:
            growth_valuation = current_price

        # Calculate AHR999 for this day
        price_ratio = current_price / dca_cost
        growth_ratio = current_price / growth_valuation
        ahr999 = price_ratio * growth_ratio
        ahr999_values.append(ahr999)
        ahr999_with_dates.append((ahr999, date_key))

    if not ahr999_values:
        raise ValueError("Could not calculate AHR999 values")

    # Find minimum value and its date
    min_value = min(ahr999_values)
    min_date = None
    for value, date in ahr999_with_dates:
        if value == min_value:
            min_date = date
            break

    # Get the last date (most recent calculation)
    last_date_str = ahr999_with_dates[-1][1] if ahr999_with_dates else None

    # Return minimum value, all values, min date, and last date
    return (min_value, ahr999_values, min_date, last_date_str)


def check_flashes(
    mvrv_values: list[float],
    puell_values: list[float],
    ahr999_values: list[float],
) -> Tuple[int, list[str]]:
    """
    Checks how many indicators have "flashed" (reached thresholds)
    in last 7 days.

    Args:
        mvrv_values: List of MVRV Z-Score values
        puell_values: List of Puell Multiple values
        ahr999_values: List of AHR999 values

    Returns:
        tuple: (flash_count, flashed_indicators)
            - flash_count: Number of indicators that flashed (0-3)
            - flashed_indicators: List of indicator names that flashed
    """
    indicator_data = [
        ("MVRV Z-Score", mvrv_values),
        ("Puell Multiple", puell_values),
        ("AHR999", ahr999_values),
    ]

    flashed_indicators = []
    for name, values in indicator_data:
        threshold = FLASH_THRESHOLDS.get(name)
        if threshold is not None and values and any(v < threshold for v in values):
            flashed_indicators.append(name)

    return (len(flashed_indicators), flashed_indicators)


def get_current_btc_price() -> Optional[float]:
    """
    Gets current Bitcoin price from CoinGecko.

    Returns:
        float: Current Bitcoin price in USD, or None if fetch fails
    """
    try:
        url = f"{COINGECKO_BASE_URL}/simple/price" "?ids=bitcoin&vs_currencies=usd"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return float(response.json()["bitcoin"]["usd"])
    except Exception as e:
        print(f"Error fetching current BTC price: {e}")
        return None


def _fetch_single_indicator(
    name: str,
    fetch_func,
    min_indicators: Dict[str, Optional[float]],
    current_indicators: Dict[str, Optional[float]],
    min_dates: Dict[str, Optional[str]],
    last_dates: Dict[str, Optional[str]],
) -> Optional[list[float]]:
    """
    Helper function to fetch a single indicator and handle errors.

    Returns:
        List of values for flash detection, or None if fetch failed
    """
    try:
        min_value, all_values, min_date, last_date = fetch_func()
        min_indicators[name] = min_value
        current_indicators[name] = all_values[-1] if all_values else None
        min_dates[name] = min_date
        last_dates[name] = last_date
        return all_values
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        min_indicators[name] = None
        current_indicators[name] = None
        min_dates[name] = None
        last_dates[name] = None
        return None


def fetch_indicators() -> Tuple[
    Dict[str, Optional[float]],
    Dict[str, Optional[float]],
    Dict[str, Optional[str]],
    Dict[str, Optional[str]],
    int,
    list[str],
]:
    """
    Fetches all three Bitcoin indicators and checks for flashes.

    Returns:
        tuple: (min_indicators, current_indicators, min_dates, last_dates,
                flash_count, flashed_list)
            - min_indicators: Dictionary with minimum values (from last 7 days)
            - current_indicators: Dictionary with current/latest values
            - min_dates: Dictionary with dates when minimum occurred
            - last_dates: Dictionary with last available dates (YYYY-MM-DD)
            - flash_count: Number of indicators that flashed (0-3)
            - flashed_list: List of indicator names that flashed

    Raises:
        Exception: If all indicators fail to fetch
                   (optional - currently handled gracefully)
    """
    min_indicators = {}
    current_indicators = {}
    min_dates = {}
    last_dates = {}

    # Fetch all indicators
    puell_values = _fetch_single_indicator(
        "Puell Multiple",
        get_puell,
        min_indicators,
        current_indicators,
        min_dates,
        last_dates,
    )
    mvrv_values = _fetch_single_indicator(
        "MVRV Z-Score",
        get_mvrv_z,
        min_indicators,
        current_indicators,
        min_dates,
        last_dates,
    )
    ahr999_values = _fetch_single_indicator(
        "AHR999",
        get_ahr999,
        min_indicators,
        current_indicators,
        min_dates,
        last_dates,
    )

    # Check for flashes
    flash_count, flashed_list = check_flashes(
        mvrv_values or [], puell_values or [], ahr999_values or []
    )

    return (
        min_indicators,
        current_indicators,
        min_dates,
        last_dates,
        flash_count,
        flashed_list,
    )


def format_email(
    min_indicators: Dict[str, Optional[float]],
    current_indicators: Dict[str, Optional[float]],
    min_dates: Dict[str, Optional[str]],
    last_dates: Dict[str, Optional[str]],
    flash_count: int,
    flashed_list: list[str],
    btc_price: Optional[float],
) -> str:
    """
    Formats the indicator values into an email body.

    Args:
        min_indicators: Dictionary with minimum values (from last 7 days)
        current_indicators: Dictionary with current/latest values
        min_dates: Dictionary with dates when minimum values occurred
        last_dates: Dictionary with last available dates
        flash_count: Number of indicators that flashed (0-3)
        flashed_list: List of indicator names that flashed
        btc_price: Current Bitcoin price in USD

    Returns:
        str: Formatted email body as HTML
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    investment_amount = INVESTMENT_AMOUNTS.get(flash_count, 0)

    html_body = """
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <style>
        .title { color: #333; font-size: 1.5em; }
        .text { font-size: 1em; }
        .footer { color: #6c757d; font-size: 0.9em; }
        .indicator-name { font-weight: bold; margin-top: 1em; }
    </style>
    """

    # Current Bitcoin price (at the top)
    if btc_price:
        html_body += f'<h2 class="title">BTC Price: ${btc_price:,.2f}</h2>'

    html_body += "<br><hr>"

    # Investment recommendation
    if investment_amount > 0:
        html_body += (
            '<h2 class="title">'
            f"Investment Recommendation: "
            f"Invest {investment_amount} EUR</h2>"
        )
    else:
        html_body += (
            '<h2 class="title">'
            "Investment Recommendation: "
            "No investment (0 EUR)</h2>"
        )

    html_body += "<br><hr>"

    html_body += (
        '<h2 class="title">' "Minimum Values for Indicators (Last 7 Days)</h2>"
    )

    for name, value in min_indicators.items():
        if value is not None:
            min_date = min_dates.get(name, "N/A")
            last_date = last_dates.get(name, "N/A")
            current_val = current_indicators.get(name)
            html_body += f'<div class="text"><div class="indicator-name">{name}</div>'
            if min_date:
                html_body += (
                    f"<div>Lowest: <strong>{value:.4f}</strong> ({min_date})</div>"
                )
            else:
                html_body += f"<div>Lowest: <strong>{value:.4f}</strong></div>"
            if current_val is not None and last_date:
                html_body += f"<div>Current: {current_val:.4f} ({last_date})</div>"
            elif current_val is not None:
                html_body += f"<div>Current: {current_val:.4f}</div>"
            html_body += "</div>"
        else:
            html_body += (
                f'<div class="text"><div class="indicator-name">{name}</div>'
                "<div>[Error fetching data]</div></div>"
            )

    html_body += "<br><hr>"

    # Flash information
    html_body += "<br>" f'<h2 class="title">Indicators Flashed: {flash_count}/3</h2>'
    if flashed_list:
        html_body += (
            f'<h2 class="title">' f"Flashed Indicators: {', '.join(flashed_list)}</h2>"
        )
    html_body += '<ul class="text">'
    for name, threshold in FLASH_THRESHOLDS.items():
        html_body += f"<li>{name}: &lt; {threshold}</li>"
    html_body += (
        "</ul>"
        "<br>"
        "<hr>"
        f'<p class="footer">'
        f"Generated: {timestamp}<br>"
        "BTC Indicator Emailer</p>"
        "</body>"
        "</html>"
    )

    return html_body


def send_email(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    subject: str,
    body: str,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
) -> bool:
    """
    Sends an email via SMTP.

    Args:
        sender_email: Email address of the sender
        sender_password: Password or app-specific password for the sender
        recipient_email: Email address of the recipient
        subject: Email subject line
        body: Email body text
        smtp_server: SMTP server address (default: Gmail)
        smtp_port: SMTP server port (default: 587 for TLS)

    Returns:
        bool: True if email sent successfully, False otherwise

    Supported email providers:
    - Gmail: smtp.gmail.com, port 587 (TLS) or 465 (SSL)
    - Outlook: smtp-mail.outlook.com, port 587
    - Yahoo: smtp.mail.yahoo.com, port 587
    """
    try:
        # Create message
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        # Connect to server and send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Enable encryption
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()

        print(f"Email sent successfully to {recipient_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("Error: Authentication failed. Check your email and password.")
        return False
    except smtplib.SMTPException as e:
        print(f"Error: SMTP error occurred: {e}")
        return False
    except Exception as e:
        print(f"Error: Failed to send email: {e}")
        return False


def main():
    """
    Main function that orchestrates fetching indicators and sending email.
    """
    # ============================================
    # CONFIGURATION
    # ============================================
    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
    RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

    # SMTP Configuration (defaults work for Gmail)
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

    # Email subject
    EMAIL_SUBJECT = "BTC DCA TIME"

    # ============================================
    # EXECUTION
    # ============================================
    print("Fetching Bitcoin indicators...")
    (
        min_indicators,
        current_indicators,
        min_dates,
        last_dates,
        flash_count,
        flashed_list,
    ) = fetch_indicators()

    # Check if we got at least one indicator
    if all(v is None for v in min_indicators.values()):
        print("Error: All indicators failed to fetch. Aborting email send.")
        return

    print("Fetching current BTC price...")
    btc_price = get_current_btc_price()

    print("Formatting email...")
    email_body = format_email(
        min_indicators,
        current_indicators,
        min_dates,
        last_dates,
        flash_count,
        flashed_list,
        btc_price,
    )

    print("Sending email...")
    success = send_email(
        sender_email=SENDER_EMAIL,
        sender_password=SENDER_PASSWORD,
        recipient_email=RECIPIENT_EMAIL,
        subject=EMAIL_SUBJECT,
        body=email_body,
        smtp_server=SMTP_SERVER,
        smtp_port=SMTP_PORT,
    )

    if success:
        print("Process completed successfully!")
    else:
        print("Process completed with errors. Check the output above.")


if __name__ == "__main__":
    main()

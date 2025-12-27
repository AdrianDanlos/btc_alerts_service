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


def get_puell() -> Tuple[float, list[float], str]:
    """
    Fetches Puell Multiple from ChartInspect API for last 7 days.

    Returns:
        tuple: (minimum_value, list_of_all_values, last_date)
            - minimum_value: Lowest Puell Multiple in last 7 days
            - list_of_all_values: All values for flash detection
            - last_date: Last available date (YYYY-MM-DD format)

    Raises:
        Exception: If API call fails or returns invalid data
    """
    api_key = os.getenv("CHARTINSPECT_API_KEY")
    if not api_key:
        raise ValueError("CHARTINSPECT_API_KEY environment variable not set")

    url = "https://chartinspect.com/api/v1/onchain/puell-multiple"
    params = {"days": 7}
    headers = {"X-API-Key": api_key}

    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not data.get("success") or not data.get("data"):
        raise ValueError("No data returned from ChartInspect API")

    # Extract all puell_multiple values and get last date
    values = [item["puell_multiple"] for item in data["data"]]
    if not values:
        raise ValueError("Invalid data format from ChartInspect API")

    # Get the last date (most recent data point)
    last_item = data["data"][-1]
    last_date = last_item.get("formattedDate") or last_item.get("date")

    # Return minimum value, all values, and last date
    return (min(values), values, last_date)


def get_mvrv_z() -> Tuple[float, list[float], str]:
    """
    Fetches MVRV Z-Score from ChartInspect API for last 7 days.

    Returns:
        tuple: (minimum_value, list_of_all_values, last_date)
            - minimum_value: Lowest MVRV Z-Score in last 7 days
            - list_of_all_values: All values for flash detection
            - last_date: Last available date (YYYY-MM-DD format)

    Raises:
        Exception: If API call fails or returns invalid data
    """
    api_key = os.getenv("CHARTINSPECT_API_KEY")
    if not api_key:
        raise ValueError("CHARTINSPECT_API_KEY environment variable not set")

    url = "https://chartinspect.com/api/v1/onchain/mvrv-z-score"
    params = {"days": 7}
    headers = {"X-API-Key": api_key}

    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not data.get("success") or not data.get("data"):
        raise ValueError("No data returned from ChartInspect API")

    # Extract all z_score values and get last date
    values = [item["z_score"] for item in data["data"]]
    if not values:
        raise ValueError("Invalid data format from ChartInspect API")

    # Get the last date (most recent data point)
    last_item = data["data"][-1]
    last_date = last_item.get("formattedDate") or last_item.get("date")

    # Return minimum value, all values, and last date
    return (min(values), values, last_date)


def get_ahr999() -> Tuple[float, list[float], str]:
    """
    Calculates AHR999 indicator using CoinGecko API for last 7 days.

    Formula: AHR999 = (Price / 200-day DCA Cost) × (Price / Growth Valuation)

    Returns:
        tuple: (minimum_value, list_of_all_values, last_date)
            - minimum_value: Lowest AHR999 in last 7 days
            - list_of_all_values: All values for flash detection
            - last_date: Last available date (YYYY-MM-DD format)

    Raises:
        Exception: If API call fails or calculation fails
    """
    # Get 7 days of historical prices plus 200 days for DCA calculation
    end_date = datetime.now()
    start_date = end_date - timedelta(days=207)  # 7 days + 200 days buffer
    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())

    historical_url = (
        f"https://api.coingecko.com/api/v3/coins/bitcoin"
        f"/market_chart/range?vs_currency=usd"
        f"&from={start_timestamp}&to={end_timestamp}"
    )
    response = requests.get(historical_url, timeout=30)
    response.raise_for_status()
    historical_data = response.json()

    # Extract prices from historical data
    price_points = historical_data.get("prices", [])
    if not price_points:
        raise ValueError("No price data returned from CoinGecko API")

    # Get prices for last 7 days (for AHR999 calculation)
    seven_days_ago = end_date - timedelta(days=7)
    seven_days_timestamp = int(seven_days_ago.timestamp())

    ahr999_values = []
    last_date_str = None
    bitcoin_genesis = datetime(2009, 1, 3)

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
        point_start = point_date - timedelta(days=200)
        point_start_ts = point_start.timestamp()

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
        days_since_genesis = (point_date - bitcoin_genesis).days

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

        # Track the last date (most recent calculation)
        last_date_str = date_key

    if not ahr999_values:
        raise ValueError("Could not calculate AHR999 values")

    # Return minimum value, all values, and last date
    return (min(ahr999_values), ahr999_values, last_date_str)


def check_flashes(
    mvrv_values: list[float],
    puell_values: list[float],
    ahr999_values: list[float],
) -> Tuple[int, list[str]]:
    """
    Checks how many indicators have "flashed" (reached thresholds)
    in last 7 days.

    Thresholds:
    - MVRV Z-Score: < 0
    - Puell Multiple: < 0.5
    - AHR999: < 0.45

    Args:
        mvrv_values: List of MVRV Z-Score values
        puell_values: List of Puell Multiple values
        ahr999_values: List of AHR999 values

    Returns:
        tuple: (flash_count, flashed_indicators)
            - flash_count: Number of indicators that flashed (0-3)
            - flashed_indicators: List of indicator names that flashed
    """
    flashes = 0
    flashed_indicators = []

    if mvrv_values and any(v < 0 for v in mvrv_values):
        flashes += 1
        flashed_indicators.append("MVRV Z-Score")

    if puell_values and any(v < 0.5 for v in puell_values):
        flashes += 1
        flashed_indicators.append("Puell Multiple")

    if ahr999_values and any(v < 0.45 for v in ahr999_values):
        flashes += 1
        flashed_indicators.append("AHR999")

    return (flashes, flashed_indicators)


def get_current_btc_price() -> Optional[float]:
    """
    Gets current Bitcoin price from CoinGecko.

    Returns:
        float: Current Bitcoin price in USD, or None if fetch fails
    """
    try:
        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin&vs_currencies=usd"
        )
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return float(response.json()["bitcoin"]["usd"])
    except Exception as e:
        print(f"Error fetching current BTC price: {e}")
        return None


def fetch_indicators() -> Tuple[
    Dict[str, Optional[float]],
    Dict[str, Optional[float]],
    Dict[str, Optional[str]],
    int,
    list[str],
]:
    """
    Fetches all three Bitcoin indicators and checks for flashes.

    Returns:
        tuple: (min_indicators, current_indicators, last_dates, flash_count,
                flashed_list)
            - min_indicators: Dictionary with minimum values (from last 7 days)
            - current_indicators: Dictionary with current/latest values
            - last_dates: Dictionary with last available dates (YYYY-MM-DD)
            - flash_count: Number of indicators that flashed (0-3)
            - flashed_list: List of indicator names that flashed

    Raises:
        Exception: If all indicators fail to fetch
                   (optional - currently handled gracefully)
    """
    min_indicators = {}
    current_indicators = {}
    last_dates = {}
    mvrv_values = None
    puell_values = None
    ahr999_values = None

    try:
        min_value, all_values, last_date = get_puell()
        min_indicators["Puell Multiple"] = min_value
        current_indicators["Puell Multiple"] = all_values[-1] if all_values else None
        last_dates["Puell Multiple"] = last_date
        puell_values = all_values
    except Exception as e:
        print(f"Error fetching Puell Multiple: {e}")
        min_indicators["Puell Multiple"] = None
        current_indicators["Puell Multiple"] = None
        last_dates["Puell Multiple"] = None

    try:
        min_value, all_values, last_date = get_mvrv_z()
        min_indicators["MVRV Z-Score"] = min_value
        current_indicators["MVRV Z-Score"] = all_values[-1] if all_values else None
        last_dates["MVRV Z-Score"] = last_date
        mvrv_values = all_values
    except Exception as e:
        print(f"Error fetching MVRV Z-Score: {e}")
        min_indicators["MVRV Z-Score"] = None
        current_indicators["MVRV Z-Score"] = None
        last_dates["MVRV Z-Score"] = None

    try:
        min_value, all_values, last_date = get_ahr999()
        min_indicators["AHR999"] = min_value
        current_indicators["AHR999"] = all_values[-1] if all_values else None
        last_dates["AHR999"] = last_date
        ahr999_values = all_values
    except Exception as e:
        print(f"Error fetching AHR999: {e}")
        min_indicators["AHR999"] = None
        current_indicators["AHR999"] = None
        last_dates["AHR999"] = None

    # Check for flashes
    flash_count, flashed_list = check_flashes(
        mvrv_values or [], puell_values or [], ahr999_values or []
    )

    return (
        min_indicators,
        current_indicators,
        last_dates,
        flash_count,
        flashed_list,
    )


def format_email(
    min_indicators: Dict[str, Optional[float]],
    current_indicators: Dict[str, Optional[float]],
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
        last_dates: Dictionary with last available dates
        flash_count: Number of indicators that flashed (0-3)
        flashed_list: List of indicator names that flashed
        btc_price: Current Bitcoin price in USD

    Returns:
        str: Formatted email body as HTML
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Investment recommendation based on flash count
    investment_amounts = {0: 0, 1: 550, 2: 1100, 3: 2100}
    investment_amount = investment_amounts.get(flash_count, 0)

    html_body = """
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6;">
    """

    # Investment recommendation
    if investment_amount > 0:
        html_body += (
            f'<h2 style="color: #28a745;">💰 INVESTMENT RECOMMENDATION: '
            f"Invest <strong>{investment_amount} EUR</strong></h2>"
        )
    else:
        html_body += (
            '<h2 style="color: #6c757d;">💰 INVESTMENT RECOMMENDATION: '
            "No investment (0 EUR)</h2>"
        )

    html_body += "<hr>"

    # Current Bitcoin price
    if btc_price:
        html_body += (
            f"<p><strong>📊 Current BTC Price:</strong> "
            f"<strong>${btc_price:,.2f}</strong></p>"
        )

    html_body += "<h3>Minimum Values (Last 7 Days):</h3><ul>"

    for name, value in min_indicators.items():
        if value is not None:
            last_date = last_dates.get(name, "N/A")
            current_val = current_indicators.get(name)
            if last_date:
                if current_val is not None:
                    html_body += (
                        f"<li><strong>{name}:</strong> {value:.4f} "
                        f"(Current: <strong>{current_val:.4f}</strong> "
                        f"from {last_date})</li>"
                    )
                else:
                    html_body += (
                        f"<li><strong>{name}:</strong> {value:.4f} "
                        f"(Last fetch: {last_date})</li>"
                    )
            else:
                html_body += f"""
                <li><strong>{name}:</strong> {value:.4f}</li>
                """
        else:
            html_body += f"""
            <li><strong>{name}:</strong> [Error fetching data]</li>
            """

    html_body += "</ul><hr>"

    # Flash information
    html_body += (
        f"<p><strong>Indicators Flashed:</strong> "
        f"<strong>{flash_count}/3</strong></p>"
    )
    if flashed_list:
        html_body += (
            f"<p><strong>Flashed Indicators:</strong> " f'{", ".join(flashed_list)}</p>'
        )
    html_body += """
    <p><strong>Flash Thresholds:</strong></p>
    <ul>
    <li>MVRV Z-Score: &lt; 0</li>
    <li>Puell Multiple: &lt; 0.5</li>
    <li>AHR999: &lt; 0.45</li>
    </ul>
    <hr>
    <p style="color: #6c757d; font-size: 0.9em;">Generated: {timestamp}<br>'
        'BTC Indicator Emailer</p>'
    </body>
    </html>
    """.format(
        timestamp=timestamp
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

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


def get_puell() -> Tuple[float, list[float]]:
    """
    Fetches Puell Multiple from ChartInspect API for last 7 days.

    Returns:
        tuple: (minimum_value, list_of_all_values)
            - minimum_value: Lowest Puell Multiple in last 7 days
            - list_of_all_values: All values for flash detection

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

    # Extract all puell_multiple values
    values = [item["puell_multiple"] for item in data["data"]]
    if not values:
        raise ValueError("Invalid data format from ChartInspect API")

    # Return minimum value and all values for flash detection
    return (min(values), values)


def get_mvrv_z() -> Tuple[float, list[float]]:
    """
    Fetches MVRV Z-Score from ChartInspect API for last 7 days.

    Returns:
        tuple: (minimum_value, list_of_all_values)
            - minimum_value: Lowest MVRV Z-Score in last 7 days
            - list_of_all_values: All values for flash detection

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

    # Extract all z_score values
    values = [item["z_score"] for item in data["data"]]
    if not values:
        raise ValueError("Invalid data format from ChartInspect API")

    # Return minimum value and all values for flash detection
    return (min(values), values)


def get_ahr999() -> Tuple[float, list[float]]:
    """
    Calculates AHR999 indicator using CoinGecko API for last 7 days.

    Formula: AHR999 = (Price / 200-day DCA Cost) × (Price / Growth Valuation)

    Returns:
        tuple: (minimum_value, list_of_all_values)
            - minimum_value: Lowest AHR999 in last 7 days
            - list_of_all_values: All values for flash detection

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
    bitcoin_genesis = datetime(2009, 1, 3)

    # Calculate AHR999 for each day in the last 7 days
    for point in price_points:
        point_timestamp = point[0] / 1000  # Convert from ms to seconds
        point_date = datetime.fromtimestamp(point_timestamp)

        # Only calculate for last 7 days
        if point_timestamp < seven_days_timestamp:
            continue

        current_price = point[1]

        # Get 200 days of prices before this point for DCA calculation
        point_start = point_date - timedelta(days=200)
        point_start_ts = int(point_start.timestamp())

        # Find prices in the 200-day window before this point
        prices_200d = [
            p[1]
            for p in price_points
            if point_start_ts <= p[0] / 1000 < point_timestamp
        ]

        if not prices_200d:
            # Fallback: use all available prices
            prices_200d = [p[1] for p in price_points if p[0] / 1000 < point_timestamp]

        # Calculate 200-day DCA cost
        if prices_200d:
            dca_cost = sum(prices_200d) / len(prices_200d)
        else:
            dca_cost = current_price

        # Calculate exponential growth valuation
        days_since_genesis = (point_date - bitcoin_genesis).days
        log_prices = [math.log(p) for p in prices_200d if p > 0]
        if log_prices:
            avg_log_price = sum(log_prices) / len(log_prices)
            growth_factor = 0.0001 * days_since_genesis
            growth_valuation = math.exp(avg_log_price + growth_factor)
        else:
            growth_valuation = current_price

        # Calculate AHR999 for this day
        price_ratio = current_price / dca_cost
        growth_ratio = current_price / growth_valuation
        ahr999 = price_ratio * growth_ratio
        ahr999_values.append(ahr999)

    if not ahr999_values:
        raise ValueError("Could not calculate AHR999 values")

    # Return minimum value and all values for flash detection
    return (min(ahr999_values), ahr999_values)


def check_flashes(
    mvrv_values: list[float],
    puell_values: list[float],
    ahr999_values: list[float],
) -> int:
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
        int: Number of indicators that flashed (0-3)
    """
    flashes = 0

    if mvrv_values and any(v < 0 for v in mvrv_values):
        flashes += 1

    if puell_values and any(v < 0.5 for v in puell_values):
        flashes += 1

    if ahr999_values and any(v < 0.45 for v in ahr999_values):
        flashes += 1

    return flashes


def fetch_indicators() -> Tuple[Dict[str, Optional[float]], int]:
    """
    Fetches all three Bitcoin indicators and checks for flashes.

    Returns:
        tuple: (indicators_dict, flash_count)
            - indicators_dict: Dictionary with indicator names as keys and
              minimum values (from last 7 days) as floats.
              Values are None if fetching fails.
            - flash_count: Number of indicators that flashed (0-3)

    Raises:
        Exception: If all indicators fail to fetch
                   (optional - currently handled gracefully)
    """
    indicators = {}
    mvrv_values = None
    puell_values = None
    ahr999_values = None

    try:
        min_value, all_values = get_puell()
        indicators["Puell Multiple"] = min_value
        puell_values = all_values
    except Exception as e:
        print(f"Error fetching Puell Multiple: {e}")
        indicators["Puell Multiple"] = None

    try:
        min_value, all_values = get_mvrv_z()
        indicators["MVRV Z-Score"] = min_value
        mvrv_values = all_values
    except Exception as e:
        print(f"Error fetching MVRV Z-Score: {e}")
        indicators["MVRV Z-Score"] = None

    try:
        min_value, all_values = get_ahr999()
        indicators["AHR999"] = min_value
        ahr999_values = all_values
    except Exception as e:
        print(f"Error fetching AHR999: {e}")
        indicators["AHR999"] = None

    # Check for flashes
    flash_count = check_flashes(
        mvrv_values or [], puell_values or [], ahr999_values or []
    )

    return (indicators, flash_count)


def format_email(indicators: Dict[str, Optional[float]], flash_count: int) -> str:
    """
    Formats the indicator values into an email body.

    Args:
        indicators: Dictionary with indicator names and minimum values
        flash_count: Number of indicators that flashed (0-3)

    Returns:
        str: Formatted email body text
    """
    body_lines = []
    body_lines.append("Bitcoin Indicator Update (Last 7 Days)\n")
    body_lines.append("=" * 40 + "\n")
    body_lines.append("Minimum Values (Last 7 Days):\n")

    for name, value in indicators.items():
        if value is not None:
            body_lines.append(f"{name}: {value:.4f}")
        else:
            body_lines.append(f"{name}: [Error fetching data]")

    body_lines.append("\n" + "=" * 40)
    body_lines.append(f"\nIndicators Flashed: {flash_count}/3")
    body_lines.append("\nFlash Thresholds:")
    body_lines.append("  - MVRV Z-Score: < 0")
    body_lines.append("  - Puell Multiple: < 0.5")
    body_lines.append("  - AHR999: < 0.45")
    body_lines.append("\n" + "=" * 40)
    body_lines.append("\nGenerated automatically by BTC Indicator Emailer")

    return "\n".join(body_lines)


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
        msg.attach(MIMEText(body, "plain"))

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
    EMAIL_SUBJECT = "BTC Indicator Update"

    # ============================================
    # EXECUTION
    # ============================================
    print("Fetching Bitcoin indicators...")
    indicators, flash_count = fetch_indicators()

    # Check if we got at least one indicator
    if all(v is None for v in indicators.values()):
        print("Error: All indicators failed to fetch. Aborting email send.")
        return

    print("Formatting email...")
    email_body = format_email(indicators, flash_count)

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

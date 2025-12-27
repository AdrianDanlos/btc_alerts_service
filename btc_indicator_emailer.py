#!/usr/bin/env python3
"""
Bitcoin Indicator Emailer

This script fetches three Bitcoin indicators
(Puell Multiple, MVRV Z-Score, AHR999x)
and sends them via email on a scheduled basis.

Configuration:
1. Replace placeholder functions (get_puell, get_mvrv_z, get_ahr999x)
   with real API calls
2. Schedule using cron (PythonAnywhere), GitHub Actions, or Replit scheduler
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import Dict, Optional


def get_puell() -> float:
    """
    Placeholder function for fetching Puell Multiple.

    TODO: Replace with actual API call.
    Example sources:
    - Glassnode API: https://docs.glassnode.com/
    - Alternative: Web scraping from public sources

    Returns:
        float: Puell Multiple value
    """
    # Placeholder: returns a sample value
    # Replace this with actual API call, e.g.:
    # import requests
    # url = 'https://api.glassnode.com/v1/metrics/indicators/puell_multiple'
    # response = requests.get(url)
    # return response.json()['value']
    return 1.25


def get_mvrv_z() -> float:
    """
    Placeholder function for fetching MVRV Z-Score.

    TODO: Replace with actual API call.
    Example sources:
    - Glassnode API: https://docs.glassnode.com/
    - Alternative: Calculate from market cap and realized cap data

    Returns:
        float: MVRV Z-Score value
    """
    # Placeholder: returns a sample value
    # Replace this with actual API call, e.g.:
    # import requests
    # url = 'https://api.glassnode.com/v1/metrics/market/mvrv_zscore'
    # response = requests.get(url)
    # return response.json()['value']
    return 0.85


def get_ahr999x() -> float:
    """
    Placeholder function for fetching AHR999x indicator.

    TODO: Replace with actual API call.
    Example sources:
    - Custom calculation based on price and 200-day MA
    - Alternative: Fetch from specialized Bitcoin indicator APIs

    Returns:
        float: AHR999x value
    """
    # Placeholder: returns a sample value
    # Replace this with actual API call, e.g.:
    # import requests
    # response = requests.get('https://api.example.com/ahr999x')
    # return response.json()['value']
    return 0.65


def fetch_indicators() -> Dict[str, Optional[float]]:
    """
    Fetches all three Bitcoin indicators.

    Returns:
        dict: Dictionary with indicator names as keys and values as floats.
              Values are None if fetching fails.

    Raises:
        Exception: If all indicators fail to fetch
                   (optional - currently handled gracefully)
    """
    indicators = {}

    try:
        indicators["Puell Multiple"] = get_puell()
    except Exception as e:
        print(f"Error fetching Puell Multiple: {e}")
        indicators["Puell Multiple"] = None

    try:
        indicators["MVRV Z-Score"] = get_mvrv_z()
    except Exception as e:
        print(f"Error fetching MVRV Z-Score: {e}")
        indicators["MVRV Z-Score"] = None

    try:
        indicators["AHR999x"] = get_ahr999x()
    except Exception as e:
        print(f"Error fetching AHR999x: {e}")
        indicators["AHR999x"] = None

    return indicators


def format_email(indicators: Dict[str, Optional[float]]) -> str:
    """
    Formats the indicator values into an email body.

    Args:
        indicators: Dictionary with indicator names and values

    Returns:
        str: Formatted email body text
    """
    body_lines = []
    body_lines.append("Bitcoin Indicator Update\n")
    body_lines.append("=" * 30 + "\n")

    for name, value in indicators.items():
        if value is not None:
            body_lines.append(f"{name}: {value:.4f}")
        else:
            body_lines.append(f"{name}: [Error fetching data]")

    body_lines.append("\n" + "=" * 30)
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
    indicators = fetch_indicators()

    # Check if we got at least one indicator
    if all(v is None for v in indicators.values()):
        print("Error: All indicators failed to fetch. Aborting email send.")
        return

    print("Formatting email...")
    email_body = format_email(indicators)

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

import logging
import os
import requests
from bs4 import BeautifulSoup
import azure.functions as func
from datetime import datetime
import smtplib
from email.message import EmailMessage

# Create your Function App instance using the new programming model
app = func.FunctionApp()

# Define a list of websites and the expected text for each.
WEBSITES = [
    {
        "name": "Golden Harmony Wurfplanung",
        "url": "https://www.goldenharmony.ch/zucht/wurfplanung",
        "expected_text": ("Aktuell ist kein Wurf geplant. Daher nehmen wir auch keine Anfragen entgegen. "
                          "Wir bitten um Verständnis."),
        # CSS selector for the element containing the text
        "selector": {"tag": "h2", "class": "uk-h2 uk-text-warning"}
    },
    # Add additional website dictionaries here if needed.
]

@app.function_name(name="CheckPuppies")
@app.timer_trigger(schedule="0 0 9 * * *", arg_name="mytimer", run_on_startup=True)
def check_websites(mytimer: func.TimerRequest) -> None:
    logging.info(f"CheckWebsites function started at {datetime.utcnow()}")
    changes = []  # Collect changes for sites that have updated

    for site in WEBSITES:
        url = site["url"]
        expected_text = site["expected_text"]
        tag = site["selector"].get("tag")
        css_class = site["selector"].get("class")
        logging.info(f"Checking website: {site['name']} ({url})")
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logging.error(f"Error fetching {url}: {e}")
            changes.append(f"{site['name']} ({url}) - Error fetching page: {e}")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.find(tag, class_=css_class)
        if element:
            # Extract text and remove extra white space
            extracted_text = element.get_text(separator=" ", strip=True)
            logging.info(f"Extracted text for {site['name']}: {extracted_text}")
            
            if extracted_text != expected_text:
                changes.append(f"{site['name']} ({url}) - Updated text:\n{extracted_text}")
            else:
                logging.info(f"No change detected for {site['name']}.")
        else:
            logging.error(f"Could not find the target element in {url}")
            changes.append(f"{site['name']} ({url}) - Target element not found.")

    if changes:
        email_body = "The following websites have changed:\n\n" + "\n\n".join(changes)
        send_email_notification("Puppies might be available", email_body)
    else:
        logging.info("No changes detected across all websites.")

def send_email_notification(subject: str, body: str) -> None:
    """
    Send an email using Brevo's SMTP relay.
    Credentials and SMTP settings are read from environment variables.
    """
    # Retrieve SMTP settings from environment variables or use defaults
    smtp_server = os.environ.get("SMTP_SERVER", "smtp-relay.brevo.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ.get("SMTP_USERNAME", "89f727001@smtp-brevo.com")
    smtp_password = os.environ.get("SMTP_PASSWORD", "MhNGDF9AHd8avKsP")
    
    # Get sender and receiver email addresses from environment variables.
    sender_email = os.environ.get("SENDER_EMAIL", smtp_username)
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    if not receiver_email:
        logging.error("Receiver email is not set in the environment variables.")
        return
    
    # Create email message
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg.set_content(body)
    
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Secure the connection with TLS
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        logging.info("Notification email sent successfully using Brevo SMTP.")
    except Exception as e:
        logging.error(f"Error sending email via Brevo SMTP: {e}")

# Uncomment the following HTTP trigger function for testing purposes if needed.
# @app.function_name(name="HttpTest")
# @app.http_trigger(methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS, route="test")
# def http_test(req: func.HttpRequest) -> func.HttpResponse:
#     logging.info(f"HTTP trigger function called at {datetime.utcnow()}")
#     return func.HttpResponse("HTTP trigger test successful", status_code=200)

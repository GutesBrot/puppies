import logging
import os
import requests
from bs4 import BeautifulSoup
import azure.functions as func
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Create your Function App instance
app = func.FunctionApp()

# Define a list of websites and the expected text for each.
WEBSITES = [
    {
        "name": "Golden Harmony Wurfplanung",
        "url": "https://www.goldenharmony.ch/zucht/wurfplanung",
        "expected_text": ("Aktuell ist kein Wurf geplant. Daher nehmen wir auch keine Anfragen entgegen. "
                          "Wir bitten um Verständnis."),
        # A CSS selector, or use a combination of tag and class for BeautifulSoup.
        "selector": {"tag": "h2", "class": "uk-h2 uk-text-warning"}
    },
    # You can add more website dictionaries here
    # {
    #     "name": "Other Website Name",
    #     "url": "https://example.com/somepage",
    #     "expected_text": "Expected content goes here.",
    #     "selector": {"tag": "div", "class": "some-class"}
    # } 0 0 9 * * *
]

@app.function_name(name="CheckPuppies")
@app.timer_trigger(schedule="0 */2 * * * *", arg_name="mytimer", run_on_startup=True)
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
        # Compose an email body including the URL(s) and details of the changes.
        email_body = "The following websites have changed:\n\n" + "\n\n".join(changes)
        send_email_notification("Puppies might be available", email_body)
    else:
        logging.info("No changes detected across all websites.")

def send_email_notification(subject: str, body: str) -> None:
    """
    Send an email using Twilio SendGrid.
    Ensure these environment variables are set:
      - SENDGRID_API_KEY
      - SENDER_EMAIL
      - RECEIVER_EMAIL
    """
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    sender_email = os.environ.get("SENDER_EMAIL")
    receiver_email = os.environ.get("RECEIVER_EMAIL")

    if not all([sendgrid_api_key, sender_email, receiver_email]):
        logging.error("SendGrid email configuration is missing. Check your environment variables.")
        return

    message = Mail(
        from_email=sender_email,
        to_emails=receiver_email,
        subject=subject,
        html_content=body
    )

    try:
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        logging.info(f"Email sent successfully. Status Code: {response.status_code}")
    except Exception as e:
        logging.error(f"Error sending email via SendGrid: {e}")

# Add an HTTP trigger function for testing
@app.function_name(name="HttpTest")
@app.http_trigger(methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS, route="test")
def http_test(req: func.HttpRequest) -> func.HttpResponse:
    logging.info(f"HTTP trigger function called at {datetime.utcnow()}")
    return func.HttpResponse("HTTP trigger test successful", status_code=200)

"""Send the rendered HTML digest via SMTP."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send(cfg: dict, subject: str, html_body: str) -> None:
    ec = cfg["email"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{ec['sender_name']} <{ec['smtp_user']}>"
    msg["To"] = ec["recipient"]
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(ec["smtp_host"], ec["smtp_port"]) as server:
        server.ehlo()
        server.starttls()
        server.login(ec["smtp_user"], ec["smtp_password"])
        server.sendmail(ec["smtp_user"], ec["recipient"], msg.as_string())

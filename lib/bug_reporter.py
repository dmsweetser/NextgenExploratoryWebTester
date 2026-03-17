import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from lib.config import Config

class BugReporter:
    def send_notification(self, summary, knowledge):
        if not Config.get_smtp_host():
            return

        msg = MIMEMultipart()
        msg['From'] = Config.get_smtp_from()
        msg['To'] = Config.get_bug_notification_emails()
        msg['Subject'] = f"New Bug Found: {summary}"

        body = f"""
        A new bug has been found by the bot system.

        Summary: {summary}

        Knowledge about this bug:
        {knowledge}

        Please investigate and update the system accordingly.
        """
        msg.attach(MIMEText(body, 'plain'))

        try:
            with smtplib.SMTP(Config.get_smtp_host(), Config.get_smtp_port()) as server:
                server.starttls()
                server.login(Config.get_smtp_user(), Config.get_smtp_password())
                server.send_message(msg)
        except Exception as e:
            logging.error(f"Failed to send email notification: {str(e)}")

import resend
from django.core.mail.backends.base import BaseEmailBackend
import os

class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        resend.api_key = os.environ.get('RESEND_API_KEY')
        sent = 0
        for msg in email_messages:
            try:
                resend.Emails.send({
                    "from": "Asilo Virtual <onboarding@resend.dev>",
                    "to": msg.to,
                    "subject": msg.subject,
                    "text": msg.body,
                })
                sent += 1
            except Exception as e:
                print(f"ERROR RESEND: {e}")
        return sent
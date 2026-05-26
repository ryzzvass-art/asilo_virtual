import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from django.core.mail.backends.base import BaseEmailBackend
import os
import logging

logger = logging.getLogger(__name__)

class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        api_key = os.environ.get('BREVO_API_KEY')
        if not api_key:
            logger.error("❌ BREVO_API_KEY no configurada en Render")
            return 0

        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        sent = 0
        for msg in email_messages:
            try:
                to_list = [{"email": email} for email in msg.to]

                # === EXTRAER HTML CORRECTAMENTE ===
                html_content = None
                if hasattr(msg, 'alternatives') and msg.alternatives:
                    for content, mimetype in msg.alternatives:
                        if mimetype == 'text/html':
                            html_content = content
                            break

                # Usar el remitente desde settings (mejor práctica)
                from_email = getattr(msg, 'from_email', None) or os.environ.get('BREVO_EMAIL')

                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                    to=to_list,
                    sender={
                        "name": "Asilo Virtual",
                        "email": from_email or "ryzzvass@gmail.com"
                    },
                    subject=msg.subject,
                    text_content=msg.body,
                    html_content=html_content,
                )

                response = api_instance.send_transac_email(send_smtp_email)
                
                logger.info(f"✅ Email HTML enviado a {msg.to} | ID: {response.message_id}")
                sent += 1

            except ApiException as e:
                logger.error(f"❌ Brevo API Error: {e.status} - {e.reason}")
                if hasattr(e, 'body'):
                    logger.error(f"Brevo Body: {e.body}")
                raise
            except Exception as e:
                logger.error(f"❌ Error general: {str(e)}")
                raise

        return sent
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
            logger.error("❌ BREVO_API_KEY no encontrada en variables de entorno de Render")
            return 0

        try:
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key['api-key'] = api_key
            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )

            sent = 0
            for msg in email_messages:
                to_list = [{"email": email} for email in msg.to]

                # Extraer HTML (crucial para tu password reset)
                html_content = None
                if msg.alternatives:
                    for content, mimetype in msg.alternatives:
                        if mimetype == 'text/html':
                            html_content = content
                            break

                # Usar el DEFAULT_FROM_EMAIL de settings o fallback
                from_email = getattr(msg, 'from_email', None) or os.environ.get('BREVO_EMAIL')

                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                    to=to_list,
                    sender={
                        "name": "Asilo Virtual",
                        "email": from_email or "ryzzvass@gmail.com"   # ← Importante
                    },
                    subject=msg.subject,
                    text_content=msg.body,
                    html_content=html_content,
                )

                response = api_instance.send_transac_email(send_smtp_email)
                
                logger.info(f"✅ Email enviado a {msg.to} | Message ID: {response.message_id}")
                sent += 1

            return sent

        except ApiException as e:
            logger.error(f"❌ Brevo API Error [{e.status}]: {e.reason}")
            if hasattr(e, 'body'):
                logger.error(f"Detalles: {e.body}")
            raise
        except Exception as e:
            logger.error(f"❌ Error general en Brevo backend: {str(e)}")
            raise
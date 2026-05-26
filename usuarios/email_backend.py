import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from django.core.mail.backends.base import BaseEmailBackend
import os

class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        api_key = os.environ.get('BREVO_API_KEY')
        if not api_key:
            print("❌ BREVO_API_KEY no configurada")
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
                
                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                    to=to_list,
                    sender={
                        "name": "Asilo Virtual",           # ← Exacto como en Brevo
                        "email": "ryzvass@gmail.com"
                    },
                    subject=msg.subject,
                    text_content=msg.body,
                    # Si usas HTML en recuperación de contraseña:
                    # html_content=msg.alternatives[0][0] if msg.alternatives else None,
                )

                response = api_instance.send_transac_email(send_smtp_email)
                print(f"✅ BREVO ENVIADO A: {msg.to} | ID: {response.message_id}")
                sent += 1

            except ApiException as e:
                print(f"❌ BREVO ERROR: {e}")
                raise
            except Exception as e:
                print(f"❌ ERROR GENERAL: {e}")
                raise

        return sent
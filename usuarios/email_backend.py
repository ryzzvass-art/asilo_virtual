import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from django.core.mail.backends.base import BaseEmailBackend
import os

class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        api_key = os.environ.get('BREVO_API_KEY')
        if not api_key:
            print("ERROR: No se encontró BREVO_API_KEY")
            return 0

        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key
        
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        sent = 0
        for msg in email_messages:
            try:
                # Convertir destinatarios
                to_list = [{"email": email} for email in msg.to]
                
                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                    to=to_list,
                    sender={
                        "name": "Asilo Virtual", 
                        "email": "ryzvass@gmail.com"   # ← Cambia si quieres
                    },
                    subject=msg.subject,
                    text_content=msg.body,
                    # html_content=...  (si usas HTML)
                )

                response = api_instance.send_transac_email(send_smtp_email)
                print(f"✅ BREVO SUCCESS: {response}")
                sent += 1

            except ApiException as e:
                print(f"❌ BREVO API ERROR: {e}")
                raise
            except Exception as e:
                print(f"❌ ERROR GENERAL: {e}")
                raise

        return sent
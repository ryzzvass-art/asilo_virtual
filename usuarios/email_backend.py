import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from django.core.mail.backends.base import BaseEmailBackend
import os

class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        api_key = os.environ.get('BREVO_API_KEY')
        if not api_key:
            print("❌ ERROR: BREVO_API_KEY no encontrada")
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
                        "name": "Asilo Virtual",           # ← Nombre que aparecerá
                        "email": "ryzvass@gmail.com"       # ← Usa el email verificado
                    },
                    subject=msg.subject,
                    text_content=msg.body,
                    # html_content=msg.alternatives[0][0] if hasattr(msg, 'alternatives') and msg.alternatives else None,
                )

                response = api_instance.send_transac_email(send_smtp_email)
                print(f"✅ BREVO ENVIADO: {response}")
                sent += 1

            except ApiException as e:
                print(f"❌ BREVO API ERROR: {e}")
                raise
            except Exception as e:
                print(f"❌ ERROR: {e}")
                raise

        return sent
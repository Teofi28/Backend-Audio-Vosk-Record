from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging import error
from smtplib import SMTP

from .setting import SettingDepends


class Sender:
    def __init__(self, setting: SettingDepends) -> None:
        self.setting = setting
        self.sub_type = "html"

    def send(self, message: str, subject: str = "CONTACTENOS"):
        try:
            msg = MIMEMultipart("alternative")
            msg["from"] = self.setting.email_user
            msg["to"] = self.setting.email_to
            msg["Subject"] = subject
            msg.attach(MIMEText(message, self.sub_type))

            server = SMTP(self.setting.smtp_server, self.setting.smtp_port)
            server.starttls()
            server.login(self.setting.email_user, self.setting.email_password)
            server.sendmail(
                self.setting.email_user, self.setting.email_to, msg.as_string()
            )
        except Exception as e:
            error("Error when send email", e)

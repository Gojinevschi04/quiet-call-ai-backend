"""Email translations for all supported languages.

Centralized translation strings for email notifications.
Each language has the same set of keys. Default fallback is English.
"""

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "call_completed": "Call Completed",
        "call_failed": "Call Failed",
        "call_scheduled": "Call Scheduled",
        "call_completed_body": "Your automated call has been completed successfully.",
        "call_failed_body": "Your automated call could not be completed.",
        "ai_summary": "AI Summary",
        "reason": "Reason",
        "view_transcript": "View Full Transcript",
        "view_task_retry": "View Task & Retry",
        "phone_number": "Phone number",
        "scheduled_for": "Scheduled for",
        "scheduled_body": (
            "Your call has been scheduled and will be executed automatically."
        ),
        "scheduled_followup": (
            "You will receive another email when the call is completed."
        ),
        "welcome_title": "Welcome aboard!",
        "welcome_body": (
            "Welcome to <strong>Quiet Call AI</strong>! Your account is ready."
        ),
        "welcome_body2": (
            "You can now create tasks to automate your phone calls. "
            "Pick a template, fill in the details, and let the AI agent "
            "handle the conversation."
        ),
        "go_to_dashboard": "Go to Dashboard",
        "reset_title": "Password Reset",
        "reset_body": (
            "We received a request to reset your password. "
            "Click the button below to choose a new one."
        ),
        "reset_button": "Reset Password",
        "reset_note": (
            "If you did not request this, you can safely ignore this email. "
            "The link expires in 1 hour."
        ),
        "password_changed_title": "Password Changed",
        "password_changed_body": "Your password was changed successfully.",
        "password_changed_warning": (
            "If you did not make this change, please reset your password "
            "immediately or contact support."
        ),
        "email_changed_title": "Email Changed",
        "email_changed_body": "Your account email has been changed to",
        "email_changed_warning": (
            "If you did not make this change, "
            "please contact support immediately."
        ),
    },
    "ru": {
        "call_completed": "Звонок завершён",
        "call_failed": "Звонок не удался",
        "call_scheduled": "Звонок запланирован",
        "call_completed_body": (
            "Ваш автоматический звонок был успешно завершён."
        ),
        "call_failed_body": (
            "Ваш автоматический звонок не удалось завершить."
        ),
        "ai_summary": "Резюме ИИ",
        "reason": "Причина",
        "view_transcript": "Просмотреть транскрипцию",
        "view_task_retry": "Просмотреть задачу",
        "phone_number": "Номер телефона",
        "scheduled_for": "Запланирован на",
        "scheduled_body": (
            "Ваш звонок запланирован и будет выполнен автоматически."
        ),
        "scheduled_followup": (
            "Вы получите ещё одно письмо, когда звонок будет завершён."
        ),
        "welcome_title": "Добро пожаловать!",
        "welcome_body": (
            "Добро пожаловать в <strong>Quiet Call AI</strong>! "
            "Ваш аккаунт готов."
        ),
        "welcome_body2": (
            "Теперь вы можете создавать задачи для автоматизации звонков. "
            "Выберите шаблон, заполните детали, и ИИ-агент проведёт разговор."
        ),
        "go_to_dashboard": "Перейти к панели",
        "reset_title": "Сброс пароля",
        "reset_body": (
            "Мы получили запрос на сброс пароля. "
            "Нажмите кнопку ниже, чтобы выбрать новый."
        ),
        "reset_button": "Сбросить пароль",
        "reset_note": (
            "Если вы не запрашивали это, просто проигнорируйте письмо. "
            "Ссылка действительна 1 час."
        ),
        "password_changed_title": "Пароль изменён",
        "password_changed_body": "Ваш пароль был успешно изменён.",
        "password_changed_warning": (
            "Если вы не делали этого, немедленно сбросьте пароль "
            "или свяжитесь с поддержкой."
        ),
        "email_changed_title": "Email изменён",
        "email_changed_body": "Email вашего аккаунта был изменён на",
        "email_changed_warning": (
            "Если вы не делали этого, "
            "немедленно свяжитесь с поддержкой."
        ),
    },
    "ro": {
        "call_completed": "Apel finalizat",
        "call_failed": "Apel eșuat",
        "call_scheduled": "Apel programat",
        "call_completed_body": (
            "Apelul tău automatizat a fost finalizat cu succes."
        ),
        "call_failed_body": (
            "Apelul tău automatizat nu a putut fi finalizat."
        ),
        "ai_summary": "Rezumat AI",
        "reason": "Motiv",
        "view_transcript": "Vezi transcrierea",
        "view_task_retry": "Vezi sarcina",
        "phone_number": "Număr de telefon",
        "scheduled_for": "Programat pentru",
        "scheduled_body": (
            "Apelul tău a fost programat și va fi executat automat."
        ),
        "scheduled_followup": (
            "Vei primi un alt email când apelul va fi finalizat."
        ),
        "welcome_title": "Bine ai venit!",
        "welcome_body": (
            "Bine ai venit la <strong>Quiet Call AI</strong>! "
            "Contul tău este gata."
        ),
        "welcome_body2": (
            "Acum poți crea sarcini pentru a automatiza apelurile telefonice. "
            "Alege un șablon, completează detaliile și lasă agentul AI "
            "să poarte conversația."
        ),
        "go_to_dashboard": "Mergi la panou",
        "reset_title": "Resetare parolă",
        "reset_body": (
            "Am primit o cerere de resetare a parolei. "
            "Apasă butonul de mai jos pentru a alege una nouă."
        ),
        "reset_button": "Resetează parola",
        "reset_note": (
            "Dacă nu ai solicitat acest lucru, poți ignora acest email. "
            "Linkul expiră în 1 oră."
        ),
        "password_changed_title": "Parola a fost schimbată",
        "password_changed_body": "Parola ta a fost schimbată cu succes.",
        "password_changed_warning": (
            "Dacă nu ai făcut această modificare, resetează-ți parola "
            "imediat sau contactează suportul."
        ),
        "email_changed_title": "Email-ul a fost schimbat",
        "email_changed_body": "Email-ul contului tău a fost schimbat la",
        "email_changed_warning": (
            "Dacă nu ai făcut această modificare, "
            "contactează suportul imediat."
        ),
    },
}


def get_translations(language: str) -> dict[str, str]:
    """Return translation dict for the given language, defaulting to English."""
    return TRANSLATIONS.get(language, TRANSLATIONS["en"])

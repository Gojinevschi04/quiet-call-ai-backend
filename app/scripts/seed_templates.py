import asyncio

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import engine
from app.modules.templates.models import DialogTemplate

EN_TEMPLATES = [
    {
        "name": "Make appointment",
        "base_script": (
            "You need to schedule an appointment. "
            "Greet, state your name and the service you need, mention your preferred date and time. "
            "If the slot is unavailable, ask for the nearest alternative. "
            "Confirm the final details (date, time, location) before ending. "
            "Thank them and say goodbye."
        ),
        "required_slots": [
            "preferred_date",
            "preferred_time",
            "service_type",
            "patient_name",
        ],
    },
    {
        "name": "Confirm reservation",
        "base_script": (
            "You need to confirm your existing reservation. "
            "Greet, give your reservation ID and name. "
            "Ask if the reservation is still active for the given date. "
            "Note any changes. Confirm final details and say goodbye."
        ),
        "required_slots": ["reservation_id", "reservation_date", "guest_name"],
    },
    {
        "name": "Request information",
        "base_script": (
            "You need to get information about a specific topic. "
            "Greet, state your name and what you need to know. "
            "Ask about hours, pricing, or available services as needed. "
            "Thank them and say goodbye."
        ),
        "required_slots": ["question_topic", "business_name"],
    },
    {
        "name": "Cancel appointment",
        "base_script": (
            "You need to cancel your appointment. "
            "Greet, state your name, the appointment date and time. "
            "If asked for a reason, explain briefly. "
            "Ask if there are cancellation fees. Confirm the cancellation and say goodbye."
        ),
        "required_slots": ["appointment_date", "appointment_time", "booked_name", "reason"],
    },
    {
        "name": "Follow-up call",
        "base_script": (
            "You are following up on a previous interaction. "
            "Greet, state your name and reference number. "
            "Ask about the current status or updates on the topic. "
            "Note what actions are needed. Thank them and say goodbye."
        ),
        "required_slots": ["reference_number", "contact_name", "follow_up_topic"],
    },
    {
        "name": "Reschedule appointment",
        "base_script": (
            "You need to reschedule your appointment. "
            "Greet, state your name, the original date and time. "
            "Ask to move it to the new preferred date and time. "
            "If unavailable, ask for the closest alternative. "
            "Confirm the new details and say goodbye."
        ),
        "required_slots": [
            "original_date",
            "original_time",
            "new_preferred_date",
            "new_preferred_time",
            "booked_name",
            "service_type",
        ],
    },
    {
        "name": "Order status check",
        "base_script": (
            "You need to check the status of your order. "
            "Greet, state your name and order number. "
            "Ask if it is processing, shipped, or delivered. "
            "If shipped, ask for estimated delivery date. "
            "Note all details and say goodbye."
        ),
        "required_slots": ["order_number", "customer_name"],
    },
    {
        "name": "File a complaint",
        "base_script": (
            "You need to report an issue. "
            "Greet, state your name and describe the problem clearly. "
            "Ask for a complaint reference number. "
            "Ask about expected resolution timeline. "
            "Confirm the complaint is registered and say goodbye."
        ),
        "required_slots": ["complaint_subject", "complaint_details", "customer_name"],
    },
    {
        "name": "Prescription refill request",
        "base_script": (
            "You need to refill your prescription. "
            "Greet, state your name and prescription number. "
            "Ask if the refill can be processed and when it will be ready. "
            "If expired, ask what steps are needed. "
            "Confirm pickup details and say goodbye."
        ),
        "required_slots": ["patient_name", "prescription_number", "pharmacy_name"],
    },
    {
        "name": "Service outage report",
        "base_script": (
            "You need to report a service outage. "
            "Greet, state your name and account number, describe the issue. "
            "Ask if there is a known outage in the area. "
            "If not, ask for a trouble ticket number and estimated restoration time. "
            "Say goodbye."
        ),
        "required_slots": ["account_number", "service_type", "issue_description", "customer_name"],
    },
    {
        "name": "Insurance claim inquiry",
        "base_script": (
            "You need to check the status of your insurance claim. "
            "Greet, state your name and claim number. "
            "Ask if the claim is pending, approved, or denied. "
            "If approved, ask about payout timeline. If not, ask what is needed. "
            "Confirm next steps and say goodbye."
        ),
        "required_slots": ["claim_number", "policyholder_name", "claim_type"],
    },
    {
        "name": "Payment reminder",
        "base_script": (
            "You are calling about a pending payment. "
            "Greet, state your company name and reference the invoice number and amount. "
            "Politely ask if the payment has been made or when it is expected. "
            "If paid, ask for the transaction reference. If not, confirm payment methods and deadline. "
            "Thank them and say goodbye."
        ),
        "required_slots": ["invoice_number", "amount_due", "due_date", "company_name"],
    },
]

RU_TEMPLATES = [
    {
        "name": "Запись на приём",
        "language": "ru",
        "base_script": (
            "Вам нужно записаться на приём. "
            "Поздоровайтесь, назовите своё имя и нужную услугу. "
            "Укажите желаемую дату и время. "
            "Если время недоступно, спросите ближайшее свободное. "
            "Подтвердите данные и попрощайтесь."
        ),
        "required_slots": ["preferred_date", "preferred_time", "service_type", "patient_name"],
    },
    {
        "name": "Подтверждение бронирования",
        "language": "ru",
        "base_script": (
            "Вам нужно подтвердить бронирование. "
            "Поздоровайтесь, назовите номер бронирования и имя. "
            "Спросите, активно ли бронирование на указанную дату. "
            "Отметьте изменения, подтвердите данные и попрощайтесь."
        ),
        "required_slots": ["reservation_id", "reservation_date", "guest_name"],
    },
    {
        "name": "Запрос информации",
        "language": "ru",
        "base_script": (
            "Вам нужно узнать информацию по определённой теме. "
            "Поздоровайтесь, назовите имя и спросите что нужно. "
            "Уточните часы работы, цены или доступные услуги. "
            "Поблагодарите и попрощайтесь."
        ),
        "required_slots": ["question_topic", "business_name"],
    },
    {
        "name": "Отмена записи",
        "language": "ru",
        "base_script": (
            "Вам нужно отменить запись. "
            "Поздоровайтесь, назовите имя, дату и время записи. "
            "Если спросят причину, кратко объясните. "
            "Спросите про штраф за отмену. Подтвердите и попрощайтесь."
        ),
        "required_slots": ["appointment_date", "appointment_time", "booked_name", "reason"],
    },
    {
        "name": "Перенос записи",
        "language": "ru",
        "base_script": (
            "Вам нужно перенести запись. "
            "Поздоровайтесь, назовите имя, исходную дату и время. "
            "Попросите перенести на новую дату и время. "
            "Если недоступно, спросите ближайшее. "
            "Подтвердите новые данные и попрощайтесь."
        ),
        "required_slots": [
            "original_date",
            "original_time",
            "new_preferred_date",
            "new_preferred_time",
            "booked_name",
            "service_type",
        ],
    },
    {
        "name": "Последующий звонок",
        "language": "ru",
        "base_script": (
            "Вы перезваниваете по предыдущему обращению. "
            "Поздоровайтесь, назовите имя и номер обращения. "
            "Спросите текущий статус или обновления. "
            "Уточните какие действия необходимы. Поблагодарите и попрощайтесь."
        ),
        "required_slots": ["reference_number", "contact_name", "follow_up_topic"],
    },
    {
        "name": "Проверка статуса заказа",
        "language": "ru",
        "base_script": (
            "Вам нужно узнать статус заказа. "
            "Поздоровайтесь, назовите имя и номер заказа. "
            "Спросите обрабатывается ли, отправлен или доставлен. "
            "Если отправлен, спросите ожидаемую дату доставки. "
            "Запишите детали и попрощайтесь."
        ),
        "required_slots": ["order_number", "customer_name"],
    },
    {
        "name": "Подача жалобы",
        "language": "ru",
        "base_script": (
            "Вам нужно сообщить о проблеме. "
            "Поздоровайтесь, назовите имя и чётко опишите ситуацию. "
            "Попросите номер обращения. "
            "Уточните сроки рассмотрения. "
            "Подтвердите что жалоба зарегистрирована и попрощайтесь."
        ),
        "required_slots": ["complaint_subject", "complaint_details", "customer_name"],
    },
    {
        "name": "Запрос повтора рецепта",
        "language": "ru",
        "base_script": (
            "Вам нужно повторить рецепт. "
            "Поздоровайтесь, назовите имя и номер рецепта. "
            "Спросите можно ли оформить повтор и когда он будет готов. "
            "Если рецепт истёк, уточните что нужно сделать. "
            "Подтвердите детали получения и попрощайтесь."
        ),
        "required_slots": ["patient_name", "prescription_number", "pharmacy_name"],
    },
    {
        "name": "Сообщение о сбое услуги",
        "language": "ru",
        "base_script": (
            "Вам нужно сообщить о сбое услуги. "
            "Поздоровайтесь, назовите имя и номер лицевого счёта, опишите проблему. "
            "Спросите есть ли известный сбой в вашем районе. "
            "Если нет, попросите номер заявки и ожидаемое время восстановления. "
            "Попрощайтесь."
        ),
        "required_slots": ["account_number", "service_type", "issue_description", "customer_name"],
    },
    {
        "name": "Запрос по страховому случаю",
        "language": "ru",
        "base_script": (
            "Вам нужно узнать статус страхового случая. "
            "Поздоровайтесь, назовите имя и номер дела. "
            "Спросите на рассмотрении ли, одобрен или отклонён. "
            "Если одобрен, уточните сроки выплаты. Если нет — что нужно предоставить. "
            "Подтвердите дальнейшие шаги и попрощайтесь."
        ),
        "required_slots": ["claim_number", "policyholder_name", "claim_type"],
    },
    {
        "name": "Напоминание о платеже",
        "language": "ru",
        "base_script": (
            "Вы звоните по поводу ожидаемого платежа. "
            "Поздоровайтесь, назовите компанию и укажите номер счёта и сумму. "
            "Вежливо спросите был ли платёж произведён или когда ожидается. "
            "Если оплачен — попросите референс транзакции. Если нет — уточните способы оплаты и крайний срок. "
            "Поблагодарите и попрощайтесь."
        ),
        "required_slots": ["invoice_number", "amount_due", "due_date", "company_name"],
    },
]

RO_TEMPLATES = [
    {
        "name": "Programare la medic",
        "language": "ro",
        "base_script": (
            "Trebuie să faci o programare. "
            "Salută, spune-ți numele și serviciul de care ai nevoie. "
            "Menționează data și ora preferată. "
            "Dacă nu e disponibil, întreabă de cea mai apropiată alternativă. "
            "Confirmă detaliile și ia-ți la revedere."
        ),
        "required_slots": ["preferred_date", "preferred_time", "service_type", "patient_name"],
    },
    {
        "name": "Confirmare rezervare",
        "language": "ro",
        "base_script": (
            "Trebuie să confirmi o rezervare. "
            "Salută, dă numărul rezervării și numele. "
            "Întreabă dacă rezervarea e activă pentru data indicată. "
            "Notează modificările, confirmă detaliile și ia-ți la revedere."
        ),
        "required_slots": ["reservation_id", "reservation_date", "guest_name"],
    },
    {
        "name": "Solicitare informații",
        "language": "ro",
        "base_script": (
            "Trebuie să afli informații despre un subiect. "
            "Salută, spune-ți numele și ce vrei să afli. "
            "Întreabă despre program, prețuri sau servicii disponibile. "
            "Mulțumește și ia-ți la revedere."
        ),
        "required_slots": ["question_topic", "business_name"],
    },
    {
        "name": "Anulare programare",
        "language": "ro",
        "base_script": (
            "Trebuie să anulezi o programare. "
            "Salută, spune-ți numele, data și ora programării. "
            "Dacă te întreabă motivul, explică pe scurt. "
            "Întreabă dacă există taxă de anulare. Confirmă anularea și ia-ți la revedere."
        ),
        "required_slots": ["appointment_date", "appointment_time", "booked_name", "reason"],
    },
    {
        "name": "Reprogramare programare",
        "language": "ro",
        "base_script": (
            "Trebuie să reprogramezi o programare. "
            "Salută, spune-ți numele, data și ora inițială. "
            "Cere reprogramarea pentru noua dată și oră preferată. "
            "Dacă nu e disponibil, întreabă cea mai apropiată alternativă. "
            "Confirmă noile detalii și ia-ți la revedere."
        ),
        "required_slots": [
            "original_date",
            "original_time",
            "new_preferred_date",
            "new_preferred_time",
            "booked_name",
            "service_type",
        ],
    },
    {
        "name": "Apel de revenire",
        "language": "ro",
        "base_script": (
            "Revii asupra unei interacțiuni anterioare. "
            "Salută, spune-ți numele și numărul de referință. "
            "Întreabă de statusul curent sau de noutăți pe subiect. "
            "Notează ce acțiuni sunt necesare. Mulțumește și ia-ți la revedere."
        ),
        "required_slots": ["reference_number", "contact_name", "follow_up_topic"],
    },
    {
        "name": "Verificare status comandă",
        "language": "ro",
        "base_script": (
            "Trebuie să afli statusul comenzii. "
            "Salută, spune-ți numele și numărul comenzii. "
            "Întreabă dacă e în procesare, expediată sau livrată. "
            "Dacă e expediată, cere data estimativă de livrare. "
            "Notează detaliile și ia-ți la revedere."
        ),
        "required_slots": ["order_number", "customer_name"],
    },
    {
        "name": "Depunere plângere",
        "language": "ro",
        "base_script": (
            "Trebuie să raportezi o problemă. "
            "Salută, spune-ți numele și descrie clar situația. "
            "Cere un număr de referință pentru plângere. "
            "Întreabă despre termenul estimat de soluționare. "
            "Confirmă că plângerea e înregistrată și ia-ți la revedere."
        ),
        "required_slots": ["complaint_subject", "complaint_details", "customer_name"],
    },
    {
        "name": "Cerere rețetă",
        "language": "ro",
        "base_script": (
            "Trebuie să reînnoiești o rețetă. "
            "Salută, spune-ți numele și numărul rețetei. "
            "Întreabă dacă poate fi procesată reînnoirea și când va fi gata. "
            "Dacă rețeta a expirat, întreabă ce pași sunt necesari. "
            "Confirmă detaliile de ridicare și ia-ți la revedere."
        ),
        "required_slots": ["patient_name", "prescription_number", "pharmacy_name"],
    },
    {
        "name": "Raportare întrerupere serviciu",
        "language": "ro",
        "base_script": (
            "Trebuie să raportezi o întrerupere a serviciului. "
            "Salută, spune-ți numele și numărul de client, descrie problema. "
            "Întreabă dacă există o întrerupere cunoscută în zonă. "
            "Dacă nu, cere un număr de sesizare și timpul estimat de restaurare. "
            "Ia-ți la revedere."
        ),
        "required_slots": ["account_number", "service_type", "issue_description", "customer_name"],
    },
    {
        "name": "Întrebare dosar asigurare",
        "language": "ro",
        "base_script": (
            "Trebuie să afli statusul unui dosar de asigurare. "
            "Salută, spune-ți numele și numărul dosarului. "
            "Întreabă dacă e în evaluare, aprobat sau respins. "
            "Dacă e aprobat, întreabă termenul plății. Dacă nu, ce e necesar suplimentar. "
            "Confirmă pașii următori și ia-ți la revedere."
        ),
        "required_slots": ["claim_number", "policyholder_name", "claim_type"],
    },
    {
        "name": "Reamintire plată",
        "language": "ro",
        "base_script": (
            "Suni pentru o plată în așteptare. "
            "Salută, spune numele firmei și fă referire la numărul facturii și suma. "
            "Întreabă politicos dacă plata a fost efectuată sau când e așteptată. "
            "Dacă e plătită, cere referința tranzacției. Dacă nu, confirmă metodele de plată și termenul. "
            "Mulțumește și ia-ți la revedere."
        ),
        "required_slots": ["invoice_number", "amount_due", "due_date", "company_name"],
    },
]

TEMPLATES = EN_TEMPLATES + RU_TEMPLATES + RO_TEMPLATES


async def seed() -> None:
    async with AsyncSession(engine) as session:
        for template_data in TEMPLATES:
            result = await session.exec(select(DialogTemplate).where(DialogTemplate.name == template_data["name"]))
            existing = result.first()
            if existing:
                existing.base_script = template_data["base_script"]
                existing.required_slots = template_data.get("required_slots", existing.required_slots)
                await session.commit()
                await session.refresh(existing)
                print(f"  UPDATED: '{template_data['name']}' (id={existing.id})")
                continue

            template = DialogTemplate(**template_data)
            session.add(template)
            await session.commit()
            await session.refresh(template)
            print(f"  CREATED: '{template.name}' (id={template.id})")

    print("\nSeed completed.")


def main() -> None:
    print("Seeding dialog templates...")
    asyncio.run(seed())


if __name__ == "__main__":
    main()

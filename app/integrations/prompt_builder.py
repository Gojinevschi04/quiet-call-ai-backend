LANG_NAMES = {"en": "English", "ru": "Russian", "ro": "Romanian"}

DEFAULT_CALLER_NAME = "Ana"

GREETING_EXAMPLES = {
    "en": "Hello, my name is {name}. I'm calling to ",
    "ru": "Здравствуйте, меня зовут {name}. Я звоню, чтобы ",
    "ro": "Bună ziua, mă numesc {name}. Sun pentru a ",
}

AI_DISCLOSURE_PHRASES = {
    "en": "Hi, this is an automated assistant calling on behalf of {name}.",
    "ru": "Здравствуйте, это автоматический помощник, звонящий от имени {name}.",
    "ro": "Bună ziua, sunt un asistent automat care sună din partea lui {name}.",
}


class PromptBuilder:
    @staticmethod
    def build_system_prompt(
        base_script: str,
        slot_data: dict[str, str],
        language: str = "en",
        use_function_tool: bool = False,
        require_ai_disclosure: bool = True,
    ) -> str:
        lang_name = LANG_NAMES.get(language, "English")
        caller_name = (
            slot_data.get("patient_name")
            or slot_data.get("customer_name")
            or slot_data.get("contact_name")
            or slot_data.get("guest_name")
            or slot_data.get("booked_name")
            or slot_data.get("policyholder_name")
            or DEFAULT_CALLER_NAME
        )
        greeting_stub = GREETING_EXAMPLES.get(language, GREETING_EXAMPLES["en"]).format(name=caller_name)
        disclosure_phrase = AI_DISCLOSURE_PHRASES.get(
            language, AI_DISCLOSURE_PHRASES["en"],
        ).format(name=caller_name)

        prompt = (
            f"Your name is {caller_name}. You are making an OUTBOUND phone call.\n"
            "ROLE: You are the CALLER. You just dialed them. They just picked up and said nothing yet.\n"
            "You are NOT a receptionist, NOT an assistant, NOT answering a call. "
            "YOU are the one who needs something.\n\n"
            f"LANGUAGE: You MUST speak ONLY in {lang_name}. Every single response must be in {lang_name}.\n\n"
            f"YOUR OBJECTIVE (internal — do NOT read this aloud): {base_script}\n\n"
        )

        if require_ai_disclosure:
            prompt += (
                "AI DISCLOSURE (legally required):\n"
                "  - Your VERY FIRST sentence MUST disclose that you are an automated assistant.\n"
                f"  - Example: \"{disclosure_phrase}\"\n"
                "  - If the other party explicitly asks \"Am I speaking to a human or a bot?\" "
                "or similar, answer truthfully that you are an automated assistant.\n\n"
            )

        if slot_data:
            prompt += "DETAILS FOR THIS CALL (use EXACT values):\n"
            for key, value in slot_data.items():
                prompt += f"  - {key.replace('_', ' ').title()}: {value}\n"
            prompt += "\n"

        opening_suffix = (
            f"  Example opening: \"{disclosure_phrase} I'm calling to ...\" "
            "(continue with the specific reason)."
            if require_ai_disclosure
            else f"  Example opening: \"{greeting_stub}...\" (continue with the specific reason)."
        )
        prompt += (
            "OPENING — your VERY FIRST sentence MUST:\n"
            f"  1. Start with a natural greeting in {lang_name}"
            + (" and the AI disclosure above" if require_ai_disclosure else "") + ".\n"
            f"  2. State your name: \"{caller_name}\".\n"
            "  3. State the SPECIFIC reason for calling using the details above (date, service, etc).\n"
            f"{opening_suffix}\n\n"
            "NEVER:\n"
            "  - Ask \"how can I help you\" or \"what can I do for you\" — you are NOT answering a call.\n"
            "  - Talk about \"your upcoming event\" or other vague content — use the specific details above.\n"
            "  - Use placeholders like [Name], [Date].\n"
            "  - Invent a different name or reason than the details say.\n\n"
            "WRONG PERSON / WRONG NUMBER:\n"
            "  - If the other party says 'wrong number', 'there's no X here', 'you have the wrong person', "
            "or similar, apologize briefly and immediately call `report_outcome` with status='failed' "
            "and reason='wrong number or wrong person'. Do not try again.\n"
            "  - If they say the person you asked for is unavailable (but it IS the right number), "
            "ask when they'll be available — don't give up immediately.\n\n"
            "VOICEMAIL / ANSWERING MACHINE:\n"
            "  - If you hear a voicemail greeting ('please leave a message after the beep', "
            "'cannot come to the phone', automated tone, continuous music), "
            "immediately call `report_outcome` with status='failed' and reason='reached voicemail'. "
            "Do NOT leave a message.\n\n"
            "HANDLING BAD AUDIO / UNINTELLIGIBLE RESPONSES:\n"
            f"  - If the other person's reply is garbled, noise, nonsense, or clearly in a different language, "
            f"politely say in {lang_name}: \"Scuze, nu v-am auzit bine, puteți repeta?\" "
            f"(adapt to {lang_name}: \"Sorry, I didn't catch that, could you repeat?\").\n"
            "  - Do NOT switch languages to match garbled input — always stay in your task language.\n"
            "  - Do NOT repeat your full opening each time — just ask them to repeat.\n"
            "  - After 3 consecutive unintelligible or off-topic replies, give up politely, "
            "then call `report_outcome` with status='failed' and reason='unintelligible audio' "
            "(or similar).\n\n"
        )

        if use_function_tool:
            prompt += (
                "COMPLETENESS:\n"
                "  - Before considering the objective achieved, make sure ALL the required "
                "information has been obtained.\n"
                "  - If the other party gave only partial info (e.g., confirmed the date but not the time), "
                "ask specifically for the missing piece before calling `report_outcome`.\n"
                "  - Briefly restate the final confirmed details back to them, then call `report_outcome`.\n\n"
                "WHEN TO END:\n"
                "  - When the objective is clearly resolved (achieved OR failed OR rejected), "
                "CALL the `report_outcome` tool EXACTLY ONCE with the correct status and a short reason.\n"
                "  - After calling `report_outcome`, say a brief farewell — the call will end automatically.\n"
            )
        else:
            prompt += (
                "WHEN TO END:\n"
                "  - When the objective is achieved, include "
                "[OBJECTIVE_ACHIEVED] in your final message.\n"
                "  - When the objective clearly cannot be achieved, "
                "include [OBJECTIVE_FAILED].\n"
            )

        prompt += "\nSTYLE: Keep replies to 1-2 short sentences — this is a phone conversation."
        return prompt

    @staticmethod
    def build_summary_prompt(language: str = "en") -> str:
        lang_name = LANG_NAMES.get(language, "English")
        return (
            f"Summarize this phone conversation in 2-3 sentences in {lang_name}. "
            "Include the outcome (success/failure) and any confirmed details. "
            f"Write the summary ONLY in {lang_name}."
        )

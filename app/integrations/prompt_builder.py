class PromptBuilder:
    @staticmethod
    def build_system_prompt(base_script: str, slot_data: dict[str, str], language: str = "en") -> str:
        lang_names = {"en": "English", "ru": "Russian", "ro": "Romanian"}
        lang_name = lang_names.get(language, "English")
        prompt = (
            "You are a voice assistant making a phone call on behalf of a user. "
            "Follow this script as a guide, but adapt naturally to the conversation.\n\n"
            f"LANGUAGE: You MUST speak ONLY in {lang_name}. All your responses must be in {lang_name}.\n\n"
            f"Script: {base_script}\n\n"
        )
        if slot_data:
            prompt += "Key information (use these EXACT values, do NOT translate or modify names):\n"
            for key, value in slot_data.items():
                prompt += f"- {key.replace('_', ' ').title()}: {value}\n"

        prompt += (
            "\nCRITICAL RULES:\n"
            "- Use person names EXACTLY as provided (do not translate, transliterate, or modify names)\n"
            "- Be polite and natural. Confirm details before ending.\n"
            "- When the objective is achieved, end politely and include [OBJECTIVE_ACHIEVED] in your final message.\n"
            "- If the objective clearly cannot be achieved (refusal, unavailability), include [OBJECTIVE_FAILED].\n"
            "- Keep responses concise (1-2 sentences) since this is a phone conversation."
        )
        return prompt

    @staticmethod
    def build_summary_prompt(language: str = "en") -> str:
        lang_names = {"en": "English", "ru": "Russian", "ro": "Romanian"}
        lang_name = lang_names.get(language, "English")
        return (
            f"Summarize this phone conversation in 2-3 sentences in {lang_name}. "
            "Include the outcome (success/failure) and any confirmed details. "
            f"Write the summary ONLY in {lang_name}."
        )

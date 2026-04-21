from app.integrations.prompt_builder import PromptBuilder


def test_build_system_prompt_with_subject_name() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Book an appointment.",
        slot_data={"patient_name": "Ion Popescu", "preferred_date": "2026-05-01"},
        language="en",
        use_function_tool=False,
    )
    assert "on behalf of Ion Popescu" in prompt
    assert "ENGLISH" in prompt.upper()
    assert "[OBJECTIVE_ACHIEVED]" in prompt
    assert "CALL the `report_outcome` tool" not in prompt


def test_build_system_prompt_falls_back_when_no_subject_name() -> None:
    """Regression: when no *_name slot is present, use a neutral disclosure rather
    than impersonating some default identity."""
    prompt = PromptBuilder.build_system_prompt(
        base_script="Request information.",
        slot_data={"question_topic": "working hours"},
        language="en",
    )
    assert "on behalf of" not in prompt or "on behalf of {subject}" not in prompt
    assert "automated assistant" in prompt


def test_build_system_prompt_with_function_tool_mode() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Confirm reservation.",
        slot_data={"guest_name": "Alex"},
        language="en",
        use_function_tool=True,
    )
    assert "report_outcome" in prompt
    assert "[OBJECTIVE_ACHIEVED]" not in prompt
    assert "WRONG PERSON" in prompt
    assert "VOICEMAIL" in prompt
    assert "COMPLETENESS" in prompt


def test_build_system_prompt_language_directive_romanian() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Programează o consultație.",
        slot_data={"patient_name": "Maria"},
        language="ro",
    )
    assert "Romanian" in prompt
    assert "Bună ziua" in prompt


def test_build_system_prompt_language_directive_russian() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Подтвердите бронирование.",
        slot_data={"guest_name": "Дмитрий"},
        language="ru",
    )
    assert "Russian" in prompt
    assert "Здравствуйте" in prompt


def test_build_system_prompt_includes_all_slot_data() -> None:
    slots = {
        "preferred_date": "2026-05-10",
        "preferred_time": "14:00",
        "service_type": "dental cleaning",
    }
    prompt = PromptBuilder.build_system_prompt(
        base_script="Book dental appointment.",
        slot_data=slots,
        language="en",
    )
    for value in slots.values():
        assert value in prompt


def test_build_system_prompt_subject_name_priority() -> None:
    slots = {
        "patient_name": "First",
        "customer_name": "Second",
        "contact_name": "Third",
    }
    prompt = PromptBuilder.build_system_prompt(
        base_script="Call.",
        slot_data=slots,
        language="en",
    )
    assert "on behalf of First" in prompt
    assert "on behalf of Second" not in prompt


def test_build_system_prompt_does_not_impersonate_subject() -> None:
    """Regression: AI must not say 'my name is <subject>' — it's an assistant, not the subject."""
    prompt = PromptBuilder.build_system_prompt(
        base_script="Book appointment.",
        slot_data={"patient_name": "Ion Popescu"},
        language="en",
    )
    assert "my name is Ion Popescu" not in prompt.lower()
    assert "your name is ion popescu" not in prompt.lower()
    assert "NOT the person" in prompt
    assert "impersonate" in prompt


def test_build_system_prompt_includes_commitment_guardrail() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Confirm reservation.",
        slot_data={"guest_name": "Alex"},
        language="en",
    )
    assert "COMMITMENT GUARDRAIL" in prompt
    assert "payment" in prompt.lower()
    assert "sensitive personal info" in prompt.lower()


def test_build_system_prompt_includes_mid_call_questions() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Confirm reservation.",
        slot_data={"guest_name": "Alex"},
        language="en",
        use_function_tool=True,
    )
    assert "MID-CALL QUESTIONS" in prompt
    assert "Who is calling" in prompt
    assert "call back later" in prompt.lower()
    assert "Remove me" in prompt
    assert "Put me through to a human" in prompt


def test_build_summary_prompt_for_each_language() -> None:
    for language_code, language_name in (("en", "English"), ("ru", "Russian"), ("ro", "Romanian")):
        summary_prompt = PromptBuilder.build_summary_prompt(language_code)
        assert language_name in summary_prompt
        assert "2-3 sentences" in summary_prompt


def test_build_summary_prompt_unknown_language_defaults_to_english() -> None:
    summary_prompt = PromptBuilder.build_summary_prompt("de")
    assert "English" in summary_prompt


def test_build_system_prompt_includes_ai_disclosure_when_required() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Book an appointment.",
        slot_data={"patient_name": "Eva"},
        language="en",
        require_ai_disclosure=True,
    )
    assert "AI DISCLOSURE" in prompt
    assert "automated assistant" in prompt
    assert "Eva" in prompt


def test_build_system_prompt_skips_ai_disclosure_when_disabled() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Book an appointment.",
        slot_data={"patient_name": "Eva"},
        language="en",
        require_ai_disclosure=False,
    )
    assert "AI DISCLOSURE" not in prompt


def test_build_system_prompt_includes_prior_attempt_context_when_provided() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Book an appointment.",
        slot_data={"patient_name": "Eva"},
        language="en",
        prior_attempt_context="Agent: Hello.\nInterlocutor: Hold on, I need to find my diary.",
    )
    assert "PREVIOUS ATTEMPT TRANSCRIPT" in prompt
    assert "find my diary" in prompt
    assert "do NOT repeat the full introduction" in prompt


def test_build_system_prompt_omits_prior_context_when_none() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Book an appointment.",
        slot_data={"patient_name": "Eva"},
        language="en",
    )
    assert "PREVIOUS ATTEMPT TRANSCRIPT" not in prompt


def test_build_system_prompt_disclosure_adapts_to_language() -> None:
    prompt_ro = PromptBuilder.build_system_prompt(
        base_script="Fă o programare.",
        slot_data={"patient_name": "Eva"},
        language="ro",
        require_ai_disclosure=True,
    )
    assert "asistent automat" in prompt_ro

    prompt_ru = PromptBuilder.build_system_prompt(
        base_script="Запишитесь на приём.",
        slot_data={"patient_name": "Eva"},
        language="ru",
        require_ai_disclosure=True,
    )
    assert "автоматический помощник" in prompt_ru


def test_prompt_does_not_attach_a_company_name_to_the_assistant() -> None:
    """Regression: AI must not call itself any company/brand name — just 'automated assistant'."""
    prompt = PromptBuilder.build_system_prompt(
        base_script="Confirm.",
        slot_data={"patient_name": "Eva"},
        language="en",
    )
    assert "Quiet Call AI" not in prompt
    assert "automated assistant" in prompt
    assert "on behalf of Eva" in prompt


def test_prompt_disclosure_mentions_only_subject_for_on_behalf() -> None:
    """Regression: 'on behalf of' must reference the slot_data subject, no other name."""
    prompt = PromptBuilder.build_system_prompt(
        base_script="Confirm.",
        slot_data={"patient_name": "Ion Popescu", "preferred_date": "2026-05-01"},
        language="en",
    )
    assert "on behalf of Ion Popescu" in prompt
    assert "on behalf of Quiet Call AI" not in prompt


def test_prompt_uses_assistant_name_when_set() -> None:
    """Regression: assistant_name from user profile threads into the disclosure."""
    prompt = PromptBuilder.build_system_prompt(
        base_script="Confirm reservation.",
        slot_data={"guest_name": "Eva"},
        language="en",
        assistant_name="Ana",
    )
    assert "Hi, this is Ana, an automated assistant calling on behalf of Eva." in prompt


def test_prompt_uses_assistant_name_in_romanian() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Confirmă rezervarea.",
        slot_data={"guest_name": "Eva Popescu"},
        language="ro",
        assistant_name="Maria",
    )
    assert "Bună ziua, sunt Maria, un asistent automat care sună din partea lui Eva Popescu." in prompt


def test_prompt_falls_back_to_neutral_when_assistant_name_is_none() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Confirm.",
        slot_data={"guest_name": "Eva"},
        language="en",
        assistant_name=None,
    )
    assert "Hi, this is an automated assistant calling on behalf of Eva." in prompt
    assert "Hi, this is None," not in prompt


def test_prompt_named_without_subject_uses_short_intro() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Ask about opening hours.",
        slot_data={"business_name": "Pharmacy"},
        language="en",
        assistant_name="Ana",
    )
    assert "Hi, this is Ana, an automated assistant." in prompt


def test_assistant_name_appears_in_identity_question_guidance() -> None:
    """If asked their name mid-call, the AI should identify with the configured name."""
    prompt = PromptBuilder.build_system_prompt(
        base_script="Confirm.",
        slot_data={"guest_name": "Eva"},
        language="en",
        assistant_name="Ana",
    )
    assert "I'm Ana, an automated assistant" in prompt

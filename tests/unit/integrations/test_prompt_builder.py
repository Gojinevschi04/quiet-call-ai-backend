from app.integrations.prompt_builder import DEFAULT_CALLER_NAME, PromptBuilder


def test_build_system_prompt_with_caller_name() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Book an appointment.",
        slot_data={"patient_name": "Ion Popescu", "preferred_date": "2026-05-01"},
        language="en",
        use_function_tool=False,
    )
    assert "Your name is Ion Popescu" in prompt
    assert "ENGLISH" in prompt.upper()
    assert "[OBJECTIVE_ACHIEVED]" in prompt
    assert "CALL the `report_outcome` tool" not in prompt


def test_build_system_prompt_uses_default_name_when_missing() -> None:
    prompt = PromptBuilder.build_system_prompt(
        base_script="Request information.",
        slot_data={"question_topic": "working hours"},
        language="en",
    )
    assert f"Your name is {DEFAULT_CALLER_NAME}" in prompt


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


def test_build_system_prompt_caller_name_priority() -> None:
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
    assert "Your name is First" in prompt


def test_build_summary_prompt_for_each_language() -> None:
    for language_code, language_name in (("en", "English"), ("ru", "Russian"), ("ro", "Romanian")):
        summary_prompt = PromptBuilder.build_summary_prompt(language_code)
        assert language_name in summary_prompt
        assert "2-3 sentences" in summary_prompt


def test_build_summary_prompt_unknown_language_defaults_to_english() -> None:
    summary_prompt = PromptBuilder.build_summary_prompt("de")
    assert "English" in summary_prompt

from lobster_assistant.voice.server import _extract_whatsapp_text_messages


def test_extract_whatsapp_text_messages() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "15551234567", "text": {"body": "hi"}}
                            ]
                        }
                    }
                ]
            }
        ]
    }

    assert _extract_whatsapp_text_messages(payload) == [
        {"from": "15551234567", "text": "hi"}
    ]

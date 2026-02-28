from bot.telegram.states import CharacterFSM, GreetingFSM, PaymentFSM


def test_fsm_states_exist() -> None:
    assert GreetingFSM.waiting_text_choice.state.endswith(":waiting_text_choice")
    assert CharacterFSM.confirming_order.state.endswith(":confirming_order")
    assert PaymentFSM.waiting_payment.state.endswith(":waiting_payment")

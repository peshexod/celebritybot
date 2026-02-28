from aiogram.fsm.state import State, StatesGroup


class GreetingFSM(StatesGroup):
    waiting_text_choice = State()
    waiting_own_text = State()
    waiting_recipient_name = State()
    waiting_occasion = State()
    waiting_details = State()
    waiting_text_approval = State()


class CharacterFSM(StatesGroup):
    browsing_characters = State()
    browsing_creatives = State()
    confirming_order = State()


class PaymentFSM(StatesGroup):
    waiting_payment = State()

from aiogram.fsm.state import State, StatesGroup


class ExpenseForm(StatesGroup):
    amount = State()
    date = State()
    category = State()
    description = State()
    recurring = State()


class ExtraIncomeForm(StatesGroup):
    amount = State()
    date = State()
    description = State()


class TransportTripForm(StatesGroup):
    amount = State()
    date = State()
    description = State()


class SettingsForm(StatesGroup):
    value = State()


class MonthOverrideForm(StatesGroup):
    value = State()


class QuickCustomForm(StatesGroup):
    amount = State()

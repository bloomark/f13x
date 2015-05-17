from flask.ext.wtf import Form
from wtforms import StringField, BooleanField, TextAreaField, HiddenField, SelectField, IntegerField, FloatField, RadioField
from wtforms.validators import DataRequired, Length, Email
from wtforms.validators import DataRequired, NumberRange

action_dict       = [('0', 'Buy'),     ('1', 'Sell')]
currency_dict     = [('0', 'Bitcoin'), ('1', 'Dogecoin')]
order_type_dict   = [('0', 'At Market'),  ('1', 'For Price')]
order_expiry_dict = [('0', 'Good Until Canceled'), ('1', 'Fill or Kill'), ('2', 'Day Only')]
chart_dict        = [('0', 'Order Book'), ('1', 'Candle Stick'), ('2', 'Price History')]
empty_choice      = []

def get_action_id(action):
    return get_select_field_key_from_value(action, action_dict)

def get_currency_id(currency):
    return get_select_field_key_from_value(currency, currency_dict)

def get_order_type_id(order_type):
    return get_select_field_key_from_value(order_type, order_type_dict)

def get_expiry_id(expiry):
    if expiry > 2:
        return 2
    return get_select_field_key_from_value(expiry, order_expiry_dict)

def get_select_field_key_from_value(value, select_field_dict):
    value = str(value)
    for select_field in select_field_dict:
        if select_field[1] == value:
            return select_field[0]

class ProfileForm(Form):
    name       = StringField('name', validators=[DataRequired()])

class TransactionForm(Form):
    action     = SelectField('action',    choices=action_dict, default='1')
    currency   = SelectField('currency',  choices=currency_dict[1:], default='1')
    quantity   = FloatField('quantity',   validators= [NumberRange(min=0, max=2147483647)])
    order_type = RadioField('order_type', choices=order_type_dict, default='1')
    expiry     = SelectField('expiry',    choices=order_expiry_dict, default='0')
    rate       = FloatField('rate',       validators = [NumberRange(min=0, max=2147483647)], default=0.0)

class ModifyTransactionForm(Form):
    order_id   = HiddenField('order_id')
    action     = SelectField('action',    choices=action_dict, default='1')
    currency   = SelectField('currency',  choices=currency_dict[1:], default='1')
    quantity   = FloatField('quantity',   validators= [NumberRange(min=0, max=2147483647)])
    order_type = RadioField('order_type', choices=order_type_dict)
    expiry     = SelectField('expiry',    choices=order_expiry_dict)
    rate       = FloatField('rate',       validators = [NumberRange(min=0, max=2147483647)], default=0.0)

class AddFundsForm(Form):
    funds    = FloatField('funds',     default=0, validators = [NumberRange(min=0, max=2147483647)])
    Bitcoin  = FloatField('Bitcoin',   default=0, validators = [NumberRange(min=0, max=2147483647)])
    Dogecoin = FloatField('Dogecoin',  default=0, validators = [NumberRange(min=0, max=2147483647)])

class ChartsForm(Form):
    currency     = SelectField('currency',    choices=currency_dict[1:], default='0')
    chart_type   = SelectField('chart_type',  choices=chart_dict,    default='0')

class SendBitcoinForm(Form):
    address = StringField('name', validators=[DataRequired()])
    amount  = FloatField('amount', validators = [NumberRange(min=0.00000001, max=2147483647)])

class AdminUserManageForm(Form):
    email            = StringField('email', validators=[DataRequired()])
    name             = StringField('name', validators=[DataRequired()])
    funds            = FloatField('funds', default=0, validators = [NumberRange(min=0, max=2147483647)])
    Bitcoin          = FloatField('Bitcoin', default=0, validators = [NumberRange(min=0, max=2147483647)])
    Dogecoin         = FloatField('Dogecoin', default=0, validators = [NumberRange(min=0, max=2147483647)])
    bitcoin_address  = StringField('bitcoin_address')
    dogecoin_address = StringField('dogecoin_address')

class AdminUserForm(Form):
    email = SelectField('email', choices=empty_choice)

class SendDogecoinForm(Form):
    address = StringField('name', validators=[DataRequired()])
    amount  = FloatField('amount', validators = [NumberRange(min=0.00000001, max=2147483647)])    
# -*- coding: utf-8 -*-

from odoo import api, fields, models, _,exceptions
from datetime import timedelta
from datetime import datetime
from dateutil.relativedelta import relativedelta


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    under_collection = fields.Many2one('account.account', string="Checks Under Collection")



# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrRecruitmentStage(models.Model):
    _inherit = 'hr.recruitment.stage'

    contract_proposal = fields.Boolean(string='Contract Proposal')

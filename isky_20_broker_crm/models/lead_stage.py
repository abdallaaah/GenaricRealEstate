from odoo import fields, models


class LeadStage(models.Model):
    """Pre-qualification pipeline, separate from the deal pipeline (crm.stage).

    New -> No Answer / Call Later / Follow Up -> Qualified (or Qualified,
    Limited Budget) / Unqualified, with a Locked state reachable from any of
    them.
    """
    _name = 'lead.stage'
    _description = "Lead Pre-Qualification Stage"
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    first = fields.Boolean(string="Is New Stage")
    no_answer = fields.Boolean(string="Is No Answer Stage")
    call_later = fields.Boolean(string="Is Call Later Stage")
    follow_up = fields.Boolean(string="Is Follow Up Stage")
    qualified = fields.Boolean(string="Is Qualified Stage")
    qualified_limited_budget = fields.Boolean(string="Is Qualified (Limited Budget) Stage")
    unqualified = fields.Boolean(string="Is Unqualified Stage")
    locked = fields.Boolean(string="Is Locked Stage")

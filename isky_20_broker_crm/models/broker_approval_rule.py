from odoo import fields, models


class BrokerApprovalRule(models.Model):
    """Which group must approve a given deal phase x approver role.

    Replaces the v17 system's 12 hardcoded `self.env.user.has_group(
    'isky_18_realestate_broker.<group>')` checks (one Python method per
    phase x role combination, the same code seven times with a different
    external id) with one configurable row per combination, editable by a
    broker administrator so a different client can rewire the approval
    chain without a code change.
    """
    _name = 'broker.approval.rule'
    _description = "Broker Approval Rule"
    _rec_name = 'group_id'

    phase = fields.Selection([
        ('eoi', "EOI"),
        ('reservation', "Reservation"),
        ('contract', "Contract"),
    ], required=True)
    role = fields.Selection([
        ('manager', "Manager"),
        ('financial', "Financial"),
        ('sales', "Sales"),
        ('operations', "Operations"),
    ], required=True)
    group_id = fields.Many2one('res.groups', required=True)

    _unique_phase_role = models.UniqueIndex('(phase, role)')

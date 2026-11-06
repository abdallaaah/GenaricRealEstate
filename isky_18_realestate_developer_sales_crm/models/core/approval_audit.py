from odoo import fields, models


class ApprovalAudit(models.Model):
    """S7 decision 3: every approver-group change is audited, and every approval records who
    approved, when, and which group they matched on.

    One model with `entry_type` rather than two: the two kinds share every column that matters
    (company, stage, user, timestamp) and a single chronological trail per company is what an
    auditor actually wants to read.
    """
    _name = 'realestate.approval.audit'
    _description = 'Approval Settings and Approval Audit Trail'
    _order = 'create_date desc, id desc'
    _rec_name = 'stage'

    entry_type = fields.Selection([
        ('config', 'Configuration Change'),
        ('approval', 'Approval'),
    ], string='Entry Type', required=True, index=True)

    company_id = fields.Many2one('res.company', string='Company', required=True, index=True)
    stage = fields.Char(string='Approval Stage', index=True)

    # configuration changes
    field_name = fields.Char(string='Setting')
    old_value = fields.Char(string='Old Value')
    new_value = fields.Char(string='New Value')

    # approvals
    approver_id = fields.Many2one('res.users', string='Approver')
    matched_group_id = fields.Many2one(
        'res.groups', string='Matched Group',
        help="The approver group the user satisfied at the moment of approval. Recorded because "
             "the configuration can change afterwards - decision 1 makes group changes "
             "retroactive, so the group that authorised a past approval is only knowable from "
             "this row.")
    res_model = fields.Char(string='Document Model')
    res_id = fields.Integer(string='Document ID')

    # create_date / create_uid carry the "when" and "who changed it"

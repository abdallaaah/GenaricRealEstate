from odoo import models, fields,api

class ResPartnerInherit(models.Model):

    _inherit = 'res.partner'

    reconciliation_percentage = fields.Float(
        string='Reconciliation Percentage',
        help='Default percentage to apply when reconciling payments for this partner'
    )

    reconciliation_line_ids = fields.One2many(
        'res.partner.reconciliation.line',
        'partner_id',
        string='Reconciliation Lines'
    )

    def get_reconciliation_percentage(self, building_id):
        """Get reconciliation percentage for a specific building"""
        self.ensure_one()
        if building_id:
            line = self.reconciliation_line_ids.filtered(
                lambda l: l.building_id.id == building_id
            )
            if line:
                return line[0].reconciliation_percentage
        # Return default percentage if no building-specific percentage found
        return self.reconciliation_percentage


class ResPartnerReconciliationLine(models.Model):
    _name = 'res.partner.reconciliation.line'
    _description = 'Partner Reconciliation Line'

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        ondelete='cascade'
    )
    building_id = fields.Many2one(
        'real.estate.building',
        string='Building',
        required=True
    )
    reconciliation_percentage = fields.Float(
        string='Reconciliation Percentage',
        required=True,
        help='Percentage to apply when reconciling payments for this partner and building'
    )

    _sql_constraints = [
        ('unique_partner_building',
         'UNIQUE(partner_id, building_id)',
         'A partner can only have one reconciliation percentage per building!')
    ]

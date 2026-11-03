from odoo import models, fields, api


class PersonCommission(models.Model):
    """Commission model for Opportunity, EOI, Reservation, and Sale Proposal"""
    _name = "realestate.commission"
    _description = "Realestate Commission Line"

    opportunity_id = fields.Many2one('crm.lead', string='Opportunity', ondelete='cascade')
    eoi_id = fields.Many2one('eoi.eoi', string='EOI', ondelete='cascade')
    sale_reservation_id = fields.Many2one('real.estate.sale.reservation', string='Reservation', ondelete='cascade')
    sale_proposal_id = fields.Many2one('sale.proposal', string='Sale Proposal', ondelete='cascade')

    employee_id = fields.Many2one('res.users', string='Employee', required=True)
    jop_position = fields.Char(string='Job Position')
    commission = fields.Float(string='Commission %', default=100)

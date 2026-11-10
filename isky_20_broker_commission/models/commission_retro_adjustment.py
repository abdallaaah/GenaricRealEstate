from odoo import api, fields, models


class CommissionRetroAdjustment(models.Model):
    """One retroactive correction to an already-booked commission.

    Cliff segmentation means a later deal can lift the rate that applies to the whole
    period, so commission already booked on earlier deals has to be topped up (or, on
    a cancellation, clawed back).

    The previous generation of this engine wrote that correction straight into a
    ``retro_active`` float on the achievement, overwriting whatever was there. The
    amount was then unexplainable: you could not tell which deal caused it, what rate
    it moved from, or how many times it had been revised. Here each correction is a
    row, and ``realestate.commission.achievement.retro_active`` is their sum.

    ``difference`` is incremental -- measured against the achievement's current
    effective total, not its original amount -- so successive corrections sum to
    exactly "amount at the current segment minus amount as first booked".
    """
    _name = 'commission.retro.adjustment'
    _description = "Commission Retroactive Adjustment"
    _order = 'date desc, id desc'

    achievement_id = fields.Many2one(
        'realestate.commission.achievement', required=True, ondelete='cascade', index=True)
    trigger_opportunity_id = fields.Many2one(
        'crm.lead', ondelete='set null',
        help="The deal whose confirmation or cancellation moved the rate.")
    old_segment_id = fields.Many2one('commission.segment', ondelete='set null')
    new_segment_id = fields.Many2one('commission.segment', ondelete='set null')
    old_amount = fields.Monetary(
        currency_field='currency_id', help="Effective commission before this correction.")
    new_amount = fields.Monetary(
        currency_field='currency_id', help="Effective commission after this correction.")
    difference = fields.Monetary(
        compute='_compute_difference', store=True, currency_field='currency_id')
    date = fields.Date(default=fields.Date.context_today, required=True)
    currency_id = fields.Many2one(related='achievement_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(related='achievement_id.company_id', store=True, readonly=True)

    @api.depends('old_amount', 'new_amount')
    def _compute_difference(self):
        for adjustment in self:
            adjustment.difference = adjustment.new_amount - adjustment.old_amount

# -*- coding: utf-8 -*-

from odoo import api, fields, models


class Lead2OpportunityPartner(models.TransientModel):
    _inherit = 'crm.lead2opportunity.partner'

    stage_id = fields.Many2one('crm.stage', domain=[('is_cancel', '=', False), ('is_request_to_cancel', '=', False)])
    buying_type = fields.Selection([
        ('primary', 'Primary'),
        ('resale', 'Resale')
    ])
    unit_number = fields.Char()
    eoi_attachment = fields.Binary()
    eoi_amount = fields.Float()
    reservation_attachment = fields.Binary()
    contract_attachment = fields.Binary()
    is_eoi = fields.Boolean(related='stage_id.is_eoi')
    is_reserved = fields.Boolean(related='stage_id.is_reserved')
    is_contract = fields.Boolean(related='stage_id.is_contract')

    related_action = fields.Selection([
        ('create', 'Create a new customer'),
        ('exist', 'Link to an existing customer'),
    ], string='Related Customer')

    reservation_price = fields.Float()
    contract_price = fields.Float()
    reserved_date = fields.Date()
    contracted_date = fields.Date()

    @api.onchange('related_action')
    def onchange_method(self):
        for rec in self:
            if rec.related_action == 'create':
                rec.action = 'create'
            elif rec.related_action == 'exist':
                rec.action = 'exist'

    def _get_achievement_date(self):
        """Calculate achievement date based on stage and dates"""
        achievement_date = False

        if self.is_reserved and self.reserved_date:
            achievement_date = self.reserved_date
        elif self.is_contract and self.contracted_date:
            achievement_date = self.contracted_date

        return achievement_date

    def _action_convert(self):
        """Extend conversion to include stage and achievement date."""
        result_opportunities = super(Lead2OpportunityPartner, self)._action_convert()

        achievement_date = self._get_achievement_date()

        for opportunity in result_opportunities:
            opportunity.write({
                'stage_id': self.stage_id.id,
                'buying_type': self.buying_type,
                'unit_number': self.unit_number,
                'eoi_attachment': self.eoi_attachment,
                'eoi_amount': self.eoi_amount,
                'reservation_attachment': self.reservation_attachment,
                'contract_attachment': self.contract_attachment,
                'reservation_price': self.reservation_price if self.reservation_price else 0,
                'contract_price': self.contract_price if self.contract_price else 0,
                'reserved_date': self.reserved_date if self.reserved_date else False,
                'contracted_date': self.contracted_date if self.contracted_date else False,
                'achievement_date': achievement_date,
                'is_converted': True
            })
        return result_opportunities

    def _action_merge(self):
        """Extend merge to include state and achievement date."""
        result_opportunity = super(Lead2OpportunityPartner, self)._action_merge()

        if result_opportunity:
            achievement_date = self._get_achievement_date()

            # Only set achievement_date if it's not already set (preserve first achievement)
            update_values = {
                'stage_id': self.stage_id.id,
                'buying_type': self.buying_type,
                'unit_number': self.unit_number,
                'eoi_attachment': self.eoi_attachment,
                'eoi_amount': self.eoi_amount,
                'reservation_attachment': self.reservation_attachment,
                'contract_attachment': self.contract_attachment,
                'is_converted': True,
                'reservation_price': self.reservation_price if self.reservation_price else 0,
                'contract_price': self.contract_price if self.contract_price else 0,
                'reserved_date': self.reserved_date if self.reserved_date else False,
                'contracted_date': self.contracted_date if self.contracted_date else False,
            }

            # Only update achievement_date if it's not already set
            if not result_opportunity.achievement_date and achievement_date:
                update_values['achievement_date'] = achievement_date

            result_opportunity.write(update_values)

        return result_opportunity

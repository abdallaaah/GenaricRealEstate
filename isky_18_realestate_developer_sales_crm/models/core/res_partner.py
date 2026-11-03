from odoo import models, fields,api,_
from odoo.exceptions import ValidationError


class ResPartnerInherit(models.Model):

    _inherit = 'res.partner'
    _rec_names_search = ['complete_name', 'email', 'ref', 'vat', 'company_registry', 'code', 'phone', 'mobile']  # TODO vat must be sanitized the same way for storing/searching


    is_broker = fields.Boolean(string='Is Broker', default=False)
    type = fields.Selection(
        selection_add=[("broker", "Broker")], ondelete={"broker": "cascade"}
    )
    is_ambassador = fields.Boolean(string='Is Ambassador')
    is_agent = fields.Boolean(string='Is Agent')
    commission_claim_count = fields.Integer(compute='_compute_commission_claim_count')
    academic_qualifications = fields.Char('Academic Qualifications')
    is_manufacturer = fields.Boolean(string='Manufacturer')
    code = fields.Char()
    born_country_id = fields.Many2one('res.country', string='Country of Birth')
    nationality = fields.Char('Nationality')
    from_realestate = fields.Boolean()

    @api.onchange('type')
    def type_onchange(self):
        if self.type == 'broker':
            self.is_broker = True

    def _compute_commission_claim_count(self):
        claim_counts = dict(self.env['broker.claim']._read_group(
            [('broker_company', 'in', self.ids)], ['broker_company'], ['__count']
        ))
        for partner in self:
            partner.commission_claim_count = claim_counts.get(partner, 0)

    def action_view_commission_claims(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Commissions'),
            'res_model': 'broker.claim',
            'view_mode': 'list,form',
            'domain': [('broker_company', '=', self.id)],
        }

    @api.onchange('country_id')
    def country_onchange(self):
        for rec in self:
            if rec.country_id:
                rec.born_country_id = rec.country_id.id
            else:
                rec.born_country_id = rec.born_country_id

    @api.onchange('born_country_id')
    def born_country_onchange(self):
        for rec in self:
            if rec.born_country_id:
                rec.nationality = rec.born_country_id.nationality

    @api.constrains('national_id', 'passport_number', 'is_company')
    def _check_not_blank(self):
        for rec in self:
            if rec.from_realestate and rec.is_company == False and (not rec.passport_number or not rec.passport_number.strip()) and \
                    (not rec.national_id or not rec.national_id.strip()):
                raise ValidationError(_("Please provide either a National ID or a Passport Number for customer '%s'.", rec.name))
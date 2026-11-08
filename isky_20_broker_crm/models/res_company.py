from odoo import api, fields, models
from odoo.exceptions import ValidationError

SEQUENCE_CODES = {
    'isky_20_broker_crm.lead': 'L',
    'isky_20_broker_crm.opportunity': 'O',
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    broker_sequence_prefix = fields.Char(string="Broker Sequence Prefix", size=3)

    def _register_hook(self):
        super()._register_hook()
        self._fix_broker_sequence_company_scope()

    def _fix_broker_sequence_company_scope(self):
        """Self-heal, runs on every registry build (server start or upgrade) rather than
        depending on ir.sequence XML data-loading rules: the two seed Lead/Opportunity
        ir.sequence records must stay company_id=False (global template) so next_by_code()
        resolves for every company, not just whichever one was active when the data first
        loaded. If a company already customized the prefix directly on that seed record
        (a symptom of this same bug), preserve it as that company's own dedicated sequence
        before resetting the seed back to the shared default.
        """
        for xmlid, default_prefix in (
            ('isky_20_broker_crm.lead_sequence', 'L/'),
            ('isky_20_broker_crm.opportunity_sequence', 'O/'),
        ):
            sequence = self.env.ref(xmlid, raise_if_not_found=False)
            if not sequence or not sequence.company_id:
                continue
            if sequence.prefix != default_prefix:
                sequence.copy({
                    'company_id': sequence.company_id.id,
                    'prefix': sequence.prefix,
                    'number_next': sequence.number_next,
                })
            sequence.write({'company_id': False, 'prefix': default_prefix})

    @api.constrains('broker_sequence_prefix')
    def _check_broker_sequence_prefix(self):
        for company in self:
            prefix = company.broker_sequence_prefix
            if prefix and (len(prefix) != 3 or not prefix.isalpha()):
                raise ValidationError(self.env._("The Broker Sequence Prefix must be exactly 3 letters."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('broker_sequence_prefix'):
                vals['broker_sequence_prefix'] = vals['broker_sequence_prefix'].upper()
        companies = super().create(vals_list)
        for company in companies:
            if company.broker_sequence_prefix:
                company._sync_broker_sequence_prefix()
        return companies

    def write(self, vals):
        if vals.get('broker_sequence_prefix'):
            vals['broker_sequence_prefix'] = vals['broker_sequence_prefix'].upper()
        result = super().write(vals)
        if 'broker_sequence_prefix' in vals:
            for company in self:
                company._sync_broker_sequence_prefix()
        return result

    def _sync_broker_sequence_prefix(self):
        """Repoint the lead/opportunity ir.sequence prefix to this company's 3-letter
        code without touching number_next, so numbering continues where it left off
        instead of restarting -- changing the prefix is a cosmetic, not a reset.
        """
        self.ensure_one()
        prefix = self.broker_sequence_prefix
        for code, letter in SEQUENCE_CODES.items():
            new_prefix = f"{prefix}-{letter}/" if prefix else f"{letter}/"
            sequence = self.env['ir.sequence'].search([
                ('code', '=', code), ('company_id', '=', self.id),
            ], limit=1)
            if sequence:
                sequence.prefix = new_prefix
                continue
            template = self.env['ir.sequence'].search([
                ('code', '=', code), ('company_id', '=', False),
            ], limit=1)
            if template:
                template.copy({
                    'company_id': self.id,
                    'prefix': new_prefix,
                    'number_next': template.number_next,
                })

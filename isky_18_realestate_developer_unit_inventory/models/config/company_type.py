from odoo import fields, models

# Phase 8 (G4, decided by the owner 2026-11-08): which side of the product a database runs.
#
# The field is named `realestate_company_type`, not `company_type`, because `res.partner` already
# declares a `company_type` (person / company). `res.company` does not delegate to `res.partner` in
# Odoo 18, so the bare name would be legal - but two fields of that name on two models this closely
# related is a trap for the next reader and for any search() on it. See the decisions log, D2.
COMPANY_TYPES = [
    ('developer', 'Developer'),
    ('broker', 'Broker'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    realestate_company_type = fields.Selection(
        COMPANY_TYPES, string='Real Estate Company Type', default='developer', required=True,
        help="Developer: this company builds and sells its own units, and owns the unit "
             "hierarchy and its system codes. Broker: this company brokers units belonging to "
             "developers, and receives each unit's system code from the developer rather than "
             "generating it.")

    def _is_broker(self):
        self.ensure_one()
        return self.realestate_company_type == 'broker'

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Phase 7 (D2, D3): the revenue split used to be two hardcoded business lines - four settings
# named after the client's GIS and OAYA entities, two client-named booleans on
# account.analytic.account, and sixty lines of the same money math written out three times.
#
# It is now configuration: one row per business line, and one shared helper that every posting
# path calls. A client's own business-line names live in these rows, which is data, not code.


class RevenueSplitLine(models.Model):
    _name = 'realestate.revenue.split.line'
    _description = 'Revenue Split Line'
    _order = 'sequence, name, id'

    name = fields.Char(
        string='Business Line', required=True,
        help="The business line this share of a collection is credited to.")
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    account_id = fields.Many2one(
        'account.account', string='Credit Account', required=True,
        domain=[('deprecated', '=', False)],
        help="Account credited with this business line's share.")
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        help="Analytic account carried on this line's share of the collection expense. "
             "Optional; only the payment-registration path uses it.")
    percentage = fields.Float(
        string='Percentage (%)', required=True, digits=(16, 4),
        help="Share of the collected amount credited to this business line.")
    active = fields.Boolean(default=True)

    @api.constrains('percentage')
    def _check_percentage(self):
        for line in self:
            if line.percentage <= 0.0:
                raise ValidationError(_(
                    "Revenue split percentage must be greater than zero (line '%(name)s').",
                    name=line.name))
            if line.percentage > 100.0:
                raise ValidationError(_(
                    "Revenue split percentage cannot exceed 100%% (line '%(name)s').",
                    name=line.name))

    @api.constrains('name', 'company_id')
    def _check_unique_name_per_company(self):
        for line in self:
            if self.search_count([('name', '=', line.name), ('id', '!=', line.id),
                                  ('company_id', '=', line.company_id.id)]):
                raise ValidationError(_(
                    "A revenue split line named '%(name)s' already exists for this company.",
                    name=line.name))


class RevenueSplitMixin(models.AbstractModel):
    """The one engine every collection-entry path shares.

    Three models used to carry their own copy of this: `sale.proposal` (on client signature),
    `account.payment` (on payment registration, through the sales_accounting bridge) and
    `cheque.manage` (on collection, through the sales_cheques bridge). They differ in how they
    group the result - the payment path posts one move per business line, the other two post a
    single move - so this provides the pieces rather than the whole entry: the rows, the config,
    the rounded per-row amounts, and the line dictionaries.

    Each caller keeps its own behaviour when configuration is missing, deliberately: the contract
    path raises, and the two bridges return quietly. Phase 7 moved where the values come from, not
    what happens when they are absent.
    """
    _name = 'realestate.revenue.split.mixin'
    _description = 'Revenue Split Engine'

    # ---------------------------------------------------------------- configuration

    def _revenue_split_company(self):
        company = getattr(self, 'company_id', False)
        return company or self.env.company

    def _revenue_split_lines(self):
        """The configured business lines, lowest sequence first."""
        company = self._revenue_split_company()
        return self.env['realestate.revenue.split.line'].sudo().search([
            ('company_id', 'in', (company.id, False)),
        ])

    def _revenue_split_posting_config(self):
        """(debit_account_id, journal_id, missing) - ids as ints, `missing` as labels.

        Both come from the generic `realestate.` parameters Phase 7 renamed; they are the parts
        of a collection entry that are not per-business-line.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        debit_account_id = ICP.get_param('realestate.collection_debit_account_id')
        journal_id = ICP.get_param('realestate.collection_journal_id')
        missing = []
        if not debit_account_id:
            missing.append(_("Collection Debit Account"))
        if not journal_id:
            missing.append(_("Collection Journal"))
        if not self._revenue_split_lines():
            missing.append(_("at least one Revenue Split Line"))
        return (int(debit_account_id) if debit_account_id else False,
                int(journal_id) if journal_id else False,
                missing)

    # ---------------------------------------------------------------- amounts and lines

    def _revenue_split_amounts(self, total_amount):
        """[(line, amount)] for every configured business line with a non-zero share.

        Same arithmetic as the three copies it replaces: each share is rounded to two decimals
        independently, and the debit is the sum of the rounded shares, so the entry balances.
        """
        result = []
        for line in self._revenue_split_lines():
            amount = round((total_amount * line.percentage) / 100.0, 2)
            if amount > 0:
                result.append((line, amount))
        return result

    def _revenue_split_credit_line(self, line, amount, reference, partner_id,
                                   analytic_distribution=False):
        return {
            'name': _('%(business_line)s Collection (%(percentage).2f%%) - %(reference)s',
                      business_line=line.name, percentage=line.percentage,
                      reference=reference),
            'account_id': line.account_id.id,
            'partner_id': partner_id,
            'debit': 0.0,
            'credit': amount,
            'analytic_distribution': analytic_distribution,
        }

    def _revenue_split_debit_line(self, debit_account_id, amount, reference, partner_id,
                                  analytic_distribution=False):
        return {
            'name': _('Collection Expense - %(reference)s', reference=reference),
            'account_id': debit_account_id,
            'partner_id': partner_id,
            'debit': amount,
            'credit': 0.0,
            'analytic_distribution': analytic_distribution,
        }

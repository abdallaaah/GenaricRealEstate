from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class RealestateSplitLineMixin(models.AbstractModel):
    """Phase 3 step 5: the one split-line engine (decisions log section 3: split = 100%).

    Holds the percentage, the ordering and the sum-to-100 rule. Reservation and contract share
    it through `customer.ownership`, which carries both FKs.

    The party field is NOT declared here. Concrete models name their own via
    `_split_party_field`, which is how the mixin supports "partner or user" without forcing a
    redundant column on models that already have one: `customer.ownership` keeps its existing
    `customer_id`, which legacy reports and views read by name.

    `_order` lives here, not on the concrete model: the ordering is part of the shared contract,
    so every split model inherits it rather than restating it.
    """
    _name = 'realestate.split.line.mixin'
    _description = 'Real Estate Split Line'
    _order = 'sequence, id'

    # Concrete models override: the Many2one holding the party this share belongs to
    # ('customer_id' here, 'user_id' for a user-based split).
    _split_party_field = 'partner_id'
    # The parent Many2ones, in PRECEDENCE order. A line belongs to exactly one group: the
    # first of these that is set. Declaration order therefore matters - see _split_group_field.
    _split_parent_fields = ()

    sequence = fields.Integer(string='Sequence', default=10)
    percentage = fields.Float(string='Percentage(%)')

    def _split_party(self):
        self.ensure_one()
        return self[self._split_party_field]

    # -- grouping ---------------------------------------------------------------------------

    def _split_group_field(self):
        """The ONE parent field that governs this line, by precedence.

        B2: `customer.ownership._compute_reservation_id` deliberately keeps the automatic
        contract -> reservation link, so a contract line also carries `reservation_id`. Before
        this, such a line was counted in BOTH groups, and a reservation holding its own lines
        plus a contract holding its own totalled 200% - which made every later write on those
        lines raise. One line, one group: the contract wins because it is the more specific
        parent.
        """
        self.ensure_one()
        for field_name in self._split_parent_fields:
            if self[field_name]:
                return field_name
        return False

    def _split_group_domain(self, field_name, parent_id):
        """Every line in one group: linked to this parent, and not claimed by a
        higher-precedence parent."""
        domain = [(field_name, '=', parent_id)]
        for higher in self._split_parent_fields:
            if higher == field_name:
                break
            domain.append((higher, '=', False))
        return domain

    def _split_groups(self):
        """{(parent_field, parent_id): lines} for every parent governing a line in self.

        Reads from the database rather than from self, so the total covers sibling lines the
        current write did not touch. R5: `sudo()` is kept so the total is complete regardless
        of record rules, but the search is confined to the parent's own company - otherwise a
        multi-company database could count another company's lines into the total.
        """
        groups = {}
        for line in self:
            field_name = line._split_group_field()
            if not field_name:
                # a template row with no parent: not validated here, only at copy time (R1)
                continue
            parent = line[field_name]
            key = (field_name, parent.id)
            if key in groups:
                continue
            domain = self._split_group_domain(field_name, parent.id)
            company = parent.company_id if 'company_id' in parent._fields else False
            if company and 'company_id' in self._fields:
                domain.append(('company_id', 'in', (company.id, False)))
            groups[key] = self.sudo().search(domain)
        return groups

    # -- the rule ---------------------------------------------------------------------------

    def _split_precision(self):
        """Decimal places used to compare the total against 100.

        R4: read from the Financials setting rather than hardcoded, so a company that works to
        three decimals is not told its exact split is wrong. Defaults to 2, which is the value
        this rule used before the setting existed."""
        company = self.env.company
        if 'split_percentage_precision' in company._fields:
            return company.split_percentage_precision or 2
        return 2

    def _validate_split_total(self):
        """The sum of percentages in each group must be exactly 100.

        An empty group is skipped: ownership lines are optional, so a single-owner deal with no
        lines stays valid. A saved 0% line is NOT skipped (R2) - the escape that used to
        tolerate one blank line also tolerated a real 0% split, which is wrong. An unsaved row
        in a form never reaches a constrains, so the form stays usable without the escape.
        """
        precision = self._split_precision()
        for (field_name, parent_id), lines in self._split_groups().items():
            if not lines:
                continue
            total = sum(lines.mapped('percentage'))
            if float_compare(total, 100.0, precision_digits=precision) != 0:
                parent = self.env[lines._fields[field_name].comodel_name].browse(parent_id)
                raise ValidationError(_(
                    "The split percentages for %(parent)s must add up to exactly 100%%, "
                    "not %(total).2f%%.\n\n"
                    "%(count)d line(s): %(detail)s",
                    parent=parent.display_name or _('this record'),
                    total=total,
                    count=len(lines),
                    detail=', '.join(
                        '%s %.2f%%' % (line._split_party().display_name or _('(no party)'),
                                       line.percentage)
                        for line in lines),
                ))

    def _validate_template_total(self):
        """The total of a set of template rows, checked before they are copied onto a deal (R1).

        Template rows carry no parent, so `_validate_split_total` deliberately ignores them
        while they are being edited. The copy action is the point where they become a real
        split, so that is where the total has to hold.
        """
        if not self:
            return True
        precision = self._split_precision()
        total = sum(self.mapped('percentage'))
        if float_compare(total, 100.0, precision_digits=precision) != 0:
            raise ValidationError(_(
                "The ownership template adds up to %(total).2f%%, not 100%%, so it cannot be "
                "copied.\n\n%(count)d line(s): %(detail)s",
                total=total,
                count=len(self),
                detail=', '.join(
                    '%s %.2f%%' % (line._split_party().display_name or _('(no party)'),
                                   line.percentage)
                    for line in self),
            ))
        return True

    @api.constrains('percentage', 'sequence')
    def _check_split_total_is_100(self):
        self._validate_split_total()


class RealestateSplitParentMixin(models.AbstractModel):
    """The deal side of a split: copies template lines onto the deal.

    Exists because `action_copy_customer_ownership_ids` was duplicated verbatim in
    sale_reservation.py and sale_proposal.py, differing only in the FK key and one word of the
    error message. One engine, per CLAUDE.md.
    """
    _name = 'realestate.split.parent.mixin'
    _description = 'Real Estate Split Parent'

    # Concrete models override: the FK on customer.ownership pointing back at them, and the
    # word used in the error message.
    _split_child_fk = False
    _split_parent_label = 'record'
    # C1: the o2m holding this deal's split lines. The constrains that validates it is declared
    # on each concrete model (which owns the field) and delegates here, rather than being
    # declared on this abstract model against a field it does not have.
    _split_child_o2m = 'customer_new_ownership_ids'
    # and the Many2many holding the template rows the copy action reads
    _split_template_m2m = 'customer_ownership_ids'

    def _validate_split_children(self):
        """Validate the whole set whenever the deal's split lines change.

        The line-level constraint cannot catch a deletion - unlink() does not fire
        @api.constrains - so removing one of two 50% lines would otherwise leave an
        unvalidated 50% split. The concrete model's constrains fires on the parent write that
        performs the deletion and calls this.
        """
        for rec in self:
            lines = rec[rec._split_child_o2m]
            if lines:
                lines._validate_split_total()

    def action_copy_customer_ownership_ids(self):
        already_done_recs = []
        to_create = []

        for rec in self:
            template = rec[rec._split_template_m2m]
            # R1: a template only becomes a real split here, so this is where the total has to
            # hold. Validated per deal, before anything is created, so a bad template creates
            # nothing at all.
            template._validate_template_total()
            for line in template:
                existed_line = rec[rec._split_child_o2m].filtered(
                    lambda l: l.percentage == line.percentage
                    and l.customer_id.id == line.customer_id.id and l.from_action)
                if existed_line:
                    already_done_recs.append(rec.name)
                    break
                to_create.append({
                    'customer_id': line.customer_id.id,
                    'percentage': line.percentage,
                    'company_id': line.company_id.id,
                    rec._split_child_fk: rec.id,
                    'from_action': True,
                })

        if already_done_recs:
            raise ValidationError(_(
                "Server action already ran for %(label)ss: %(names)s",
                label=self._split_parent_label,
                names=', '.join(already_done_recs)))
        if to_create:
            self.env['customer.ownership'].create(to_create)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Success"),
                'message': _("%s ownership record(s) copied successfully.", len(to_create)),
                'type': 'success',
                'sticky': False,
            }
        }

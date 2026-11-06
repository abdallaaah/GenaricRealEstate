from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_is_zero


class RealestateSplitLineMixin(models.AbstractModel):
    """Phase 3 step 5: the one split-line engine (decisions log section 3: split = 100%).

    Holds the percentage, the ordering and the sum-to-100 rule. Reservation and contract share
    it through `customer.ownership`, which carries both FKs and is already used by both sides -
    step 0 confirmed there is no second implementation to remove, only a missing constraint.

    The party field is NOT declared here. Concrete models name their own via
    `_split_party_field`, which is how the mixin supports "partner or user" without forcing a
    redundant column on models that already have one: `customer.ownership` keeps its existing
    `customer_id`, which legacy reports and views read by name.
    """
    _name = 'realestate.split.line.mixin'
    _description = 'Real Estate Split Line'
    _order = 'sequence, id'

    # Concrete models override: the Many2one holding the party this share belongs to
    # ('customer_id' here, 'user_id' for a user-based split).
    _split_party_field = 'partner_id'
    # The Many2one fields that identify which parent a line belongs to. Lines are grouped by
    # these for the sum-to-100 check; a line with none of them set is a standalone template
    # and is not validated.
    _split_parent_fields = ()

    sequence = fields.Integer(string='Sequence', default=10)
    percentage = fields.Float(string='Percentage(%)')

    def _split_party(self):
        self.ensure_one()
        return self[self._split_party_field]

    def _split_groups(self):
        """{(parent_field, parent_id): lines} for every parent touched by this recordset.

        Reads from the database rather than from self, so the total covers sibling lines the
        current write did not touch."""
        groups = {}
        for field_name in self._split_parent_fields:
            for line in self:
                parent = line[field_name]
                if not parent:
                    continue
                key = (field_name, parent.id)
                if key not in groups:
                    groups[key] = self.sudo().search([(field_name, '=', parent.id)])
        return groups

    def _validate_split_total(self):
        """The sum of percentages in each group must be exactly 100.

        Skipped for an empty group: ownership lines are optional (a single-owner deal has
        none), so "no lines" must stay valid - only a partially filled split is an error.
        """
        precision = 2
        for (field_name, parent_id), lines in self._split_groups().items():
            if not lines:
                continue
            total = sum(lines.mapped('percentage'))
            if float_is_zero(total, precision_digits=precision) and len(lines) == 1 \
                    and float_is_zero(lines.percentage, precision_digits=precision):
                # a single blank line being set up; let the user finish typing
                continue
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

    @api.constrains('percentage', 'sequence')
    def _check_split_total_is_100(self):
        self._validate_split_total()


class RealestateSplitParentMixin(models.AbstractModel):
    """The deal side of a split: copies template lines onto the deal.

    Exists because `action_copy_customer_ownership_ids` was duplicated verbatim in
    sale_reservation.py and sale_proposal.py, differing only in the FK key and one word of the
    error message (step 0 finding). One engine, per CLAUDE.md.
    """
    _name = 'realestate.split.parent.mixin'
    _description = 'Real Estate Split Parent'

    # Concrete models override: the FK on customer.ownership pointing back at them, and the
    # word used in the error message.
    _split_child_fk = False
    _split_parent_label = 'record'

    @api.constrains('customer_new_ownership_ids')
    def _check_ownership_split_total(self):
        """Validate the whole set whenever the deal's split lines change.

        The line-level constraint cannot catch a deletion - unlink() does not fire
        @api.constrains - so removing one of two 50% lines would otherwise leave an
        unvalidated 50% split. This fires on the parent write that performs the deletion.
        """
        for rec in self:
            lines = rec.customer_new_ownership_ids
            if lines:
                lines._validate_split_total()

    def action_copy_customer_ownership_ids(self):
        already_done_recs = []
        to_create = []

        for rec in self:
            for line in rec.customer_ownership_ids:
                existed_line = rec.customer_new_ownership_ids.filtered(
                    lambda l: l.percentage == line.percentage
                    and l.customer_id.id == line.customer_id.id and l.from_action is True)
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

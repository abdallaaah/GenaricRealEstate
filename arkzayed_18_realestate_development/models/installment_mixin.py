import math
from datetime import date
from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class InstallmentMixin(models.AbstractModel):
    _name = "installment.mixin"
    _description = "A mixin to handle installment rounding adjustments"

    def _get_installment_rounding_params(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'apply_cents': ICP.get_param(
                'arkzayed_18_realestate_development.apply_cents_in_last_line', 'False') == 'True',
            'apply_tens': ICP.get_param(
                'arkzayed_18_realestate_development.apply_to_nearer_ten', 'False') == 'True',
        }

    def _get_installment_price_tolerance(self):
        """Max pre-adjustment drift (in company currency) the system will silently
        absorb into the last line. Beyond this, something upstream is wrong (not
        just per-line rounding), so generation is refused instead of silently
        dumping a large, unexplained amount onto one line."""
        ICP = self.env['ir.config_parameter'].sudo()
        return float(ICP.get_param('arkzayed_18_realestate_development.installment_price_tolerance', '50.0') or 0.0)

    def _force_lines_to_match_total(self, lines, target_total, amount_field='amount', label=''):
        """Adjust the last line (by date) so the lines sum to EXACTLY target_total,
        regardless of any per-line rounding/float drift introduced while generating
        them. Raises if the pre-adjustment drift exceeds the configured tolerance,
        since that signals a real calculation error rather than rounding noise."""
        if not lines:
            return lines

        current_total = sum(getattr(l, amount_field) for l in lines)
        drift = target_total - current_total
        tolerance = self._get_installment_price_tolerance()
        if float_compare(abs(drift), tolerance, precision_digits=2) > 0:
            raise UserError(_(
                "%(label)s lines total %(current).2f, which is %(drift).2f away from the expected "
                "%(target).2f — more than the configured tolerance (%(tolerance).2f). "
                "Please check the payment plan configuration.",
                label=label or _('The'), current=current_total, drift=abs(drift),
                target=target_total, tolerance=tolerance,
            ))

        sorted_lines = lines.sorted(key=lambda l: l.date or date.min)
        last_line = sorted_lines[-1]
        other_lines = sorted_lines - last_line

        # Round every other line to piaster precision and track that exact total,
        # so the last line can be set to close the gap with no leftover float noise.
        other_total = 0.0
        for line in other_lines:
            rounded = round(getattr(line, amount_field), 2)
            setattr(line, amount_field, rounded)
            other_total += rounded

        setattr(last_line, amount_field, round(target_total - other_total, 2))
        return lines

    def apply_installment_rounding(self, lines, amount_field='amount'):
        """Apply configured cents/tens rounding to an ORM recordset of lines."""
        if not lines:
            return lines

        params = self._get_installment_rounding_params()
        if params['apply_cents']:
            self._apply_cents_to_lines(lines, amount_field)
        if params['apply_tens']:
            self._apply_tens_to_lines(lines, amount_field)
        return lines

    def apply_installment_rounding_dicts(self, dict_list, amount_field='unit_amount'):
        """Apply configured cents/tens rounding to a list of dictionaries (for reports)."""
        if not dict_list:
            return dict_list

        params = self._get_installment_rounding_params()
        if params['apply_cents']:
            self._apply_cents_to_dicts(dict_list, amount_field)
        if params['apply_tens']:
            self._apply_tens_to_dicts(dict_list, amount_field)
        return dict_list

    def _apply_cents_to_lines(self, lines, amount_field='amount'):
        sorted_lines = lines.sorted(key=lambda l: l.date or date.min)
        last_line = sorted_lines[-1]
        other_lines = sorted_lines - last_line

        remainder = 0.0
        for line in other_lines:
            amount = getattr(line, amount_field)
            truncated = math.trunc(amount)
            remainder += amount - truncated
            setattr(line, amount_field, float(truncated))

        final_amount = round(getattr(last_line, amount_field) + remainder, 2)
        setattr(last_line, amount_field, final_amount)

    def _apply_tens_to_lines(self, lines, amount_field='amount'):
        sorted_lines = lines.sorted(key=lambda l: l.date or date.min)
        last_line = sorted_lines[-1]
        other_lines = sorted_lines - last_line

        remainder = 0.0
        for line in other_lines:
            amount = getattr(line, amount_field)
            rounded = math.floor(amount / 10) * 10
            remainder += amount - rounded
            setattr(line, amount_field, float(rounded))

        final_amount = round(getattr(last_line, amount_field) + remainder, 2)
        setattr(last_line, amount_field, final_amount)

    def _apply_cents_to_dicts(self, dict_list, amount_field='unit_amount'):
        sorted_dicts = sorted(dict_list, key=lambda d: d.get('date') or date.min)
        last_dict = sorted_dicts[-1]
        other_dicts = sorted_dicts[:-1]

        remainder = 0.0
        for d in other_dicts:
            amount = d[amount_field]
            truncated = math.trunc(amount)
            remainder += amount - truncated
            d[amount_field] = float(truncated)

        last_dict[amount_field] = round(last_dict[amount_field] + remainder, 2)

    def _apply_tens_to_dicts(self, dict_list, amount_field='unit_amount'):
        sorted_dicts = sorted(dict_list, key=lambda d: d.get('date') or date.min)
        last_dict = sorted_dicts[-1]
        other_dicts = sorted_dicts[:-1]

        remainder = 0.0
        for d in other_dicts:
            amount = d[amount_field]
            rounded = math.floor(amount / 10) * 10
            remainder += amount - rounded
            d[amount_field] = float(rounded)

        last_dict[amount_field] = round(last_dict[amount_field] + remainder, 2)
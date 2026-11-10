from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_is_zero

SEGMENT_PRECISION = 4


class CommissionSegment(models.Model):
    """One band of a segmented commission plan: from-to, at a percentage.

    Deliberately a model of our own rather than Odoo's
    ``sale.commission.plan.target.commission``. That field's ``amount`` is a *stored
    compute* (``amount_rate x plan.commission_amount``) with an inverse, so Odoo
    rewrites it whenever the plan's on-target commission changes -- a configured rate
    can shift without anyone touching it. Money logic cannot sit on a field the
    framework owns.

    ``percentage`` here is a true percent: 2.5 means 2.5%. The legacy "(/M)"
    convention (where 5000 meant 0.5%) applies only to the native bracket path, which
    is still available when ``use_custom_segments`` is off.

    Bounds are half-open, ``amount_from <= value < amount_to``, so a value landing
    exactly on a boundary belongs to the upper band. ``amount_to`` of 0 means
    open-ended, and only the last band may be open.
    """
    _name = 'commission.segment'
    _description = "Commission Plan Segment"
    _order = 'plan_id, sequence, amount_from'

    plan_id = fields.Many2one('sale.commission.plan', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    amount_from = fields.Float(
        string="From", required=True,
        help="Lower bound, inclusive. In currency when the plan's basis is Sales Volume, "
             "or in percent (0-100) when it is Target Completion.")
    amount_to = fields.Float(
        string="To",
        help="Upper bound, exclusive. Leave at 0 for the last, open-ended band.")
    percentage = fields.Float(
        string="Percentage", required=True, digits=(16, 4),
        help="A true percent applied to the deal amount: 2.5 means 2.5%.")
    segment_basis = fields.Selection(related='plan_id.segment_basis', readonly=True)
    currency_id = fields.Many2one(related='plan_id.currency_id', readonly=True)

    @property
    def is_open_ended(self):
        self.ensure_one()
        return float_is_zero(self.amount_to, precision_digits=SEGMENT_PRECISION)

    @api.constrains('amount_from', 'amount_to', 'percentage', 'plan_id', 'sequence')
    def _check_ladder(self):
        """Validate the whole plan's ladder, not just the edited row.

        A band only means anything relative to its neighbours, so the checks are:
        starts at zero, no gaps, no overlaps, and exactly one open-ended band, last.
        Modelled on project.commission._check_dates, which validates dated rows the
        same way.
        """
        for plan in self.plan_id:
            segments = plan.segment_ids.sorted(lambda s: (s.amount_from, s.sequence))
            if not segments:
                continue
            for segment in segments:
                if segment.percentage < 0:
                    raise ValidationError(self.env._("A segment percentage cannot be negative."))
                if not segment.is_open_ended and float_compare(
                        segment.amount_to, segment.amount_from, precision_digits=SEGMENT_PRECISION) <= 0:
                    raise ValidationError(self.env._(
                        "Segment starting at %(start)s must end above where it starts.",
                        start=segment.amount_from,
                    ))
            if not float_is_zero(segments[0].amount_from, precision_digits=SEGMENT_PRECISION):
                raise ValidationError(self.env._(
                    "The first segment of %(plan)s must start at 0, not %(start)s -- otherwise "
                    "a deal below it matches no band and earns nothing.",
                    plan=plan.display_name, start=segments[0].amount_from,
                ))
            open_ended = segments.filtered(lambda s: s.is_open_ended)
            if len(open_ended) > 1:
                raise ValidationError(self.env._(
                    "%(plan)s has %(count)s open-ended segments; only the last may be open.",
                    plan=plan.display_name, count=len(open_ended),
                ))
            if open_ended and open_ended != segments[-1]:
                raise ValidationError(self.env._(
                    "The open-ended segment of %(plan)s must be the last one.", plan=plan.display_name))
            for lower, upper in zip(segments, segments[1:]):
                if lower.is_open_ended:
                    continue
                gap = float_compare(upper.amount_from, lower.amount_to, precision_digits=SEGMENT_PRECISION)
                if gap > 0:
                    raise ValidationError(self.env._(
                        "Gap in %(plan)s between %(end)s and %(start)s: a deal in between "
                        "would match no band.",
                        plan=plan.display_name, end=lower.amount_to, start=upper.amount_from,
                    ))
                if gap < 0:
                    raise ValidationError(self.env._(
                        "Overlap in %(plan)s: %(start)s falls inside the band ending at %(end)s.",
                        plan=plan.display_name, start=upper.amount_from, end=lower.amount_to,
                    ))

    @api.model
    def _match(self, segments, value):
        """The band `value` falls in, or an empty recordset.

        Half-open bounds, so a value sitting exactly on a boundary goes to the upper
        band -- which is why a ladder validated as gapless always matches something.
        """
        for segment in segments.sorted(lambda s: (s.amount_from, s.sequence)):
            if float_compare(value, segment.amount_from, precision_digits=SEGMENT_PRECISION) < 0:
                continue
            if segment.is_open_ended or float_compare(
                    value, segment.amount_to, precision_digits=SEGMENT_PRECISION) < 0:
                return segment
        return self.browse()

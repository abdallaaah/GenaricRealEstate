from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Group allocations created before distributions existed: one distribution per wizard run
    (same bill line, creation time and user)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT move_line_id, create_date, create_uid, array_agg(id ORDER BY id)
          FROM arkzayed_cost_allocation
         WHERE distribution_id IS NULL
      GROUP BY move_line_id, create_date, create_uid
      ORDER BY create_date
    """)
    for line_id, created, uid, alloc_ids in cr.fetchall():
        allocs = env['arkzayed.cost.allocation'].browse(alloc_ids)
        units = allocs.mapped('unit_id')
        # Very old rows have no stored area/rate: fall back to the unit's current gross area.
        for alloc in allocs.filtered(lambda a: not a.unit_area):
            alloc.unit_area = alloc.unit_id.unit_area
        total_area = sum(allocs.mapped('unit_area'))
        amount = sum(allocs.mapped('amount'))
        rate = amount / total_area if total_area else 0.0
        for alloc in allocs.filtered(lambda a: not a.rate_per_sqm):
            alloc.rate_per_sqm = rate
        dist = env['arkzayed.cost.distribution'].create({
            'move_line_id': line_id,
            'amount': amount,
            'cost_type': allocs[0].cost_type,
            'total_area': total_area,
            'rate_per_sqm': rate,
            'unit_count': len(units),
            'unit_ids': [(6, 0, units.ids)],
            'building_ids': [(6, 0, units.mapped('building_id').ids)],
        })
        allocs.write({'distribution_id': dist.id})
        cr.execute("UPDATE arkzayed_cost_distribution SET create_date = %s, create_uid = %s WHERE id = %s",
                   (created, uid, dist.id))

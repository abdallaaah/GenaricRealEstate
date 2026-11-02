# -*- coding: utf-8 -*-
{
    'name': "iSky Base Modification",

    'summary': "iSky Base Modification",

    'description': """This module add fields to country and states""",

    'author': "iSky Development Team",

    'version': "18.0.0.1",

    'website': "http://www.iskydev.com",

    'depends': ['base', 'contacts'],

    'data': [
        # 'security/ir.model.access.csv',
        'views/res_company.xml',
        'views/res_partner.xml',
        # 'views/res_state.xml',
        # 'views/menu_item_view.xml',

    ],
    'installable': True,
    'application': True,
    'auto_install': False,
'license': 'LGPL-3',
}

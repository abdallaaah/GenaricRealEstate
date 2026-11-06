# cheque.manage's sales extension must load before the models whose One2many fields use its
# inverse fields (eoi_id, sale_proposal_id, installment_line_id, ...).
# S8 settings: res_company first - res_config_settings declares related fields that walk
# company_id.<field>, so the company fields must exist when those are set up.
from . import res_company
from . import res_config_settings
from . import cheque_manage
from . import account_payment
from . import payment_allocation
from . import installment_lines
from . import maintenance_installment_lines
from . import eoi
from . import eoi_payment
from . import sale_reservation
from . import sale_proposal
from . import reservation_payment

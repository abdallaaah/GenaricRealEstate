# res_company and the project override define the installments flags that core models
# read, so they load before res_config_settings' related fields.
from . import res_company
# S7: the approval stage registry, read by the gate mixin
from . import approval_settings
from . import realestate_project_sales_ext
from . import maintenance_config
from . import discount_config
from . import discount_approval
from . import res_config_settings
from . import res_config_settings_crm

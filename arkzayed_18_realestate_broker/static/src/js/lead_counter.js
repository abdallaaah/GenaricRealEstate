/** @odoo-module */

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class LeadCounter extends Component {
    static template = "arkzayed_18_realestate_broker.LeadCounter";

    setup() {
        this.orm = useService("orm");
        this.leadCounterService = useState(useService("arkzayed_18_realestate_broker.lead_counter_service"));
        onWillStart(async () => {
            let type;
            if (this.env.config.actionName == 'Leads'){
                type = 'lead'
            }
            else{
                type = 'opportunity'
            }
            await this.leadCounterService.updateRecordsCount(type);
        });
    }
}
/** @odoo-module */


import { KanbanQuickCreateController } from "@web/views/kanban/kanban_record_quick_create";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(KanbanQuickCreateController.prototype, {
    setup() {
        super.setup();
        this.leadCounterService = useService("arkzayed_18_realestate_developer_crm.lead_counter_service");
    },
    async validate(mode) {
        let result = await super.validate(mode);
        await this.updateRecordsCount();;
        return result;
    },
//    async showFormDialogInError(e) {
//        super.showFormDialogInError(e);
//        await this.updateRecordsCount();
//    },
    async updateRecordsCount(){
        let type;
        if (this.props.context.default_type == 'lead'){
            type = 'lead'
        }
        else{
            type = 'opportunity'
        }
        await this.leadCounterService.updateRecordsCount(type);
    }

});
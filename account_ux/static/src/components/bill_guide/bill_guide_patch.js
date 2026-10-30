import { patch } from "@web/core/utils/patch";
import { BillGuide } from "@account/components/bill_guide/bill_guide";

patch(BillGuide.prototype, {
    setup() {
        super.setup();
        // One BillGuide per empty purchase journal card: share a single RPC
        // instead of one per card (and again on the cached dashboard render).
        this.orm = this.orm.cache({ type: "ram" });
    },
});

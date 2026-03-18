/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { MrpDisplayAction } from "@mrp_workorder/mrp_display/mrp_display_action";

patch(MrpDisplayAction.prototype, {
	get fieldsStructure() {
		let res = super.fieldsStructure;
		res["mrp.workorder"].push("mrp_report_name");
		return res;
	},
});

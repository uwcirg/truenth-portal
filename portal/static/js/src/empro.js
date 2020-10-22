import {EMPRO_DOMAIN_MAPPINGS} from "./data/common/consts.js";
import tnthAjax from "./modules/TnthAjax.js";

var emproObj = function() {
    this.domains = [];
    this.hasHardTrigger = false;
    this.hasSoftTrigger = false;
};
emproObj.prototype.initTriggers = function() {
    var self = this;
    tnthAjax.getSubStudyTriggers(1, false, function(data) {
        console.log("data? ", data)
        if (data.triggers && data.triggers.domain) {
            self.domains = (data.triggers.domain).map(item => {
                return EMPRO_DOMAIN_MAPPINGS[Object.keys(item)[0]];
            });
            self.domains = self.domains.filter((d, index) => {
                return self.domains.indexOf(d) === index;
            });
            self.hasHardTrigger = (data.triggers.domain).filter(item => {
                let entry = Object.entries(item);
                return entry[0] && entry[0][1] && entry[0][1].indexOf("hard") !== -1;
            }).length;
            self.hasSoftTrigger = (data.triggers.domain).filter(item => {
                let entry = Object.entries(item);
                return entry[0] && entry[0][1] && entry[0][1].indexOf("soft") !== -1;
            }).length;
            console.log("self.domains? ", self.domains);
            self.domains.forEach(domain => {
                $("#hardTriggerDisplayList").append(`<li>${domain}</li>`);
                $("#hardTriggerButtonsContainer").append(`<a class="btn btn-empro-primary" href="/substudy-tailored-content#/${domain}">${domain.replace(/_/g, " ")}</a>`);
            });
            if (self.hasHardTrigger) {
                $("#emproModal .hard-trigger-item").show();
                $("#emproModal .soft-trigger-item").hide();
                $("#emproModal .no-trigger-item").hide();
            }
            console.log("has hard triggers ", self.hasHardTrigger);
            console.log("has soft triggers ", self.hasSoftTrigger);
        }
    });
}

/* TODO trigger modal based on hard trigger */
/*
 * TODO get domain topic(s) available to the user via API
 */
$(document).ready(function() {
    (new emproObj()).initTriggers();
    $("#emproModal").modal({
        show: false
    });
});

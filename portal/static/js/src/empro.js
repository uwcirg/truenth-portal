import EMPRO_DOMAIN_MAPPINGS from "./data/common/empro_domain_mappings.json";
import {SUBSTUDY_QUESTIONNAIRE_IDENTIFIER} from "./data/common/consts.js";
import tnthAjax from "./modules/TnthAjax.js";

var emproObj = function() {
    this.domains = [];
    this.hasHardTrigger = false;
    this.hasSoftTrigger = false;
    this.userId = 0;
};
emproObj.prototype.populateDomainDisplay = function() {
    this.domains.forEach(domain => {
        $("#emproModal .triggersDisplayList").append(`<li>${domain}</li>`);
        $("#emproModal .triggersButtonsContainer").append(
            `<a class="btn btn-empro-primary" href="/substudy-tailored-content#/${domain}" target="_blank">${domain.replace(/_/g, " ")}</a>`
        );
    });
};
emproObj.prototype.initThankyouModal = function() {
    if (!$("#emproModal").length) {
        return;
    }
    $("#emproModal").modal({
        show: false
    });
};
emproObj.prototype.initReportLink = function() {
    $(".longitudinal-report-link").attr("href", `/patients/longitudinal-report/${this.userId}/${SUBSTUDY_QUESTIONNAIRE_IDENTIFIER}`);
};
emproObj.prototype.initTriggerItemsVis = function() {
    if (!$("#emproModal").length) {
        return;
    }
    if (this.hasHardTrigger) {
        $("#emproModal .hard-trigger").addClass("active");
        $("#emproModal .no-trigger").hide();
         //present thank you modal if hard trigger present
        $("#emproModal").modal("show");
        return;
    }
    if (this.hasSoftTrigger) {
        $("#emproModal .soft-trigger").addClass("active");
        $("#emproModal .no-trigger").hide();
        return;
    }
   
};
emproObj.prototype.initTriggerDomains = function() {
    var self = this;
    tnthAjax.getCurrentUser((data) => {
        if (!data || !data.id) return;
        this.userId = data.id;
        tnthAjax.getSubStudyTriggers(this.userId, false, function(data) {
            if (!data || !data.triggers || !data.triggers.domain) {
                return false;
            }
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
            /*
             * display user domain topic(s)
             */
            self.populateDomainDisplay();
            /*
             * show/hide sections based on triggers
             */
            self.initTriggerItemsVis();

            /*
             * construct user report URL
             */
            self.initReportLink();
           //console.log("self.domains? ", self.domains);
           //console.log("has hard triggers ", self.hasHardTrigger);
           //console.log("has soft triggers ", self.hasSoftTrigger);
        });
    });
}

$(document).ready(function() {
    let EmproObj = new emproObj();
    EmproObj.initTriggerDomains();
    EmproObj.initThankyouModal();
});

import EMPRO_DOMAIN_MAPPINGS from "./data/common/empro_domain_mappings.json";
import tnthAjax from "./modules/TnthAjax.js";

var emproObj = function() {
    this.domains = [];
    this.hardTriggerDomains = [];
    this.softTriggerDomains = [];
    this.hasHardTrigger = false;
    this.hasSoftTrigger = false;
    this.userId = 0;
};
emproObj.prototype.populateDomainDisplay = function() {
    this.domains.forEach(domain => {
        $("#emproModal .triggersButtonsContainer").append(
            `<a class="btn btn-empro-primary" href="/substudy-tailored-content#/${domain}" target="_blank">${domain.replace(/_/g, " ")}</a>`
        );
    });
    this.hardTriggerDomains.forEach(domain => {
        $("#emproModal .hardTriggersDisplayList").append(`<li>${domain}</li>`);
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
            for (let key in data.triggers.domain) {
                if (!Object.keys(data.triggers.domain[key]).length) {
                    continue;
                }
                let mappedDomain = EMPRO_DOMAIN_MAPPINGS[key];
                /*
                 * get all user domains that have related triggers
                 */
                if (self.domains.indexOf(mappedDomain) === -1) {
                    self.domains.push(mappedDomain);
                }
                for (let q in data.triggers.domain[key]) {
                    if (data.triggers.domain[key][q] === "hard") {
                        self.hasHardTrigger = true;
                        /*
                         * get all domain topics that have hard trigger
                         */
                        if (self.hardTriggerDomains.indexOf(mappedDomain) === -1) {
                            self.hardTriggerDomains.push(mappedDomain);
                        }
                    }
                    if (data.triggers.domain[key][q] === "soft") {
                        self.hasSoftTrigger = true;
                         /*
                         * get all domain topics that have soft trigger
                         */
                        if (self.softTriggerDomains.indexOf(mappedDomain) === -1) {
                            self.softTriggerDomains.push(mappedDomain);
                        }
                    }
                }
            }

            /*
             * display user domain topic(s)
             */
            self.populateDomainDisplay();
            /*
             * show/hide sections based on triggers
             */
            self.initTriggerItemsVis();
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

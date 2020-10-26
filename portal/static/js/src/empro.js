import EMPRO_DOMAIN_MAPPINGS from "./data/common/empro_domain_mappings.json";
import tnthAjax from "./modules/TnthAjax.js";

var emproObj = function() {
    this.domains = [];
    this.hasHardTrigger = false;
    this.hasSoftTrigger = false;
};
emproObj.prototype.populateDomainDisplay = function() {
    this.domains.forEach(domain => {
        $("#hardTriggerDisplayList").append(`<li>${domain}</li>`);
        $("#hardTriggerButtonsContainer").append(
            `<a class="btn btn-empro-primary" href="/substudy-tailored-content#/${domain}">${domain.replace(/_/g, " ")}</a>`
        );
    });
};
emproObj.prototype.initTriggerDomains = function() {
    var self = this;
    tnthAjax.getSubStudyTriggers(1, false, function(data) {
        console.log("data? ", data)
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
        console.log("self.domains? ", self.domains);
        // self.domains.forEach(domain => {
        //     $("#hardTriggerDisplayList").append(`<li>${domain}</li>`);
        //     $("#hardTriggerButtonsContainer").append(`<a class="btn btn-empro-primary" href="/substudy-tailored-content#/${domain}">${domain.replace(/_/g, " ")}</a>`);
        // });
        self.populateDomainDisplay();
        if (self.hasHardTrigger) {
            $("#emproModal .hard-trigger-item").show();
            $("#emproModal .soft-trigger-item").hide();
            $("#emproModal .no-trigger-item").hide();
            //present thank you modal
            $("#emproModal").modal("show");
        }
        console.log("has hard triggers ", self.hasHardTrigger);
        console.log("has soft triggers ", self.hasSoftTrigger);
    });
}

$(document).ready(function() {
    (new emproObj()).initTriggerDomains();
    $("#emproModal").modal({
        show: false
    });
});

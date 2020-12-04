import EMPRO_DOMAIN_MAPPINGS from "./data/common/empro_domain_mappings.json";
import {EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER} from "./data/common/consts.js";
import tnthAjax from "./modules/TnthAjax.js";
import tnthDate from "./modules/TnthDate.js";

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
            `<a class="btn btn-empro-primary" href="/substudy-tailored-content#/${domain}" target="_blank">
            ${i18next.t("{domain} Tips").replace("{domain}", domain.replace(/_/g, " "))}
            </a>`
        );
    });
    this.hardTriggerDomains.forEach(domain => {
        $("#emproModal .hardTriggersDisplayList").append(`<li>${domain.replace(/_/g, " ")}</li>`);
    });
};
emproObj.prototype.initThankyouModal = function(autoShow) {
    if (!$("#emproModal").length) {
        return;
    }
    $("#emproModal").modal({
        show: autoShow
    });
};
emproObj.prototype.initReportLink = function() {
    /*
     * link to longitudinal report
     */
    $(".longitudinal-report-link").attr("href", `/patients/${this.userId}/longitudinal-report/${EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER}`);
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
emproObj.prototype.init = function() {
    tnthAjax.getCurrentUser((data) => {
        if (!data || !data.id) return;
        this.userId = data.id;
        /*
        * construct user report URL
        */
        this.initReportLink();
        tnthAjax.assessmentReport(this.userId, SUBSTUDY_QUESTIONNAIRE_IDENTIFIER, (data) => {
            if (!data || !data.entry || !data.entry.length) {
               this.initThankyouModal(false);
               return;
            }
            /*
             * make sure data item with the latest authored date is first
             */
            let assessmentData = (data.entry).sort(function(a, b) {
                return new Date(b.authored) - new Date(a.authored);
            });
            let [today, authoredDate, status] = [
                tnthDate.getDateWithTimeZone(new Date(), "yyyy-mm-dd"),
                tnthDate.getDateWithTimeZone(new Date(assessmentData[0]["authored"]), "yyyy-mm-dd"),
                assessmentData[0].status];
            let cachedAccessKey = `EMPRO_MODAL_ACCESSED_${this.userId}_${today}`;
            let assessmentCompleted = String(status).toLowerCase() === "completed";
            /*
             * automatically pops up thank you modal IF sub-study assessment is completed,
             * and sub-study assessment is completed today and the thank you modal has not already popped up today
             */
            let autoShowModal = !localStorage.getItem(cachedAccessKey) && 
                                assessmentCompleted && 
                                today === authoredDate;
            this.initThankyouModal(autoShowModal);
            if (autoShowModal) {
                /*
                 * set thank you modal accessed flag here
                 */
                localStorage.setItem(cachedAccessKey, `true`);
            }
            /*
             * don't continue on to invoke trigger API if sub-study assessment is not completed
             */
            if (!assessmentCompleted) {
                this.initThankyouModal(false);
                return;
            }
            this.initTriggerDomains();
        });
    });
};
emproObj.prototype.setLoadingVis = function(done) {
    if (done) {
        $("#emproModal .items-section").removeClass("loading");
        return;
    }
    $("#emproModal .items-section").addClass("loading");
}
emproObj.prototype.initTriggerDomains = function() {
    var self = this;
    this.setLoadingVis();
    tnthAjax.getSubStudyTriggers(this.userId, false, (data) => {
        if (!data || data.error || !data.triggers || !data.triggers.domain) {
            this.initThankyouModal(false);
            this.setLoadingVis(true);
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
        this.populateDomainDisplay();
        /*
         * show/hide sections based on triggers
         */
        this.initTriggerItemsVis();

        //finish loading
        this.setLoadingVis(true);

       //console.log("self.domains? ", self.domains);
       //console.log("has hard triggers ", self.hasHardTrigger);
       //console.log("has soft triggers ", self.hasSoftTrigger);
    });
};
$(document).ready(function() {
    let EmproObj = new emproObj();
    EmproObj.init();
});

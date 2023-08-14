import EMPRO_DOMAIN_MAPPINGS from "./data/common/empro_domain_mappings.json";
import {
  EPROMS_SUBSTUDY_ID,
  EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER,
} from "./data/common/consts.js";
import tnthAjax from "./modules/TnthAjax.js";
import tnthDate from "./modules/TnthDate.js";
import TestResponsesJson from "./data/common/test/SubStudyQuestionnaireTestData.json";
import TestTriggersJson from "./data/common/test/TestTriggersData.json";
import { getUrlParameter } from "./modules/Utility";

var emproObj = function () {
  this.domains = [];
  this.mappedDomains = [];
  this.hardTriggerDomains = [];
  this.softTriggerDomains = [];
  this.optOutDomains = [];
  this.selectedOptOutDomains = [];
  this.hasHardTrigger = false;
  this.hasSoftTrigger = false;
  this.userId = 0;
  this.visitMonth = 0;

};
emproObj.prototype.populateDomainDisplay = function () {
  if (!$("#emproModal .triggersButtonsContainer").hasClass("added")) {
    this.mappedDomains.forEach((domain) => {
      $("#emproModal .triggersButtonsContainer").append(
        `<a class="btn btn-empro-primary" href="/substudy-tailored-content#/${domain}" target="_blank">
                ${i18next
                  .t("{domain} Tips")
                  .replace("{domain}", domain.replace(/\_/g, " "))}
                </a>`
      );
    });
    $("#emproModal .triggersButtonsContainer").addClass("added");
  }
  if (!$("#emproModal .hardTriggersDisplayList").hasClass("added")) {
    this.hardTriggerDomains.forEach((domain) => {
      $("#emproModal .hardTriggersDisplayList").append(
        `<li>${domain.replace(/\_/g, " ")}</li>`
      );
    });
    $("#emproModal .hardTriggersDisplayList").addClass("added");
  }
};
emproObj.prototype.hasThankyouModal = function () {
  return $("#emproModal").length > 0;
};
emproObj.prototype.initThankyouModal = function (autoShow) {
  if (!this.hasThankyouModal()) {
    return;
  }
  $("#emproModal").modal(autoShow ? "show" : "hide");
};
emproObj.prototype.populateSelectedOptoutUI = function () {
  if (EmproObj.selectedOptOutDomains.length === 0) {
    $(".no-contact-list-wrapper").hide();
    return;
  }
  console.log("selected opt out domains ", this.selectedOptOutDomains);
  var contentHTML = this.selectedOptOutDomains.join(", ");
  $("#emproModal #noContactTriggerList").html("<b>" + contentHTML + "</b>");
  $(".no-contact-list-wrapper").show();
}
emproObj.prototype.populateOptoutInputItems = function () {
  if (!this.hasThankyouModal()) {
    return;
  }
  $("#emproOptOutModal .optout-domains-checkbox-list").html("");
  this.optOutDomains.forEach((domain) => {
    $("#emproOptOutModal .optout-domains-checkbox-list").append(`
            <div class="item"><input type="checkbox" class="ck-input" value="${domain}"><span>${domain.replace(
      /_/g,
      " "
    )}</span></div>
        `);
  });
};
emproObj.prototype.initOptOutElementEvents = function () {
  if (!this.hasOptOutModal()) {
    return;
  }
  $("#emproOptOutModal .btn-submit").on("click", function (e) {
    e.stopPropagation();
    EmproObj.initOptOutModal(false);
    EmproObj.populateSelectedOptoutUI();
    if (EmproObj.selectedOptOutDomains.length) {
      var submitData = {
        "user_id": EmproObj.userId,
        "visit_month": EmproObj.visitMonth,
        "opt_out_domains": EmproObj.selectedOptOutDomains
      }
      // TODO: call API to save
      console.log("data to be submitted ", submitData);
    }
    EmproObj.initThankyouModal(true);
  });

  $("#emproOptOutModal .btn-dismiss").on("click", function (e) {
    e.stopPropagation();
    EmproObj.initOptOutModal(false);
    EmproObj.initThankyouModal(true);
  });
  $("#emproOptOutModal .ck-input").on("click", function () {
    if ($(this).is(":checked")) {
      if (
        !EmproObj.selectedOptOutDomains.find((val) => val === $(this).val())
      ) {
        EmproObj.selectedOptOutDomains.push($(this).val());
      }
    } else {
      EmproObj.selectedOptOutDomains = EmproObj.selectedOptOutDomains.filter((val) => val !== $(this).val());
    }
  });
};
emproObj.prototype.hasOptOutModal = function () {
  return $("#emproOptOutModal").length > 0;
};
emproObj.prototype.initOptOutModal = function (autoShow) {
  if (!this.hasOptOutModal()) {
    return;
  }
  $("#emproOptOutModal").modal(autoShow ? "show" : "hide");
};
emproObj.prototype.initReportLink = function () {
  if (!this.hasThankyouModal()) return;

  let reportURL = `/patients/${this.userId}/longitudinal-report/${EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER}`;
  /*
   * link to longitudinal report
   */
  $(".longitudinal-report-link").attr("href", reportURL);
};
emproObj.prototype.initTriggerItemsVis = function () {
  if (!this.hasThankyouModal()) return;
  if (this.hasHardTrigger) {
    $("#emproModal .hard-trigger").addClass("active");
    $("#emproModal .no-trigger").hide();
    //present thank you modal if hard trigger present
    //$("#emproModal").modal("show");
    return;
  }
  if (this.hasSoftTrigger) {
    $("#emproModal .soft-trigger").addClass("active");
    $("#emproModal .no-trigger").hide();
    return;
  }
};
emproObj.prototype.init = function () {
  tnthAjax.getCurrentUser((data) => {
    if (!data || !data.id) return;
    this.userId = data.id;
    /*
     * construct user report URL
     */
    this.initReportLink();

    const isDebugging = getUrlParameter("debug");

    tnthAjax.getUserResearchStudies(this.userId, "patient", false, (data) => {
      if (
        !isDebugging &&
        data[EPROMS_SUBSTUDY_ID] &&
        data[EPROMS_SUBSTUDY_ID].errors &&
        data[EPROMS_SUBSTUDY_ID].errors.length
      ) {
        //don't present popup if errors e.g. base study questionnaire due
        return false;
      }
      this.setLoadingVis();
      this.initTriggerDomains((result) => {
        if (result && result.error) {
          console.log("Error retrieving trigger data");
          if (result.reason) {
            console.log(reason);
          }
          // TODO figure out if no triggers affect display of thank you modal
        }
        if (result && result.visit_month) {
          this.visitMonth = result.visit_month;
        }

        tnthAjax.assessmentReport(
          this.userId,
          EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER,
          (data) => {
            if (isDebugging) {
              data = TestResponsesJson;
              data.entry[0].authored = new Date().toISOString();
            }
            this.setLoadingVis(true);
            console.log("Questionnaire response data: ", data);
            if (!data || !data.entry || !data.entry.length) {
              return;
            }
            /*
             * make sure data item with the latest authored date is first
             */
            let assessmentData = data.entry.sort(function (a, b) {
              return new Date(b.authored) - new Date(a.authored);
            });
            let assessmentDate = assessmentData[0]["authored"];
            let [today, authoredDate, status] = [
              tnthDate.getDateWithTimeZone(new Date(), "yyyy-mm-dd"),
              tnthDate.getDateWithTimeZone(
                new Date(assessmentDate),
                "yyyy-mm-dd"
              ),
              assessmentData[0].status,
            ];
            let assessmentCompleted =
              String(status).toLowerCase() === "completed";
            console.log(
              "author date ",
              authoredDate,
              " assessment completed ",
              assessmentCompleted
            );

            /*
             * associating each thank you modal popup accessed by assessment date
             */
            let cachedAccessKey = `EMPRO_MODAL_ACCESSED_${this.userId}_${today}_${assessmentDate}`;
            /*
             * automatically pops up thank you modal IF sub-study assessment is completed,
             * and sub-study assessment is completed today and the thank you modal has not already popped up today
             */
            let autoShowModal =
              !localStorage.getItem(cachedAccessKey) &&
              assessmentCompleted &&
              today === authoredDate;

            if (!autoShowModal) {
              // console.log("WHAT?")
              // this.initThankyouModal(false);
              // this.initOptOutModal(false);
              return;
            }

            /*
             * set thank you modal accessed flag here
             */
            // localStorage.setItem(cachedAccessKey, `true`);

            // console.log("auto show ? ", autoShowModal);
            console.log("opt out domain? ", this.optOutDomains);
            if (this.optOutDomains.length > 0) {
              this.populateOptoutInputItems();
              this.initOptOutElementEvents();
              this.initOptOutModal(true);
              this.initThankyouModal(false);
              return;
            }

            this.initThankyouModal(true);

            // /*
            // * don't continue on to invoke trigger API if sub-study assessment is not completed
            // */
            // if (!assessmentCompleted) {
            //     this.initThankyouModal(false);
            //     return;
            // }
          }
        );
      });
    });
  });
};
emproObj.prototype.setLoadingVis = function (done) {
  var LOADING_INDICATOR_ID = ".portal-body .loading-container";
  if (done) {
    $(LOADING_INDICATOR_ID).addClass("hide");
    return;
  }
  $(LOADING_INDICATOR_ID).removeClass("hide");
};
emproObj.prototype.initTriggerDomains = function (callbackFunc) {
  var callback = callbackFunc || function () {};
  if (!$("#emproModal").length) {
    callback({ error: true });
    return;
  }
  var self = this;
  const isDebugging = getUrlParameter("debug");
  tnthAjax.getSubStudyTriggers(this.userId, { maxTryAttempts: 3 }, (data) => {
    if (isDebugging) {
      data = TestTriggersJson;
    }
    if (!data || data.error || !data.triggers || !data.triggers.domain) {
      this.initThankyouModal(false);
      console.log("No trigger data");
      callback({ error: true, reason: "no trigger data" });
      return false;
    }
    console.log("trigger data ", data);
    for (let key in data.triggers.domain) {
      if (!Object.keys(data.triggers.domain[key]).length) {
        continue;
      }
      let mappedDomain = EMPRO_DOMAIN_MAPPINGS[key];
      /*
       * get all user domains that have related triggers
       */
      if (self.domains.indexOf(key) === -1) {
        self.domains.push(key);
      }
      /*
       * get all mapped domains for tailored content
       */
      if (self.mappedDomains.indexOf(mappedDomain) === -1) {
        self.mappedDomains.push(mappedDomain);
      }
      for (let q in data.triggers.domain[key]) {
        if (
          q === "_sequential_hard_trigger_count" &&
          parseInt(data.triggers.domain[key][q]) === 3
        ) {
          if (self.optOutDomains.indexOf(key) === -1) {
            self.optOutDomains.push(key);
          }
          // TODO add key to opt out domain(s)
        }
        if (data.triggers.domain[key][q] === "hard") {
          self.hasHardTrigger = true;
          /*
           * get all domain topics that have hard trigger
           */
          if (self.hardTriggerDomains.indexOf(key) === -1) {
            self.hardTriggerDomains.push(key);
          }
        }
        if (data.triggers.domain[key][q] === "soft") {
          self.hasSoftTrigger = true;
          /*
           * get all domain topics that have soft trigger
           */
          if (self.softTriggerDomains.indexOf(key) === -1) {
            self.softTriggerDomains.push(key);
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

    // //finish loading
    // this.setLoadingVis(true);

    callback(data);

    //console.log("self.domains? ", self.domains);
    //console.log("has hard triggers ", self.hasHardTrigger);
    //console.log("has soft triggers ", self.hasSoftTrigger);
  });
};
let EmproObj = new emproObj();
$(document).ready(function () {
  EmproObj.init();
});

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
  this.submittedOptOutDomains = [];
  this.optOutSubmitData = null;
  this.hasHardTrigger = false;
  this.hasSoftTrigger = false;
  this.userId = 0;
  this.visitMonth = 0;
  this.authorDate = null;
  this.cachedAccessKey = null;
};
emproObj.prototype.getDomainDisplay = function (domain) {
  if (!domain) return "";
  return domain.replace(/_/g, " ");
};
emproObj.prototype.populateDomainDisplay = function () {
  var triggerButtonsContainerElement = $(
    "#emproModal .triggersButtonsContainer"
  );
  if (!triggerButtonsContainerElement.hasClass("added")) {
    this.mappedDomains.forEach((domain) => {
      triggerButtonsContainerElement.append(
        `<a class="btn btn-empro-primary" 
            href="/substudy-tailored-content#/${domain}"
            target="_blank">
            ${i18next
              .t("{domain} Tips")
              .replace("{domain}", this.getDomainDisplay(domain))}
        </a>`
      );
    });
    triggerButtonsContainerElement.addClass("added");
  }
  var hardTriggersDisplayListElement = $(
    "#emproModal .hardTriggersDisplayList"
  );
  if (!hardTriggersDisplayListElement.hasClass("added")) {
    this.hardTriggerDomains.forEach((domain) => {
      hardTriggersDisplayListElement.append(
        `<li>${this.getDomainDisplay(domain)}</li>`
      );
    });
    hardTriggersDisplayListElement.addClass("added");
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
  if (
    !this.submittedOptOutDomains ||
    this.submittedOptOutDomains.length === 0
  ) {
    return;
  }
  console.log("submitted opt out domains: ", this.submittedOptOutDomains);
  var contentHTML = this.submittedOptOutDomains
    .map((domain) => this.getDomainDisplay(domain))
    .join(", ");
  $("#emproModal #noContactTriggerList").html("<b>" + contentHTML + "</b>");
  $(".no-contact-list-wrapper").removeClass("hide");
};
emproObj.prototype.populateOptoutInputItems = function () {
  if (!this.hasThankyouModal()) {
    return;
  }
  var optOutDomainsListElement = $(
    "#emproOptOutModal .optout-domains-checkbox-list"
  );
  optOutDomainsListElement.html("");
  this.optOutDomains.forEach((domain) => {
    optOutDomainsListElement.append(`
            <div class="item">
              <input type="checkbox" class="ck-input ck-input-${domain}" value="${domain}">
              <span class="ck-display" data-domain="${domain}">${this.getDomainDisplay(
      domain
    )}</span>
            </div>
        `);
  });
};
emproObj.prototype.setOptoutSubmitData = function () {
  if (!EmproObj.selectedOptOutDomains || !EmproObj.selectedOptOutDomains.length)
    return;
  var triggerObject = {};
  EmproObj.selectedOptOutDomains.forEach((item) => {
    triggerObject[item] = {
      _opt_out_next_visit: "true",
    };
  });
  var submitData = {
    user_id: EmproObj.userId,
    visit_month: EmproObj.visitMonth,
    triggers: {
      domains: triggerObject,
    },
  };
  console.log("Optout data to be submitted: ", submitData);
  EmproObj.optOutSubmitData = submitData;
};
emproObj.prototype.setOptoutError = function(text) {
  document.querySelector("#emproOptOutModal .error-message").innerText = text;
}
emproObj.prototype.onBeforeSubmitOptoutData = function () {
  // reset error
  EmproObj.setOptoutError("");
  // set data in the correct format for submission to API
  EmproObj.setOptoutSubmitData();
  // disable buttons
  $("#emproOptOutModal .btn-submit").attr("disabled", true);
  $("#emproOptOutModal .btn-dismiss").attr("disabled", true);
  // display saving in progress indicator icon
  $("#emproOptOutModal .saving-indicator-container").removeClass("hide");
};
emproObj.prototype.onAfterSubmitOptoutData = function (data) {
  // enable buttons
  $("#emproOptOutModal .btn-submit").attr("disabled", false);
  $("#emproOptOutModal .btn-dismiss").attr("disabled", false);
  // hide saving in progress indicator icon
  $("#emproOptOutModal .saving-indicator-container").addClass("hide");
  // show error if any
  if (data && data.error) {
    EmproObj.setOptoutError("System error: Unable to save your choices.");
    return false;
  }
  EmproObj.submittedOptOutDomains = EmproObj.selectedOptOutDomains;
  EmproObj.populateSelectedOptoutUI();
  EmproObj.initOptOutModal(false);
  EmproObj.initThankyouModal(true);
  return true;
};
emproObj.prototype.initObservers = function () {
  let errorObserver = new MutationObserver(function (mutations) {
    for (let mutation of mutations) {
      console.log("error mutation? ", mutation);
      if (mutation.type === "childList") {
        // do something here if error occurred
        const errorNode =
          mutation.addedNodes && mutation.addedNodes.length
            ? mutation.addedNodes[0]
            : null;
        let continueContainerElement = document.querySelector(
          "#emproOptOutModal .continue-container"
        );
        if (continueContainerElement) {
          if (errorNode.data) {
            continueContainerElement.classList.remove("hide");
          } else {
            continueContainerElement.classList.add("hide");
          }
        }
      }
    }
  });
  errorObserver.observe(
    document.querySelector("#emproOptOutModal .error-message"),
    {
      childList: true,
    }
  );
  $(window).on("unload", function () {
    errorObserver.disconnect();
  });
  //other observers if needed
};
emproObj.prototype.initOptOutElementEvents = function () {
  if (!this.hasOptOutModal()) {
    return;
  }
  EmproObj.initObservers();

  // submit buttons
  $("#emproOptOutModal .btn-submit").on("click", function (e) {
    e.preventDefault();
    e.stopPropagation();
    EmproObj.onBeforeSubmitOptoutData();
    tnthAjax.setOptoutTriggers(
      EmproObj.userId,
      {
        data: JSON.stringify(EmproObj.optOutSubmitData),
        max_attempts: 1,
      },
      (data) => {
        return EmproObj.onAfterSubmitOptoutData(data);
      }
    );
  });

  // close and dismiss buttons
  $("#emproOptOutModal .btn-dismiss").on("click", function (e) {
    e.stopPropagation();
    EmproObj.initOptOutModal(false);
    EmproObj.initThankyouModal(true);
  });

  // checkboxes
  $("#emproOptOutModal .ck-input").on("click", function () {
    if ($(this).is(":checked")) {
      if (
        !EmproObj.selectedOptOutDomains.find((val) => val === $(this).val())
      ) {
        EmproObj.selectedOptOutDomains.push($(this).val());
      }
    } else {
      EmproObj.selectedOptOutDomains = EmproObj.selectedOptOutDomains.filter(
        (val) => val !== $(this).val()
      );
    }
  });

  // checkbox display text, clicking on which should check or uncheck the associated checkbox
  $("#emproOptOutModal .ck-display").on("click", function () {
    var domain = $(this).attr("data-domain");
    var associatedCkInput = $("#emproOptOutModal .ck-input-" + domain);
    if (associatedCkInput.is(":checked"))
      associatedCkInput.prop("checked", false);
    else associatedCkInput.prop("checked", true);
  });

  // continue button that displays when error
  $("#emproOptOutModal .continue-button").on("click", function () {
    EmproObj.initThankyouModal(true);
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

    this.setLoadingVis(true);

    tnthAjax.getUserResearchStudies(this.userId, "patient", false, (data) => {
      if (
        !isDebugging &&
        data[EPROMS_SUBSTUDY_ID] &&
        data[EPROMS_SUBSTUDY_ID].errors &&
        data[EPROMS_SUBSTUDY_ID].errors.length
      ) {
        //don't present popup if errors e.g. base study questionnaire due
        this.setLoadingVis();
        return false;
      }
      this.initTriggerDomains((result) => {
        if (result && result.error) {
          console.log("Error retrieving trigger data");
          if (result.reason) {
            console.log(reason);
          }
        }
        tnthAjax.assessmentReport(
          this.userId,
          EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER,
          (data) => {
            this.setLoadingVis(); // hide loading indicator when done
            if (isDebugging) {
              data = TestResponsesJson;
              data.entry[0].authored = new Date().toISOString();
            }
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
              "today ",
              today,
              "author date ",
              authoredDate,
              " assessment completed ",
              assessmentCompleted
            );

            this.authorDate = authoredDate;

            /*
             * associating each thank you modal popup accessed by assessment date
             */
            let cachedAccessKey = `EMPRO_MODAL_ACCESSED_${this.userId}_${today}_${authoredDate}`;
            this.cachedAccessKey = cachedAccessKey;

            const clearCacheData = getUrlParameter("clearCache");
            if (clearCacheData) {
              localStorage.removeItem(this.cachedAccessKey);
            }
            /*
             * automatically pops up thank you modal IF sub-study assessment is completed,
             * and sub-study assessment is completed today and the thank you modal has not already popped up today
             */
            let autoShowModal =
              !localStorage.getItem(cachedAccessKey) &&
              assessmentCompleted &&
              today === authoredDate;

            if (!autoShowModal) {
              return;
            }

            /*
             * set thank you modal accessed flag here
             */
            localStorage.setItem(cachedAccessKey, `true`);

            // console.log("Opt out domain? ", this.optOutDomains);
            if (this.optOutDomains.length > 0) {
              this.populateOptoutInputItems();
              this.initOptOutElementEvents();
              this.initOptOutModal(true);
              this.initThankyouModal(false);
              return;
            }

            this.initThankyouModal(true);
          }
        );
      });
    });
  });
};
emproObj.prototype.setLoadingVis = function (loading) {
  var LOADING_INDICATOR_ID = ".portal-body .loading-container";
  if (!loading) {
    $(LOADING_INDICATOR_ID).addClass("hide");
    return;
  }
  $(LOADING_INDICATOR_ID).removeClass("hide");
};
emproObj.prototype.processTriggerData = function (data) {
  if (!data || data.error || !data.triggers || !data.triggers.domain) {
    //this.initThankyouModal(false);
    console.log("No trigger data");
    return false;
  }
  var self = this;
  console.log("trigger data ", data);

  // set visit month related to trigger data
  this.visitMonth = data.visit_month;

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
      // if sequence count > 1, that means it has been asked before
      if (
        q === "_sequential_hard_trigger_count" &&
        parseInt(data.triggers.domain[key][q]) > 1
      ) {
        // console.log("domain? ", key, " sequence ", parseInt(data.triggers.domain[key][q]));
        if (self.optOutDomains.indexOf(key) === -1) {
          self.optOutDomains.push(key);
        }
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
};
emproObj.prototype.initTriggerDomains = function (callbackFunc) {
  var callback = callbackFunc || function () {};
  if (!this.hasThankyouModal()) {
    callback({ error: true });
    return;
  }
  //var self = this;
  const isDebugging = getUrlParameter("debug");
  tnthAjax.getSubStudyTriggers(this.userId, { maxTryAttempts: 3 }, (data) => {
    if (isDebugging) {
      data = TestTriggersJson;
    }
    if (!data || data.error || !data.triggers || !data.triggers.domain) {
      callback({ error: true, reason: "no trigger data" });
      return false;
    }

    this.processTriggerData(data);

    /*
     * display user domain topic(s)
     */
    this.populateDomainDisplay();
    /*
     * show/hide sections based on triggers
     */
    this.initTriggerItemsVis();

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

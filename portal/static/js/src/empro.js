import EMPRO_DOMAIN_MAPPINGS from "./data/common/empro_domain_mappings.json";
import {
  EPROMS_MAIN_STUDY_ID,
  EPROMS_SUBSTUDY_ID,
  EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER,
  EMPRO_TRIGGER_STATE_OPTOUT_KEY,
} from "./data/common/consts.js";
import tnthAjax from "./modules/TnthAjax.js";
import tnthDate from "./modules/TnthDate.js";
import { CurrentUserObj } from "./mixins/CurrentUser.js";
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
  this.userOrgs = [];
  this.visitMonth = 0;
  this.authorDate = null;
  this.cachedAccessKey = null;
  this.optOutNotAllowed = false;
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
  console.log("Submitted opt out domains: ", this.submittedOptOutDomains);
  var contentHTML = this.submittedOptOutDomains
    .map((domain) => this.getDomainDisplay(domain))
    .join(", ");
  $("#emproModal #noContactTriggerList").html("<b>" + contentHTML + "</b>");
  $("#emproModal .no-contact-list-wrapper").removeClass("hide");
};
emproObj.prototype.populateOptoutInputItems = function () {
  var optOutDomainsListElement = $(
    "#emproOptOutModal .optout-domains-checkbox-list"
  );
  if (!optOutDomainsListElement.length) return;
  if (!this.optOutDomains || !this.optOutDomains.length) return;
  if (optOutDomainsListElement.find(".ck-input").length) return;
  // render checkbox input element for each domain
  this.optOutDomains.forEach((domain) => {
    optOutDomainsListElement.append(`
            <div class="item">
              <input type="checkbox" class="ck-input ck-input-${domain}" value="${domain}">
              <span class="ck-display" data-domain="${domain}">
                ${this.getDomainDisplay(domain)}
              </span>
            </div>
        `);
  });
};
emproObj.prototype.hasSelectedOptOutDomains = function () {
  return (
    EmproObj.selectedOptOutDomains && EmproObj.selectedOptOutDomains.length
  );
};
emproObj.prototype.setOptoutSubmitData = function () {
  if (!EmproObj.hasSelectedOptOutDomains()) {
    return;
  }
  var triggerObject = {};
  EmproObj.selectedOptOutDomains.forEach((item) => {
    triggerObject[item] = {
      [EMPRO_TRIGGER_STATE_OPTOUT_KEY]: true,
    };
  });
  var submitData = {
    user_id: EmproObj.userId,
    visit_month: EmproObj.visitMonth,
    triggers: {
      domains: triggerObject,
    },
  };
  console.log("Data to be submitted for optout: ", submitData);
  EmproObj.optOutSubmitData = submitData;
};
emproObj.prototype.setError = function (strSeletor, text) {
  if (!document.querySelector(strSeletor)) return;
  document.querySelector(strSeletor).innerText = text;
};
emproObj.prototype.setButtonsDisableState = function (
  strSelector,
  boolDisable
) {
  $(strSelector).attr("disabled", boolDisable);
};
emproObj.prototype.toggleSavingIndicator = function (strSelector, boolShow) {
  if (boolShow) {
    $(strSelector).removeClass("hide");
    return;
  }
  $(strSelector).addClass("hide");
};
emproObj.prototype.setOptoutError = function (text) {
  EmproObj.setError("#emproOptOutModal .error-message", text);
};
emproObj.prototype.setOptoutButtonsState = function (boolDisable) {
  EmproObj.setButtonsDisableState(
    "#emproOptOutModal .btn-submit, #emproOptOutModal .btn-dismiss",
    boolDisable
  );
};
emproObj.prototype.toggleOptoutSavingIndicator = function (boolShow) {
  EmproObj.toggleSavingIndicator(
    "#emproOptOutModal .saving-indicator-container",
    boolShow
  );
};
emproObj.prototype.hasErrorText = function () {
  return !!$("#emproOptOutModal .error-message").text().trim();
};
emproObj.prototype.onBeforeSubmitOptoutData = function () {
  // reset error
  EmproObj.setOptoutError("");
  // set data in the correct format for submission to API
  EmproObj.setOptoutSubmitData();
  // disable buttons
  EmproObj.setOptoutButtonsState(true);
  // display saving in progress indicator icon
  EmproObj.toggleOptoutSavingIndicator(true);
};
emproObj.prototype.onAfterSubmitOptoutData = function (data) {
  // hide saving in progress indicator icon
  EmproObj.toggleOptoutSavingIndicator(false);
  // show error if any
  if (data && data.error) {
    // enable buttons
    EmproObj.setOptoutButtonsState(false);
    EmproObj.setOptoutError(
      i18next.t(
        "System error: Unable to save your choices.\r\nPlease click 'Submit' to try again."
      )
    );
    return false;
  }
  // show successful save feedback
  $("#emproOptOutModal .save-success-indicator-container").removeClass("hide");

  setTimeout(() => {
    // enable buttons
    EmproObj.setOptoutButtonsState(false);
    EmproObj.submittedOptOutDomains = EmproObj.selectedOptOutDomains;
    EmproObj.populateSelectedOptoutUI();
    // TODO different text will appear in thank you modal, waiting for approval before changes
    // EmproObj.handleFullOptout();
    EmproObj.initOptOutModal(false);
    EmproObj.initThankyouModal(true);
  }, 1000);
  return true;
};
emproObj.prototype.handleNoOptOutSelection = function () {
  EmproObj.initOptOutModal(false);
  EmproObj.initThankyouModal(true);
};
emproObj.prototype.isFullOptout = function () {
  return (
    this.submittedOptOutDomains.length > 0 &&
    this.submittedOptOutDomains.length === this.hardTriggerDomains.length
  );
};
emproObj.prototype.handleFullOptout = function () {
  if (this.isFullOptout()) {
    $(".full-optout-hide").addClass("hide");
  }
};
emproObj.prototype.handleSubmitOptoutData = function () {
  // if (!EmproObj.hasErrorText() && !EmproObj.hasSelectedOptOutDomains()) {
  //   EmproObj.setOptoutError(
  //     i18next.t(
  //       "You didn't select anything. Are you sure?\r\nIf so, click 'Dismiss' to continue."
  //     )
  //   );
  //   return;
  // }
  if (!EmproObj.hasSelectedOptOutDomains()) {
    // allow user to continue without selecting any option
    EmproObj.handleNoOptOutSelection();
    return;
  }
  EmproObj.onBeforeSubmitOptoutData();
  tnthAjax.setOptoutTriggers(
    EmproObj.userId,
    {
      data: JSON.stringify(EmproObj.optOutSubmitData),
      max_attempts: 3,
      timeout: 10000, // 10 seconds
    },
    (data) => {
      return EmproObj.onAfterSubmitOptoutData(data);
    }
  );
};
emproObj.prototype.initOptOutElementEvents = function () {
  if (!this.hasOptOutModal()) {
    return;
  }
  // x, close button in OPT OUT modal, need to make sure thank you modal is initiated after closing out opt out modal
  $("#emproOptOutModal .close").on("click", function (e) {
    EmproObj.initOptOutModal(false);
    EmproObj.initThankyouModal(true);
    EmproObj.postToAudit("Opt out modal dismissed");
  });

  // submit buttons
  $("#emproOptOutModal .btn-submit").on("click", function (e) {
    e.preventDefault();
    e.stopPropagation();
    EmproObj.handleSubmitOptoutData();
  });

  // close and dismiss buttons
  $("#emproOptOutModal .btn-dismiss").on("click", function (e) {
    e.stopPropagation();
    if (!EmproObj.hasErrorText()) {
      if (!EmproObj.hasSelectedOptOutDomains()) {
        EmproObj.setOptoutError(
          i18next.t(
            "You didn't select anything. Are you sure?\r\nIf so, click 'Dismiss' again to continue."
          )
        );
        return;
      } else {
        EmproObj.setOptoutError(
          i18next.t(
            "You have made selection(s). Click 'Submit' to save your selection(s).\r\nOtherwise, click 'Dismiss' again to continue."
          )
        );
        return;
      }
    }
    EmproObj.initOptOutModal(false);
    EmproObj.initThankyouModal(true);
  });

  // checkboxes
  $("#emproOptOutModal .ck-input").on("click", function () {
    EmproObj.setOptoutError("");
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
    EmproObj.setOptoutError("");
    var domain = $(this).attr("data-domain");
    var associatedCkInput = $("#emproOptOutModal .ck-input-" + domain);
    associatedCkInput.trigger("click");
  });

  // continue button that displays when error
  $("#emproOptOutModal .continue-button").on("click", function () {
    EmproObj.initOptOutModal(false);
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
  $("#emproOptOutModal").modal({
    backdrop: "static",
    keyboard: false,
  });
  $("#emproOptOutModal").modal(autoShow ? "show" : "hide");
};
emproObj.prototype.onDetectOptOutDomains = function () {
  this.populateOptoutInputItems();
  this.initOptOutElementEvents();
  this.initOptOutModal(true);
  this.initThankyouModal(false);
  this.postToAudit("Opt out modal presented");
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
emproObj.prototype.checkUserOrgAllowOptOut = function (
  userId,
  userOrgs,
  callback
) {
  callback = callback || function () {};
  if (!userId || !userOrgs || !userOrgs.length) {
    callback(false);
    return;
  }
  const OPT_OUT_ORGS_KEY = "OPT_OUT_DISABLED_ORG_IDS";
  // get opt out disabled orgs from setting
  tnthAjax.setting(OPT_OUT_ORGS_KEY, userId, null, (data) => {
    if (!data || !data[OPT_OUT_ORGS_KEY]) {
      callback(false);
      return;
    }
    const optOutDisabledOrgs = data[OPT_OUT_ORGS_KEY];
    if (!optOutDisabledOrgs.length) {
      callback(false);
      return;
    }
    const orgsToCompare = optOutDisabledOrgs.map((orgId) => parseInt(orgId));
    // callback return true if the userOrg is in the OPT OUT disabled org list
    callback(
      !!userOrgs.find((orgId) => orgsToCompare.indexOf(parseInt(orgId)) !== -1)
    );
  });
};
emproObj.prototype.postToAudit = function (message) {
  if (!message) return;
  tnthAjax.postAuditLog(this.userId, {
    message: message,
    context: "assessment"
  });
};
emproObj.prototype.init = function () {
  const self = this;
  this.setLoadingVis(true);
  CurrentUserObj.initCurrentUser(() => {
    this.userId = CurrentUserObj.getUserId();
    this.userOrgs = CurrentUserObj.getUserOrgs();
    const isDebugging = getUrlParameter("debug");
    if (!this.userId || !this.userOrgs || !this.userOrgs.length) {
      this.setLoadingVis(false);
      return;
    }
    tnthAjax.getUserResearchStudies(this.userId, "patient", false, (data) => {
      if (
        !isDebugging &&
        data[EPROMS_MAIN_STUDY_ID] &&
        data[EPROMS_MAIN_STUDY_ID].ready
      ) {
        //don't present popup if main study is due
        this.setLoadingVis();
        return false;
      }
      if (
        !isDebugging &&
        (!data[EPROMS_SUBSTUDY_ID] ||
          (data[EPROMS_SUBSTUDY_ID] &&
            (data[EPROMS_SUBSTUDY_ID].ready ||
              (data[EPROMS_SUBSTUDY_ID].errors &&
                data[EPROMS_SUBSTUDY_ID].errors.length))))
      ) {
        //don't present popup if EMPRO study errors or EMPRO is due
        this.setLoadingVis();
        return false;
      }
      /*
       * construct user report URL
       */
      this.initReportLink();

      tnthAjax.assessmentReport(
        this.userId,
        EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER,
        (data) => {
          if (isDebugging) {
            if (!data) {
              data = TestResponsesJson;
            }
          }
          console.log("Questionnaire response data: ", data);
          // no questionnaire data, just return here
          if (!data || !data.entry || !data.entry.length) {
            this.setLoadingVis(); // hide loading indicator
            return;
          }
          /*
           * make sure data item with the latest authored date is first
           */
          let assessmentData = data.entry.sort(function (a, b) {
            return new Date(b.authored) - new Date(a.authored);
          });
          if (isDebugging) {
            assessmentData[0].authored = new Date().toISOString();
            assessmentData[0].status = "completed";
          }
          let assessmentDate = assessmentData[0]["authored"];
          let [today, authoredDate, status, identifier] = [
            tnthDate.getDateWithTimeZone(new Date(), "yyyy-mm-dd"),
            tnthDate.getDateWithTimeZone(
              new Date(assessmentDate),
              "yyyy-mm-dd"
            ),
            assessmentData[0].status,
            assessmentData[0].identifier && assessmentData[0].identifier.value
              ? assessmentData[0].identifier.value
              : assessmentDate,
          ];
          let assessmentCompleted =
            String(status).toLowerCase() === "completed";
          console.log(
            "today ",
            today,
            "author date ",
            authoredDate,
            " assessment completed ",
            assessmentCompleted,
            " identifier ",
            identifier
          );

          this.authorDate = authoredDate;

          /*
           * associating each thank you modal popup accessed by assessment date
           */
          let cachedAccessKey = `EMPRO_MODAL_ACCESSED_${this.userId}_${today}_${authoredDate}_${identifier}`;
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

          console.log("Should show EMPRO thank you modal ", autoShowModal);

          this.initTriggerDomains(
            {
              // retry up to at least a minute, the call times out a 5 seconds, retry after 1.5 ~ 2.5 second each time (including browser connection time)
              // so 5 * 14 * 2.5 seconds (175 seconds, approximately 2 minute and 35 seconds)
              // hopefully gives the server plenty of time to process triggers
              maxTryAttempts: !autoShowModal ? 0 : isDebugging ? 0 : 14, //no need to retry if thank you modal isn't supposed to show
              clearCache: autoShowModal,
            },
            (result) => {
              this.setLoadingVis(); // hide loading indicator when done
              if (result && result.error) {
                console.log("Error retrieving trigger data");
                if (result.reason) {
                  console.log("Error retrieving trigger data: ", result.reason);
                }
              }
              /*
               * set thank you modal accessed flag here
               */
              if (autoShowModal) {
                localStorage.setItem(this.cachedAccessKey, `true`);
                // console.log("Opt out domain? ", this.optOutDomains);
                if (this.optOutDomains.length > 0) {
                  this.onDetectOptOutDomains();
                  return;
                }
              }

              this.initThankyouModal(autoShowModal);
            }
          );
        }
      );
    });
  });
};
emproObj.prototype.setLoadingVis = function (loading) {
  var LOADING_INDICATOR_ID = ".portal-body .wait-indicator-wrapper";
  if (!loading) {
    $(LOADING_INDICATOR_ID).addClass("hide");
    return;
  }
  $(LOADING_INDICATOR_ID).removeClass("hide");
};
emproObj.prototype.processTriggerData = function (data, historyData) {
  if (!data || data.error || !data.triggers || !data.triggers.domain) {
    console.log("No trigger data");
    return false;
  }

  // set visit month related to trigger data
  this.visitMonth = data.visit_month;

  var self = this;

  let processedHistoryData = [];
  if (historyData) {
    processedHistoryData = historyData
      .filter((item) => item.triggers && item.triggers.domain)
      .map((item) => item.triggers.domain);
  }

  console.log("processed history data ", processedHistoryData);

  if (!data || !data.triggers || !data.triggers.domain) {
    return;
  }

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

      if (self.optOutNotAllowed) {
        continue;
      }
      const MAX_ALLOWED_OPT_OUT_NUM = 3;
      // check if user has chosen to opt out this domain 3 times before
      const hasReachedMaxOptOut = processedHistoryData.find(
        (item) =>
          item[key] &&
          parseInt(item[key]["_total_opted_out"]) >= MAX_ALLOWED_OPT_OUT_NUM
      );
      // if sequence count >= 3, the user can choose to opt_out of respective domain
      if (
        !hasReachedMaxOptOut &&
        q === "_sequential_hard_trigger_count" &&
        parseInt(data.triggers.domain[key][q]) >= 3
      ) {
        // console.log("domain? ", key, " sequence ", parseInt(data.triggers.domain[key][q]));
        if (self.optOutDomains.indexOf(key) === -1) {
          self.optOutDomains.push(key);
        }
      }
    }
  }
};
emproObj.prototype.initTriggerDomains = function (params, callbackFunc) {
  var callback = callbackFunc || function () {};
  if (!this.hasThankyouModal()) {
    callback({ error: true });
    return;
  }
  const isDebugging = getUrlParameter("debug");
  this.checkUserOrgAllowOptOut(
    this.userId,
    this.userOrgs,
    (isOptOutDisabled) => {
      this.optOutNotAllowed = isOptOutDisabled;
      console.log("Opt out is disabled ", isOptOutDisabled);
      Promise.allSettled([
        // current triggers
        new Promise((resolve, reject) =>
          tnthAjax.getSubStudyTriggers(this.userId, params, (data) => {
            if (data && data.error) {
              reject({ error: true });
              return;
            }
            resolve(data);
          })
        ),
        // trigger history
        new Promise((resolve, reject) =>
          tnthAjax.getTriggersHistory(this.userId, params, (data) => {
            if (data && data.error) {
              reject({ error: true });
              return;
            }
            resolve(data);
          })
        ),
      ]).then((results) => {
        let currentTriggerData =
          results[0] && results[0].status === "fulfilled" && results[0].value
            ? results[0].value
            : null;
        const historyTriggerData =
          results[1] && results[1].status === "fulfilled" && results[1].value
            ? results[1].value
            : null;
        if (
          isDebugging &&
          (!currentTriggerData ||
            (currentTriggerData && !currentTriggerData.triggers))
        ) {
          currentTriggerData = TestTriggersJson;
        }
        if (!currentTriggerData) {
          callback({ error: true, reason: "no trigger data" });
          return false;
        }
        this.processTriggerData(currentTriggerData, historyTriggerData);
        /*
         * display user domain topic(s)
         */
        this.populateDomainDisplay();
        /*
         * show/hide sections based on triggers
         */
        this.initTriggerItemsVis();

        callback(currentTriggerData);
      });
    }
  );
};
let EmproObj = new emproObj();
$(document).ready(function () {
  EmproObj.init();
});

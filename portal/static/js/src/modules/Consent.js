import OrgTool from "./OrgTool";
import tnthAjax from "./TnthAjax";
import tnthDates from "./TnthDate";
import CONSENT_ENUM from "./CONSENT_ENUM";
import Utility from "./Utility";

export default { /*global i18next datepicker $*/
    orgTool: null,
    getOrgTool: function() {
        if (!this.orgTool) {
            this.orgTool = new OrgTool();
            this.orgTool.init();
        }
        return this.orgTool;
    },
    getModalElementSelectors: function() {
        return "#consentContainer .modal, #defaultConsentModal, #defaultConsentContainer .modal";
    },
    initFieldEvents: function(userId) {
        var __self = this, orgTool = this.getOrgTool(), modalElements = $(this.getModalElementSelectors());
        var closeButtons = modalElements.find("button.btn-consent-close, button[data-dismiss]");
        $("#consentHistoryModal").modal({"show": false});
        modalElements.each(function() {
            var agreemntUrl = $(this).find(".agreement-url").val();
            if (/stock\-org\-consent/.test(agreemntUrl)) {
                $(this).find(".terms-wrapper").hide();
            }
        });
        modalElements.find("input[name='toConsent']").off("click").on("click", function(e) {
            e.stopPropagation();
            closeButtons.attr("disabled", true);
            var orgId = $(this).attr("data-org");
            var postUpdate = function(orgId, errorMessage) {
                if (errorMessage) {
                    $("#"+orgId+"_consentAgreementMessage").html(errorMessage);
                } else {
                    $("#"+orgId+"_consentAgreementMessage").html("");
                    setTimeout(function() { modalElements.modal("hide"); __self.removeObsoleteConsent(userId); }, 250);
                }
                $("#" + orgId + "_loader.loading-message-indicator").hide();
                closeButtons.attr("disabled", false);
            };
            $("#" + orgId + "_loader.loading-message-indicator").show();
            if ($(this).val() === "yes") {
                var params = CONSENT_ENUM.consented;
                params.org = orgId;
                params.agreementUrl = $("#" + orgId + "_agreement_url").val() || __self.getDefaultAgreementUrl(orgId);
                setTimeout(function() {tnthAjax.setConsent(userId, params,"",false, function(data) {
                    postUpdate(orgId, data.error);
                });}, 50);
            } else {
                tnthAjax.deleteConsent(userId, {"org": orgId});
                postUpdate(orgId);
            }
        });

        closeButtons.off("click").on("click", function(e) {
            e.preventDefault();
            e.stopPropagation();
            setTimeout(function() { location.reload(); }, 10);
        });
        modalElements.each(function() {
            $(this).on("hidden.bs.modal", function() {
                if ($(this).find("input[name='toConsent']:checked").length > 0) {
                    $("#userOrgs input[name='organization']").each(function() {
                        $(this).removeAttr("data-require-validate");
                    });
                    orgTool.updateOrgs(userId, $("#clinics"), true);
                }
            });
            $(this).on("show.bs.modal", function() {
                var checkedOrg = $("#userOrgs input[name='organization']:checked");
                var shortName = checkedOrg.attr("data-short-name") || checkedOrg.attr("data-org-name") || orgTool.getShortName(checkedOrg.val());
                if (shortName) {
                    $(this).find(".consent-clinic-name").text(i18next.t(shortName));
                }
                $("#consentContainer input[name='toConsent']").each(function() {
                    $(this).prop("checked", false);
                });
                var o = $(this);
                $(this).find("button.btn-consent-close, button[data-dismiss]").attr("disabled", false).show();
                $(this).find(".content-loading-message-indicator").fadeOut(50, function() {
                    o.find(".main-content").removeClass("tnth-hide");
                });
            });
        });
    },
    initConsentListModalEvent: function() {
        $("#profileConsentListModal").off("show.bs.modal").on("show.bs.modal", function(e) {
            var relatedTarget = $(e.relatedTarget), orgId = $(e.relatedTarget).attr("data-orgId"), agreementUrl = relatedTarget.attr("data-agreementUrl");
            var userId = relatedTarget.attr("data-userId"), status = relatedTarget.attr("data-status");
            $(this).find("input[class='radio_consent_input']").each(function() {
                $(this).attr({ "data-agreementUrl": agreementUrl, "data-userId": userId, "data-orgId": orgId,
                    "data-researchStudyId": relatedTarget.attr("data-researchStudyId")
                });
                if (String($(this).val()) === String(status)) {
                    $(this).prop("checked", true);
                }
                if ((status === "unknown") && $(this).val() !== "consented") {
                    $(this).closest("label").hide();
                } else {
                    $(this).closest("label").show();
                }
            });
        });
        $("#profileConsentListModal input[class='radio_consent_input']").each(function() {
            $(this).off("click").on("click", function() { //remove pre-existing events as when consent list is re-drawn
                var o = CONSENT_ENUM[$(this).val()];
                if (o) {
                    o.org = $(this).attr("data-orgId");
                    o.agreementUrl = $(this).attr("data-agreementUrl");
                    o.research_study_id = $(this).attr("data-researchStudyId");
                }
                if (String($(this).val()) === "purged") {
                    tnthAjax.deleteConsent($(this).attr("data-userId"), o, function() {
                        $("#profileConsentListModal").removeClass("fade").modal("hide");
                        $("#profileConsentListModal").trigger("updated");
                    });
                    $("#profileConsentListModal").trigger("updated");
                } else if (String($(this).val()) === "suspended") {
                    tnthAjax.withdrawConsent($(this).attr("data-userId"), $(this).attr("data-orgId"), o, function() {
                        $("#profileConsentListModal").removeClass("fade").modal("hide");
                        $("#profileConsentListModal").trigger("updated");
                    });
                } else {
                    tnthAjax.setConsent($(this).attr("data-userId"), o, $(this).val(), false, function() {
                        $("#profileConsentListModal").removeClass("fade").modal("hide");
                        $("#profileConsentListModal").trigger("updated");
                    });
                }
            });
        });
    },
    validateConsentDateFields: function(d, h, m, s) {
        var errorMessage = "";
        var isValid = tnthDates.isValidDefaultDateFormat(d);
        if (d && !isValid) {
            errorMessage += (errorMessage ? "<br/>" : "") + i18next.t("Date must in the valid format.");
        }
        if (h && !(/^([1-9]|0[0-9]|1\d|2[0-3])$/.test(h))) { //validate hour [0]0
            errorMessage += (errorMessage ? "<br/>" : "") + i18next.t("Hour must be in valid format, range 0 to 23.");
        }
        if (m && !(/^(0[0-9]|[1-9]|[1-5]\d)$/.test(m))) {
            errorMessage += (errorMessage ? "<br/>" : "") + i18next.t("Minute must be in valid format, range 0 to 59.");
        }
        if (s && !(/^(0[0-9]|[1-9]|[1-5]\d)$/.test(s))) {
            errorMessage += (errorMessage ? "<br/>" : "") + i18next.t("Second must be in valid format, range 0 to 59.");
        }
        return errorMessage;
    },
    initConsentDateFieldEvents: function() {
        $("#consentDateModal").on("shown.bs.modal", function(e) {
            $(this).find(".consent-date").focus();
            $(this).addClass("active");
            var relatedTarget = $(e.relatedTarget), orgId = relatedTarget.attr("data-orgId");
            var agreementUrl = relatedTarget.attr("data-agreementUrl"), userId = relatedTarget.attr("data-userId"), status = relatedTarget.attr("data-status");
            $(this).find(".data-current-consent-date").text(tnthDates.formatDateString(relatedTarget.attr("data-signed-date"), "d M y hh:mm:ss")); //display user friendly date
            $(this).find("input.form-control").each(function() {
                $(this).attr({
                    "data-agreementUrl": agreementUrl,
                    "data-userId": userId,
                    "data-orgId": orgId,
                    "data-status": status,
                    "data-researchStudyId": relatedTarget.attr("data-researchStudyId")
                });
                if ($(this).attr("data-default-value")) {
                    $(this).val($(this).attr("data-default-value"));
                } else {
                    $(this).val("");
                }
            });
            $("#consentDateModal [data-dismiss]").on("click", function() {
                $(this).modal("hide");
            });
            $("#consentDateContainer").show();
            $("#consentDateLoader").hide();
            $("#consentDateModalError").html("");
        });
        $("#consentDateModal").on("hidden.bs.modal", function() {
            $(this).removeClass("active");
        });
        $("#consentDateModal .consent-date").datepicker({"format": "d M yyyy","forceParse": false, "autoclose": true});
        $("#consentDateModal .consent-hour, #consentDateModal .consent-minute, #consentDateModal .consent-second").each(function() {
            Utility.convertToNumericField($(this));
        });
        var self = this;
        $("#consentDateModal .consent-date, #consentDateModal .consent-hour, #consentDateModal .consent-minute, #consentDateModal .consent-second").each(function() {
            $(this).on("change", function() {
                var d = $("#consentDateModal_date").val(), h = $("#consentDateModal_hour").val(), m = $("#consentDateModal_minute").val(), s = $("#consentDateModal_second").val();
                var errorMessage = self.validateConsentDateFields(d, h, m, s);
                if (errorMessage) {
                    $("#consentDateModal_date").datepicker("hide");
                }
                $("#consentDateModalError").html(errorMessage);
            });
        });

        $("#consentDateModal .btn-submit").off("click").on("click", function() {
            var ct = $("#consentDateModal_date"), o = CONSENT_ENUM[ct.attr("data-status")];
            if (!ct.val()) {
                $("#consentDateModalError").text(i18next.t("You must enter a date/time"));
                return false;
            }
            var h = $("#consentDateModal_hour").val(),m = $("#consentDateModal_minute").val(),s = $("#consentDateModal_second").val();
            var dt = new Date(ct.val()); //2017-07-06T22:04:50 format
            var int = function(n) {
                if (!n) return 0;
                return parseInt(n);
            }
            var cDate = dt.setHours(int(h), int(m), int(s));
            cDate = tnthDates.formatDateString(cDate, "system");
            o.org = ct.attr("data-orgId");
            o.agreementUrl = ct.attr("data-agreementUrl");
            o.acceptance_date = cDate;
            o.testPatient = true;
            o.research_study_id = ct.attr("data-researchStudyId");
            setTimeout((function() { $("#consentDateContainer").hide();})(), 200);
            setTimeout((function() {$("#consentDateLoader").show();})(), 450);
            $("#consentDateModal button[data-dismiss]").attr("disabled", true); //disable close buttons while processing reques
            setTimeout(tnthAjax.setConsent(ct.attr("data-userId"), o, ct.attr("data-status"), true, function(data) {
                if (!data || data.error) {
                    $("#consentDateModalError").text(i18next.t("Error processing data.  Make sure the date is in the correct format."));
                    setTimeout(function() {
                        $("#consentDateContainer").show();
                        $("#consentDateModal button[data-dismiss]").attr("disabled", false);
                        $("#consentDateLoader").hide();
                    }, 450);
                    return false;
                }
                $("#consentDateModal button[data-dismiss]").attr("disabled", false);
                $("#consentDateModal").removeClass("fade").modal("hide");
                $("#consentDateModal").trigger("updated");
            }), 100);
        });
    },
    getConsentModal: function(parentOrg) {
        var orgTool = this.getOrgTool();
        if (!parentOrg) { return false; }
        var __modal = $("#" + parentOrg + "_consentModal");
        if (__modal.length) {
            return __modal;
        }
        return this.getDefaultModal(orgTool.getSelectedOrg());
    },
    getConsentOrgShortName: function(orgItem, el) {
        return (orgItem && orgItem.shortname) ? orgItem.shortname : ($(el).attr("data-parent-name") || $(el).closest("label").text());
    },
    getDefaultModal: function(o) {
        if (!o) { return false;}
        var orgTool = this.getOrgTool();
        var orgId = orgTool.getElementParentOrg(o), orgModalId = orgId + "_defaultConsentModal", orgElement = $("#"+orgModalId);
        if (orgElement.length) { return orgElement; }
        var orgsList = orgTool.getOrgsList(), orgItem = orgsList.hasOwnProperty(orgId) ? orgsList[orgId]: null,
            orgName = this.getConsentOrgShortName(orgItem, o);
        var title = i18next.t("Consent to share information");
        var consentText = i18next.t("I consent to sharing information with <span class='consent-clinic-name'>{orgName}</span>.".replace("{orgName}", orgName));
        var orgModalElement = $("#defaultConsentModal").clone(true);
        var tempHTML = orgModalElement.html();
        if (tempHTML) {
            tempHTML = tempHTML.replace(/\{orgId\}/g, orgId)
                .replace(/\{close\}/g, i18next.t("Close"))
                .replace(/\{yes\}/g, i18next.t("Yes"))
                .replace(/\{no\}/g, i18next.t("No"))
                .replace(/\{title\}/g, title)
                .replace(/\{consentText\}/g, consentText);
            orgModalElement.html(tempHTML);
        }
        orgModalElement.attr("id", orgModalId);
        $("#defaultConsentContainer").append(orgModalElement);
        return $("#"+orgModalId);
    },
    getDefaultAgreementUrl: function(orgId) {
        var stockConsentUrl = $("#stock_consent_url").val(), agreementUrl = "", orgElement = $("#" + orgId + "_org");
        if (stockConsentUrl && orgElement.length > 0) {
            var orgName = orgElement.attr("data-parent-name") || orgElement.attr("data-org-name");
            agreementUrl = stockConsentUrl.replace("placeholder", encodeURIComponent(orgName));
        }
        return agreementUrl;
    },
    setDefaultConsent: function(userId, orgId) {
        if (!userId) { return false;}
        var agreementUrl = this.getDefaultAgreementUrl(orgId), self = this;
        if (!agreementUrl) {
            $($("#consentContainer .error-message").get(0)).text(i18next.t("Unable to set default consent agreement"));
            return false;
        }
        var params = CONSENT_ENUM.consented;
        params.org = orgId;
        params.agreementUrl = agreementUrl;
        tnthAjax.setConsent(userId, params, "default");
        setTimeout(function() { //need to remove all other consents associated w un-selected org(s)
            self.removeObsoleteConsent(userId);
        }, 100);
        $($("#consentContainer .error-message").get(0)).text("");
    },
    removeObsoleteConsent: function(userId) {
        var co = [], OT = this.getOrgTool();
        $("#userOrgs input[name='organization']").each(function() {
            if ($(this).is(":checked")) {
                co.push($(this).val());
                var po = OT.getElementParentOrg(this);
                if (po) { co.push(po);}
            }
        });
        tnthAjax.deleteConsent(userId, {org: "all", exclude: co.join(",")}); //exclude currently selected orgs
    },
    setConsentByOrgElement: function(userId, el, isConsentWithTopLevelOrg) {
        var self = this, OT = this.getOrgTool(), parentOrg = OT.getElementParentOrg(el), orgId = $(el).val();
        var agreementUrl = $("#" + parentOrg + "_agreement_url").val();
        if (String(agreementUrl) !== "") {
            var params = CONSENT_ENUM.consented;
            params.org = isConsentWithTopLevelOrg ? parentOrg : orgId;
            params.agreementUrl = agreementUrl;
            setTimeout(function() {
                tnthAjax.setConsent(userId, params, "all", true, function() {
                    self.removeObsoleteConsent(userId);
                });
            }, 350);
            return;
        }
        self.setDefaultConsent(userId, parentOrg);
    },
    removeConsentByOrgElement: function(userId, el, isConsentWithTopLevelOrg) {
        var OT = this.getOrgTool();
        var parentOrg = OT.getElementParentOrg(el), orgId = $(el).val();
        if (isConsentWithTopLevelOrg) {
            var childOrgs = $("#userOrgs input[data-parent-id='" + parentOrg + "']");
            if ($("#fillOrgs").attr("patient_view")) {
                childOrgs = $("#userOrgs div.org-container[data-parent-id='" + parentOrg + "']").find("input[name='organization']");
            }
            var allUnchecked = !childOrgs.is(":checked");
            if (allUnchecked) {
                setTimeout(function() { tnthAjax.deleteConsent(userId, {"org": parentOrg});}, 350);
            }
            return;
        }
        setTimeout(function() { tnthAjax.deleteConsent(userId, {"org": orgId});}, 350);
    },
    /*
        parameter: consent data item, as returned from consent API
        boolean: return whether the item has all the relevant consent flags
    */
    hasConsentedFlags: function(item) {
        if (!item) {
            return false;
        }
        return item.send_reminders && item.staff_editable && item.include_in_reports;
    },
    setConsentBySelectedOrg: function(userId, obj, isConsentWithTopLevelOrg, callback) {
        callback = callback || function() {};
        var self = this;
        $(obj).each(function() {
            if ($(this).prop("checked")) {
                if ($(this).attr("id") !== "noOrgs") {
                    self.setConsentByOrgElement(userId, this, isConsentWithTopLevelOrg);
                } else { //remove all valid consent if no org is selected
                    setTimeout(function() { tnthAjax.deleteConsent(userId, {"org": "all"});}, 350);
                }
            } else {
                self.removeConsentByOrgElement(userId, this, isConsentWithTopLevelOrg);
            }
        });
        setTimeout(function() {
            callback();
        }, 500);
    }
};


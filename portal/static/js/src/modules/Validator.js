import Utility from "./Utility.js";
import tnthDates from "./TnthDate.js";
import tnthAjax  from "./TnthAjax.js";

import SYSTEM_IDENTIFIER_ENUM from "./SYSTEM_IDENTIFIER_ENUM.js";

var ValidatorObj = { /*global  $ i18next */
    "birthdayValidation": function(m, d, y, errorFieldId) {
        return  tnthDates.validateDateInputFields(m, d, y, errorFieldId);
    },
    "emailValidation": function($el) {
        var emailVal = $.trim($el.val());
        var update = function($el) {
            if ($el.attr("data-update-on-validated") === "true" && $el.attr("data-user-id")) {
                $el.trigger("postEventUpdate");
            }
        };
        if (emailVal === "") {
            if (!$el.attr("data-optional")) {
                return false;
            }
            update($el); //if email address is optional, update it as is
            return true;
        }
        var emailReg = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        var addUserId = ""; // Add user_id to api call (used on patient_profile page so that staff can edit)
        if ($el.attr("data-user-id")) {
            addUserId = "&user_id=" + $el.attr("data-user-id");
        }
        const fieldHelper = tnthAjax.FieldLoaderHelper;
        var url = "/api/unique_email?email=" + encodeURIComponent(emailVal) + addUserId;
        fieldHelper.showLoader($el);
        Utility.sendRequest(url, {max_attempts:1}, function(data) {
            fieldHelper.hideLoader($el);
            if (data && data.constructor === String) {
                data = JSON.parse(data);
            }
            if (data.error) { //note a failed request will be logged
                $("#erroremail").html(i18next.t("invalid email address")).parents(".form-group").addClass("has-error");
                return false; //stop proceeding to update email
            }
            if (data.unique) {
                $("#erroremail").html("").parents(".form-group").removeClass("has-error");
                $("#erroremail").removeClass("with-errors");
                update($el);
                return true;
            }
            $("#erroremail").html(i18next.t("This e-mail address is already in use. Please enter a different address.")).parents(".form-group").addClass("has-error");
            return false;
        });
    
        return emailReg.test(emailVal);
    },
    htmltagsValidation: function($el) {
        var containHtmlTags = function(text) {
            if (!(text)) {return false;}
            return /[<>]/.test(text);
        };
        var invalid = containHtmlTags($el.val());
        if (invalid) {
            $("#error" + $el.attr("id")).html(i18next.t("Invalid characters in text."));
            return false;
        }
        $("#error" + $el.attr("id")).html("");
        return !invalid;
    },
    identifierValidation: function($el) {
        if (!$el.val()) {
            return;
        }
        let systemtype = $el.attr("data-systemtype");
        let system = SYSTEM_IDENTIFIER_ENUM.hasOwnProperty(systemtype) ? SYSTEM_IDENTIFIER_ENUM[systemtype]: "";
        let userId = $el.attr("data-userid");
        let identifierValue = $el.val();
        let url = `/api/user/${userId}/unique?identifier=${system}|${identifierValue}`;
        Utility.sendRequest(url, {max_attempts:1}, function(data) {
            if (data && data.constructor === String) {
                data = JSON.parse(data);
            }
            if (!data.unique) {
                $el.closest(".form-group").find(".error-message").text(i18next.t("Identifier value must be unique"));
                return false;
            }
            $el.trigger("update");
            $el.closest(".form-group").find(".error-message").text("");
            return true;
        });
        return true;

    },
    initValidator: function() {
        const VALIDATION_EVENTS = "keyup change";
        let self = this;
        /*
         * init validation event for fields with custom validation attribute
         */
        $("form.to-validate[data-toggle=validator] [data-birthday]").attr("novalidate", true).on(VALIDATION_EVENTS,function() {
            return self.birthdayValidation($("#month").val(), $("#date").val(), $("#year").val(), "errorbirthday"); /* applied to month, day and year fields of birthday group elements */
        });
        $("form.to-validate[data-toggle=validator] [data-customemail]").attr("novalidate", true).on("change", function() {
            return self.emailValidation($(this));
        });
        $("form.to-validate[data-toggle=validator] [data-htmltags]").attr("novalidate", true).on(VALIDATION_EVENTS, function() {
            return self.htmltagsValidation($(this));
        });
        $("form.to-validate[data-toggle=validator] [data-identifier]").attr("novalidate", true).on("change", function() {
            return self.identifierValidation($(this));
        });
    }
};
export default ValidatorObj;
export var emailValidation = ValidatorObj.emailValidation;
export var htmltagsValidation = ValidatorObj.htmltagsValidation;
export var birthdayValidation = ValidatorObj.birthdayValidation;

import Utility from "./modules/Utility.js";
import tnthDates from "./modules/TnthDate.js";
import tnthAjax from "./modules/TnthAjax.js";
import SYSTEM_IDENTIFIER_ENUM from "./modules/SYSTEM_IDENTIFIER_ENUM.js";
import OrgTool from "./modules/OrgTool.js";
import ProcApp from "./modules/Procedures.js";
import {CurrentUserObj} from "./mixins/CurrentUser.js";
import {
  REQUIRED_PI_ROLES,
  REQUIRED_PI_ROLES_WARNING_MESSAGE,
} from "./data/common/consts.js";

(function() {
    var AccountCreationObj = window.AccountCreationObj = function (dependencies) { /*global $ tnthDates Utility*/
        this.attempts = 0;
        this.maxAttempts = 3;
        this.params = null;
        this.roles = [];
        this.userId = "None created";
        this.dependencies = dependencies||{};
        this.treatmentIntervalVar = null;
        this.CONSENT_WITH_TOP_LEVEL_ORG = false;

        $.ajaxSetup({
            timeout: 5000,
            retryAfter:3000
        });

        const HELP_BLOCK_IDENTIFIER = ".help-block";

        function getParentOrgId(obj) {
            var parentOrgId =  $(obj).attr("data-parent-id");
            if (!parentOrgId) {
                parentOrgId = $(obj).closest(".org-container[data-parent-id]").attr("data-parent-id");
            }
            return parentOrgId;
        }

        this.__getDependency = function(key) {
            if (key && this.dependencies.hasOwnProperty(key)) {
                return this.dependencies[key];
            }
            else {
                return false;
            }
        };

        var i18next = this.__getDependency("i18next");
        var OT = new OrgTool();

        this.__isPatient = function() {
            return $("#accountCreationContentContainer").attr("data-account") === "patient";
        };
        this.__request = function(params) {
            params = params || {};
            params.callback = params.callback || function() {};

            var self = this;
            if (!params.apiUrl) {
                (params.callback).call(self, {"error": "API url is required."});
                return false;
            }
            var errorMessage = "";
            self.attempts++;
            self.params = params;
            $.ajax ({
                type: (params.requestType ? params.requestType : "GET"),
                url: String(params.apiUrl).replace("//", "/"),
                contentType: "application/json; charset=utf-8",
                dataType: "json",
                async: params.sync ? false : true,
                data: params.requestData
            }).done(function(data) {
                self.attempts = 0;
                (params.callback).call(self, {"data": data});
            }).fail(function(xhr) {
                if (self.attempts < self.maxAttempts) {
                    setTimeout ( function() { self.__request( self.params ); } , $.ajaxSetup().retryAfter );
                } else {
                    self.attempts = 0;
                    var displayError = i18next.t("Server error occurred updating data.");
                    $("#error_response_text").html(displayError);
                    (params.callback).call(self, {"error": displayError});
                    tnthAjax.sendError(xhr, params.apiUrl, self.userId);
                }
            });
            return errorMessage;
        };
        this.__setAccount = function() {
            var orgIDs = $("#userOrgs input:checked").map(function(){
                return { organization_id: $(this).val() };
            }).get();

            var _accountArray = {};
            _accountArray["organizations"] = orgIDs;
            if (this.roles) {
                _accountArray["roles"] =  this.roles;
                $("#rolesContainer .input-role").each(function() {
                    if ($(this).is(":checked")) {
                        _accountArray["roles"] = _accountArray["roles"].concat([{"name": $(this).attr("data-role")}]);
                    }
                });
            }
            _accountArray["consents"] = this.getConsents();

            //note, this will call put/demographics to update demographics after
            this.__request({"apiUrl": "/api/account", "requestType": "POST", "requestData": JSON.stringify(_accountArray), "sync": true, "callback": this.__setDemo});
        };
        this.__setDemo = function(returnedData) {
            var responseData = returnedData && returnedData.data? returnedData.data : null;
            var self = this;

            if (!responseData || returnedData.error) { //Display Error Here
                this.__handleError(returnedData.error);
                this.__handleButton();
                return false;
            }
            self.userId = responseData["user_id"];

            if (isNaN(self.userId)) {
                self.__handleError(i18next.t("Invalid user id: %d").replace("%d", self.userId));
                self.__handleButton();
                return false;
            }

            var _demoArray = {};
            _demoArray["resourceType"] = "Patient";
            _demoArray["name"] = {
                "given": $.trim($("input[name=firstname]").val()),
                "family":$.trim($("input[name=lastname]").val())
            };

            var y = $("#year").val(), m = $("#month").val(), d = $("#date").val();
            if (y && m && d) {
                _demoArray["birthDate"] = y + "-" + m + "-" + d;
            }

            _demoArray["telecom"] = [];

            var emailVal = $.trim($("input[name=email]").val());
            if (emailVal) {
                _demoArray["telecom"].push({ "system": "email", "value": emailVal });
            } else {
                _demoArray["telecom"].push({ "system": "email", "value": "__no_email__"});
            }
            _demoArray["telecom"].push({ "system": "phone", "use": "mobile", "value": $.trim($("input[name=phone]").val())});
            _demoArray["telecom"].push({ "system": "phone", "use": "home", "value": $.trim($("input[name=altPhone]").val())});

            var orgIDs = $("#userOrgs input:checked").map(function(){
                return { reference: "api/organization/"+$(this).val() };
            }).get();

            _demoArray["careProvider"] = orgIDs;

            var arrCommunication = self.getCommunicationArray();
            if (arrCommunication.length > 0) {
                _demoArray["communication"] = arrCommunication;
            }

            var studyId = $("#profileStudyId").val();
            if (studyId) {
                var studyIdObj = {
                    system: SYSTEM_IDENTIFIER_ENUM.external_study_id,
                    use: "secondary",
                    value: studyId
                };
                if (!_demoArray["identifier"]) {
                    _demoArray["identifier"] = [];
                }
                _demoArray["identifier"].push(studyIdObj);
            }

            var siteId = $("#profileSiteId").val();
            if (siteId) {
                var siteIdObj = {
                    system: SYSTEM_IDENTIFIER_ENUM.external_site_id,
                    use: "secondary",
                    value: siteId
                };
                if (!_demoArray["identifier"]) {
                    _demoArray["identifier"] = [];
                }
                _demoArray["identifier"].push(siteIdObj);
            }

            self.__request({"apiUrl":"/api/demographics/"+this.userId, "requestType": "PUT", "requestData": JSON.stringify(_demoArray), "sync": true, "callback":
                function(data){
                    if (data.error) {
                        self.__handleError(data.error);
                        self.__handleButton();
                        return;
                    }
                    self.__setPcaLocalized(function(data) {
                        self.__setProcedures(function(data) {
                            data = data || {};
                            if (!data.error) {
                                self.__handleDisplay();
                                return true;
                            }
                            self.__handleError(data.error + " " + i18next.t("Account created. Redirecting to profile..."));
                            self.__handleButton();
                            /*
                             * redirect to profile since account has been created
                             */
                            (function(self) {
                                setTimeout(function() { self.__redirect(); }, 5000);
                            })(self);
                        });
                    });
                }
            });
        };
        this.__getSettings = function(callback) {
            callback = callback || function() {};
            tnthAjax.getConfiguration("account", "", function(result) { /* this will return configuration from sessionStorage if it is stored */
                callback({data:result});
            });
        };
        this.__setPcaLocalized = function(callback) {
            callback = callback || function() {};
            if (!this.userId || !this.__isPatient()) {
                callback();
                return false;
            }
            var userId = this.userId;
            var parentOrg = OT.getSelectedOrgTopLevelParentOrg();
            if (!parentOrg) {
                callback();
                return false;
            }
            this.__getSettings(function(result) { //check config
                if (!result || !result.data.LOCALIZED_AFFILIATE_ORG) {
                    callback();
                    return false;
                }
                tnthAjax.postClinical(userId,"pca_localized", OT.getOrgName(parentOrg) === result.data.LOCALIZED_AFFILIATE_ORG, false, false, false, function(data) {
                    callback(data);
                });
            });
        };
        this.__setProcedures = function(callback) {

            var self = this;
            callback = callback || function() {};
            var treatmentRows = $("#pastTreatmentsContainer tr[data-code]");
            if (treatmentRows.length === 0) {
                callback();
                self.__handleDisplay();
                return false;
            }
            if (isNaN(self.userId)) {
                self.__handleError(i18next.t("Invalid user id: %d").replace("%d", self.userId));
                self.__handleButton();
                callback();
                return false;
            }
            // Submit the data
            self.treatmentCount = treatmentRows.length;
            self.counter = 0;
            var errorMessage = "";
            treatmentRows.each(function() {
                var procArray = {};
                var procID = [{ "code": $(this).attr("data-code"), "display": $(this).attr("data-display"), system: $(this).attr("data-system") }];
                procArray["resourceType"] = "Procedure";
                procArray["subject"] = {"reference": "Patient/" + self.userId };
                procArray["code"] = {"coding": procID};
                procArray["performedDateTime"] = $(this).attr("data-performeddatetime");
                (function(self) {
                    setTimeout(function(){ tnthAjax.postProc(self.userId,procArray,false, function(data) {
                        if (data.error) {
                            errorMessage = data.error;
                        }
                        self.counter++;
                    });}, 100);
                })(self);
            });

            self.treatmentIntervalVar = setInterval(function() {
                if (self.counter === self.treatmentCount) {
                    callback({error: errorMessage});
                    clearInterval(self.treatmentIntervalVar);
                }
            }, 100);

        };
        this.__handleDisplay = function(responseObj) {
            var err = responseObj && responseObj.error ? responseObj.error: null;
            var self = this;
            if (!err) {
                setTimeout(function() {
                    self.__handleButton();
                    $("#confirmMsg").fadeIn();
                }, 800);
                setTimeout(function() {
                    self.__redirect(self.userId);
                }, 1000);
                setTimeout(function() {
                    $("#confirmMsg").fadeOut();
                }, 1500);
                self.__clear();
            } else {
                self.__handleError(err);
                self.__handleButton();
            }
        };
        this.__handleError = function(errorMessage) {
            if (errorMessage) {
                $("#serviceErrorMsg").html("<small>" + i18next.t("[Processing error] ") + errorMessage + "</small>").fadeIn();
            }
        };
        this.__redirect = function() {
            if (this.userId) {
                var isPatient = false;
                if (this.roles) {
                    this.roles.forEach(function(role) {
                        if (!isPatient && role.name.toLowerCase() === "patient") {
                            isPatient = true;
                        }
                    });
                }
                if (isPatient) {
                    $("#redirectLink").attr("href", "/patients/patient_profile/" + this.userId);
                } else {
                    $("#redirectLink").attr("href", "/staff_profile/" + this.userId);
                }
                $("#redirectLink")[0].click();
            }
        };
        this.__clear = function() {
            $("input.form-control, select.form-control").val("");
            $("#pastTreatmentsContainer").html("");
        };
        this.__handleButton = function(vis) {
            if (vis === "hide") {
                $("#updateProfile").attr("disabled", true).hide();
                $(".save-button-container").find(".loading-message-indicator").show();
            } else {
                $("#updateProfile").attr("disabled", false).show();
                $(".save-button-container").find(".loading-message-indicator").hide();
            }
        };

        this.hasErrorText = function() {
            var hasError = false;
            $("#createProfileForm " + HELP_BLOCK_IDENTIFIER).each(function () {
              if (hasError) {
                return false;
              }
              hasError = $(this).text() !== "";
            });
            return hasError;
        }

        this.__checkFields = function() {
           
            var hasError = false;

            /* organization fields */
            if ($("#userOrgs input").length) {
                hasError = $("#userOrgs input:checked").length === 0;
                this.setHelpText("userOrgs", hasError?i18next.t("An organization must be selected."):"", hasError);
            }
    
            let rolesList = $("#rolesContainer .input-role");
            /* check if at least one required role is checked */
            if (rolesList.length) {
                let requiredRoleSelected = false;
                rolesList.each(function() {
                    if (requiredRoleSelected) {
                        return false;
                    }
                    requiredRoleSelected = $(this).is(":checked");
                });
                hasError = !requiredRoleSelected;
                this.setHelpText("rolesContainer", hasError?i18next.t("A role must be selected."):"", hasError);
            }

            /* finally check fields to make sure there isn't error, e.g. due to validation error */
              if (!hasError) {
                hasError = this.hasErrorText();
            }

            if (hasError) {
                this.showError();
            } else {
                this.clearError();
            }
    
            return hasError;
        };


        this.isRoleChecked = function(role) {
            if (!role) return false;
            return $(`#createProfileForm .input-role[data-role='${role}']`).is(
              ":checked"
            );
        };

        this.initFieldEvents = function() {
            let self = this;
            Utility.convertToNumericField($("#date, #year, #phone, #altPhone"));

            $("#createProfileForm [required]").on("change", function() {
                if (self.hasErrorText()) return;
                $("#updateProfile").attr("disabled", false);
                setTimeout(function() { self.clearError(); }, 600);
            });
    
            //clear error text if value changed
            $("#createProfileForm input[type='text']").on("change keyup", function() {
                $(this).closest(".profile-section").find(HELP_BLOCK_IDENTIFIER).text("").removeClass("error-message");
            });
            //clear error text when checkbox is checked
            $("#createProfileForm input[type='checkbox']").on("change", function() {
                $(this).closest(".profile-section").find(HELP_BLOCK_IDENTIFIER).text("").removeClass("error-message");
            });

            $("#createProfileForm .input-role").on("change", function() {
                // PI role checked
                var primaryInvestatorRoleChecked = self.isRoleChecked(
                  "primary_investigator"
                );

                if (!primaryInvestatorRoleChecked) {
                    $(this)
                    .closest(".profile-section")
                    .find(HELP_BLOCK_IDENTIFIER)
                    .text("")
                    .removeClass("error-message");
                    $("#updateProfile").attr("disabled", false);
                    return;
                }
                var requiredRolesChecked = REQUIRED_PI_ROLES.filter((role) =>
                  self.isRoleChecked(role)
                ).length > 0;
               
                if (!requiredRolesChecked) {
                  $(this)
                    .closest(".profile-section")
                    .find(HELP_BLOCK_IDENTIFIER)
                    .html(REQUIRED_PI_ROLES_WARNING_MESSAGE)
                    .addClass("error-message");
                  $("#updateProfile").attr("disabled", true);
                } else {
                  $(this)
                    .closest(".profile-section")
                    .find(HELP_BLOCK_IDENTIFIER)
                    .html("")
                    .addClass("error-message");
                  $("#updateProfile").attr("disabled", false);
                }
    
                
            });
        };

        this.setDefaultRoles = function() {
            this.roles =  [{"name": "write_only"}];
            if (this.__isPatient()) {
                this.roles =  [{"name": "patient"}, {"name": "write_only"}];
            }
        };

        this.showError = function() {
            $("#errorMsg").fadeIn("slow");
        }

        this.clearError = function() {
            $("#errorMsg").html("").hide();
            $("#serviceErrorMsg").html("").hide();
        };
        this.setHelpText = function(elementId, message, hasError) {
            if (hasError) {
                $("#" + elementId).find(HELP_BLOCK_IDENTIFIER).text(message).addClass("error-message");
                return;
            }
            $("#" + elementId).find(HELP_BLOCK_IDENTIFIER).text("").removeClass("error-message");
        };
        this.getOrgs = function(callback, params) {
            var self = this;
            callback = callback || function() {};
            $("#clinicsLoader").removeClass("tnth-hide");
            tnthAjax.getOrgs(self.userId, params, function(data) {
                $("#clinicsLoader").addClass("tnth-hide");
                if (!data) {
                    callback.call(self, {"error": i18next.t("no data returned")});
                    return false;
                }
                if (data.error) {
                    callback.call(self, {"error": i18next.t("Error occurred retrieving clinics data.")});
                    return false;
                }
                callback.call(self, data);
            });
        };
        this.populateOrgsByRole = function(data) {
            if (!data) {
                $("#userOrgs .get-orgs-error").html(i18next.t("No clinics data available."));
                return false;
            }
            if (data.error) {
                $("#userOrgs .get-orgs-error").html(data.error);
                return false;
            }
            OT.populateOrgsList(data.entry);
            OT.populateUI();

            if (!$("#userOrgs input[name='organization']").length) {
                //UI orgs aren't populated for some reason and no indication of error from returned data from ajax call, e.g. related to cached session data
                $("#userOrgs .get-orgs-error").html(i18next.t("No clinics data available."));
                return false;
            }
            var isPatient = $.grep(this.roles, function(role) {
                return role.name === "patient";
            });
            if (isPatient.length > 0) {
                this.populatePatientOrgs();
            } else {
                this.populateStaffOrgs();
            }
            var visibleOrgs = $("#userOrgs input[name='organization']:visible");
            if (visibleOrgs.length === 1) {
                visibleOrgs.prop("checked", true);
            }
        };
        this.populatePatientOrgs = function() {
            OT.filterOrgs(CurrentUserObj.getLeafOrgs());
            var userOrgs = $("#userOrgs input[name='organization']");
            userOrgs.each(function() {
                $(this).closest("label").addClass("radio-label");
                $(this).attr("type", "radio");
            });
        };
        this.populateStaffOrgs = function() {
            OT.filterOrgs(CurrentUserObj.getHereBelowOrgs());
        };
        this.getCommunicationArray = function() {
            var arrCommunication = [];
            $("#userOrgs input:checked").each(function() {
                var oList = OT.getOrgsList(), oi = oList[$(this).val()];
                if (parseInt($(this).val()) === 0 || !oi) {
                    return true; //don't count none
                }
                if (oi.language) {
                    arrCommunication.push({"language": {"coding": [{"code": oi.language,"system": SYSTEM_IDENTIFIER_ENUM.language_system}]}});
                } else {
                    oi.extension = oi.extension || [];
                    var arrExtension = $.grep(oi.extension, function(ex) {
                        return String(ex.url) === String(SYSTEM_IDENTIFIER_ENUM.language) && ex.valueCodeableConcept.coding;
                    });
                    arrExtension = arrExtension.map(function(ex) {
                        return ex.valueCodeableConcept.coding;
                    });
                    arrExtension.forEach(function(coding) {
                        arrCommunication.push({"language": { "coding": coding}});
                    });
                }
            });
            return arrCommunication;
        };
        this.handleCurrentUser = function() {
            let self = this;
            CurrentUserObj.initCurrentUser(function() {
                OT.init(function() {
                    setTimeout(function() {
                        //delay a bit to call orgs api after current user info is loaded
                        this.getOrgs(this.populateOrgsByRole);
                        this.handleMedidataRave(CurrentUserObj.topLevelOrgs, CurrentUserObj.isAdminUser());
                    }.bind(self), 150);
                });
            });
        };
        this.getCurrentUserTopLevelOrgs = function() {
            var topLevelOrgs = OT.getUserTopLevelParentOrgs(CurrentUserObj.getLeafOrgs());
            return topLevelOrgs.map(function(item) {
                return OT.getOrgName(item);
            });
        };
        this.handleMedidataRave = function(orgs, noDisable) { /* due to MedidataRave Integration, IRONMAN patient accounts, in particular, are created externally, instead of via the portal, hence, editing is disabled */
            if (noDisable) {
                return false;
            }
            var self = this;
            orgs = orgs || this.getCurrentUserTopLevelOrgs();
            this.__getSettings(function(result) {
                if (result.data.PROTECTED_ORG && orgs.indexOf(result.data.PROTECTED_ORG) !== -1) {
                    self.setDisableAccountCreation();
                }
            });
        };
        this.setDisableAccountCreation = function() {
            if (this.__isPatient()) { //creating an overlay that prevents user from editing fields
                $("#createProfileForm .create-account-container").append("<div class='overlay'></div>");
            }
        };
        this.initButtons = function() {
            var self = this;
            $("#createProfileForm .back-button-container").prepend(this.__getLoaderHTML());
            $("#createProfileForm .save-button-container").prepend(this.__getLoaderHTML());
            $("#createProfileForm .btn-tnth-back").on("click", function(e) {
                e.preventDefault();
                $(this).prev(".loading-message-indicator").show();
                $(this).hide();
                window.location = $(this).attr("href");
            });
            $("#updateProfile").attr("disabled", true);
            $("#createProfileForm").on("submit", function (e) { //submit on clicking save button
                if (e.isDefaultPrevented()) {
                    // handle the invalid form...
                    return false;
                } 
                if (self.__checkFields()) { return false; }
                e.preventDefault(); // everything looks good!
                self.__handleButton("hide");
                setTimeout(function() { self.__setAccount(); } , 0);
            });
        };
        this.getConsentOrgId = function(element, CONSENT_WITH_TOP_LEVEL_ORG) {
            var consentOrgId = $(element).val();
            if (CONSENT_WITH_TOP_LEVEL_ORG) {
                consentOrgId = getParentOrgId(element);
            }
            return consentOrgId;
        };
        this.getConsentAgreementUrl = function(parentOrg) {
            return $("#" + parentOrg + "_agreement_url").val() || $("#stock_consent_url").val();
        };
        this.getConsents = function() {
            var orgs = {}, consents = [], CONSENT_WITH_TOP_LEVEL_ORG = false, self = this;
            tnthAjax.setting("CONSENT_WITH_TOP_LEVEL_ORG", "", {sync: true}, function(data) {
                if (!data.error && data.CONSENT_WITH_TOP_LEVEL_ORG) {
                    CONSENT_WITH_TOP_LEVEL_ORG = true;
                }
            });
            $("#createProfileForm input[name='organization']").each(function() {
                if (!$(this).prop("checked")) { return true; }
                var consentOrgId = self.getConsentOrgId(this, CONSENT_WITH_TOP_LEVEL_ORG);
                if (!consentOrgId || orgs.hasOwnProperty(consentOrgId)) {
                    return false;
                }
                orgs[consentOrgId] = true;
                var agreement = self.getConsentAgreementUrl(getParentOrgId(this));
                agreement = String(agreement).replace("placeholder", encodeURIComponent($(this).attr("data-parent-name")));
                var ct = $("#consentDate").val();
                if (!agreement) {
                    return true;
                }
                var consentItem = {};
                if (ct) {
                    consentItem["acceptance_date"] = ct;
                }
                consentItem["organization_id"] = consentOrgId;
                consentItem["agreement_url"] = agreement;
                consentItem["staff_editable"] = true;
                consentItem["include_in_reports"] = true;
                consentItem["send_reminders"] = true;
                consents.push(consentItem);
            });
            return consents;
        };
        this.handleEditConsentDate = function() {
            if ($("#consentDateEditContainer").length === 0) {
                return;
            }
            //default consent date to today's date
            var today = new Date();
            var pad = function(n) {n = parseInt(n); return (n < 10) ? "0" + n : n;};
            var td = pad(today.getDate()), tm = pad(today.getMonth()+1), ty = pad(today.getFullYear());
            var th = today.getHours(), tmi = today.getMinutes(), ts = today.getSeconds();

            $("#consentDay").val(td);
            $("#consentMonth").val(tm);
            $("#consentYear").val(ty);
            //saving the consent date in GMT - default to today's date
            $("#consentDate").val(tnthDates.getDateWithTimeZone(tnthDates.getDateObj(ty, tm, td, th, tmi, ts)));
            if (Utility.isTouchDevice()) {
                $("#consentDay, #consentYear").each(function() {
                    $(this).attr("type", "tel");
                });
            }
            $("#consentDay, #consentMonth, #consentYear").on("change", function() {
                var d = $("#consentDay");
                var m = $("#consentMonth");
                var y = $("#consentYear");
                //get today's date/time
                var today = new Date();
                var td = pad(today.getDate()), tm = pad(today.getMonth()+1), ty = pad(today.getFullYear());
                var th = today.getHours(), tmi = today.getMinutes(), ts = today.getSeconds();
                if (!y.get(0).validity.valid || !m.get(0).validity.valid || !d.get(0).validity.valid) {
                    $("#consentDate").val("");
                    return false;
                }
                var isValid = tnthDates.validateDateInputFields(m.val(), d.val(), y.val(), "errorConsentDate");
                if (isValid) {
                    /*
                     * check if date entered is today, if so use today's date/time
                     */
                    if (td+tm+ty === (pad(d.val())+pad(m.val())+pad(y.val()))) {
                        $("#consentDate").val(tnthDates.getDateWithTimeZone(tnthDates.getDateObj(ty, tm, td, th, tmi, ts)));
                    } else {
                        //saving the time at 12
                        $("#consentDate").val(tnthDates.getDateWithTimeZone(tnthDates.getDateObj(y.val(),m.val(),d.val(),12,0,0)));
                    }
                    $("#errorConsentDate").text("").hide();
                } else {
                    $("#consentDate").val("");
                }
            });
        };
        this.handleNoEmail = function() {
            $("#noEmail").on("click, change", function() {
                if ($(this).is(":checked")) {
                    $("#erroremail").css("visibility", "hidden");
                    $("#email").val("").attr("disabled", true).removeAttr("required").removeAttr("data-customemail");
                    setTimeout(function() {
                        $("#erroremail").text("");
                        $("#email").closest("form-group").removeClass("has-error");
                        $("#email").css("border-color", "#ccc");
                    }, 600);
                }
                else {
                    $("#erroremail").css("visibility", "visible");
                    $("#email").attr("disabled", false).attr("required", "required").attr("data-customemail", "true");
                }
            });
        };
        this.__getLoaderHTML = function(message) {
            return `<div class="loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i>${(message ? "&nbsp;" + message : "")}</div>`;
        };
    };

    //events associated with elements on the account creation page
    $(document).ready(function(){
        /* global i18next, tnthAjax, OrgTool, SYSTEM_IDENTIFIER_ENUM */
        var aco = new AccountCreationObj({"i18next": i18next});
        aco.setDefaultRoles();
        /*** 
         *** need to run this instead of the one function from main.js because we don't want to pre-check any org here
         ***/
        aco.handleCurrentUser();
        aco.handleEditConsentDate();
        aco.initFieldEvents();
        aco.initButtons();
        aco.handleNoEmail();
        ProcApp.initViaTemplate();
    });
})();

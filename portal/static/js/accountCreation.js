/*
 * dependency: JQuery, main.js
 */

var AccountCreationObj = function (roles, dependencies) {
    this.attempts = 0;
    this.maxAttempts = 3;
    this.params = null;
    this.roles = roles;
    this.userId = "None created";
    this.dependencies = dependencies||{};
    this.treatmentIntervalVar = null;


    $.ajaxSetup({
        timeout: 5000,
        retryAfter:3000
    });

    function hasValue(val) {
        return val != null && val != "" && val != "undefined";
    };

    function getParentOrgId(obj) {
        var parentOrgId =  $(obj).attr("data-parent-id");
        if (!hasValue(parentOrgId)) {
            parentOrgId = $(obj).closest(".org-container[data-parent-id]").attr("data-parent-id");
        };
        return parentOrgId;
    };

    this.__getDependency = function(key) {
        if (key && this.dependencies.hasOwnProperty(key)) {
            return this.dependencies[key];
        }
        else {
            return false;
        };
    };

    var i18next = this.__getDependency("i18next");
    var tnthAjax = this.__getDependency("tnthAjax");
    var SYSTEM_IDENTIFIER_ENUM = this.__getDependency("SYSTEM_IDENTIFIER_ENUM");
    var OT = this.__getDependency("OrgTool");
    var leafOrgs = this.__getDependency("leafOrgs");
    var orgList = this.__getDependency("orgList");


    this.__request = function(params) {
        params = params || {};

        var self = this;
        if (!hasValue(params.apiUrl)) {
            if (params.callback) {
                (params.callback).call(self, {"error": "API url is required."});
            };
            return false;
        };
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
            if (params.callback) {
                (params.callback).call(self, {"data": data});
            };
        }).fail(function(xhr) {
            if (self.attempts < self.maxAttempts) {
                setTimeout ( function() { self.__request( self.params ); } , $.ajaxSetup().retryAfter );
            } else {
                var displayError = i18next.t("Server error occurred updating data.");
                $("#error_response_text").html(displayError);
                errorMessage = "Error processing request: " + params.apiUrl;
                errorMessage += ";  response status code: " + (parseInt(xhr.status) === 0 ? "request timed out/network error": xhr.status);
                errorMessage +=";  response text: " + (hasValue(xhr.responseText) ? xhr.responseText : "no response text returned from server");
                tnthAjax.reportError(self.userId, "/patients/patient-profile-create", errorMessage, true);
                self.attempts = 0;
                if (params.callback) {
                    (params.callback).call(self, {"error": displayError});
                };
            };
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
        };
        _accountArray["consents"] = this.getConsents();

        //note, this will call put/demographics to update demographics after
        this.__request({"apiUrl": "/api/account", "requestType": "POST", "requestData": JSON.stringify(_accountArray), "sync": true, "callback": this.__setDemo});
    };
    this.__setDemo = function(returnedData) {
        var responseData = returnedData && returnedData.data? returnedData.data : null;
        var self = this;
        if (responseData) {

            self.userId = responseData["user_id"];

            if (isNaN(self.userId)) {
                self.__handleError(i18next.t("Invalid user id: %d").replace("%d", self.userId));
                self.__handleButton();
                return false;
            };

            var _demoArray = {};
            _demoArray["resourceType"] = "Patient";
            _demoArray["name"] = {
                "given": $.trim($("input[name=firstname]").val()),
                "family":$.trim($("input[name=lastname]").val())
            };

            var y = $("#year").val(), m = $("#month").val(), d = $("#date").val();
            _demoArray["birthDate"] = y + "-" + m + "-" + d;

            _demoArray["telecom"] = [];

            var emailVal = $.trim($("input[name=email]").val());
            if (hasValue(emailVal)) {
                _demoArray["telecom"].push({ "system": "email", "value": emailVal });
            } else {
                _demoArray["telecom"].push({ "system": "email", "value": "__no_email__"});
            };
            _demoArray["telecom"].push({ "system": "phone", "use": "mobile", "value": $.trim($("input[name=phone]").val())});
            _demoArray["telecom"].push({ "system": "phone", "use": "home", "value": $.trim($("input[name=altPhone]").val())});

            var orgIDs = $("#userOrgs input:checked").map(function(){
                return { reference: "api/organization/"+$(this).val() };
            }).get();

            _demoArray["careProvider"] = orgIDs;

            var arrCommunication = OT.getCommunicationArray();
            if (arrCommunication.length > 0) {
                _demoArray["communication"] = arrCommunication;
            };

            /*** SYSTEM uri is defined by SYSTEM_IDENTIFIER_ENUM, see main.js for details **/
            var studyId = $("#profileStudyId").val();
            if (hasValue(studyId)) {
                var studyIdObj = {
                    system: SYSTEM_IDENTIFIER_ENUM["external_study_id"],
                    use: "secondary",
                    value: studyId
                };
                if (!_demoArray["identifier"]) {
                    _demoArray["identifier"] = [];
                };
                _demoArray["identifier"].push(studyIdObj);
            };

            var siteId = $("#profileSiteId").val();
            if (hasValue(siteId)) {
                var siteIdObj = {
                    system: SYSTEM_IDENTIFIER_ENUM["external_site_id"],
                    use: "secondary",
                    value: siteId
                };
                if (!_demoArray["identifier"]) {
                    _demoArray["identifier"] = [];
                };
                _demoArray["identifier"].push(siteIdObj);
            };


            var states = [];
            $("#userOrgs input[name='organization']").each(function() {
                if ($(this).is(":checked")) {
                    if (hasValue($(this).attr("state"))) {
                        states.push($(this).attr("state"));
                    };
                };
            });

            if (states.length > 0) {
                if (!_demoArray["identifier"]) {
                    _demoArray["identifier"] = [];
                };
                states.forEach(function(state) {
                    _demoArray["identifier"].push({
                        system: SYSTEM_IDENTIFIER_ENUM["practice_region"],
                        use: "secondary",
                        value: "state:" + state
                    });
                });
            };
            self.__request({"apiUrl":"/api/demographics/"+this.userId, "requestType": "PUT", "requestData": JSON.stringify(_demoArray), "sync": true, "callback":
                function(data){
                    if (data.error) {
                        self.__handleError(data.error);
                        self.__handleButton();
                    } else {
                        self.__setProcedures();
                    };
                }
            });
        } else {
            //Display Error Here
            if (returnedData.error) {
               this.__handleError(returnedData.error);
               this.__handleButton();
            };
        };
    };
    this.__setProcedures = function() {

        var self = this;

        var treatmentRows = $("#pastTreatmentsContainer tr[data-code]");
        if (treatmentRows.length === 0) {
            self.__handleDisplay();
            return false;
        };

        if (isNaN(self.userId)) {
            self.__handleError(i18next.t("Invalid user id: %d").replace("%d", self.userId));
            self.__handleButton();
            return false;
        };
        // Submit the data
        self.treatmentCount = treatmentRows.length;
        self.counter = 0;
        var errorMessage = "";

        treatmentRows.each(function() {
            var procArray = {};
            var procID = [{ "code": $(this).attr("data-code"),
                            "display": $(this).attr("data-display"),
                            system: $(this).attr("data-system") }];
            procArray["resourceType"] = "Procedure";
            procArray["subject"] = {"reference": "Patient/" + self.userId };
            procArray["code"] = {"coding": procID};
            procArray["performedDateTime"] = $(this).attr("data-performeddatetime");
            (function(self) {
                setTimeout(function(){ tnthAjax.postProc(self.userId,procArray,false, function(data) {
                    if (data.error) {
                        errorMessage = data.error;
                    };
                    self.counter++;
                });}, 100);
            })(self);
        });

        self.treatmentIntervalVar = setInterval(function() {
            if (self.counter === self.treatmentCount) {
                if (hasValue(errorMessage)) {
                    self.__handleError(errorMessage + i18next.t(" Account created.  Redirecting to profile..."));
                    self.__handleButton();
                    /*
                     * redirect to profile since account has been created
                     */
                    (function(self) {
                        setTimeout(function() { self.__redirect(); }, 5000);
                    })(self);
                } else {
                    self.__handleDisplay();
                };
                clearInterval(self.treatmentIntervalVar);
            };
        }, 100);

    };
    this.__handleDisplay = function(responseObj) {
        var err = responseObj && responseObj.error ? responseObj.error: null;
        var self = this;
        if (!hasValue(err)) {
            $("#confirmMsg").fadeIn();
            self.__handleButton();
            setTimeout(function() { $("#confirmMsg").fadeOut(); }, 800);
            setTimeout(function() { self.__redirect(self.userId); }, 1000);
            self.__clear();
        } else {
            self.__handleError(err);
            self.__handleButton();
        };
    };
    this.__handleError = function(errorMessage) {
        if (hasValue(errorMessage)) {
            $("#serviceErrorMsg").html("<small>" + i18next.t("[Processing error] ") + errorMessage + "</small>").fadeIn();
        };
    };
    this.__redirect = function() {
        if (this.userId) {
            var isPatient = false;
            if (this.roles) {
                this.roles.forEach(function(role) {
                    if (!isPatient && role.name.toLowerCase() === "patient") {
                        isPatient = true;
                    };
                });
            };
            if (isPatient) {
                $("#redirectLink").attr("href", "/patients/patient_profile/" + this.userId);
            } else {
                $("#redirectLink").attr("href", "/staff_profile/" + this.userId);
            };
            $("#redirectLink")[0].click();
        };
    };
    this.__clear = function() {
        $("input.form-control, select.form-control").each(
            function() {
                $(this).val("");
        });
        $("#pastTreatmentsContainer").html("");
    };
    this.__handleButton = function(vis) {
        if (vis === "hide") {
            $("#updateProfile").attr("disabled", true).hide();
            $(".save-button-container").find(".loading-message-indicator").show();
        } else {
            $("#updateProfile").attr("disabled", false).show();
            $(".save-button-container").find(".loading-message-indicator").hide();
        };
    };

    this.__checkFields = function(silent) {
        var hasError = false;

        /* check all required fields to make sure all fields are filled in */
        $("input[required], select[required]").each(function() {
            if (!hasValue($(this).val())) {
                //this should display error message associated with empty field
                if (!silent) {
                    $(this).trigger("focusout");
                };
                hasError = true;
            };
        });
        /* check email field */
        if ($("#noEmail").length > 0 && !$("#noEmail").is(":checked")) {
            if ($("#emailGroup").hasClass("has-error")) {
                hasError = true;
            } else {
                if ($("#current_user_email").val() === $("#email").val()) {
                    if (!silent) {
                        this.setHelpText("emailGroup", i18next.t("Email is already in use."), true);
                    };
                    hasError = true;
                } else {
                    this.setHelpText("emailGroup", "", false);
                };
            };
        };
        /* check organization */
        if ($("#userOrgs input").length > 0 && $("#userOrgs input:checked").length === 0) {
            if (!silent) {
                this.setHelpText("userOrgs", i18next.t("An organization must be selected."), true);
            };
            hasError = true;
        } else {
            this.setHelpText("userOrgs", "", false);
        };

        /* finally check fields to make sure there isn't error, e.g. due to validation error */
        $("#createProfileForm .help-block.with-errors").each(function() {
            if ($(this).text() !== "") {
                hasError = true;
            };
        });

        if (hasError) {
            if (!silent) {
                $("#errorMsg").fadeIn("slow");
            };
        } else {
            $("#errorMsg").hide();
            $("#serviceErrorMsg").html("").hide();
        };
        return hasError;
    };

    this.clearError = function() {
        var hasError = this.__checkFields(true);
        if (!hasError) $("#errorMsg").html("").hide();
    };

    this.setHelpText = function(elementId, message, hasError) {
        if (hasError) {
            $("#" + elementId).find(".help-block").text(message).addClass("error-message");
        }
        else {
            $("#" + elementId).find(".help-block").text("").removeClass("error-message");
        };
    };
    this.getOrgs = function(callback) {
        var self = this;
        self.attempts++;
        $.ajax ({
            type: "GET",
            url: "/api/organization"
        }).done(function(data) {
            self.attempts = 0;
            if (data) {
                if (callback) {
                    callback(data);
                };
            } else {
                if (callback) {
                    callback({"error": i18next.t("no data returned")});
                };
            };
        }).fail(function(xhr) {
            /*
             * retry here
             */
            if (self.attempts < self.maxAttempts) {
                setTimeout ( function() { self.getOrgs( callback ); } , $.ajaxSetup().retryAfter );
            } else {
                var errorMessage = i18next.t("Error occurred retrieving clinics data.");
                if (callback) {
                    callback({"error": errorMessage});
                };
                self.attempts = 0;
            };
            tnthAjax.sendError(xhr, "", "/api/organization");
        });
    };
    this.populatePatientOrgs = function(data) {
        if (data) {
            if (!data.error) {
                OT.populateOrgsList(data.entry);
                OT.populateUI();

                if (leafOrgs) {
                    OT.filterOrgs(leafOrgs);
                };

                var userOrgs = $("#userOrgs input[name='organization']");
                userOrgs.each(function() {
                    $(this).attr("type", "radio");
                });

                $("#userOrgs input[name='organization']").each(function() {
                    $(this).on("click", function() {
                        $("#userOrgs").find(".help-block").html("");
                    });
                });

                var visibleOrgs = $("#userOrgs input[name='organization']:visible");
                if (visibleOrgs.length === 1) {
                    visibleOrgs.prop("checked", true);
                };
            } else {
                $("#userOrgs .get-orgs-error").html(data.error);
            };
        } else {
            $("#userOrgs .get-orgs-error").html(i18next.t("No clinics data available."));
        };
    };
    this.populateStaffOrgs = function(data) {
        if (data) {
            if (!data.error) {
                OT.populateOrgsList(data.entry);
                OT.populateUI();

                if (orgList) {
                    OT.filterOrgs(orgList);
                };

                var userOrgs = $("#userOrgs input[name='organization']").not("[parent_org]");

                $("#userOrgs input[name='organization']").each(function() {
                    $(this).on("click", function() {
                        $("#userOrgs").find(".help-block").html("");
                    });
                });

                var visibleOrgs = $("#userOrgs input[name='organization']:visible");
                if (visibleOrgs.length === 1) {
                    visibleOrgs.prop("checked", true);
                };

            } else {
                $("#userOrgs .get-orgs-error").html(data.error);
            };

        } else {
            $("#userOrgs .get-orgs-error").html(i18next.t("No clinics data available."));
        };
    };
    this.getConsents = function() {
        var orgs = {}, consents = [], self = this;
        $("#createProfileForm input[name='organization']").each(function() {
            if ($(this).prop("checked")) {
                var consentOrgId, CONSENT_WITH_TOP_LEVEL_ORG = false;
                tnthAjax.setting("CONSENT_WITH_TOP_LEVEL_ORG", "", {sync: true}, function(data) {
                    if (!data.error) {
                        if (data["CONSENT_WITH_TOP_LEVEL_ORG"]) {
                            CONSENT_WITH_TOP_LEVEL_ORG = true;
                        };
                    };
                });
                if (CONSENT_WITH_TOP_LEVEL_ORG) {
                    consentOrgId = getParentOrgId(this);
                }
                else {
                    consentOrgId = $(this).val();
                }

                if (consentOrgId && !orgs[consentOrgId]) {
                    orgs[consentOrgId] = true;
                    var agreement = $("#" + getParentOrgId(this) + "_agreement_url").val();
                    if (!hasValue(agreement)) {
                        var stockConsentUrl = $("#stock_consent_url").val();
                        agreement = stockConsentUrl.replace("placeholder", encodeURIComponent($(this).attr("data-parent-name")));
                    };
                    if (hasValue(agreement)) {
                        var ct = $("#consentDate").val();
                        var consentItem = {};
                        if (hasValue(ct)) {
                            consentItem["acceptance_date"] = ct;
                        };
                        consentItem["organization_id"] = consentOrgId;
                        consentItem["agreement_url"] = agreement;
                        consentItem["staff_editable"] = true;
                        consentItem["include_in_reports"] = true;
                        consentItem["send_reminders"] = true;
                        consents.push(consentItem);
                    };
                };
            };
        });
        return consents;
    };
};

//events associated with elements on the account creation page
$(document).ready(function(){

    $("#createProfileForm .optional-diplay-text").removeClass("tnth-hide");

    $("#createProfileForm .back-button-container").prepend(__getLoaderHTML());
    $("#createProfileForm .save-button-container").prepend(__getLoaderHTML());
    $("#createProfileForm .btn-tnth-back").on("click", function(e) {
        e.preventDefault();
        $(this).prev(".loading-message-indicator").show();
        $(this).hide();
        window.location = $(this).attr("href");
    });
    $("#updateProfile").attr("disabled", true);
    $("#createProfileForm input, #createProfileForm select").on("focusout", function() {
        $("#updateProfile").attr("disabled", false);
        setTimeout(function() { aco.clearError(); }, 600);
    });
    $("#noEmail").on("click, change", function() {
        if ($(this).is(":checked")) {
            $("#erroremail").css("visibility", "hidden");
            $("#email").val("").attr("disabled", true).removeAttr("required").removeAttr("data-customemail");
            setTimeout('$("#erroremail").text(""); $("#email").closest("form-group").removeClass("has-error"); $("#email").css("border-color", "#ccc");', 600);
        }
        else {
            $("#erroremail").css("visibility", "visible");
            $("#email").attr("disabled", false).attr("required", "required").attr("data-customemail", "true");
        };
    });

    if ($("#consentDateEditContainer").length > 0) {
        //default consent date to today's date
        var today = new Date();
        var td = pad(today.getDate()), tm = pad(today.getMonth()+1), ty = pad(today.getFullYear());
        var th = today.getHours(), tmi = today.getMinutes(), ts = today.getSeconds();
        $("#consentDay").val(td);
        $("#consentMonth").val(tm);
        $("#consentYear").val(ty);
        //saving the consent date in GMT
        //default to today's date
        $("#consentDate").val(tnthDates.getDateWithTimeZone(tnthDates.getDateObj(ty, tm, td, th, tmi, ts)));
        if (_isTouchDevice()) {
            $("#consentDay, #consentYear").each(function() {
                $(this).attr("type", "tel");
            });
        };
        $("#consentDay, #consentMonth, #consentYear").each(function() {
          $(this).on("change", function() {
                var d = $("#consentDay");
                var m = $("#consentMonth");
                var y = $("#consentYear");
                //get today's date/time
                var today = new Date();
                var td = pad(today.getDate()), tm = pad(today.getMonth()+1), ty = pad(today.getFullYear());
                var th = today.getHours(), tmi = today.getMinutes(), ts = today.getSeconds();
             
                var isValid = tnthDates.validateDateInputFields(m, d, y, "errorConsentDate");
                if (isValid) {
                /*
                 * check if date entered is today, if so use today's date/time
                 */
                if (td+tm+ty === (pad(d.val())+pad(m.val())+pad(y.val()))) {
                    $("#consentDate").val(tnthDates.getDateWithTimeZone(tnthDates.getDateObj(ty, tm, td, th, tmi, ts)));
                } else {
                    var timezoneOffset = Math.floor(((new Date()).getTimezoneOffset())/60);
                    //saving the time at 12
                    $("#consentDate").val(tnthDates.getDateWithTimeZone(tnthDates.getDateObj(y.val(),m.val(),d.val(),12,0,0)));
                };
                $("#errorConsentDate").text("").hide();
                //success
                } else {
                 //fail
                $("#consentDate").val("");
                };
          });
        });
    };
    $("#createProfileForm").on("submit", function (e) {
        if (e.isDefaultPrevented()) {
            // handle the invalid form...
            aco.__checkFields();
            return false;
        } else {
           var hasError = aco.__checkFields();
           if (hasError) return false;

            // everything looks good!
            e.preventDefault();

            aco.__handleButton("hide");
            setTimeout("aco.__setAccount();", 0);

        };
    });
});
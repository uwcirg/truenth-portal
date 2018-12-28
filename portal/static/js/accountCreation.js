(function() {
    var AccountCreationObj = window.AccountCreationObj = function (roles, dependencies) { /*global pad $ tnthDates Utility isTouchDevice*/
        this.attempts = 0;
        this.maxAttempts = 3;
        this.params = null;
        this.roles = roles;
        this.userId = "None created";
        this.dependencies = dependencies||{};
        this.treatmentIntervalVar = null;
        this.CONSENT_WITH_TOP_LEVEL_ORG = false;

        $.ajaxSetup({
            timeout: 5000,
            retryAfter:3000
        });

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
        var tnthAjax = this.__getDependency("tnthAjax");
        var OT = this.__getDependency("OrgTool");
        var leafOrgs = this.__getDependency("leafOrgs");
        var orgList = this.__getDependency("orgList");

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
            var self = this, SYSTEM_IDENTIFIER_ENUM = this.__getDependency("SYSTEM_IDENTIFIER_ENUM");

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
            this.__request({"apiUrl": "/api/settings", "requestType": "GET", "callback": function(result) { //check config
                callback(result);
            }});
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

        this.__checkFields = function(silent) {
            var hasError = false;

            /* check all required fields to make sure all fields are filled in */
            $("input[required], select[required]").each(function() {
                if (!$(this).val()) {
                    //this should display error message associated with empty field
                    if (!silent) {
                        $(this).trigger("focusout");
                    }
                    hasError = true;
                }
            });
            /* check email field */
            if ($("#noEmail").length > 0 && !$("#noEmail").is(":checked")) {
                if ($("#emailGroup").hasClass("has-error")) {
                    hasError = true;
                } else {
                    if ($("#current_user_email").val() === $("#email").val()) {
                        if (!silent) {
                            this.setHelpText("emailGroup", i18next.t("Email is already in use."), true);
                        }
                        hasError = true;
                    } else {
                        this.setHelpText("emailGroup", "", false);
                    }
                }
            }
            /* check organization */
            if ($("#userOrgs input").length > 0 && $("#userOrgs input:checked").length === 0) {
                if (!silent) {
                    this.setHelpText("userOrgs", i18next.t("An organization must be selected."), true);
                }
                hasError = true;
            } else {
                this.setHelpText("userOrgs", "", false);
            }

            /* finally check fields to make sure there isn't error, e.g. due to validation error */
            $("#createProfileForm .help-block.with-errors").each(function() {
                if ($(this).text() !== "") {
                    hasError = true;
                }
            });

            if (hasError) {
                if (!silent) {
                    $("#errorMsg").fadeIn("slow");
                }
            } else {
                $("#errorMsg").hide();
                $("#serviceErrorMsg").html("").hide();
            }
            return hasError;
        };
        this.clearError = function() {
            var hasError = this.__checkFields(true);
            if (!hasError) { $("#errorMsg").html("").hide(); }
        };
        this.setHelpText = function(elementId, message, hasError) {
            if (hasError) {
                $("#" + elementId).find(".help-block").text(message).addClass("error-message");
            }
            else {
                $("#" + elementId).find(".help-block").text("").removeClass("error-message");
            }
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
            $("#userOrgs input[name='organization']").on("click", function() {
                $("#userOrgs").find(".help-block").html("");
            });
            var visibleOrgs = $("#userOrgs input[name='organization']:visible");
            if (visibleOrgs.length === 1) {
                visibleOrgs.prop("checked", true);
            }
        };
        this.populatePatientOrgs = function() {
            if (leafOrgs) { /* global leafOrgs */
                OT.filterOrgs(leafOrgs);
            }
            var userOrgs = $("#userOrgs input[name='organization']");
            userOrgs.each(function() {
                $(this).closest("label").addClass("radio-label");
                $(this).attr("type", "radio");
            });
        };
        this.populateStaffOrgs = function() {
            if (orgList) { /*global orgList */
                OT.filterOrgs(orgList);
            }
        };
        this.getCommunicationArray = function() {
            var arrCommunication = [], SYSTEM_IDENTIFIER_ENUM = this.__getDependency("SYSTEM_IDENTIFIER_ENUM");
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
        this.getConsents = function() {
            var orgs = {}, consents = [], CONSENT_WITH_TOP_LEVEL_ORG = false;
            tnthAjax.setting("CONSENT_WITH_TOP_LEVEL_ORG", "", {sync: true}, function(data) {
                if (!data.error && data.CONSENT_WITH_TOP_LEVEL_ORG) {
                    CONSENT_WITH_TOP_LEVEL_ORG = true;
                }
            });
            $("#createProfileForm input[name='organization']").each(function() {
                if (!$(this).prop("checked")) { return true; }
                var consentOrgId = $(this).val();
                if (CONSENT_WITH_TOP_LEVEL_ORG) {
                    consentOrgId = getParentOrgId(this);
                }
                if (!consentOrgId || orgs.hasOwnProperty(consentOrgId)) {
                    return false;
                }
                orgs[consentOrgId] = true;
                var agreement = $("#" + getParentOrgId(this) + "_agreement_url").val() || $("#stock_consent_url").val();
                agreement = (agreement||"").replace("placeholder", encodeURIComponent($(this).attr("data-parent-name")));
                if (agreement) {
                    var ct = $("#consentDate").val();
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
                }
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
                var isValid = tnthDates.validateDateInputFields(m, d, y, "errorConsentDate");
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
        this.__getLoaderHTML = function(message) {
            return '<div class="loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i>' + (message ? "&nbsp;" + message : "") + '</div>';
        }
    };

    //events associated with elements on the account creation page
    $(document).ready(function(){
        var isStaff = $("#accountCreationContentContainer").attr("data-account") === "staff";
        var roles =  [{"name": "patient"}, {"name": "write_only"}];
        if (isStaff) {
            roles = [{"name": "staff"}, {"name": "write_only"}];
        }
        /* global i18next, tnthAjax, OrgTool, orgList, leafOrgs, SYSTEM_IDENTIFIER_ENUM */
        var aco = new AccountCreationObj(roles, {"i18next": i18next, "tnthAjax": tnthAjax, "OrgTool": new OrgTool(), "orgList": orgList, "leafOrgs": leafOrgs, SYSTEM_IDENTIFIER_ENUM: SYSTEM_IDENTIFIER_ENUM});
        /*** need to run this instead of the one function from main.js because we don't want to pre-check any org here ***/
        aco.getOrgs(aco.populateOrgsByRole);
        aco.handleEditConsentDate();
        $("#createProfileForm .optional-diplay-text").removeClass("tnth-hide");
        $("#createProfileForm .back-button-container").prepend(aco.__getLoaderHTML());
        $("#createProfileForm .save-button-container").prepend(aco.__getLoaderHTML());
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

        $("#createProfileForm").on("submit", function (e) {
            if (e.isDefaultPrevented()) {
                aco.__checkFields(); // handle the invalid form...
                return false;
            } else {
                var hasError = aco.__checkFields();
                if (hasError) { return false; }
                e.preventDefault(); // everything looks good!
                aco.__handleButton("hide");
                setTimeout(function() { aco.__setAccount(); } , 0);
            }
        });
    });
})();

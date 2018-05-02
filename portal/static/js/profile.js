/*
 * helper Object for initializing profile sections  TODO streamline this more
 */
(function() {
    var i18next = window.portalModules.i18next;
    var ProfileObj = window.ProfileObj = new Vue({
        el: "#mainDiv",
        components: {
            "section-view": {
                props: ["data", "nodatatext"],
                template: '<div v-if="data">{{data}}</div><div class="text-muted" v-else>{{nodatatext}}</div>'
            },
            "section-view-extension": {
                props: ["data", "nodatatext"],
                template: ' <div v-if="data"><p v-for="item in data">{{item.display}}</p></div><div class="text-muted" v-else>{{nodatatext}}</div>'
            }
        },
        errorCaptured: function(Error, Component, info) {
            console.error("Error: ", Error, " Component: ", Component, " Message: ", info);
            return false;
        },
        created: function() {
            DELAY_LOADING = true;
            this.registerDependencies();
            this.setUserSettings();
            this.onBeforeSectionsLoad();
            this.initStartTime = new Date();
            var self = this;
            if (this.subjectId) {
                this.initChecks.push({done: false});
                this.setDemoData(function() {
                    self.onInitChecksDone();
                });
            }
            if (this.currentUserId) { //get user roles - note using the current user Id - so we can determine: if user is an admin, if he/she can edit the consent, etc.
                this.initChecks.push({done: false});
                this.modules.tnthAjax.getRoles(this.currentUserId, false, function(data) {
                    if (data && data.roles) {
                        data.roles.forEach(function(role) {
                            self.currentUserRoles.push(role.name.toLowerCase());
                        });
                    }
                    self.onInitChecksDone();
                });
            }
            this.initChecks.push({ done: false});
            this.modules.tnthAjax.getConfiguration(this.currentUserId || this.subjectId, false, function(data) { //get config settings
                var CONSENT_WITH_TOP_LEVEL_ORG = "CONSENT_WITH_TOP_LEVEL_ORG";
                if (data) {
                    self.settings = data;
                    if (data.hasOwnProperty(CONSENT_WITH_TOP_LEVEL_ORG)) { //for use by UI later, e.g. handle consent submission
                        self.modules.tnthAjax.setConfigurationUI(CONSENT_WITH_TOP_LEVEL_ORG, data[CONSENT_WITH_TOP_LEVEL_ORG] + "");
                    }
                }
                self.onInitChecksDone();
            });
        },
        mounted: function() {
            var self = this;
            setTimeout(function() {self.setVis();}, 100);

            this.getOrgTool();
            this.initIntervalId = setInterval(function() { //wait for ajax calls to finish
                self.initEndTime = new Date();
                var elapsedTime = self.initEndTime - self.initStartTime;
                elapsedTime /= 1000;
                var checkFinished = true;
                if (self.initChecks.length > 0) {
                    checkFinished = (self.initChecks).filter(function(item) {
                        return item.done === true;
                    }).length === (self.initChecks).length;
                }
                if (checkFinished || (elapsedTime >= 5)) {
                    clearInterval(self.initIntervalId);
                    self.onSectionsDidLoad();
                    self.initSections(function() {
                        self.handleOptionalCoreData();
                    });
                }
            }, 10);
        },
        data: {
            subjectId: "",
            currentUserId: "",
            settings: {},
            orgTool: null,
            orgsList: {},
            orgsData: [],
            initChecks: [],
            initIntervalId: 0,
            currentUserRoles: [],
            userRoles: [],
            mode: "profile",
            demo: { //skeleton 
                data: {
                    email: "",
                    name: {given: "",family: ""},
                    birthDay: "",
                    birthMonth: "",
                    birthYear: ""
                }
            },
            roles: {data: []},
            CONSENT_ENUM: {
                "consented": {
                    "staff_editable": true,
                    "include_in_reports": true,
                    "send_reminders": true
                },
                "suspended": {
                    "staff_editable": true,
                    "include_in_reports": true,
                    "send_reminders": false
                },
                "purged": {
                    "staff_editable": false,
                    "include_in_reports": false,
                    "send_reminders": false
                }
            },
            CANCER_TREATMENT_CODE: "118877007",
            NONE_TREATMENT_CODE: "999",
            consent: {
                consentHeaderArray: [ //html for consent header cell in array
                    i18next.t("Organization"),
                    '<span class="eproms-consent-status-header">' + i18next.t("Consent Status") + '</span><span class="truenth-consent-status-header">' + i18next.t("Consent Status") + '</span>',
                    '<span class="agreement">' + i18next.t("Agreement") + '</span>',
                    '<span class="eproms-consent-date-header">' + i18next.t("Date") + '</span><span class="truenth-consent-date-header">' + i18next.t("Registration Date") + '</span> <span class="gmt">(' + i18next.t("GMT") + ')</span>'
                ],
                consentHistoryHeaderArray: [
                    i18next.t("Organization"),
                    '<span class="eproms-consent-status-header">' + i18next.t("Consent Status") + '</span><span class="truenth-consent-status-header">' + i18next.t("Consent Status") + '</span>',
                    i18next.t("Consent Date"),
                    i18next.t("Last Updated") + "<br/><span class='smaller-text'>" + i18next.t("( GMT, Y-M-D )") + "</span>",
                    i18next.t("User")
                ],
                consentLabels: {
                    "default": i18next.t("Consented"),
                    "consented": i18next.t("Consented / Enrolled"),
                    "withdrawn": "<span data-eproms='true'>" + i18next.t("Withdrawn - Suspend Data Collection and Report Historic Data") + "</span>" +
                        "<span data-truenth='true'>" + i18next.t("Suspend Data Collection and Report Historic Data") + "</span>",
                    "purged": "Purged / Removed"
                },
                consentItems: [],
                touObj: [],
                consentDisplayRows: [],
                consentListErrorMessage: "",
                consentLoading: false,
                showInitialConsentTerms: false,
                hasCurrentConsent: false,
                hasConsentHistory: false
            },
            assessment: {
                assessmentListItems: [],
                assessmentListError: ""
            },
            emailLog: {data: []},
            patientReport: {
                data: [],
                hasP3PReport: false
            },
            manualEntry: {
                loading: false,
                initloading: false,
                method: "",
                consentDate: "",
                completionDate: "",
                todayObj: {
                    displayDay: "",
                    displayMonth: "",
                    displayYear: ""
                },
                errorMessage: ""
            },
            fillViews: {},
            modules: {}
        },
        computed: {
    
        },
        methods: {
            registerDependencies: function() {
                var self = this;
                for (var key in window.portalModules) {
                    if ({}.hasOwnProperty.call(window.portalModules, key)) {
                        self.modules[key] = window.portalModules[key];
                    }
                }
            },
            notProvidedText: function() {
                return i18next.t("not provided");
            },
            onInitChecksDone: function() {
                this.initChecks = this.initChecks.map(function() {
                    return {"done": true};
                });
            },
            setDemoData: function(callback) {
                var self = this;
                callback = callback || function() {};
                if (!this.subjectId) {
                    callback();
                    return false;
                }
                this.modules.tnthAjax.getDemo(this.subjectId, "", "", function(data) {
                    if (data) {
                        self.demo.data = data;
                        if (data.telecom) {
                            data.telecom.forEach(function(item) {
                                if (item.system === "email") {
                                    self.demo.data.email = item.value;
                                }
                                if (item.system === "phone") {
                                    if (item.use === "mobile") {
                                        self.demo.data.cellPhone = item.value;
                                    }
                                    if (item.use === "home") {
                                        self.demo.data.homePhone = item.value;
                                    }
                                }
                            });
                        }
                        if (data.name) {
                            if (data.name.family && data.name.given) {
                                self.demo.data.fullName = data.name.given + " " + data.name.family;
                            } else if (data.name.family) {
                                self.demo.data.fullName = data.name.family;
                            } else if (data.name.given) {
                                self.demo.data.fullName = data.name.given;
                            }
                        } else {
                            self.demo.data.name = {family: "",given: ""};
                        }
                        var datesArray;
                        if (data.birthDate) {
                            datesArray = data.birthDate.split("-");
                            self.demo.data.displayBirthDate = self.modules.tnthDates.displayDateString(datesArray[1], datesArray[2], datesArray[0]);
                            self.demo.data.birthDay = datesArray[2];
                            self.demo.data.birthMonth = datesArray[1];
                            self.demo.data.birthYear = datesArray[0];
                        } else {
                            self.demo.data.displayBirthDate = "";
                            self.demo.data.birthDay = "";
                            self.demo.data.birthMonth = "";
                            self.demo.data.birthYear = "";
                        }
                        if (data.deceasedDateTime) {
                            datesArray = (data.deceasedDateTime).substring(0, (data.deceasedDateTime).indexOf("T")).split("-");
                            self.demo.data.displayDeceasedDate = self.modules.tnthDates.displayDateString(datesArray[1], datesArray[2], datesArray[0]);
                            self.demo.data.deceasedDay = datesArray[2];
                            self.demo.data.deceasedMonth = datesArray[1];
                            self.demo.data.deceasedYear = datesArray[0];
                        } else {
                            self.demo.data.displayDeceasedDate = "";
                            self.demo.data.deceasedDay = "";
                            self.demo.data.deceasedMonth = "";
                            self.demo.data.deceasedYear = "";
                        }

                        if (data.identifier) {
                            (data.identifier).forEach(function(item) {
                                if (item.system === "http://us.truenth.org/identity-codes/external-site-id") {
                                    data.siteId = item.value;
                                }
                                if (item.system === "http://us.truenth.org/identity-codes/external-study-id") {
                                    data.studyId = item.value;
                                }
                            });
                        }
                        self.demo.data.language = "";
                        if (data.communication) {
                            data.communication.forEach(function(o) {
                                if (o.language && o.language.coding) {
                                    o.language.coding.forEach(function(item) {
                                        if (item.display) item.display = i18next.t(item.display);
                                        self.demo.data.language = item;
                                        self.demo.data.languageCode = item.code;
                                        self.demo.data.languageDisplay = item.display;
                                    });
                                }
                            });
                        }
                        if (data.extension) {
                            (data.extension).forEach(function(item) {
                                if (item.url === "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity") {
                                    item.valueCodeableConcept.coding.forEach(function(ethnicity) {
                                        if (ethnicity.display) ethnicity.display = i18next.t(ethnicity.display);
                                        if (!self.demo.data.ethnicity) self.demo.data.ethnicity = [];
                                        self.demo.data.ethnicity.push(ethnicity);
                                        self.demo.data.ethnicityCodes = ethnicity.code;
                                    });
                                }
                                if (item.url === "http://hl7.org/fhir/StructureDefinition/us-core-race") {
                                    item.valueCodeableConcept.coding.forEach(function(race) {
                                        if (race.display) race.display = i18next.t(race.display);
                                        if (!self.demo.data.race) self.demo.data.race = [];
                                        self.demo.data.race.push(race);
                                    });
                                    if (self.demo.data.race) self.demo.data.raceCodes = self.demo.data.race.map(function(item) {
                                        return item.code;
                                    });
                                }
                                if (!self.demo.data.timezone && item.url === "http://hl7.org/fhir/StructureDefinition/user-timezone") {
                                    self.demo.data.timezone = item.timezone ? item.timezone : "";
                                }
                            });
                        }
                        if (!self.demo.data.raceCodes) self.demo.data.raceCodes = []; 
                    }
                    callback(data);
                });
            },
            setUserSettings: function() {
                if ($("#profileForm").length > 0) {
                    this.subjectId = $("#profileUserId").val();
                    this.currentUserId = $("#profileCurrentUserId").val();
                    this.mode = "profile";
                }
                if ($("#aboutForm").length > 0) {
                    this.subjectId = $("#iq_userId").val();
                    this.currentUserId = $("#iq_userId").val();
                    this.mode = "initialQueries";
                }
                if ($("#createProfileForm").length > 0) {
                    this.currentUserId = $("#currentStaffUserId").val();
                    this.mode = "createAccount";
                }
            },
            getOrgTool: function(callback) {
                if (!this.orgTool) {
                    var self = this;
                    callback = callback || function() {};
                    this.orgTool = new (this.modules.orgTool) ();
                    this.orgTool.init(function(data) {
                        if (data && !data.error) self.orgsData = data;
                        callback(data);
                    });
                    this.orgsList = this.orgTool.getOrgsList();
                }
                return this.orgTool;
            },
            isEditable: function() {
                var isStaff = this.currentUserRoles.indexOf("staff") !== -1;
                var isPatient = this.currentUserRoles.indexOf("patient") !== -1;
                var isEditableByStaff = this.settings.hasOwnProperty("CONSENT_EDIT_PERMISSIBLE_ROLES") && this.settings.CONSENT_EDIT_PERMISSIBLE_ROLES.indexOf("staff") !== -1;
                var isEditableByPatient = this.settings.hasOwnProperty("CONSENT_EDIT_PERMISSIBLE_ROLES") && this.settings.CONSENT_EDIT_PERMISSIBLE_ROLES.indexOf("patient") !== -1;

                return this.isAdmin() || (isStaff && isEditableByStaff) || (isPatient && isEditableByPatient);
            },
            isTestPatient: function() {
                return String(this.settings.SYSTEM_TYPE).toLowerCase() !== "production";
            },
            isAdmin: function() {
                return this.currentUserRoles.indexOf("admin") !== -1;
            },
            isConsentWithTopLevelOrg: function() {
                return this.settings.CONSENT_WITH_TOP_LEVEL_ORG;
            },
            getShowInMacro: function() {
                return this.settings.SHOW_PROFILE_MACROS || [];
            },
            onBeforeSectionsLoad: function() {
                if ($("#profileForm").length > 0) {
                    $("#mainDiv").addClass("profile");
                }
            },
            onSectionsDidLoad: function() {
                if (this.mode === "profile") { //Note, this attach loader indicator to element with the class data-loader-container, in order for this to work, the element needs to have an id attribute
                    var self = this;
                    setTimeout(function() {
                        $("#profileForm [data-loader-container]").each(function() {
                            var attachId = $(this).attr("id");
                            if (!attachId) {
                                return false;
                            }
                            self.getSaveLoaderDiv("profileForm", attachId);
                            var targetFields = $(this).find("input, select");
                            if (targetFields.length > 0) {
                                targetFields.each(function() {
                                    if ($(this).attr("type") === "hidden") {
                                        return false;
                                    }
                                    $(this).attr("data-save-container-id", attachId);
                                    var triggerEvent = $(this).attr("data-trigger-event");
                                    if (!triggerEvent) triggerEvent = $(this).attr("type") === "text" ? "blur" : "change";
                                    $(this).on(triggerEvent, function(e) {
                                        e.stopPropagation();
                                        var valid = this.validity ? this.validity.valid : true;
                                        if (valid) {
                                            var hasError = false;
                                            if ($(this).attr("data-error-field")) {
                                                var customErrorField = $("#" + $(this).attr("data-error-field"));
                                                if (customErrorField.length > 0) {
                                                    hasError = (customErrorField.text() !== "");
                                                }
                                            }
                                            if (!hasError && !$(this).attr("data-update-on-validated")) {
                                                self.modules.assembleContent.demo(self.subjectId, true, $(this));
                                            }
                                        }
                                    });
                                });
                            }
                        });

                        $("#loginAsButton").on("click", function(e) {
                            e.preventDefault();
                            e.stopPropagation();
                            self.handleLoginAs(e);
                        });

                        $("#profileForm .profile-item-container.editable").each(function() {
                            $(this).prepend('<input type="button" class="btn profile-item-edit-btn" value="{edit}" aria-label="{editButton}"></input>'.replace("{edit}", i18next.t("Edit")).replace("{editButton}", i18next.t("Edit Button")));
                        });

                        self.fillViews = self.setView();

                        $("#profileForm .profile-item-edit-btn").each(function() {
                            $(this).on("click", function(e) {
                                e.preventDefault();
                                var container = $(this).closest(".profile-item-container");
                                container.toggleClass("edit");
                                $(this).val(container.hasClass("edit") ? i18next.t("DONE") : i18next.t("EDIT"));
                                if (!container.hasClass("edit")) {
                                    container.find(".form-group").removeClass("has-error");
                                    container.find(".help-block.with-errors").html("");
                                    self.setDemoData();
                                    self.fillSectionView(container.attr("data-sections"));
                                    self.handleOptionalCoreData();
                                }
                            });
                        });
                        $("#userOrgs input[name='organization']").on("click", function(e) {
                            e.stopImmediatePropagation();
                            setTimeout(function() {
                                self.reloadSendPatientEmailForm(self.subjectId);
                            }, 150);
                        });
                    }, 50);
                }
            },
            setVis: function() {
                $("#mainHolder").css({"visibility": "visible", "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=100)","filter": "alpha(opacity=100)","-moz-opacity": 1,"-khtml-opacity": 1,"opacity": 1
                });
                setTimeout(function() {$("#loadingIndicator").hide();}, 150);
                DELAY_LOADING = false;
            },
            initSections: function(callback) {
                var self = this, sectionsInitialized = {}, initCount = 0;
                $("[data-profile-section-id]").each(function() {
                    var sectionId = $(this).attr("data-profile-section-id");
                    if (!sectionsInitialized[sectionId]) {
                        setTimeout(function() {
                            self.initSection(sectionId);
                        }, initCount += 50);
                        sectionsInitialized[sectionId] = true;
                    }
                });
                if (callback) {
                    setTimeout(function() {callback();}, initCount);
                }
            },
            handleOptionalCoreData: function() {
                var targetSection = $(".profile-item-container[data-sections='detail']"), self = this;
                if (targetSection.length > 0) {
                    var loadingElement = targetSection.find(".profile-item-loader");
                    loadingElement.show();
                    this.modules.tnthAjax.getOptionalCoreData(self.subjectId, false, function(data) {
                        if (data.optional) {
                            var sections = $("#profileForm .optional");
                            sections.each(function() {
                                var sectionElement = $(this);
                                var section = sectionElement.attr("data-section-id");
                                var parent = sectionElement.closest(".profile-item-container");
                                var visibleRows = parent.find(".view-container tr:visible").length;
                                var noDataContainer = parent.find(".no-data-container");
                                var btn = parent.find(".profile-item-edit-btn");
                                if (section) {
                                    if ((data.optional).indexOf(section) !== -1) {
                                        sectionElement.show();
                                        noDataContainer.html("");
                                        btn.show();
                                    } else {
                                        sectionElement.hide();
                                        if (visibleRows == 0) {
                                            noDataContainer.html("<p class='text-muted'>" + i18next.t("No information available") + "</p>");
                                            btn.hide();
                                        }
                                    }
                                }
                            });
                        }
                        loadingElement.hide();
                    });
                }
            },
            fillSectionView: function(sectionID) {
                if (sectionID && this.fillViews[sectionID]) this.fillViews[sectionID]();
            },
            setView: function() {
                var self = this;
                return {
                    "setContent": function(field, content) {
                        if ($.trim(content)) {
                            field.html(i18next.t(content));
                        } else {
                            field.html("<p class='text-muted'>" + i18next.t("not provided") + "</p>");
                        }
                    },
                    "deceased": function() {
                        if ($("#boolDeath").is(":checked")) {
                            $("#boolDeath_view").text(i18next.t("Patient is deceased"));
                            if ($("#deathDate").val() && !$("#deathDayContainer").hasClass("has-error") && !$("#deathMonthContainer").hasClass("has-error") && !$("#deathYearContainer").hasClass("has-error")) {
                                var displayString = self.modules.tnthDates.displayDateString($("#deathMonth").val(), $("#deathDay").val(), $("#deathYear").val());
                                $("#deathDate_view").text(i18next.t(displayString));
                            }
                        } else {
                            $("#boolDeath_view").html("<p class='text-muted'>" + i18next.t("not provided") + "</p>");
                            $("#deathDate_view").text("");
                        }
                    },
                    "clinical": function() {
                        var content = "",
                            tnthDates = self.modules.tnthDates;
                        if (!$("#biopsyDateContainer").hasClass("has-error")) {
                            var f = $("#patBiopsy input[name='biopsy']:checked");
                            var a = f.val();
                            var biopsyDate = $("#biopsyDate").val();
                            if (a == "true" && biopsyDate) {
                                var displayDate = "";
                                if ($.trim($("#biopsy_month option:selected").val() + $("#biopsy_year").val() + $("#biopsy_day").val())) {
                                    displayDate = tnthDates.displayDateString($("#biopsy_month option:selected").val(), $("#biopsy_day").val(), $("#biopsy_year").val());
                                }
                                if (!displayDate) displayDate = i18next.t("not provided");
                                content = f.closest("label").text();
                                content += "&nbsp;&nbsp;" + displayDate;
                            } else {
                                content = f.closest("label").text();
                            }
                            if (String(a) === "true") {
                                $("#biopsyDateContainer").show();
                            }
                            this.setContent($("#biopsy_view"), content);
                        }
                        this.setContent($("#pca_diag_view"), $("#patDiag input[name='pca_diag']:checked").closest("label").text());
                        this.setContent($("#pca_localized_view"), $("#patMeta input[name='pca_localized']:checked").closest("label").text());
                    }
                };
            },
            initSection: function(type) {
                switch (String(type).toLowerCase()) {
                case "demo":
                    this.initBirthdaySection();
                    this.initEmailSection();
                    this.initPhoneSection();
                    this.initAltPhoneSection();
                    break;
                case "patientonly":
                    this.initPatientReportSection();
                    this.initAssessmentListSection();
                    this.initClinicalQuestionsSection();
                    this.initPatientEmailFormSection();
                    this.initDeceasedSection();
                    break;
                case "communication":
                    this.initResetPasswordSection();
                    this.initCommunicationSection();
                    break;
                case "birthday":
                    this.initBirthdaySection();
                    break;
                case "locale":
                    this.initLocaleSection();
                    break;
                case "email":
                    this.initEmailSection();
                    break;
                case "patientemailform":
                    this.initPatientEmailFormSection();
                    break;
                case "staffemailform":
                    this.initStaffRegistrationEmailSection();
                    break;
                case "phone":
                    this.initPhoneSection();
                    break;
                case "altphone":
                    this.initAltPhoneSection();
                    break;
                case "resetpassword":
                    this.initResetPasswordSection();
                    break;
                case "timezone":
                    this.initTimeZoneSection();
                    break;
                case "deceased":
                    this.initDeceasedSection();
                    break;
                case "patientreport":
                    this.initPatientReportSection();
                    break;
                case "assessmentlist":
                    this.initAssessmentListSection();
                    break;
                case "clinicalquestions":
                    this.initClinicalQuestionsSection();
                    break;
                case "orgsstateselector":
                    this.initOrgsStateSelectorSection();
                    this.initConsentSection();
                    break;
                case "orgs":
                    this.initDefaultOrgsSection();
                    this.initConsentSection();
                    break;
                case "consent":
                    this.initConsentSection();
                    break;
                case "custompatientdetail":
                    this.initCustomPatientDetailSection();
                    break;
                case "roleslist":
                    this.initRolesListSection();
                    break;
                case "auditlog":
                    this.initAuditLogSection();
                    break;
                case "biopsy":
                    this.initBiopsySection();
                    break;
                }
            },
            handleLoginAs: function(e) {
                if (e) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                try { //sessionStorage does not work in private mode
                    sessionStorage.setItem("loginAsPatient", "true");
                } catch (ex) { //alert user if this is not set properly
                    alert(i18next.t("Unable to properly set session storage variable for login-as. ") + ex.message);
                }
                location.replace("/login-as/" + this.subjectId);
            },
            getSaveLoaderDiv: function(parentID, containerID) {
                var el = $("#" + containerID + "_load");
                if (el.length === 0) {
                    var c = $("#" + parentID + " #" + containerID), displayStyle = "";
                    if (c.length > 0) {
                        var snippet = '<div class="load-container">' + '<i id="' + containerID + '_load" class="fa fa-spinner fa-spin load-icon fa-lg save-info" style="margin-left:4px; margin-top:5px" aria-hidden="true"></i><i id="' + containerID + '_success" class="fa fa-check success-icon save-info" style="color: green" aria-hidden="true">Updated</i><i id="' + containerID + '_error" class="fa fa-times error-icon save-info" style="color:red" aria-hidden="true">' + i18next.t("Unable to Update.System error.") + '</i></div>';
                        if (window.getComputedStyle) {
                            displayStyle = window.getComputedStyle(c.get(0), null).getPropertyValue("display");
                        } else {
                            displayStyle = (c.get(0)).currentStyle.display;
                        }
                        if (String(displayStyle) === "block") {
                            c.append(snippet);
                        } else {
                            if (String(displayStyle) === "none" || !displayStyle) {
                                if (c.get(0).nodeName.toUpperCase() === "DIV" || c.get(0).nodeName.toUpperCase() === "P") {
                                    c.append(snippet);
                                } else {
                                    c.after(snippet);
                                }
                            } else {
                                c.after(snippet);
                            }
                        }
                    }
                }
            },
            initBirthdaySection: function() {
                $("#month").on("change", function() {
                    $(this).trigger("focusout");
                });
                $("#year", "#date").each(function() {
                    $(this).on("change", function() {
                        $(this).trigger("blur");
                    });
                });
                var self = this;
                ["year", "month", "date"].forEach(function(fn) {
                    var field = $("#" + fn);
                    var triggerEvent = field.attr("data-trigger-event") ? field.attr("data-trigger-event") : (field.attr("type") == "text" ? "blur" : "change");
                    field.on(triggerEvent, function() {
                        var y = $("#year"), m = $("#month"),d = $("#date");
                        var isValid = self.modules.tnthDates.validateDateInputFields(m, d, y, "errorbirthday");
                        if (isValid) {
                            $("#birthday").val(y.val() + "-" + m.val() + "-" + d.val());
                            self.demo.birthDate = $("#birthday").val();
                            $("#errorbirthday").html("");
                        } else {
                            $("#birthday").val("");
                            return false;
                        }

                    });
                });
                this.__convertToNumericField($("#date, #year"));
            },
            initLocaleSection: function() {
                var self = this;
                $("#locale").on("change", function() {
                    self.modules.tnthDates.clearSessionLocale();
                    setTimeout(function() {window.location.reload(true);}, 1000);
                });
            },
            getAccessUrl: function() {
                var url = "";
                this.modules.tnthAjax.accessUrl(this.subjectId, true, function(data) {
                    if (!data.error) {
                        url = data.url;
                    }
                });
                return url;
            },
            initEmailSection: function() {
                var self = this;
                $("#email").attr("data-update-on-validated", "true").attr("data-user-id", self.subjectId);
                $(".btn-send-email").blur();
            },
            "reloadSendPatientEmailForm": function(userId) {
                if ($("#sendPatientEmailTabContent").length > 0) { //update registration and assessment status email tiles in communications section, needed when org changes
                    var self = this; 
                    $("#sendPatientEmailTabContent").animate({opacity: 0}, function() {
                        $(this).css("opacity", 1);
                        setTimeout(function() {
                            var checkedOrgInput = $("#userOrgs input[name='organization']:checked");
                            if (checkedOrgInput.attr("id") !== "noOrgs") {
                                if (self.settings.hasOwnProperty("ACCEPT_TERMS_ON_NEXT_ORG") &&
                                    checkedOrgInput.attr("data-parent-name") === self.settings.ACCEPT_TERMS_ON_NEXT_ORG) {
                                    $("#profileassessmentSendEmailContainer").addClass("active");
                                    self.assessmentStatus(userId);
                                } else {
                                    $("#profileassessmentSendEmailContainer").removeClass("active");
                                }
                            }
                        }, 500);
                    });
                }
            },
            "assessmentStatus": function(userId) {
                var self = this;
                this.modules.tnthAjax.patientReport(userId, function(data) {
                    if (!data.error) {
                        var pcpReports;
                        if (data.user_documents) {
                            self.patientReport.data = data.user_documents;
                            pcpReports = $.grep(data.user_documents, function(document) {
                                return /P3P/gi.test(document.filename);
                            });
                            self.patientReport.hasP3PReport = pcpReports && pcpReports.length > 0;
                            if (self.patientReport.hasP3PReport) {
                                $("#btnProfileSendassessmentEmail").hide();
                                $("#assessmentStatusContainer .email-selector-container").hide();
                            }
                        }
                    }
                });
            },
            getEmailContent: function(userId, messageId) {
                this.modules.tnthAjax.emailLog(userId, function(data) {
                    if (data.messages) {
                        (data.messages).forEach(function(item) {
                            if (item.id == messageId) {
                                $("#emailBodyModal .body-content").html(item.body);
                                $("#emailBodyModal .body-content a").each(function() { // email content contains clickable link/button - need to prevent click event of those from being triggered
                                    $(this).on("click", function(e) {
                                        e.preventDefault();
                                        return false;
                                    });
                                });
                                $("#emailBodyModal .body-content style").remove(); //need to remove inline style specifications - as they can be applied globally and override the classes specified in stylesheet
                                $("#emailBodyModal .body-content a.btn").addClass("btn-tnth-primary");
                                $("#emailBodyModal .body-content td.btn, #emailBodyModal .body-content td.btn a").addClass("btn-tnth-primary").removeAttr("width").removeAttr("style");
                                $("#emailBodyModal").modal("show"); //remove inline style in email body, style here is already applied via css
                                return true;
                            }
                        });
                    }
                });
            },
            getEmailLog: function(userId, data) {
                var self = this;
                if (!data.error) {
                    if (data.messages && data.messages.length > 0) {
                        (data.messages).forEach(function(item) {
                            item.sent_at = self.modules.tnthDates.formatDateString(item.sent_at, "iso");
                            item.subject = "<a onclick='ProfileObj.getEmailContent(" + userId + "," + item.id + ")'><u>" + item.subject + "</u></a>";
                        });
                        $("#emailLogContent").html("<table id='profileEmailLogTable'></table>");
                        $("#profileEmailLogTable").bootstrapTable({
                            data: data.messages,
                            pagination: true,
                            pageSize: 5,
                            pageList: [5, 10, 25, 50, 100],
                            classes: "table table-responsive profile-email-log",
                            sortName: "sent_at",
                            sortOrder: "desc",
                            search: true,
                            smartDisplay: true,
                            showColumns: true,
                            toolbar: "#emailLogTableToolBar",
                            rowStyle: function rowStyle(row, index) {
                                return {
                                    css: {"background-color": (index % 2 != 0 ? "#F9F9F9" : "#FFF")}
                                };
                            },
                            formatShowingRows: function(pageFrom, pageTo, totalRows) {
                                var rowInfo;
                                rowInfo = i18next.t("Showing {pageFrom} to {pageTo} of {totalRows} records").
                                    replace("{pageFrom}", pageFrom).
                                    replace("{pageTo}", pageTo).
                                    replace("{totalRows}", totalRows);
                                $(".pagination-detail .pagination-info").html(rowInfo);
                                return rowInfo;
                            },
                            formatRecordsPerPage: function(pageNumber) {
                                return i18next.t("{pageNumber} records per page").replace("{pageNumber}", pageNumber);
                            },
                            undefinedText: "--",
                            columns: [{
                                field: "sent_at",
                                title: i18next.t("Date (GMT), Y-M-D"),
                                searchable: true,
                                sortable: true
                            }, {
                                field: "subject",
                                title: i18next.t("Subject"),
                                searchable: true,
                                sortable: true
                            }, {
                                field: "recipients",
                                title: i18next.t("Email"),
                                sortable: true,
                                searchable: true,
                                width: "20%"
                            }]
                        });
                        setTimeout(function() {
                            $("#lbEmailLog").addClass("active");
                        }, 100);
                    } else {
                        $("#emailLogContent").html("<span class='text-muted'>" + i18next.t("No audit entry found.") + "</span>");
                    }
                } else {
                    $("#emailLogMessage").text(data.error);
                }
            },
            initPatientEmailFormSection: function() {
                var self = this;

                if ($("#profileassessmentSendEmailContainer.active").length > 0) {
                    self.assessmentStatus(self.subjectId);
                }

                $("#userOrgs input[name='organization']").on("click", function(e) {
                    e.stopImmediatePropagation();
                    self.reloadSendPatientEmailForm(self.subjectId);
                });

                $(".email-selector").off("change").on("change", function() {
                    var message = "";
                    var emailType = $(this).closest(".profile-email-container").attr("data-email-type");
                    var btnEmail = $("#btnProfileSend" + emailType + "Email");
                    var messageContainer = $("#profile" + emailType + "EmailMessage");
                    if (this.value != "" && $("#email").val() != "" && $("#erroremail").text() == "") {
                        message = i18next.t("{emailType} email will be sent to {email}");
                        message = message.replace("{emailType}", $(this).children("option:selected").text())
                            .replace("{email}", $("#email").val());
                        messageContainer.html(message);
                        btnEmail.removeClass("disabled");
                    } else {
                        messageContainer.html("");
                        btnEmail.addClass("disabled");
                    }
                });

                $(".btn-send-email").off("click").on("click", function(event) {
                    event.preventDefault();
                    event.stopPropagation();
                    var emailType = $(this).closest(".profile-email-container").attr("data-email-type");
                    var emailTypeElem = $("#profile" + emailType + "EmailSelect"), selectedOption = emailTypeElem.children("option:selected");
                    var infoMessageContainer = $("#profile" + emailType + "EmailMessage"), errorMessageContainer = $("#profile" + emailType + "EmailErrorMessage");
                    var btnSelf = $(this);

                    if (selectedOption.val() !== "") {
                        var emailUrl = selectedOption.attr("data-url"), email = $("#email").val(), subject = "", body = "", returnUrl = "";
                        if (emailUrl) {
                            $.ajax({ //get email content via API
                                type: "GET",
                                url: emailUrl,
                                cache: false,
                                async: false
                            }).done(function(data) {
                                if (data) {
                                    subject = data.subject;
                                    body = data.body;
                                }
                            }).fail(function(xhr) { //report error
                                self.modules.tnthAjax.reportError(self.subjectId, emailUrl, xhr.responseText);
                            });
                        } else {
                            errorMessageContainer.append("<div>" + i18next.t("Url for email content is unavailable.") + "</div>");
                        }

                        if (body && subject && email) {
                            var inviteError = "";
                            if (selectedOption.val() === "invite" && emailType === "registration") {
                                returnUrl = self.getAccessUrl();
                                if (returnUrl) {
                                    body = body.replace(/url_placeholder/g, decodeURIComponent(returnUrl));
                                } else {
                                    inviteError = i18next.t("failed request to get email invite url");
                                }
                            }
                            if (inviteError) {
                                errorMessageContainer.html(inviteError);
                            } else {
                                self.modules.tnthAjax.invite(self.subjectId, {
                                    "subject": subject,
                                    "recipients": email,
                                    "body": body
                                }, function(data) {
                                    if (!data.error) {
                                        infoMessageContainer.html("<strong class='text-success'>" + i18next.t("{emailType} email sent to {emailAddress}").replace("{emailType}", selectedOption.text()).replace("{emailAddress}", email) + "</strong>");
                                        emailTypeElem.val("");
                                        btnSelf.addClass("disabled");
                                        self.modules.tnthAjax.emailLog(self.subjectId, function(data) { //reload email audit log
                                            setTimeout(function() {
                                                self.getEmailLog(self.subjectId, data);
                                            }, 100);
                                        });
                                    } else {
                                        errorMessageContainer.append("<div>" + i18next.t("Unable to send email") + "</div>");
                                    }
                                });
                            }
                        } else {
                            errorMessageContainer.html("");
                            errorMessageContainer.append("<div>" + i18next.t("Unable to send email.") + "</div>");
                            if (!body) {
                                errorMessageContainer.append("<div>" + i18next.t("Email body content is missing.") + "</div>");
                            }
                            if (!subject) {
                                errorMessageContainer.append("<div>" + i18next.t("Email subject is missing.") + "</div>");
                            }
                            if (!email) {
                                errorMessageContainer.append("<div>" + i18next.t("Email address is missing.") + "</div>");
                            }
                        }
                    } else errorMessageContainer.text(i18next.t("You must select a email type"));
                });
            },
            initStaffRegistrationEmailSection: function() {
                var self = this;
                $("#btnProfileSendEmail").on("click", function(event) {
                    event.preventDefault();
                    var email = $("#email").val(), subject = "", body = "", return_url = "";
                    var clinicName = (function() {
                        var orgs = $("#userOrgs input[name='organization']:checked"), parentName = "";
                        if (orgs.length > 0) {
                            orgs.each(function() {
                                if (!parentName) {
                                    parentName = $(this).attr("data-parent-name");
                                    if (!parentName) parentName = $(this).closest(".org-container[data-parent-id]").attr("data-parent-name");
                                }
                            });
                        }
                        var cn = parentName ? parentName : i18next.t("your clinic");
                        return cn;
                    })();
                    $.ajax({
                        type: "GET",
                        url: $("#staffRegistrationEmailUrl").val(),
                        cache: false,
                        async: false
                    }).done(function(data) {
                        if (data) {
                            subject = data.subject;
                            body = data.body;
                        }
                    }).fail(function() {});

                    if (!body) { ////provide default body content if no body content was returned from ajax call
                        body = "<p>" + i18next.t("Hello, this is an invitation to complete your registration.") + "</p>";
                        return_url = self.getAccessUrl();
                        if (return_url) {
                            body += "<a href='" + decodeURIComponent(return_url) + "'>" + i18next.t("Verify your account to complete registration") + "</a>";
                        }
                    }
                    if (!subject) {
                        subject = i18next.t("Registration invite from {clinicName}").replace("{clinicName}", clinicName);
                    }

                    self.modules.tnthAjax.invite(self.subjectId, {
                        "subject": subject,"recipients": email,"body": body}, function(data) {
                        if (!data.error) {
                            $("#profileEmailMessage").text(i18next.t("invite email sent to {email}").replace("{email}", email));
                            $("#btnProfileSendEmail").attr("disabled", true);
                        } else {
                            if (data.error) $("#profileEmailErrorMessage").text(i18next.t("Unable to send email."));
                        }
                    });
                });
            },
            initCommunicationSection: function() {
                $("#communicationsContainer .tab-label").on("click", function() {
                    $("#communicationsContainer .tab-label").removeClass("active");
                    $(this).addClass("active");
                });
                $("#emailBodyModal").modal({"show": false});
                var subjectId = this.subjectId, self = this;
                this.modules.tnthAjax.emailLog(subjectId, function(data) {
                    setTimeout(function() {
                        self.getEmailLog(subjectId, data);
                    }, 100);
                });
            },
            initPhoneSection: function() {
                this.__convertToNumericField($("#phone"));
            },
            initAltPhoneSection: function() {
                this.__convertToNumericField($("#altPhone"));
            },
            initResetPasswordSection: function() {
                var self = this;
                $("#btnPasswordResetEmail").on("click", function(event) {
                    event.preventDefault();
                    event.stopImmediatePropagation(); //stop bubbling of events
                    var email = $("#email").val();
                    if (email) {
                        self.modules.tnthAjax.passwordReset(self.subjectId, function(data) {
                            if (!data.error) {
                                $("#passwordResetMessage").text(i18next.t("Password reset email sent to {email}").replace("{email}", email));
                            } else {
                                $("#passwordResetMessage").text(i18next.t("Unable to send email."));
                            }
                        });
                    } else {
                        $("#passwordResetMessage").text(i18next.t("No email address found for user"));
                    }
                });
            },
            initTimeZoneSection: function() {
                var self = this;
                self.getSaveLoaderDiv("profileForm", "profileTimeZoneGroup");
                $("#profileTimeZone").on("change", function() {
                    $(".timezone-error").html("");
                    $(".timezone-warning").html("");
                    self.modules.assembleContent.demo(self.subjectId, true, $(this), true);
                });
            },
            updateDeceasedSection: function(deceasedDateTime, deceasedBoolean) {
                if (deceasedDateTime) {
                    var datesArray = (deceasedDateTime).substring(0, (deceasedDateTime).indexOf("T")).split("-");
                    $("#deathYear").val(datesArray[0]);
                    $("#deathMonth").val(datesArray[1]);
                    $("#deathDay").val(datesArray[2]);
                    $("#deathDate").val(datesArray[0] + "-" + datesArray[1] + "-" + datesArray[2]);
                    $("#boolDeath").prop("checked", true);
                } else {
                    $("#deathYear").val("");
                    $("#deathMonth").val("");
                    $("#deathDay").val("");
                    $("#deathDate").val("");
                    $("#boolDeath").prop("checked", false);
                }
                if (deceasedBoolean) {
                    if (String(deceasedBoolean).toLowerCase() == "true") {
                        $("#boolDeath").prop("checked", true);
                    } else $("#boolDeath").prop("checked", false);
                }
                this.fillSectionView("deceased");
            },
            initDeceasedSection: function() {
                var self = this;
                if (this.demo.data.deceasedDateTime || this.demo.data.hasOwnProperty("deceasedBoolean")) this.updateDeceasedSection(this.demo.data.deceasedDateTime, this.demo.data.deceasedBoolean);
                else {
                    this.modules.tnthAjax.getDemo(this.subjectId, false, false, function(data) {
                        self.updateDeceasedSection(data.deceasedDateTime, data.deceasedBoolean);
                    });
                }
                this.__convertToNumericField($("#deathDay, #deathYear"));
                var saveLoaderDiv = self.getSaveLoaderDiv;
                saveLoaderDiv("profileForm", "boolDeathGroup");
                $("#boolDeath").on("change", function() {
                    if (!($(this).is(":checked"))) {
                        $("#deathYear").val("");
                        $("#deathDay").val("");
                        $("#deathMonth").val("");
                        $("#deathDate").val("");
                    }
                    self.modules.assembleContent.demo(self.subjectId, true, $(this));
                });

                ["deathDay", "deathMonth", "deathYear"].forEach(function(fn) {
                    saveLoaderDiv("profileForm", $("#" + fn).attr("data-save-container-id"));
                    var fd = $("#" + fn);
                    var triggerEvent = fd.attr("type") == "text" ? "blur" : "change";
                    fd.on(triggerEvent, function() {
                        var d = $("#deathDay"), m = $("#deathMonth"), y = $("#deathYear");
                        if (d.val() != "" && m.val() != "" && y.val() != "") {
                            if (d.get(0).validity.valid && m.get(0).validity.valid && y.get(0).validity.valid) {
                                var errorMsg = self.modules.tnthDates.dateValidator(d.val(), m.val(), y.val(), true);
                                if (errorMsg === "") {
                                    $("#deathDate").val(y.val() + "-" + m.val() + "-" + d.val());
                                    $("#boolDeath").prop("checked", true);
                                    $("#errorDeathDate").text("");
                                    self.modules.assembleContent.demo(self.subjectId, true, $(this));
                                } else {
                                    $("#errorDeathDate").text(errorMsg);
                                }
                            }
                        }
                    });
                });
            },
            initPatientReportSection: function() {
                var self = this;
                this.modules.tnthAjax.patientReport(self.subjectId, function(data) {
                    if (!data.error) {
                        if (data.user_documents && data.user_documents.length > 0) {
                            self.patientReport.data = data.user_documents;
                            var fData = [];
                            (data.user_documents).forEach(function(item) {
                                item.filename = self.escapeHtml(item.filename);
                                item.document_type = self.escapeHtml(item.document_type);
                                item.uploaded_at = self.modules.tnthDates.formatDateString(item.uploaded_at, "iso");
                                item.actions = '<a title="' + i18next.t("Download") + '" href="' + '/api/user/' + String(item.user_id) + '/user_documents/' + String(item.id) + '"><i class="fa fa-download"></i></a>';
                                fData.push(item);
                            });

                            $("#profilePatientReportTable").bootstrapTable({
                                data: fData,
                                pagination: true,
                                pageSize: 5,
                                pageList: [5, 10, 25, 50, 100],
                                classes: "table table-responsive profile-patient-reports",
                                sortName: "uploaded_at",
                                sortOrder: "desc",
                                search: true,
                                smartDisplay: true,
                                showToggle: true,
                                showColumns: true,
                                toolbar: "#prTableToolBar",
                                rowStyle: function rowStyle(row, index) {
                                    return {
                                        css: {
                                            "background-color": (index % 2 != 0 ? "#F9F9F9" : "#FFF")
                                        }
                                    };
                                },
                                formatShowingRows: function(pageFrom, pageTo, totalRows) {
                                    var rowInfo;
                                    rowInfo = i18next.t("Showing {pageFrom} to {pageTo} of {totalRows} records").
                                        replace("{pageFrom}", pageFrom).
                                        replace("{pageTo}", pageTo).
                                        replace("{totalRows}", totalRows);
                                    $(".pagination-detail .pagination-info").html(rowInfo);
                                    return rowInfo;
                                },
                                formatRecordsPerPage: function(pageNumber) {
                                    return i18next.t("{pageNumber} records per page").replace("{pageNumber}", pageNumber);
                                },
                                undefinedText: "--",
                                columns: [{
                                    field: "contributor",
                                    title: i18next.t("Type"),
                                    searchable: true,
                                    sortable: true
                                }, {
                                    field: "filename",
                                    title: i18next.t("Report Name"),
                                    searchable: true,
                                    sortable: true
                                }, {
                                    field: "uploaded_at",
                                    title: i18next.t("Generated (GMT)"),
                                    sortable: true,
                                    searchable: true,
                                    width: "20%"
                                }, {
                                    field: "document_type",
                                    title: i18next.t("Document Type"),
                                    sortable: true,
                                    visible: false
                                }, {
                                    field: "actions",
                                    title: i18next.t("Download"),
                                    sortable: false,
                                    searchable: false,
                                    visible: true,
                                    class: "text-center"
                                }]
                            });
                        } else {
                            $("#patientReportErrorMessage").text(i18next.t("No reports available.")).removeClass("error-message");
                        }

                    } else {
                        $("#profilePatientReportTable").closest("div.profile-item-container").hide();
                        $("#patientReportErrorMessage").text(i18next.t("Problem retrieving reports from server.")).addClass("error-message");
                    }
                });
            },
            initAssessmentListSection: function() {
                var self = this;
                self.modules.tnthAjax.assessmentList(self.subjectId, function(data) {
                    if (!data.error) {
                        var sessionUserId = $("#_session_user_id").val();
                        var entries = data.entry ? data.entry : null;
                        if (entries && entries.length > 0) {
                            self.assessment.assessmentListError = "";
                            entries.forEach(function(entry, index) {
                                var reference = entry.questionnaire.reference;
                                var arrRefs = String(reference).split("/");
                                var instrumentId = arrRefs.length > 0 ? arrRefs[arrRefs.length - 1] : "";
                                var authoredDate = String(entry.authored);
                                if (instrumentId) {
                                    var reportLink = "/patients/session-report/" + sessionUserId + "/" + instrumentId + "/" + authoredDate;
                                    self.assessment.assessmentListItems.push({
                                        title: i18next.t("Click to view report"),
                                        link: reportLink,
                                        display: i18next.t(entry.questionnaire.display),
                                        status: i18next.t(entry.status),
                                        class: (index % 2 !== 0 ? "class='odd'" : "class='even'"),
                                        date: self.modules.tnthDates.formatDateString(entry.authored, "iso")
                                    });
                                }
                            });
                        }

                    } else {
                        self.assessment.assessmentListError = i18next.t("Problem retrieving session data from server.");
                    }
                });
            },
            initOrgsStateSelectorSection: function() {
                var self = this, orgTool = this.getOrgTool(), subjectId = this.subjectId;
                var stateDict={AL: i18next.t("Alabama"),AK: i18next.t("Alaska"), AS: i18next.t("American Samoa"),AZ: i18next.t("Arizona"),AR:i18next.t("Arkansas"),CA: i18next.t("California"),CO:i18next.t("Colorado"),CT:i18next.t("Connecticut"),DE:i18next.t("Delaware"),DC:i18next.t("District Of Columbia"),FM: i18next.t("Federated States Of Micronesia"),FL:i18next.t("Florida"),GA:i18next.t("Georgia"),GU:i18next.t("Guam"),HI:i18next.t("Hawaii"),ID:i18next.t("Idaho"),IL:i18next.t("Illinois"),IN:i18next.t("Indiana"),IA:i18next.t("Iowa"),KS:i18next.t("Kansas"),KY:i18next.t("Kentucky"),LA:i18next.t("Louisiana"),ME:i18next.t("Maine"),MH:i18next.t("Marshall Islands"),MD:i18next.t("Maryland"),MA:i18next.t("Massachusetts"),MI:i18next.t("Michigan"),MN:i18next.t("Minnesota"),MS:i18next.t("Mississippi"),MO:i18next.t("Missouri"),MT:i18next.t("Montana"),NE: i18next.t("Nebraska"),NV:i18next.t("Nevada"),NH:i18next.t("New Hampshire"),NJ:i18next.t("New Jersey"),NM:i18next.t("New Mexico"),NY:i18next.t("New York"),NC:i18next.t("North Carolina"),ND:i18next.t("North Dakota"),MP:i18next.t("Northern Mariana Islands"),OH:i18next.t("Ohio"),OK:i18next.t("Oklahoma"),OR:i18next.t("Oregon"),PW:i18next.t("Palau"),PA:i18next.t("Pennsylvania"),PR:i18next.t("Puerto Rico"),RI:i18next.t("Rhode Island"),SC:i18next.t("South Carolina"),SD:i18next.t("South Dakota"),TN:i18next.t("Tennessee"),TX:i18next.t("Texas"),UT:i18next.t("Utah"),VT:i18next.t("Vermont"),VI:i18next.t("Virgin Islands"),VA:i18next.t("Virginia"),WA:i18next.t("Washington"),WV:i18next.t("West Virginia"),WI:i18next.t("Wisconsin"),WY:i18next.t("Wyoming")};
                this.getSaveLoaderDiv("profileForm", "userOrgs");
                $("#stateSelector").on("change", function() {
                    var selectedState = $(this).find("option:selected"),
                        container = $("#" + selectedState.val() + "_container");
                    var defaultPrompt = i18next.t("What is your main clinic for prostate cancer care");
                    $("#userOrgsInfo").hide();
                    if (selectedState.val() != "") {
                        if (selectedState.val() == "none") {
                            $(".state-container, .noOrg-container").hide();
                            $(".clinic-prompt").text("").hide();
                            $("#noOrgs").prop("checked", true).trigger("click");
                            //send of ajax to update org to 0 here
                        } else {
                            if (container.length > 0) {
                                $(".state-container").hide();
                                $(".clinic-prompt").text(defaultPrompt + " in " + selectedState.text() + "?").show();
                                $(".noOrg-container").show();
                                $("#noOrgs").prop("checked", false);
                                container.show();
                            } else {
                                $(".state-container, .clinic-prompt, .noOrg-container").hide();
                                $("#userOrgsInfo").show();
                            }
                        }
                    } else {
                        $(".state-container, .noOrg-container").hide();
                        $(".clinic-prompt").text("").hide();
                    }
                });

                var orgsList = this.orgsList;
                var states = {},
                    contentHTML = "";
                var getParentState = function(o, states) {
                    if (!o) return "";
                    var s = "",
                        found = false;
                    for (var state in states) {
                        if (!found) {
                            (states[state]).forEach(function(i) {
                                if (i == o) {
                                    s = state;
                                    found = true;
                                }
                            });
                        }
                    }
                    return s;
                };

                /**** draw state select element first to gather all states
                    assign orgs to each state in array
                ***/
                (this.orgsData).forEach(function(item) {
                    var __state = "";
                    if (item.identifier) {
                        (item.identifier).forEach(function(region) {
                            if (region.system === "http://us.truenth.org/identity-codes/practice-region" && region.value) {
                                __state = (region.value).split(":")[1];
                                if (!states[__state]) {
                                    states[__state] = [item.id];
                                    $("#userOrgs .main-state-container").prepend("<div id='" + __state + "_container' state='" + __state + "' class='state-container'></div>");
                                } else {
                                    (states[__state]).push(item.id);
                                }

                                if ($("#stateSelector option[value='" + __state + "']").length === 0) {
                                    $("#stateSelector").append("<option value='" + __state + "'>" + stateDict[__state] + "</option>");
                                }
                                /*
                                 * assign state for each item
                                 */
                                orgsList[item.id].state = __state;
                            }
                        });
                    }
                });

                /*
                 * If an organization is a top level org and has child orgs, we render legend for it.  This will prevent the organization from being selected by the user.
                 * Note: a hidden input field is rendered for the organization so it can still be referenced by the child orgs if necessary.
                 */
                var parentOrgs = $.grep(this.orgsData, function(item) {
                    return parseInt(item.id) !== 0 && !item.partOf;
                });

                parentOrgs = parentOrgs.sort(function(a, b) { //sort parent orgs so ones with children displayed first
                    var oo_1 = orgsList[a.id];
                    var oo_2 = orgsList[b.id];
                    if (oo_1 && oo_2) {
                        if (oo_1.children.length > 0 && oo_2.children.length > 0) {
                            if (a.name < b.name) return -1;
                            if (a.name > b.name) return 1;
                            return 0;
                        } else if (oo_1.children.length > 0 && oo_2.children.length == 0) return -1;
                        else if (oo_2.children.length > 0 && oo_1.children.length == 0) return 1;
                        else {
                            if (a.name < b.name) return -1;
                            if (a.name > b.name) return 1;
                            return 0;
                        }
                    } else return 0;
                });

                parentOrgs.forEach(function(item) {
                    var state = orgsList[item.id].state;
                    if ($("#" + state + "_container").length > 0) {
                        var oo = orgsList[item.id];
                        if (oo.children.length > 0) {
                            contentHTML = "<legend orgId='{orgId}'>{translatedOrgName}</legend>";
                            contentHTML += "<input class='tnth-hide' type='checkbox' name='organization' parent_org='true' org_name='{orgName}' ";
                            contentHTML += " id='{orgId}_org' value='{orgId}' />";
                            contentHTML = contentHTML.replace(/\{orgId\}/g, item.id)
                                .replace(/\{orgName\}/g, item.name)
                                .replace(/\{translatedOrgName\}/g, i18next.t(item.name));
                        } else { //also need to check for top level orgs that do not have children and render those
                            contentHTML = "<div class='radio parent-singleton'>" +
                                "<label><input class='clinic' type='radio' id='{orgId}_org' value='{orgId}' state='{state}' name='organization' data-parent-name='{orgName}' data-parent-id='{orgId}'>{translatedOrgName}</label>" +
                                "</div>";
                            contentHTML = contentHTML.replace(/\{orgId\}/g, item.id)
                                .replace(/\{state\}/g, state)
                                .replace(/\{orgName\}/g, item.name)
                                .replace(/\{translatedOrgName\}/g, i18next.t(item.name));
                        }
                        $("#" + state + "_container").append(contentHTML);
                    }
                });

                var childOrgs = $.grep(this.orgsData, function(item) { //draw input element(s) that belongs to each state based on parent organization id
                    return parseInt(item.id) !== 0 && item.partOf;
                });

                childOrgs = childOrgs.sort(function(a, b) { //// sort child clinics in alphabetical order
                    if (a.name < b.name) return 1;
                    if (a.name > b.name) return -1;
                    return 0;
                });

                childOrgs.forEach(function(item) {
                    var parentId = (item.partOf.reference).split("/")[2];
                    if (parentId) {
                        var parentState = getParentState(parentId, states);

                        contentHTML = "<div class='radio'>" +
                            "<label class='indent'><input class='clinic' type='radio' id='{orgId}_org' value='{orgId}' state='{state}' name='organization' data-parent-name='{parentOrgName}' data-parent-id='{parentOrgId}'>{translatedOrgName}</label>" +
                            "</div>";
                        contentHTML = contentHTML.replace(/\{orgId\}/g, item.id)
                            .replace(/\{state\}/g, parentState)
                            .replace(/\{parentOrgName\}/g, item.name)
                            .replace(/\{parentOrgId\}/g, parentId)
                            .replace(/\{translatedOrgName\}/g, i18next.t(item.name));

                        if ($("#" + parentState + "_container legend[orgId='" + parentId + "']").length > 0) {
                            $("#" + parentState + "_container legend[orgId='" + parentId + "']").after(contentHTML);
                        } else {
                            $("#" + parentState + "_container").append(contentHTML);
                        }
                    }
                });

                var selectOptions = $("#stateSelector").sortOptions();
                if (selectOptions.length > 0) {
                    $("#stateSelector").empty().append(selectOptions)
                        .append("<option value='none'>" + i18next.t("Other") + "</option>")
                        .prepend("<option value='' selected>" + i18next.t("Select") + "</option>")
                        .val("");
                    $(".state-container, .clinic-prompt").hide();
                    setTimeout(function() { //case of pre-selected clinic, need to check if any clinic has prechecked
                        var o = $("#userOrgs input[name='organization']:checked");
                        if (o.length > 0 && o.val() != 0) {
                            o.closest(".state-container").show();
                            $(".clinic-prompt").show();
                        }
                    }, 150);
                    $("#userOrgs input[name='organization']").each(function() {
                        if (parseInt($(this).val()) !== 0) orgTool.getDefaultModal(this);
                    });
                    orgTool.onLoaded(subjectId);
                    self.updateOrgsSection();
                } else { // if no states found, then need to draw the orgs UI
                    $("#userOrgs .selector-show").hide();
                    orgTool.onLoaded(subjectId, true);
                    self.updateOrgsSection(function() {
                        orgTool.filterOrgs(orgTool.getHereBelowOrgs());
                        orgTool.morphPatientOrgs();
                        $(".noOrg-container, .noOrg-container *").show();
                    });
                }
                if ($("#mainDiv.profile").length > 0) {
                    self.modules.tnthAjax.getConsent(subjectId, true, function(data) {
                        self.getConsentList(data);
                    });
                }

                $("#clinics").attr("loaded", true);

            },
            initDefaultOrgsSection: function() {
                var subjectId = this.subjectId;
                var orgTool = this.getOrgTool();
                var self = this;
                orgTool.onLoaded(subjectId, true);
                this.getSaveLoaderDiv("profileForm", "userOrgs");
                this.updateOrgsSection(
                    function() {
                        if ((typeof leafOrgs !== "undefined") && leafOrgs) {
                            orgTool.filterOrgs(leafOrgs);
                        }
                        if ($("#requireMorph").val()) {
                            orgTool.morphPatientOrgs();
                        }
                        self.modules.tnthAjax.getConsent(subjectId, true, function(data) {
                            self.getConsentList(data);
                        });
                        $("#clinics").attr("loaded", true);
                    });
            },
            updateOrgsSection: function(callback) {
                callback = callback || function() {};
                var data = this.demo.data ? this.demo.data : null;
                if (data && data.careProvider) {
                    $.each(data.careProvider, function(i, val) {
                        var orgID = val.reference.split("/").pop();
                        if (parseInt(orgID) === 0) {
                            $("#userOrgs #noOrgs").prop("checked", true);
                            if ($("#stateSelector").length > 0) $("#stateSelector").find("option[value='none']").prop("selected", true).val("none");
                        } else {
                            var ckOrg = $("#userOrgs input.clinic[value=" + orgID + "]");
                            if ($(".state-container").length > 0) {
                                if (ckOrg.length > 0) {
                                    ckOrg.prop("checked", true);
                                    var state = ckOrg.attr("state");
                                    if (state) {
                                        $("#stateSelector").find("option[value='" + state + "']").prop("selected", true).val(i18next.t(state));
                                    }
                                }
                                $(".noOrg-container").show();
                            } else {
                                if (ckOrg.length > 0) ckOrg.prop("checked", true);
                                else {
                                    var topLevelOrg = $("#fillOrgs").find("legend[orgid='" + orgID + "']");
                                    if (topLevelOrg.length > 0) topLevelOrg.attr("data-checked", "true");
                                }
                            }
                        }
                    });
                }
                callback(data);
            },
            initConsentSection: function() {
                var __self = this;
                $("#consentHistoryModal").modal({"show": false});
                $(".consent-modal").each(function() {
                    var agreemntUrl = $(this).find(".agreement-url").val();
                    if (/stock\-org\-consent/.test(agreemntUrl)) {
                        $(this).find(".terms-wrapper").hide();
                    }
                });
                $("#consentContainer input[name='toConsent']").each(function() {
                    $(this).on("click", function(e) {
                        e.stopPropagation();
                        $("#consentContainer button.btn-consent-close, #consentContainer button[data-dismiss]").attr("disabled", true);
                        var orgId = $(this).attr("data-org");
                        var userId = $("#fillOrgs").attr("userId");
                        $("#" + orgId + "_loader").show();
                        if ($(this).val() == "yes") {
                            (function(orgId) {
                                var params = __self.CONSENT_ENUM.consented;
                                params.org = orgId;
                                params.agreementUrl = $("#" + orgId + "_agreement_url").val();
                                setTimeout(function() {
                                    __self.modules.tnthAjax.setConsent(userId, params);
                                }, 10);
                                setTimeout(function() {
                                    __self.modules.tnthAjax.removeObsoleteConsent();
                                }, 100);
                            })(orgId);
                        } else {
                            __self.modules.tnthAjax.deleteConsent(userId, {
                                "org": orgId
                            });
                            setTimeout(function() {
                                __self.modules.tnthAjax.removeObsoleteConsent();
                            }, 100);
                        }
                        setTimeout(function() {
                            __self.reloadConsentList(userId);
                        }, 500);
                        setTimeout(function() {
                            $(".modal").modal("hide");
                        }, 250);
                    });
                });
                $(document).delegate("#consentContainer button[data-dismiss]", "click", function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    setTimeout(function() {
                        location.reload();
                    }, 10);
                });
                $("#consentContainer .modal").each(function() {
                    $(this).on("hidden.bs.modal", function() {
                        if ($("#consentContainer input[name='toConsent']:checked").length > 0) {
                            var userId = $("#fillOrgs").attr("userId");
                            __self.modules.assembleContent.demo(userId, true, $("#userOrgs input[name='organization']:checked"), true);
                        }
                    });
                    $(this).on("show.bs.modal", function() {
                        $("#consentContainer .loading-message-indicator").hide();
                        $("#consentContainer button.btn-consent-close, #consentContainer button[data-dismiss]").attr("disabled", false).show();
                        var checkedOrg = $("#userOrgs input[name='organization']:checked");
                        var shortName = checkedOrg.attr("data-short-name") || checkedOrg.attr("data-org-name");
                        if (shortName) {
                            $(this).find(".consent-clinic-name").text(i18next.t(shortName));
                        }
                        $("#consentContainer input[name='toConsent']").each(function() {
                            $(this).prop("checked", false);
                        });
                        var agreement_url = $(this).find(".agreement-url").val();
                        if (/stock\-org\-consent/.test(agreement_url)) {
                            $(".terms-wrapper").hide();
                        }
                        var self = $(this);
                        $(this).find(".content-loading-message-indicator").fadeOut(50, function() {
                            self.find(".main-content").removeClass("tnth-hide");
                        });
                    });
                });
            },
            updateClinicalSection: function(data) {
                var self = this;
                for (var i = 0; i < data.length; i++) {
                    var val = data[i];
                    var clinicalItem = val.content.code.coding[0].display;
                    var clinicalValue = val.content.valueQuantity.value;
                    var clinicalUnit = val.content.valueQuantity.units;
                    //console.log(clinicalItem + " " + clinicalValue + " issued: " + val.content.issued + " last updated: " + val.content.meta.lastUpdated + " " + (new Date(val.content.meta.lastUpdated.replace(/\-/g, "/").replace("T", " ")).getTime()))
                    var status = val.content.status;
                    if (clinicalItem == "PCa diagnosis") {
                        clinicalItem = "pca_diag";
                    } else if (clinicalItem == "PCa localized diagnosis") {
                        clinicalItem = "pca_localized";
                    }
                    var ci = $('div[data-topic="' + clinicalItem + '"]');
                    if (ci.length > 0) ci.fadeIn().next().fadeIn();
                    var $radios = $('input:radio[name="' + clinicalItem + '"]');
                    if ($radios.length > 0) {
                        if (!$radios.is(':checked')) {
                            if (status == "unknown") $radios.filter('[data-status="unknown"]').prop("checked", true);
                            else $radios.filter("[value=" + clinicalValue + "]").not("[data-status='unknown']").prop("checked", true);
                            if (clinicalItem == "biopsy") {
                                if (clinicalValue == "true" || (parseInt(clinicalValue) === 1 && !clinicalUnit)) {
                                    if (val.content.issued) {
                                        var dString = self.modules.tnthDates.formatDateString(val.content.issued, "iso-short");
                                        var dArray = dString.split("-");
                                        $("#biopsyDate").val(dString);
                                        $("#biopsy_year").val(dArray[0]);
                                        $("#biopsy_month").val(dArray[1]);
                                        $("#biopsy_day").val(dArray[2]);
                                        $("#biopsyDateContainer").show();
                                        $("#biopsyDate").removeAttr("skipped");
                                    }
                                } else {
                                    $("#biopsyDate").val("");
                                    $("#biopsyDateContainer").hide();
                                    $("#biopsyDate").attr("skipped", "true");
                                }
                            }
                            if (clinicalItem == "pca_diag") {
                                if ($("#pca_diag_no").is(":checked")) {
                                    $("#tx_yes").attr("skipped", "true");
                                    $("#tx_no").attr("skipped", "true");
                                } else {
                                    $("#tx_yes").removeAttr("skipped");
                                    $("#tx_no").removeAttr("skipped");
                                }
                            }
                        }
                    }
                }
            },
            updateTreatment: function(data) {
                var treatmentCode = this.modules.tnthAjax.hasTreatment(data);
                if (treatmentCode) {
                    if (String(treatmentCode) === String(this.CANCER_TREATMENT_CODE)) {
                        $("#tx_yes").prop("checked", true);
                    } else {
                        $("#tx_no").prop("checked", true);
                    }
                }
            },
            initClinicalQuestionsSection: function() {
                var self = this;

                self.modules.tnthAjax.getTreatment(self.subjectId, function(data) {
                    self.updateTreatment(data);
                    self.modules.tnthAjax.getClinical(self.subjectId, function(data) {
                        if (data.entry) self.updateClinicalSection(data.entry);
                        $("#patientQ").attr("loaded", "true");
                        if (self.mode === "profile") {
                            if (self.currentUserId !== self.subjectId) {
                                $("#patientQ input[type='radio']").each(function() {
                                    $(this).attr("disabled", "disabled");
                                });
                                $("#biopsy_day, #biopsy_month, #biopsy_year").each(function() {
                                    $(this).attr("disabled", true);
                                });
                            }

                            $("#patientQ").show();
                            $("#patTx").remove(); //don't show treatment
                            $("#patientQ hr").hide();

                            if (self.subjectId) {
                                $(".pat-q input:radio").off("click").on("click", function() {
                                    var thisItem = $(this);
                                    var toCall = thisItem.attr("name");
                                    var toSend = thisItem.val(); // Get value from div - either true or false
                                    if (String(toCall) !== "biopsy") {
                                        self.modules.tnthAjax.postClinical(self.subjectId, toCall, toSend, $(this).attr("data-status"), $(this));
                                    }
                                    if (String(toSend) === "true" || String(toCall) === "pca_localized") {
                                        if (String(toCall) === "biopsy") {
                                            if ($("#biopsyDate").val() === "") {
                                                return true;
                                            } else {
                                                self.modules.tnthAjax.postClinical(self.subjectId, toCall, toSend, "", $(this), {
                                                    "issuedDate": $("#biopsyDate").val()
                                                });
                                            }
                                        }
                                        thisItem.parents(".pat-q").nextAll().fadeIn();
                                    } else {
                                        if (String(toCall) === "biopsy") {
                                            self.modules.tnthAjax.postClinical(self.subjectId, toCall, "false", $(this).attr("data-status"), $(this));
                                            ["pca_diag", "pca_localized"].forEach(function(fieldName) {
                                                $("input[name='" + fieldName + "']").each(function() {
                                                    $(this).prop("checked", false);
                                                });
                                            });
                                            if ($("input[name='pca_diag']").length > 0) {
                                                self.modules.tnthAjax.putClinical(self.subjectId, "pca_diag", "false", $(this));
                                            }
                                            if ($("input[name='pca_localized']").length > 0) {
                                                self.modules.tnthAjax.putClinical(self.subjectId, "pca_localized", "false", $(this));
                                            }
                                        } else if (String(toCall) === "pca_diag") {
                                            ["pca_localized"].forEach(function(fieldName) {
                                                $("input[name='" + fieldName + "']").each(function() {
                                                    $(this).prop("checked", false);
                                                });
                                            });
                                            if ($("input[name='pca_localized']").length > 0) {
                                                self.modules.tnthAjax.putClinical(self.subjectId, "pca_localized", "false", $(this));
                                            }
                                        }
                                        thisItem.parents(".pat-q").nextAll().fadeOut();
                                    }
                                });
                                var diag = $("#pca_diag_yes");
                                if (diag.is(":checked")) {
                                    diag.parents(".pat-q").nextAll().fadeIn();
                                } else {
                                    diag.parents(".pat-q").nextAll().fadeOut();
                                }
                                if (self.currentUserId !== self.subjectId) {
                                    if (!$("#patientQ input[type='radio']").is(":checked")) {
                                        $("#patientQContainer").append("<span class='text-muted'>" + i18next.t("no answers provided") + "</span>");
                                    }
                                }
                                [{
                                    "fields": $("#patientQ input[name='biopsy']"),
                                    "containerId": "patBiopsy"
                                }, {
                                    "fields": $("#patientQ input[name='pca_diag']"),
                                    "containerId": "patDiag"
                                }, {
                                    "fields": $("#patientQ input[name='pca_localized']"),
                                    "containerId": "patMeta"
                                }].forEach(function(item) {
                                    item.fields.each(function() {
                                        self.getSaveLoaderDiv("profileForm", item.containerId);
                                        $(this).attr("data-save-container-id", item.containerId);
                                    });
                                });
                                self.fillSectionView("clinical");
                            }
                        }
                    });
                });
            },
            initBiopsySection: function() {
                /*
                 * used by both profile and initial queries
                 */
                var profileSelf = this;
                setTimeout(function() {
                    profileSelf.__convertToNumericField($("#biopsy_day, #biopsy_year"));
                    $("input[name='biopsy']").each(function() {
                        $(this).on("click", function() {
                            if ($(this).val() == "true") {
                                $("#biopsyDateContainer").show();
                                if ($(this).attr("id") == "biopsy_yes") {
                                    if (!$("#biopsy_day").val()) $("#biopsy_day").focus();
                                }
                            } else {
                                $("#biopsyDate").val("");
                                $("#biopsy_day").val("");
                                $("#biopsy_month").val("");
                                $("#biopsy_year").val("");
                                $("#biopsyDateError").text("");
                                $("#biopsyDateContainer").hide();
                            }
                        });
                    });
                    $("#biopsy_day, #biopsy_month, #biopsy_year").each(function() {
                        $(this).on("change", function() {
                            var d = $("#biopsy_day");
                            var m = $("#biopsy_month");
                            var y = $("#biopsy_year");
                            var isValid = profileSelf.modules.tnthDates.validateDateInputFields(m, d, y, "biopsyDateError");
                            if (isValid) {
                                $("#biopsyDate").val(y.val() + "-" + m.val() + "-" + d.val());
                                $("#biopsyDateError").text("").hide();
                                $("#biopsy_yes").trigger("click");
                            } else {
                                $("#biopsyDate").val("");
                            }
                        });
                    });
                    $("input[name='tx']").each(function() {
                        $(this).on("click", function() {
                            if ($(this).val() == "true") {
                                profileSelf.modules.tnthAjax.postTreatment($("#iq_userId").val(), true, "", $(this));
                            } else {
                                profileSelf.modules.tnthAjax.postTreatment($("#iq_userId").val(), false, "", $(this));
                            }
                        });
                    });
                }, 550);

            },
            manualEntryModalVis: function(hide) {
                if (hide) {
                    this.manualEntry.loading = true;
                } else {
                    this.manualEntry.loading = false;
                }
            },
            continueToAssessment: function(method, completionDate, assessment_url) {
                if (assessment_url) {
                    var still_needed = false;
                    var self = this;
                    var subjectId = this.subjectId;
                    self.modules.tnthAjax.getStillNeededCoreData(subjectId, true, function(data) {
                        if (data && !data.error && data.length > 0) {
                            still_needed = true;
                        }
                    }, method);

                    /*
                     * passing additional query params
                     */
                    if (/\?/.test(assessment_url)) {
                        assessment_url += "&entry_method=" + method;
                    } else {
                        assessment_url += "?entry_method=" + method;
                    }

                    if (method === "paper") {
                        assessment_url += "&authored=" + completionDate;
                    }

                    var winLocation = !still_needed ? assessment_url : "/website-consent-script/" + $("#manualEntrySubjectId").val() + "?entry_method=" + method + "&subject_id=" + $("#manualEntrySubjectId").val() +
                        "&redirect_url=" + encodeURIComponent(assessment_url);

                    self.manualEntryModalVis(true);

                    setTimeout(function() {
                        self.manualEntryModalVis();
                    }, 2000);

                    setTimeout(function() {
                        window.location = winLocation;
                    }, 100);

                } else {
                    self.manualEntry.errorMessage = i18next.t("The user does not have a valid assessment link.");
                }
            },
            initCustomPatientDetailSection: function() {
                var subjectId = this.subjectId, self = this;

                //fix for safari
                $(window).on("beforeunload", function() {
                    if (navigator.userAgent.indexOf("Safari") !== -1 && navigator.userAgent.indexOf("Chrome") === -1) {
                        self.manualEntry.loading = false;
                        $("#manualEntryModal").modal("hide");
                    }
                });

                $("#manualEntryModal").on("show.bs.modal", function() {
                    self.manualEntry.initloading = true;
                });
                $("#manualEntryModal").on("shown.bs.modal", function() {

                    self.manualEntry.errorMessage = "";
                    self.manualEntry.method = "";
                    self.manualEntry.todayObj = self.modules.tnthDates.getTodayDateObj(); //get GMT date/time for today
                    self.manualEntry.completionDate = self.manualEntry.todayObj.gmtDate;
                    //get consent date
                    self.modules.tnthAjax.getConsent(subjectId, true, function(data) {
                        var dataArray = [];
                        if (data && data.consent_agreements && data.consent_agreements.length > 0) {
                            dataArray = data.consent_agreements.sort(function(a, b) {
                                return new Date(b.signed) - new Date(a.signed);
                            });
                        }
                        if (dataArray.length > 0) {
                            var items = $.grep(dataArray, function(item) { //filtered out non-deleted items from all consents
                                return !item.deleted && item.status == "consented";
                            });
                            if (items.length > 0) { //consent date in GMT
                                self.manualEntry.consentDate = items[0].signed;
                            }
                        }
                    });

                    setTimeout(function() {
                        self.manualEntry.initloading = false;
                    }, 10);
                });

                $("input[name='entryMethod']").on("click", function() {
                    self.manualEntry.errorMessage = "";
                    self.manualEntry.method = $(this).val();
                    if ($(this).val() == "interview_assisted") {
                        /*
                         * if method is interview assisted, reset completion date to GMT date/time for today
                         */
                        self.manualEntry.todayObj = self.modules.tnthDates.getTodayDateObj();
                        self.manualEntry.completionDate = self.manualEntry.todayObj.gmtDate;
                    }
                });
                
                self.__convertToNumericField($("#qCompletionDay, #qCompletionYear"));


                ["qCompletionDay", "qCompletionMonth", "qCompletionYear"].forEach(function(fn) {
                    var fd = $("#" + fn),
                        tnthDates = self.modules.tnthDates;
                    fd.on("change", function() {
                        var d = $("#qCompletionDay");
                        var m = $("#qCompletionMonth");
                        var y = $("#qCompletionYear");
                        var todayObj = tnthDates.getTodayDateObj();
                        var td = todayObj.displayDay,
                            tm = todayObj.displayMonth,
                            ty = todayObj.displayYear;

                        if (d.val() != "" && m.val() != "" && y.val() != "") {
                            if (d.get(0).validity.valid && m.get(0).validity.valid && y.get(0).validity.valid) {
                                var errorMsg = tnthDates.dateValidator(d.val(), m.val(), y.val());
                                var consentDate = $("#manualEntryConsentDate").val();
                                var pad = function(n) { n = parseInt(n); return (n < 10) ? "0" + n : n; };
                                if (!errorMsg && consentDate) {
                                    /*
                                     * check if date entered is today, if so use today's date/time
                                     */
                                    if (td + tm + ty === (pad(d.val()) + pad(m.val()) + pad(y.val()))) {
                                        self.manualEntry.completionDate = todayObj.gmtDate;
                                    } else {
                                        var gmtDateObj = tnthDates.getDateObj(y.val(), m.val(), d.val(), 12, 0, 0);
                                        self.manualEntry.completionDate = self.modules.tnthDates.getDateWithTimeZone(gmtDateObj);
                                    }
                                    /*
                                     * all date/time should be in GMT date/time
                                     */
                                    var completionDate = new Date(self.manualEntry.completionDate);
                                    var cConsentDate = new Date(self.manualEntry.consentDate);
                                    var cToday = new Date(self.manualEntry.todayObj.gmtDate);
                                    var nCompletionDate = completionDate.setHours(0, 0, 0, 0);
                                    var nConsentDate = cConsentDate.setHours(0, 0, 0, 0);
                                    var nToday = cToday.setHours(0, 0, 0, 0);
                                    if (nCompletionDate < nConsentDate) {
                                        errorMsg = i18next.t("Completion date cannot be before consent date.");
                                    }
                                    if (nConsentDate >= nToday) {
                                        if (nCompletionDate > nConsentDate) {
                                            errorMsg = i18next.t("Completion date cannot be in the future.");
                                        }
                                    } else {
                                        if (nCompletionDate > nToday) {
                                            errorMsg = i18next.t("Completion date cannot be in the future.");
                                        }
                                    }
                                }
                                self.manualEntry.errorMessage = errorMsg;
                            } else {
                                self.manualEntry.errorMessage = i18next.t("All date fields are required");
                            }
                        } else {
                            $("#meSubmit").attr("disabled", true);
                        }
                    });
                });
                $(document).delegate("#meSubmit", "click", function() {

                    var method = self.manualEntry.method, completionDate = $("#qCompletionDate").val();
                    var linkUrl = "/api/present-needed?subject_id=" + $("#manualEntrySubjectId").val();

                    if (method != "") {
                        if (method === "paper") {
                            self.manualEntryModalVis(true);
                            var errorMsg = "";
                            self.modules.tnthAjax.getCurrentQB(subjectId, self.modules.tnthDates.formatDateString(completionDate, "iso-short"), null, function(data) {
                                if (!data.error) { //check questionnaire time windows
                                    if (!(data.questionnaire_bank && Object.keys(data.questionnaire_bank).length > 0)) {
                                        errorMsg = i18next.t("Invalid completion date. Date of completion is outside the days allowed.");
                                    }

                                    if (errorMsg) {
                                        self.manualEntry.errorMessage = errorMsg;
                                        self.manualEntryModalVis();
                                    } else {
                                        self.manualEntry.errorMessage = "";
                                    }

                                    if (!errorMsg) {
                                        self.continueToAssessment(method, completionDate, linkUrl);
                                    }
                                }
                            });
                        } else {
                            self.continueToAssessment(method, completionDate, linkUrl);
                        }
                    }
                });

                self.modules.tnthAjax.assessmentStatus(subjectId, function(data) {
                    if (!data.error) {
                        if (((data.assessment_status).toUpperCase() == "COMPLETED") &&
                            (parseInt(data.outstanding_indefinite_work) === 0)) {
                            $("#assessmentLink").attr("disabled", true);
                            $("#enterManualInfoContainer").text(i18next.t("All available questionnaires have been completed."));
                        }
                    }
                });
            },
            initRolesListSection: function() {
                var self = this;
                this.modules.tnthAjax.getRoleList(function(data) {
                    if (data.roles) {
                        data.roles.forEach(function(role) {
                            self.roles.data.push({
                                name: role.name,
                                display: i18next.t((role.name.replace(/\_/g, " ").replace(/\b[a-z]/g, function(f) {
                                    return f.toUpperCase();
                                })))
                            });
                        });
                    }
                    self.modules.tnthAjax.getRoles(self.subjectId, true, function(data) {
                        if (data.roles) {
                            self.userRoles = data.roles.map(function(role) {
                                return role.name;
                            });
                        }
                        setTimeout(function() {
                            $("#rolesGroup input[name='user_type']").each(function() {
                                $(this).on("click", function() {
                                    var roles = $("#rolesGroup input:checkbox:checked").map(function() {
                                        return {name: $(this).val()};
                                    }).get();
                                    var toSend = {"roles": roles};
                                    self.modules.tnthAjax.putRoles(self.subjectId, toSend, $("#rolesLoadingContainer"));
                                });
                            });

                        }, 300);
                    });
                });
            },
            initAuditLogSection: function() {
                var self = this;
                this.modules.tnthAjax.auditLog(this.subjectId, function(data) {
                    if (!data.error) {
                        var ww = $(window).width();
                        if (data.audits && data.audits.length > 0) {
                            var fData = [];
                            (data.audits).forEach(function(item) {
                                item.by = item.by.reference;
                                var r = /\d+/g;
                                var m = r.exec(String(item.by));
                                if (m) {
                                    item.by = m[0];
                                } else {
                                    item.by = "-";
                                }
                                item.lastUpdated = self.modules.tnthDates.formatDateString(item.lastUpdated, "iso");
                                item.comment = item.comment ? self.escapeHtml(item.comment) : "";
                                var c = String(item.comment);
                                var len = ((ww < 650) ? 20 : (ww < 800 ? 40 : 80));

                                item.comment = c.length > len ? (c.substring(0, len + 1) + "<span class='second hide'>" + c.substr(len + 1) + "</span><br/><sub onclick='{showText}' class='pointer text-muted'>" + i18next.t("More...") + "</sub>") : item.comment;
                                item.comment = (item.comment).replace("{showText}", "(function (obj) {" +
                                    "if (obj) {" +
                                    'var f = $(obj).parent().find(".second"); ' +
                                    'f.toggleClass("hide"); ' +
                                    '$(obj).text($(obj).text() === i18next.t("More...") ? i18next.t("Less..."): i18next.t("More...")); ' +
                                    "}  " +
                                    "})(this) "
                                );
                                fData.push(item);
                            });

                            $("#profileAuditLogTable").bootstrapTable({
                                data: fData,
                                pagination: true,
                                pageSize: 5,
                                pageList: [5, 10, 25, 50, 100],
                                classes: "table table-responsive profile-audit-log",
                                sortName: "lastUpdated",
                                sortOrder: "desc",
                                search: true,
                                smartDisplay: true,
                                showToggle: true,
                                showColumns: true,
                                toolbar: "#auditTableToolBar",
                                rowStyle: function rowStyle(row, index) {
                                    return {
                                        css: {
                                            "background-color": (index % 2 != 0 ? "#F9F9F9" : "#FFF")
                                        }
                                    };
                                },
                                undefinedText: "--",
                                columns: [{
                                    field: "by",
                                    title: i18next.t("User"),
                                    width: "5%",
                                    sortable: true,
                                    searchable: true
                                }, {
                                    field: "comment",
                                    title: i18next.t("Comment"),
                                    searchable: true,
                                    sortable: true
                                }, {
                                    field: "lastUpdated",
                                    title: i18next.t("Date/Time <span class='gmt'>{gmt}</span>").replace("{gmt}", "(GMT), Y-M-D"),
                                    sortable: true,
                                    searchable: true,
                                    width: "20%"
                                }, {
                                    field: "version",
                                    title: i18next.t("Version"),
                                    sortable: true,
                                    visible: false
                                }]
                            });
                        } else {
                            $("#profileAuditLogErrorMessage").text(i18next.t("No audit log item found."));
                        }

                    } else {
                        $("#profileAuditLogErrorMessage").text(i18next.t("Problem retrieving audit log from server."));
                    }
                });
            },
            getConsentHeaderRow: function(header) {
                var content = "", h = header || this.consent.consentHeaderArray;
                h.forEach(function(title) {
                    if (title != "n/a") {
                        content += "<TH class='consentlist-header'>" + title + "</TH>";
                    }
                });
                return content;
            },
            getConsentRow: function(item) {
                var self = this, consentStatus = self.getConsentStatus(item), sDisplay = self.getConsentStatusHTMLObj(item).statusHTML;
                var LROrgId = item ? item.organization_id : "";
                if (LROrgId) {
                    var topOrgID = (self.getOrgTool()).getTopLevelParentOrg(LROrgId);
                    if (topOrgID && (topOrgID != LROrgId)) {
                        LROrgId = topOrgID;
                    }
                }
                var editorUrlEl = $("#" + LROrgId + "_editor_url"), cflag = this.getConsentStatusHTMLObj(item).statusText;
                var contentArray = [{
                    content: self.getConsentOrgDisplayName(item)
                }, {
                    content: sDisplay + (self.isEditable() && consentStatus == "active" ? '&nbsp;&nbsp;<a data-toggle="modal" data-target="#profileConsentListModal" data-orgId="' + item.organization_id + '" data-agreementUrl="' + String(item.agreement_url).trim() + '" data-userId="' + self.subjectId + '" data-status="' + cflag + '"><span class="glyphicon glyphicon-pencil" aria-hidden="true" style="cursor:pointer; color: #000"></span></a>' : ""),
                    "_class": "indent"
                }, {
                    content: (function(item) {
                        var s = "";
                        if (self.isDefaultConsent(item)) s = i18next.t("Sharing information with clinics ") + "<span class='agreement'>&nbsp;<a href='" + decodeURIComponent(item.agreement_url) + "' target='_blank'><em>" + i18next.t("View") + "</em></a></span>";
                        else {
                            s = "<span class='agreement'><a href='" + item.agreement_url + "' target='_blank'><em>View</em></a></span>" +
                                ((editorUrlEl.length > 0 && editorUrlEl.val()) ? ("<div class='button--LR' " + (editorUrlEl.attr("data-show") == "true" ? "data-show='true'" : "data-show='false'") + "><a href='" + editorUrlEl.val() + "' target='_blank'>" + i18next.t("Edit in Liferay") + "</a></div>") : "");
                        }
                        return s;
                    })(item)
                }, {
                    content: self.modules.tnthDates.formatDateString(item.signed) + (self.isEditable() && self.isTestPatient() && consentStatus == "active" ? '&nbsp;&nbsp;<a data-toggle="modal" data-target="#consentDateModal" data-orgId="' + item.organization_id + '" data-agreementUrl="' + String(item.agreement_url).trim() + '" data-userId="' + self.subjectId + '" data-status="' + cflag + '" data-signed-date="' + self.modules.tnthDates.formatDateString(item.signed, "d M y hh:mm:ss") + '"><span class="glyphicon glyphicon-pencil" aria-hidden="true" style="cursor:pointer; color: #000"></span></a>' : "")
                }];
                this.consent.consentDisplayRows.push(contentArray);
            },
            getConsentHistoryRow: function(item) {
                var self = this, sDisplay = self.getConsentStatusHTMLObj(item).statusHTML;
                var content = "<tr>";
                var contentArray = [{
                    content: self.getConsentOrgDisplayName(item)
                }, {
                    content: sDisplay
                }, {
                    content: self.modules.tnthDates.formatDateString(item.signed)

                }, {
                    content: "<span class='text-danger'>" + self.getDeletedDisplayDate(item) + "</span>"
                }, {
                    content: (item.deleted.by && item.deleted.by.display ? item.deleted.by.display : "--")
                }];

                contentArray.forEach(function(cell) {
                    content += "<td class='consentlist-cell'>" + cell.content + "</td>";
                });
                content += "</tr>";
                return content;
            },
            getConsentOrgDisplayName: function(item) {
                if (!item) {return "";}
                var orgId = item.organization_id, OT = this.getOrgTool(), currentOrg = OT.orgsList[orgId], orgName = "";
                if (!this.isConsentWithTopLevelOrg()) {
                    var topOrgID = OT.getTopLevelParentOrg(orgId), topOrg = OT.orgsList[topOrgID];
                    if (topOrg) {
                        try {
                            orgName = topOrg.name;

                        } catch (e) {
                            orgName = currentOrg ? currentOrg.name : "";
                        }
                    }
                } else {
                    orgName = currentOrg ? currentOrg.name : "";
                }
                return i18next.t(orgName) || item.organization_id;
            },
            getConsentStatus: function(item) {
                if (!item) {
                    return "";
                }
                var expired = (item.expires) ? this.modules.tnthDates.getDateDiff(String(item.expires)) : 0;
                return item.deleted ? "deleted" : (expired > 0 ? "expired" : "active");
            },
            getDeletedDisplayDate: function(item) {
                if (!item) {
                    return "";
                }
                var deleteDate = item.deleted ? item.deleted.lastUpdated : "";
                return deleteDate.replace("T", " ");
            },
            isDefaultConsent: function(item) {
                return item && /stock\-org\-consent/.test(item.agreement_url);
            },
            getConsentStatusHTMLObj: function(item) {
                var consentStatus = this.getConsentStatus(item), sDisplay = "", cflag = "";
                var se = item.staff_editable, sr = item.send_reminders, ir = item.include_in_reports;
                var consentLabels = this.consent.consentLabels;
                var oDisplayText = {
                    "default": "<span class='text-success small-text'>" + consentLabels.default+"</span>",
                    "consented": "<span class='text-success small-text'>" + consentLabels.consented + "</span>",
                    "withdrawn": "<span class='text-warning small-text withdrawn-label'>" + consentLabels.withdrawn + "</span>",
                    "purged": "<span class='text-danger small-text'>" + consentLabels.purged + "</span>",
                    "expired": "<span class='text-warning'>&#10007; <br><span>(" + i18next.t("expired") + "</span>",
                };

                switch (consentStatus) {
                case "deleted":
                    if (se && sr && ir) {
                        sDisplay = oDisplayText.consented;
                    } else if (se && ir && !sr || (!se && ir && !sr)) {
                        sDisplay = oDisplayText.withdrawn;
                    } else if (!se && !ir && !sr) {
                        sDisplay = oDisplayText.purged;
                    } else {
                        sDisplay = oDisplayText.consented;
                    }
                    break;
                case "expired":
                    sDisplay = oDisplayText.expired;
                    break;
                case "active":
                    switch (item.status) {
                    case "consented":
                        if (this.isDefaultConsent(item)) {
                            sDisplay = oDisplayText.default;
                        } else sDisplay = oDisplayText.consented;
                        cflag = "consented";
                        break;
                    case "suspended":
                        sDisplay = oDisplayText.withdrawn;
                        cflag = "suspended";
                        break;
                    case "deleted":
                        sDisplay = oDisplayText.purged;
                        cflag = "purged";
                        break;
                    default:
                        sDisplay = oDisplayText.consented;
                        cflag = "consented";
                    }
                    break;
                }
                return {"statusText": cflag || consentStatus, "statusHTML": sDisplay};
            },
            getTerms: function() {
                if (this.consent.touObj.length > 0) {
                    return this.consent.touObj;
                } else {
                    var self = this;
                    var orgTool = this.getOrgTool();
                    var orgsList = orgTool.getOrgsList();
                    var capitalize = function(str) {
                        return str.replace(/\w\S*/g, function(txt) {
                            return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
                        });
                    };
                    self.modules.tnthAjax.getTerms(this.subjectId, "", true, function(data) {
                        if (data && data.tous) {
                            (data.tous).forEach(function(item) {
                                var fType = $.trim(item.type).toLowerCase();
                                var org = orgsList[item.organization_id];
                                if (fType == "subject website consent" || fType == "website terms of use") {
                                    item.name = (org && org.name ? i18next.t(org.name) : "--");
                                    item.truenth_name = i18next.t("TrueNTH USA"),
                                    item.accepted = self.modules.tnthDates.formatDateString(item.accepted); //format to accepted format D m y
                                    item.display_type = capitalize($.trim((item.type).toLowerCase().replace("subject", ""))); //for displaying consent type, note: this will remove text 'subject' from being displayed
                                    item.eproms_agreement_text = i18next.t("Agreed to " + capitalize(item.display_type));
                                    item.truenth_agreement_text = i18next.t("Agreed to terms");
                                    item.eproms_url_text = i18next.t(item.display_type);
                                    item.truenth_url_text = (i18next.t("{project name} Terms of Use").replace("{project name}", "TrueNTH USA"));
                                    item.view = i18next.t("View");
                                    item.type = fType;
                                    self.consent.touObj.push(item);
                                }
                            });
                        }
                    });
                }
                self.consent.showInitialConsentTerms = (self.consent.touObj.length > 0); //NEED TO CHECK THAT USER HAS ACTUALLY CONSENTED TO TERMS of USE
            },
            initConsentItemEvent: function() {
                var __self = this;
                $("#profileConsentListModal").on("show.bs.modal", function(e) {
                    var relatedTarget = $(e.relatedTarget), orgId = $(e.relatedTarget).attr("data-orgId"), agreementUrl = relatedTarget.attr("data-agreementUrl");
                    var userId = relatedTarget.attr("data-userId"), status = relatedTarget.attr("data-status");
                    $(this).find("input[class='radio_consent_input']").each(function() {
                        $(this).attr({
                            "data-agreementUrl": agreementUrl,
                            "data-userId": userId,
                            "data-orgId": orgId
                        });
                        if ($(this).val() == status) $(this).prop("checked", true);
                    });
                    if (__self.isAdmin()) {
                        $(this).find(".admin-radio").show();
                    }
                });
                $("#profileConsentListModal input[class='radio_consent_input']").each(function() {
                    $(this).on("click", function() {
                        var o = __self.CONSENT_ENUM[$(this).val()];
                        if (o) {
                            o.org = $(this).attr("data-orgId");
                            o.agreementUrl = $(this).attr("data-agreementUrl");
                        }
                        if ($(this).val() == "purged") {
                            __self.modules.tnthAjax.deleteConsent($(this).attr("data-userId"), {
                                org: $(this).attr("data-orgId")
                            });
                            __self.reloadConsentList(self.attr("data-userId"));
                        } else if ($(this).val() == "suspended") {
                            var modalElement = $("#profileConsentListModal"), self = $(this);
                            __self.modules.tnthAjax.withdrawConsent($(this).attr("data-userId"), $(this).attr("data-orgId"), null, function(data) {
                                modalElement.removeClass("fade").modal("hide");
                                if (data.error) {
                                    $("#profileConsentListModalErrorMessage").text(data.error);
                                } else {
                                    __self.reloadConsentList(self.attr("data-userId"));
                                }
                            });
                        } else {
                            __self.modules.tnthAjax.setConsent($(this).attr("data-userId"), o, $(this).val());
                            $("#profileConsentListModal").removeClass("fade").modal("hide");
                            __self.reloadConsentList($(this).attr("data-userId"));
                        }
                    });
                });
            },
            initConsentDateEvents: function() {
                var today = new Date(), __self = this;
                $("#consentDateModal").on("shown.bs.modal", function(e) {
                    $(this).find(".consent-date").focus();
                    $(this).addClass("active");
                    var relatedTarget = $(e.relatedTarget), orgId = relatedTarget.attr("data-orgId");
                    var agreementUrl = relatedTarget.attr("data-agreementUrl"), userId = relatedTarget.attr("data-userId"), status = relatedTarget.attr("data-status");
                    $(this).find(".data-current-consent-date").text(relatedTarget.attr("data-signed-date"));
                    $(this).find("input.form-control").each(function() {
                        $(this).attr({
                            "data-agreementUrl": agreementUrl,
                            "data-userId": userId,
                            "data-orgId": orgId,
                            "data-status": status
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
                $("#consentDateModal .consent-date").datepicker({"format": "d M yyyy","forceParse": false,"endDate": today,"autoclose": true});
                $("#consentDateModal .consent-hour, #consentDateModal .consent-minute, #consentDateModal .consent-second").each(function() {
                    __self.__convertToNumericField($(this));
                });
                $("#consentDateModal .consent-date, #consentDateModal .consent-hour, #consentDateModal .consent-minute, #consentDateModal .consent-second").each(function() {
                    $(this).on("change", function() {
                        var d = $("#consentDateModal_date"), h = $("#consentDateModal_hour").val(), m = $("#consentDateModal_minute").val(), s = $("#consentDateModal_second").val();
                        var errorMessage = "";
                        if (d.val()) {
                            var isValid = __self.modules.tnthDates.isValidDefaultDateFormat(d.val());
                            if (!isValid) {
                                errorMessage += (errorMessage ? "<br/>" : "") + i18next.t("Date must in the valid format.");
                                d.datepicker("hide");
                            }
                        }
                        if (h) {
                            if (!(/^([1-9]|0[0-9]|1\d|2[0-3])$/.test(h))) { //validate hour [0]0
                                errorMessage += (errorMessage ? "<br/>" : "") + i18next.t("Hour must be in valid format, range 0 to 23.");
                            }
                        }
                        if (m) { //validate minute [0]0
                            if (!(/^(0[0-9]|[1-9]|[1-5]\d)$/.test(m))) {
                                errorMessage += (errorMessage ? "<br/>" : "") + i18next.t("Minute must be in valid format, range 0 to 59.");
                            }
                        }
                        if (s) { //validate second [0]0
                            if (!(/^(0[0-9]|[1-9]|[1-5]\d)$/.test(s))) {
                                errorMessage += (errorMessage ? "<br/>" : "") + i18next.t("Second must be in valid format, range 0 to 59.");
                            }
                        }
                        if (errorMessage) {
                            $("#consentDateModalError").html(errorMessage);
                        } else {
                            $("#consentDateModalError").html("");
                        }
                    });
                });

                $("#consentDateModal .btn-submit").each(function() {
                    $(this).on("click", function() {
                        var ct = $("#consentDateModal_date"),h = $("#consentDateModal_hour").val(),m = $("#consentDateModal_minute").val(),s = $("#consentDateModal_second").val();
                        var isValid = ct.val();
                        var pad = function(n) {n = parseInt(n);return (n < 10) ? "0" + n : n;};
                        if (isValid) {
                            var dt = new Date(ct.val()); //2017-07-06T22:04:50 format
                            var cDate = dt.getFullYear() + "-" + (dt.getMonth() + 1) + "-" + dt.getDate() + "T" + (h ? pad(h) : "00") + ":" + (m ? pad(m) : "00") +
                                ":" +
                                (s ? pad(s) : "00");
                            var o = __self.CONSENT_ENUM[ct.attr("data-status")];
                            if (o) {
                                o.org = ct.attr("data-orgId");
                                o.agreementUrl = ct.attr("data-agreementUrl");
                                o.acceptance_date = cDate;
                                o.testPatient = true;
                                setTimeout((function() {
                                    $("#consentDateContainer").hide();
                                })(), 200);
                                setTimeout((function() {
                                    $("#consentDateLoader").show();
                                })(), 450);

                                $("#consentDateModal button[data-dismiss]").attr("disabled", true); //disable close buttons while processing reques

                                setTimeout(__self.modules.tnthAjax.setConsent(ct.attr("data-userId"), o, ct.attr("data-status"), true, function(data) {
                                    if (data) {
                                        if (data && data.error) {
                                            $("#consentDateModalError").text(i18next.t("Error processing data.  Make sure the date is in the correct format."));
                                            setTimeout(function() {
                                                $("#consentDateContainer").show();
                                            }, 200);
                                            setTimeout(function() {
                                                $("#consentDateLoader").hide();
                                            }, 450);
                                            $("#consentDateModal button[data-dismiss]").attr("disabled", false);
                                        } else {
                                            $("#consentDateModal").removeClass("fade").modal("hide");
                                            __self.reloadConsentList(ct.attr("data-userId"));
                                        }
                                    }
                                }), 100);
                            }
                        } else {
                            $("#consentDateModalError").text(i18next.t("You must enter a valid date/time"));
                        }
                    });
                });
            },
            getConsentHistory: function(options) {
                if (!options) {options = {};}
                var self = this, content = "";
                content = "<div id='consentHistoryWrapper'><table id='consentHistoryTable' class='table-bordered table-condensed table-responsive' style='width: 100%; max-width:100%'>";
                content += this.getConsentHeaderRow(this.consent.consentHistoryHeaderArray);
                var items = $.grep(self.consent.consentItems, function(item) { //iltered out deleted items from all consents
                    return !(/null/.test(item.agreement_url)) && item.deleted;
                });
                items = items.sort(function(a, b) { //sort items by last updated date in descending order
                    return new Date(b.deleted.lastUpdated) - new Date(a.deleted.lastUpdated);
                });
                items.forEach(function(item, index) {
                    content += self.getConsentHistoryRow(item, index);
                });
                content += "</table></div>";
                $("#consentHistoryModal .modal-body").html(content);
                $("#consentHistoryModal").modal("show");
            },
            /**** this function is used when this section becomes editable, note: this is called after the user has edited the consent list; this will refresh the list ****/
            reloadConsentList: function(userId) {
                var self = this;
                $("#consentListTable").animate({opacity: 0}, function() {
                    self.consent.consentLoading = true;
                    setTimeout(function() { // Set a one second delay before getting updated list. Mostly to give user sense of progress/make it
                        self.modules.tnthAjax.getConsent(userId || self.subjectId, true, function(data) {
                            self.getConsentList(data);
                        });
                    }, 1500);
                });
            },
            getConsentList: function(data) {
                if (data && data.error) {
                    this.consent.consentListErrorMessage = i18next.t("Error occurred retrieving consent list content.");
                    this.consent.consentLoading = false;
                    return false;
                }
                this.getTerms(); //get terms of use if any
                var self = this, dataArray = [];
                if (data && data.consent_agreements && (data.consent_agreements).length > 0) {
                    dataArray = (data.consent_agreements).sort(function(a, b) {
                        return new Date(b.signed) - new Date(a.signed);
                    });
                }
                this.consent.consentItems = dataArray, this.consent.consentDisplayRows = [];
                if (this.consent.consentItems.length > 0) {
                    var existingOrgs = {};
                    this.consent.consentItems.forEach(function(item, index) {
                        if (item.deleted) {
                            self.consent.hasConsentHistory = true;
                            return true;
                        }
                        if (!(existingOrgs[item.organization_id]) && !(/null/.test(item.agreement_url))) {
                            self.getConsentRow(item, index);
                            existingOrgs[item.organization_id] = true;
                        }

                    });
                    this.consent.hasCurrentConsent = Object.keys(existingOrgs).length > 0;
                    setTimeout(function() {
                        $("#consentListTable .button--LR").each(function() {
                            if (String($(this).attr("show")).toLowerCase() === "true") {
                                $(this).addClass("show");
                            }
                        });
                        $("#consentListTable tbody tr").each(function(index) {
                            $(this).addClass(index % 2 !== 0 ? "even" : "odd");
                        });
                        if (!self.isConsentWithTopLevelOrg()) {
                            $("#consentListTable .agreement").each(function() {
                                $(this).parent().hide();
                            });
                        }
                        $("#consentListTable").animate({
                            opacity: 1
                        });
                    }, 0);
                    if (self.isEditable() && self.consent.hasConsentHistory) {
                        $("#viewConsentHistoryButton").on("click", function(e) {
                            e.preventDefault();
                            self.getConsentHistory();
                        });
                    }
                    if (self.isEditable()) {
                        self.initConsentItemEvent();
                    }
                    if (self.isEditable() && self.isTestPatient()) {
                        self.initConsentDateEvents();
                    }
                } else {
                    $("#consentListTable").animate({opacity: 1});
                }
                this.consent.consentLoading = false;

            },
            __convertToNumericField: function(field) {
                if (field) {
                    if (("ontouchstart" in window || (typeof(window.DocumentTouch) !== "undefined" && document instanceof window.DocumentTouch))) {
                        field.each(function() {$(this).prop("type", "tel");});
                    }
                }
            },
            escapeHtml: function (text) {
                if (text === null || text !== "undefined" || String(text).length === 0) {
                    return text;
                }
                return text.replace(/[\"&'\/<>]/g, function (a) {
                    return {
                        '"': "&quot;", "&": "&amp;", "'": "&#39;",
                        "/": "&#47;",  "<": "&lt;",  ">": "&gt;"
                    }[a];
                });
            }
        }
    });
})();


/*
 * helper Object for initializing profile sections  TODO streamline this more
 */
(function() {
    var ProfileObj = window.ProfileObj = new Vue({ /*global Vue i18next $ */
        el: "#mainDiv",
        components: {
            "section-view": {
                props: ["data", "nodatatext"],
                template: "<div v-if='data'>{{data}}</div><div class='text-muted' v-else>{{nodatatext}}</div>"
            },
            "section-view-extension": {
                props: ["data", "nodatatext"],
                template: "<div v-if='data'><p v-for='item in data'>{{item.display}}</p></div><div class='text-muted' v-else>{{nodatatext}}</div>"
            },
            "email-ready-message": {
                props: ['message'],
                template: "<div class='text-warning email-ready-message' v-show='message'><span class='glyphicon glyphicon-alert warning' aria-hidden='true'></span>{{message}}</div>"
            }
        },
        errorCaptured: function(Error, Component, info) {
            console.error("Error: ", Error, " Component: ", Component, " Message: ", info);
            return false;
        },
        errorHandler: function (err, vm) {
            this.dataError = true;
            var errorElement = document.getElementById("profileErrorMessage");
            if (errorElement) {
                errorElement.innerHTML = "Error occurred initializing Profile  Vue instance.";
            }
            console.warn("Profile Vue instance threw an error: ", vm, this);
            console.error("Error thrown: ", err);
        },
        created: function() {
            var self = this;
            VueErrorHandling(); /*global VueErrorHandling */
            this.registerDependencies();
            this.getOrgTool();
            this.setUserSettings();
            this.onBeforeSectionsLoad();
            this.setCurrentUserOrgs();
            this.initStartTime = new Date();
            this.initChecks.push({done: false});
            this.setDemoData({beforeSend: self.setSectionLoaders}, function() { //this will initialize section loaders, only if ajax request is sent
                self.onInitChecksDone();
            });
            if (this.currentUserId) { //get user roles - note using the current user Id - so we can determine: if user is an admin, if he/she can edit the consent, etc.
                this.initChecks.push({done: false});
                this.modules.tnthAjax.getRoles(this.currentUserId, function(data) {
                    if (data && data.roles) {
                        data.roles.forEach(function(role) {self.currentUserRoles.push(role.name.toLowerCase());});
                    }
                    self.onInitChecksDone();
                }, {useWorker: true});
            }
            this.initChecks.push({ done: false});
            this.setConfiguration({useWorker:true}, function(data) { //get config settings
                self.onInitChecksDone();
                var CONSENT_WITH_TOP_LEVEL_ORG = "CONSENT_WITH_TOP_LEVEL_ORG";
                if (data.error || !data.hasOwnProperty(CONSENT_WITH_TOP_LEVEL_ORG)) {
                    return false;
                }
                self.modules.tnthAjax.setConfigurationUI(CONSENT_WITH_TOP_LEVEL_ORG, data.CONSENT_WITH_TOP_LEVEL_ORG + ""); //for use by UI later, e.g. handle consent submission
            });
        },
       mounted: function() {
            var self = this;
            Vue.nextTick(function () {
                // DOM updated
                self.initIntervalId = setInterval(function() { //wait for ajax calls to finish
                    self.initEndTime = new Date();
                    var elapsedTime = self.initEndTime - self.initStartTime;
                    elapsedTime /= 1000;
                    var checkFinished = self.initChecks.length === 0;
                    if (checkFinished || (elapsedTime >= 5)) {
                        clearInterval(self.initIntervalId);
                        self.initSections(function() {
                            self.onSectionsDidLoad();
                            self.handleOptionalCoreData();});
                    }
                }, 30);
            });
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
            userOrgs: [],
            userRoles: [],
            userEmailReady: true,
            messages: {
                userEmailReadyMessage: "",
                userInviteEmailInfoMessage: "",
                userInviteEmailErrorMessage: "",
            },
            mode: "profile",
            demo: { //skeleton
                data: { resourceType:"Patient", email: "", name: {given: "",family: ""}, birthDay: "",birthMonth: "",birthYear: ""}
            },
            stateDict: {AL: i18next.t("Alabama"),AK: i18next.t("Alaska"), AS: i18next.t("American Samoa"),AZ: i18next.t("Arizona"),AR:i18next.t("Arkansas"),CA: i18next.t("California"),CO:i18next.t("Colorado"),CT:i18next.t("Connecticut"),DE:i18next.t("Delaware"),DC:i18next.t("District Of Columbia"),FM: i18next.t("Federated States Of Micronesia"),FL:i18next.t("Florida"),GA:i18next.t("Georgia"),GU:i18next.t("Guam"),HI:i18next.t("Hawaii"),ID:i18next.t("Idaho"),IL:i18next.t("Illinois"),IN:i18next.t("Indiana"),IA:i18next.t("Iowa"),KS:i18next.t("Kansas"),KY:i18next.t("Kentucky"),LA:i18next.t("Louisiana"),ME:i18next.t("Maine"),MH:i18next.t("Marshall Islands"),MD:i18next.t("Maryland"),MA:i18next.t("Massachusetts"),MI:i18next.t("Michigan"),MN:i18next.t("Minnesota"),MS:i18next.t("Mississippi"),MO:i18next.t("Missouri"),MT:i18next.t("Montana"),NE: i18next.t("Nebraska"),NV:i18next.t("Nevada"),NH:i18next.t("New Hampshire"),NJ:i18next.t("New Jersey"),NM:i18next.t("New Mexico"),NY:i18next.t("New York"),NC:i18next.t("North Carolina"),ND:i18next.t("North Dakota"),MP:i18next.t("Northern Mariana Islands"),OH:i18next.t("Ohio"),OK:i18next.t("Oklahoma"),OR:i18next.t("Oregon"),PW:i18next.t("Palau"),PA:i18next.t("Pennsylvania"),PR:i18next.t("Puerto Rico"),RI:i18next.t("Rhode Island"),SC:i18next.t("South Carolina"),SD:i18next.t("South Dakota"),TN:i18next.t("Tennessee"),TX:i18next.t("Texas"),UT:i18next.t("Utah"),VT:i18next.t("Vermont"),VI:i18next.t("Virgin Islands"),VA:i18next.t("Virginia"),WA:i18next.t("Washington"),WV:i18next.t("West Virginia"),WI:i18next.t("Wisconsin"),WY:i18next.t("Wyoming")},
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
            consent: {
                consentHeaderArray: [ //html for consent header cell in array
                    i18next.t("Organization"),
                    '<span class="eproms-consent-status-header">' + i18next.t("Consent Status") + '</span><span class="truenth-consent-status-header">' + i18next.t("Consent Status") + "</span>",
                    '<span class="agreement">' + i18next.t("Agreement") + "</span>",
                    '<span class="eproms-consent-date-header">' + i18next.t("Date") + '</span><span class="truenth-consent-date-header">' + i18next.t("Registration Date") + '</span> <span class="gmt">(' + i18next.t("GMT") + ')</span>'
                ],
                consentHistoryHeaderArray: [
                    i18next.t("Organization"),
                    '<span class="eproms-consent-status-header">' + i18next.t("Consent Status") + '</span><span class="truenth-consent-status-header">' + i18next.t("Consent Status") + "</span>",
                    i18next.t("Consent Date"),
                    i18next.t("Last Updated") + "<br/><span class='smaller-text'>" + i18next.t("( GMT, Y-M-D )") + "</span>",
                    i18next.t("User")
                ],
                consentLabels: {
                    "default": i18next.t("Consented"),
                    "consented": i18next.t("Consented / Enrolled"),
                    "withdrawn": "<span data-eproms='true'>" + i18next.t("Withdrawn - Suspend Data Collection and Report Historic Data") + "</span>" +
                        "<span data-truenth='true'>" + i18next.t("Suspend Data Collection and Report Historic Data") + "</span>",
                    "purged": i18next.t("Purged / Removed"),
                    "deleted": i18next.t("Replaced")
                },
                consentItems: [],
                currentItems: [],
                historyItems: [],
                touObj: [],
                consentDisplayRows: [],
                consentListErrorMessage: "",
                consentLoading: false,
                saveLoading: false,
                showInitialConsentTerms: false
            },
            assessment: {
                assessmentListItems: [], assessmentListError: ""
            },
            emailLog: {data: []},
            patientReport: {
                data: [], hasP3PReport: false
            },
            manualEntry: {
                loading: false,
                initloading: false,
                method: "",
                consentDate: "",
                completionDate: "",
                todayObj: { displayDay: "", displayMonth: "", displayYear: ""},
                errorMessage: ""
            },
            patientEmailForm: {
                loading: false
            },
            disableFields: [],
            topLevelOrgs: [],
            fillViews: {},
            modules: {},
            bootstrapTableConfig: {
                search: true,
                smartDisplay: true,
                showToggle: true,
                showColumns: true,
                undefinedText: "--",
                pagination: true,
                pageSize: 5,
                pageList: [5, 10, 25, 50, 100],
                formatShowingRows: function(pageFrom, pageTo, totalRows) {
                    var rowInfo;
                    rowInfo = i18next.t("Showing {pageFrom} to {pageTo} of {totalRows} records").
                        replace("{pageFrom}", pageFrom).
                        replace("{pageTo}", pageTo).
                        replace("{totalRows}", totalRows);
                    return rowInfo;
                },
                formatAllRows: function() {
                    return i18next.t("All rows");
                },
                formatSearch: function() {
                    return i18next.t("Search");
                },
                formatNoMatches: function() {
                    return i18next.t("No matching records found");
                },
                formatRecordsPerPage: function(pageNumber) {
                    return i18next.t("{pageNumber} records per page").replace("{pageNumber}", pageNumber);
                },
                rowStyle: function(row, index) {
                    return {
                        css: {"background-color": (index % 2 !== 0 ? "#F9F9F9" : "#FFF")}
                    };
                }
            }
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
            setConfiguration: function(params, callback) {
                callback = callback || function() {};
                var self = this;
                this.modules.tnthAjax.getConfiguration(this.currentUserId || this.subjectId, params, function(data) { //get config settings
                    if (!data || data.error) {
                        callback({error: self.modules.i18next.t("Unable to set user settings.")});
                        return false;
                    }
                    self.settings = data;
                    callback(data);
                });
            },
            setBootstrapTableConfig: function(config) {
                if (!config) {
                    return this.bootstrapTableConfig;
                } else {
                    return $.extend({}, this.bootstrapTableConfig, config);
                }
            },
            onInitChecksDone: function() {
                if (this.initChecks.length === 0) {
                    return false;
                }
                this.initChecks.pop();
            },
            setCurrentUserOrgs: function(params, callback) {
                callback = callback||function(){};
                if (!this.currentUserId) {
                    callback({"error": "Current user id is required."});
                    return;
                }
                var self = this;
                this.modules.tnthAjax.getDemo(this.currentUserId, params, function(data) { //setting current user's (not subject's)
                    if (!data || data.error) {
                        callback({"error": self.modules.i18next.t("Unable to set current user orgs")});
                        return false;
                    }
                    if (!data.careProvider) {
                        return false;
                    }
                    var orgTool = self.getOrgTool();
                    self.userOrgs = data.careProvider.map(function(item) {
                        return item.reference.split("/").pop();
                    });
                    var topLevelOrgs = orgTool.getUserTopLevelParentOrgs(self.userOrgs);
                    self.topLevelOrgs = topLevelOrgs.map(function(item) {
                        return orgTool.getOrgName(item);
                    });
                    callback(data);
                });
            },
            isUserEmailReady: function() {
                return this.userEmailReady;
            },
            setUserEmailReady: function(params) {
                if (this.mode !== "profile") { //setting email ready status only applies to profile page
                    return false;
                }
                var self = this;
                this.modules.tnthAjax.getEmailReady(this.subjectId, params, function(data) {
                    if (data.error) {
                        return false;
                    }
                    self.userEmailReady = data.ready;
                    self.messages.userEmailReadyMessage = data.reason || "";
                });
            },
            isDisableField: function(fieldId) {
                fieldId = fieldId || "";
                return this.disableFields.indexOf(fieldId) !== -1;
            },
            handleMedidataRaveFields: function(params) {
                if (!this.settings.MEDIDATA_RAVE_FIELDS || !this.settings.MEDIDATA_RAVE_ORG) { //expected config example: MEDIDATA_RAVE_FIELDS = ['deceased', 'studyid', 'consent_status', 'dob', 'org'] and MEDIDATA_RAVE_ORG = 'IRONMAN'
                    return false;
                }
                var self = this;
                this.setCurrentUserOrgs(params, function() {
                    if (self.topLevelOrgs.indexOf(self.settings.MEDIDATA_RAVE_ORG) === -1) {
                        return false;
                    }
                    $.merge(self.disableFields, self.settings.MEDIDATA_RAVE_FIELDS);
                    self.setDisableAccountCreation(); //disable account creation
                });
            },
            setDisableEditButtons: function() {
                if (this.disableFields.length === 0) {
                    return false;
                }
                var self = this;
                $("#profileMainContent .profile-item-container").each(function() { //disable field/section that is listed in disable field array
                    var dataSection = this.getAttribute("data-sections");
                    if (!dataSection) {
                        return true;
                    }
                    if (self.isDisableField(dataSection)){ //hide edit button for the section
                        $(this).children(".profile-item-edit-btn").css("display", "none");
                    }
                });
            },
            setDisableAccountCreation: function() {
                if ($("#accountCreationContentContainer[data-account='patient']").length > 0) { //creating an overlay that prevents user from editing fields
                    $("#createProfileForm .create-account-container").append("<div class='overlay'></div>");
                }
            },
            setDisableFields: function(params) {
                if (!this.currentUserId || this.isAdmin() || !this.isPatient()) {
                    return false;
                }
                var self = this;
                this.setConfiguration(params, function() { //make sure settings are there
                    self.handleMedidataRaveFields();
                    self.setDisableEditButtons();
                });
            },
            setDemoData: function(params, callback) {
                var self = this;
                callback = callback || function() {};
                if (!this.subjectId) {
                    callback();
                    return false;
                }
                this.modules.tnthAjax.clearDemoSessionData(this.subjectId);
                this.modules.tnthAjax.getDemo(this.subjectId, params, function(data) { //get demo returned cached data if there, but we need fresh data
                    if (data) {
                        self.demo.data = data;
                        setTimeout(function() {
                            self.setUserEmailReady();
                        }, 50);
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
                                self.demo.data.fullName = $.trim(data.name.given + " " + data.name.family);
                            } else if (data.name.family) {
                                self.demo.data.fullName = data.name.family;
                            } else if (data.name.given) {
                                self.demo.data.fullName = data.name.given;
                            }
                        } else {
                            self.demo.data.name = {family: "",given: ""};
                        }
                        var datesArray = data.birthDate ? data.birthDate.split("-") : ["", "", ""];
                        self.demo.data.displayBirthDate = self.modules.tnthDates.displayDateString(datesArray[1], datesArray[2], datesArray[0]);
                        self.demo.data.birthDay = datesArray[2];
                        self.demo.data.birthMonth = datesArray[1];
                        self.demo.data.birthYear = datesArray[0];

                        var m = "", d = "", y = "", displayDeceasedDate = "";
                        if (data.deceasedDateTime) {
                            var deceasedDateObj = new Date(data.deceasedDateTime);
                            m = pad(deceasedDateObj.getUTCMonth()+1);
                            d = deceasedDateObj.getUTCDate();
                            y = deceasedDateObj.getUTCFullYear(); /*global pad*/
                            displayDeceasedDate = self.modules.tnthDates.displayDateString(pad(m), pad(d), y);
                        }
                        self.demo.data.displayDeceasedDate = displayDeceasedDate;
                        self.demo.data.deceasedDay = d;
                        self.demo.data.deceasedMonth = m;
                        self.demo.data.deceasedYear = y;

                        if (data.identifier) {
                            (data.identifier).forEach(function(item) {
                                if (item.system === self.modules.SYSTEM_IDENTIFIER_ENUM.external_site_id) {
                                    data.siteId = item.value;
                                }
                                if (item.system === self.modules.SYSTEM_IDENTIFIER_ENUM.external_study_id) {
                                    data.studyId = item.value;
                                }
                            });
                        }
                        self.demo.data.language = "";
                        if (data.communication) {
                            data.communication.forEach(function(o) {
                                if (o.language && o.language.coding) {
                                    o.language.coding.forEach(function(item) {
                                        self.demo.data.language = item;
                                        self.demo.data.languageCode = item.code;
                                        self.demo.data.languageDisplay = item.display;
                                    });
                                }
                            });
                        }
                        if (data.extension) {
                            (data.extension).forEach(function(item) {
                                if (item.url === self.modules.SYSTEM_IDENTIFIER_ENUM.ethnicity) {
                                    item.valueCodeableConcept.coding.forEach(function(ethnicity) {
                                        self.demo.data.ethnicity = self.demo.data.ethnicity || [];
                                        self.demo.data.ethnicity.push(ethnicity);
                                        self.demo.data.ethnicityCodes = ethnicity.code;
                                    });
                                }
                                if (item.url === self.modules.SYSTEM_IDENTIFIER_ENUM.race) {
                                    item.valueCodeableConcept.coding.forEach(function(race) {
                                        self.demo.data.race = self.demo.data.race || [];
                                        self.demo.data.race.push(race);
                                    });
                                    if (self.demo.data.race) {
                                        self.demo.data.raceCodes = self.demo.data.race.map(function(item) {
                                            return item.code; });
                                    }
                                }
                                if (!self.demo.data.timezone && item.url === self.modules.SYSTEM_IDENTIFIER_ENUM.timezone) {
                                    self.demo.data.timezone = item.timezone ? item.timezone : "";
                                }
                            });
                        }
                        self.demo.data.raceCodes = self.demo.data.raceCodes || [];
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
                var acoContainer = $("#accountCreationContentContainer");
                if (acoContainer.length > 0) {
                    this.currentUserId = $("#currentStaffUserId").val();
                    this.mode = acoContainer.attr("data-account") === "patient" ? "createPatientAccount": "createUserAccount";
                }
            },
            getOrgTool: function(callback) {
                if (!this.orgTool) {
                    var self = this;
                    callback = callback || function() {};
                    this.orgTool = new (this.modules.orgTool) ();
                    this.orgTool.init(function(data) {
                        if (data && !data.error) {
                            self.orgsData = data;
                        }
                        callback(data);
                    });
                    this.orgsList = this.orgTool.getOrgsList();
                }
                return this.orgTool;
            },
            isConsentEditable: function() {
                var isStaff = this.currentUserRoles.indexOf("staff") !== -1;
                var isPatient = this.currentUserRoles.indexOf("patient") !== -1;
                var isEditableByStaff = this.settings.hasOwnProperty("CONSENT_EDIT_PERMISSIBLE_ROLES") && this.settings.CONSENT_EDIT_PERMISSIBLE_ROLES.indexOf("staff") !== -1;
                var isEditableByPatient = this.settings.hasOwnProperty("CONSENT_EDIT_PERMISSIBLE_ROLES") && this.settings.CONSENT_EDIT_PERMISSIBLE_ROLES.indexOf("patient") !== -1;
                return this.isAdmin() || (isStaff && isEditableByStaff) || (isPatient && isEditableByPatient);
            },
            isTestEnvironment: function() {
                return String(this.settings.SYSTEM_TYPE).toLowerCase() !== "production";
            },
            isAdmin: function() {
                return this.currentUserRoles.indexOf("admin") !== -1;
            },
            isPatient: function() {
                if (this.mode === "createPatientAccount" || $("#profileMainContent").hasClass("patient-view")) {
                    return true;
                }
                if (this.userRoles.length === 0) { //this is a blocking call if not cached, so avoid it if possible
                    this.initUserRoles({sync:true});
                }
                return this.userRoles.indexOf("patient") !== -1;
            },
            isStaff: function() {
                return this.currentUserRoles.indexOf("staff") !== -1 ||  this.currentUserRoles.indexOf("staff_admin") !== -1;
            },
            isProxy: function() {
                return (this.currenUserId !== "") && (this.subjectId !== "") && (this.currentUserId !== this.subjectId);
            },
            isConsentWithTopLevelOrg: function() {
                return this.settings.CONSENT_WITH_TOP_LEVEL_ORG;
            },
            getShowInMacro: function() {
                return this.settings.SHOW_PROFILE_MACROS || [];
            },
            setSectionLoaders: function() {
                $("#profileForm .section-loader").removeClass("tnth-hide");
            },
            clearSectionLoaders: function() {
                $("#profileForm .section-loader").addClass("tnth-hide");
                $("#profileForm .profile-item-edit-btn").addClass("active");
            },
            onBeforeSectionsLoad: function() {
                if (this.mode === "profile") {
                    $("#mainDiv").addClass("profile");
                }
            },
            onSectionsDidLoad: function() {
                this.setDisableFields();
                if (this.mode === "profile") { //Note, this attach loader indicator to element with the class data-loader-container, in order for this to work, the element needs to have an id attribute
                    var self = this;
                    setTimeout(function() {
                        self.initFieldsEvent();
                        self.initLoginAsButtons();
                        self.fillViews = self.setView();
                        self.initEditButtons();
                    }, 50);
                    $(document).ajaxStop(function() {
                        self.clearSectionLoaders(); //clear section loaders after ajax calls completed, note this will account for failed/cancelled requests as well
                    });
                }
            },
            initLoginAsButtons: function() {
                var self = this;
                $("#loginAsButton, #btnLoginAs").on("click", function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    sessionStorage.clear();
                    self.handleLoginAs(e);
                });
            },
            initEditButtons: function() {
                var self = this;
                $("#profileForm .profile-item-edit-btn").each(function() {
                    $(this).on("click", function(e) {
                        e.preventDefault();
                        var container = $(this).closest(".profile-item-container");
                        container.toggleClass("edit");
                        $(this).val(container.hasClass("edit") ? i18next.t("DONE") : i18next.t("EDIT"));
                        if (!container.hasClass("edit")) {
                            self.fillSectionView(container.attr("data-sections"));
                            self.handleOptionalCoreData();
                        }
                    });
                });
            },
            initFieldsEvent: function() {
                var self = this;
                $("#profileMainContent [data-loader-container]").each(function() {
                    var attachId = $(this).attr("id");
                    var targetFields = $(this).find("input, select");
                    if (targetFields.length === 0) {
                        return true;
                    }
                    targetFields.each(function() {
                        if ($(this).attr("type") === "hidden") {
                            return false;
                        }
                        $(this).attr("data-save-container-id", attachId);
                        var triggerEvent = $(this).attr("data-trigger-event") || "change";
                        if ($(this).attr("data-update-on-validated")) {
                            triggerEvent = "blur";
                        }
                        if (_isTouchDevice()) { /*_isTouchDevice global */
                            triggerEvent = "change"; //account for mobile devices touch events
                        }
                        $(this).on(triggerEvent, function(e) {
                            e.stopPropagation();
                            self.modules.tnthAjax.clearDemoSessionData(self.subjectId); //seems there is a race condition here, make sure not to use cache data here as data is being updated
                            var valid = this.validity ? this.validity.valid : true;
                            if (!$(this).attr("data-update-on-validated") && valid) {
                                var o = $(this);
                                var parentContainer = $(this).closest(".profile-item-container");
                                var setDemoInterval = setInterval(function() {
                                    var customErrorField = $("#" + o.attr("data-error-field"));
                                    var hasError = customErrorField.length > 0 && customErrorField.text() !== "";
                                    if (!hasError) { //need to check default help block for error as well
                                        var errorBlock = parentContainer.find(".help-block");
                                        hasError = errorBlock.length > 0 && errorBlock.text() !== "";
                                    }
                                    if (hasError) {
                                        clearInterval(setDemoInterval);
                                        return false;
                                    }
                                    clearInterval(setDemoInterval);
                                    o.trigger("updateDemoData");
                                }, 10);
                            }
                        });
                    });
                });
            },
            initSections: function(callback) {
                var self = this, sectionsInitialized = {}, initCount = 0;
                $("#mainDiv [data-profile-section-id]").each(function() {
                    var sectionId = $(this).attr("data-profile-section-id");
                    if (!sectionsInitialized[sectionId]) {
                        setTimeout(function() {
                            self.initSection(sectionId);
                        }, initCount += 20);
                        sectionsInitialized[sectionId] = true;
                    }
                });
                if (callback) {
                    setTimeout(function() {callback();}, initCount+20);
                }
            },
            handleOptionalCoreData: function() {
                var targetSection = $("#profileDetailContainer"), self = this;
                if (targetSection.length > 0) {
                    var loadingElement = targetSection.find(".profile-item-loader");
                    loadingElement.show();
                    this.modules.tnthAjax.getOptionalCoreData(self.subjectId, {useWorker: true, cache: true}, function(data) { //cache this request as change is rare if ever for optional data
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
                                        if (visibleRows === 0) {
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
                if (sectionID && this.fillViews[sectionID]) {
                    this.fillViews[sectionID]();
                }
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
                    "clinical": function() {
                        this.setContent($("#pca_diag_view"), $("#patDiag input[name='pca_diag']:checked").closest("label").text());
                        this.setContent($("#pca_localized_view"), $("#patMeta input[name='pca_localized']:checked").closest("label").text());
                        if ($("#biopsyDateContainer").hasClass("has-error") || $("#biopsyDateError").text()) {
                            return false;
                        }
                        var tnthDates = self.modules.tnthDates;
                        var f = $("#patBiopsy input[name='biopsy']:checked");
                        var a = f.val(), m = $("#biopsy_month option:selected").val(), y = $("#biopsy_year").val(), d = $("#biopsy_day").val();
                        var content = f.closest("label").text();
                        if (String(a) === "true" && $.trim(m+y+d)) {
                            content += "&nbsp;&nbsp;" + tnthDates.displayDateString(m, d, y);
                            $("#biopsyDateContainer").show();
                        }
                        this.setContent($("#biopsy_view"), content);
                    }
                };
            },
            initSection: function(type) {
                switch (String(type).toLowerCase()) {
                case "name":
                    this.initNameSection();
                    break;
                case "birthday":
                    this.initBirthdaySection();
                    break;
                case "email":
                    this.initEmailSection();
                    break;
                case "phone":
                    this.initPhoneSection();
                    break;
                case "altphone":
                    this.initAltPhoneSection();
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
                case "communication":
                    this.initResetPasswordSection();
                    this.initCommunicationSection();
                    break;
                case "patientemailform":
                    this.initPatientEmailFormSection();
                    break;
                case "staffemailform":
                    this.initStaffRegistrationEmailSection();
                    break;
                case "resetpassword":
                    this.initResetPasswordSection();
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
                case "custompatientdetail":
                    this.initCustomPatientDetailSection();
                    break;
                case "roleslist":
                    this.initRolesListSection();
                    break;
                case "auditlog":
                    this.initAuditLogSection();
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
            postDemoData: function(field, data, callback) {
                callback = callback || function() {};
                if (!this.subjectId) {
                    callback({"error": i18next.t("Subject id is required")});
                    return false;
                }
                var self = this;
                Vue.nextTick(function () {
                    // DOM updated
                    field = field || $(field);
                    data = data || {};
                    var valid = field.get(0).validity ? field.get(0).validity.valid : true;
                    if (!valid) {
                        callback({"error": i18next.t("Invalid field value.")});
                        return false;
                    }
                    var o = field;
                    var parentContainer = field.closest(".profile-item-container");
                    var editButton = parentContainer.find(".profile-item-edit-btn");
                    var customErrorField = $("#" + o.attr("data-error-field"));
                    var hasError = customErrorField.length > 0 && customErrorField.text() !== "";
                    if (hasError) {
                        editButton.attr("disabled", false);
                        callback({"error": i18next.t("Validation error.")});
                        return;
                    }
                    editButton.attr("disabled", true);
                    data.resourceType = data.resourceType || "Patient";
                    self.modules.tnthAjax.putDemo(self.subjectId, data, field, false, function(data) {
                        callback(data);
                        setTimeout(function() {
                            self.setDemoData({cache: false}, function() {
                                var formGroup = parentContainer.find(".form-group").not(".data-update-on-validated");
                                formGroup.removeClass("has-error");
                                formGroup.find(".help-block.with-errors").html("");
                                editButton.attr("disabled", false);
                            });
                        }, 350);

                    });
                });
            },
            getTelecomData: function() {
                var telecom = [];
                var emailVal = $("#email").val();
                if ($.trim(emailVal)) {
                    telecom.push({ "system": "email", "value": $.trim(emailVal)});
                } else {
                    telecom.push({"system": "email", "value": "__no_email__"});
                }
                var phone = $.trim($("#phone").val());
                if (phone) {
                    telecom.push({"system": "phone", "use": "mobile", "value": phone});
                }
                var altphone = $.trim($("#altPhone").val());
                if (altphone) {
                    telecom.push({"system": "phone", "use": "home", "value": altphone});
                }
                return {"telecom": telecom};
            },
            getIdentifierData: function() {
                var self = this, studyIdField = $("#profileStudyId"), siteIdField = $("#profileSiteId");
                var studyId = studyIdField.val(), siteId = siteIdField.val(), identifiers = [];
                if (this.demo.data.identifier) {
                    this.demo.data.identifier.forEach(function(identifier) {
                        identifiers.push(identifier);
                    });
                } else {
                    if (self.subjectId) {
                        $.ajax({ //get current identifier(s)
                            type: "GET",
                            url: "/api/demographics/" + self.subjectId,
                            async: false
                        }).done(function(data) {
                            if (data && data.identifier) {
                                (data.identifier).forEach(function(identifier) {
                                    identifiers.push(identifier);
                                });
                            }
                        }).fail(function(xhr) {
                            self.modules.tnthAjax.reportError(self.subjectId, "api/demographics" + self.subjectId, xhr.responseText);
                        });
                    }
                }
                identifiers = $.grep(identifiers, function(identifier) { //this will save study Id or site Id only if each has a value otherwise if each is empty, it will be purged from the identifiers that had older value of each
                    return identifier.system !== self.modules.SYSTEM_IDENTIFIER_ENUM.external_study_id &&
                        identifier.system !== self.modules.SYSTEM_IDENTIFIER_ENUM.external_site_id;
                });
                studyId = $.trim(studyId);
                if (studyId) {
                    var studyIdObj = {system: self.modules.SYSTEM_IDENTIFIER_ENUM.external_study_id, use: "secondary",value: studyId};
                    identifiers.push(studyIdObj);
                }
                siteId = $.trim(siteId);
                if (siteId) {
                    var siteIdObj = { system: self.modules.SYSTEM_IDENTIFIER_ENUM.external_site_id, use: "secondary", value: siteId};
                    identifiers.push(siteIdObj);
                }
                return {"identifier": identifiers};

            },
            getExtensionData: function() {
                var self = this, e = $("#userEthnicity"), r = $("#userRace"), tz = $("#profileTimeZone"), ethnicityIDs, raceIDs, tzID;
                var extension = [];
                if (e.length > 0) {
                    ethnicityIDs = $("#userEthnicity input:checked").map(function() {
                        return {code: $(this).val(), system: self.modules.SYSTEM_IDENTIFIER_ENUM.ethnicity_system};
                    }).get();
                    if (ethnicityIDs) {
                        extension.push({"url": self.modules.SYSTEM_IDENTIFIER_ENUM.ethnicity, "valueCodeableConcept": {"coding": ethnicityIDs}});
                    }
                }
                if (r.length > 0) {
                    raceIDs = $("#userRace input:checkbox:checked").map(function() {
                        return {code: $(this).val(),system: self.modules.SYSTEM_IDENTIFIER_ENUM.race_system};
                    }).get();
                    if (raceIDs) {
                        extension.push({"url": self.modules.SYSTEM_IDENTIFIER_ENUM.race, "valueCodeableConcept": {"coding": raceIDs}});
                    }
                }
                if (tz.length > 0) {
                    tzID = $("#profileTimeZone option:selected").val();
                    if (tzID) {
                        extension.push({timezone: tzID, url: self.modules.SYSTEM_IDENTIFIER_ENUM.timezone});
                    }
                }
                return {"extension": extension};
            },
            initNameSection: function() {
                var self = this;
                $("#firstname").on("updateDemoData", function() {
                    self.postDemoData($(this), {"name": {"given": $.trim($(this).val())}});
                });
                $("#lastname").on("updateDemoData", function() {
                    self.postDemoData($(this), {"name": {"family": $.trim($(this).val())}});
                });
            },
            initBirthdaySection: function() {
                var self = this;
                ["year", "month", "date"].forEach(function(fn) {
                    var field = $("#" + fn), y = $("#year"), m = $("#month"),d = $("#date");
                    field.on("keyup focusout", function() {
                        var isValid = self.modules.tnthDates.validateDateInputFields(m, d, y, "errorbirthday");
                        if (isValid) {
                            $("#birthday").val(y.val() + "-" + m.val() + "-" + d.val());
                            $("#errorbirthday").html("");
                        } else {
                            $("#birthday").val("");
                        }
                    });
                    field.on("updateDemoData", function() {
                        if (y.val() && m.val() && d.val()) {
                            self.postDemoData($(this), {birthDate: y.val() + "-" + m.val() + "-" + d.val()});
                        }
                    });
                });
                this.__convertToNumericField($("#date, #year"));
            },
            initEmailSection: function() {
                var self = this;
                $("#email").attr("data-update-on-validated", "true").attr("data-user-id", self.subjectId);
                $(".btn-send-email").blur();
                $("#email").on("keyup", function() {
                    $("#erroremail").html("");
                });
                $("#email").on("change", function() {
                    var o = $(this);
                    setTimeout(function() {
                        var hasError = $("#emailGroup").hasClass("has-error");
                        if (!hasError) {
                            self.demo.data.email = o.val();
                            $("#erroremail").html("");
                            $("#email_view").html("<p>" + (o.val()||i18next.t("not provided")) + "</p>"); /*global i18next */
                        }
                    }, 350);
                });
                $("#email").on("postEventUpdate", function() {
                    self.postDemoData($(this), self.getTelecomData());
                });
            },
            updateTelecomData: function(event) {
                this.postDemoData($(event.target), this.getTelecomData());
            },
            initPhoneSection: function() {
                this.__convertToNumericField($("#phone"));
            },
            initAltPhoneSection: function() {
                this.__convertToNumericField($("#altPhone"));
            },
            updateExtensionData: function(event) {
                this.postDemoData($(event.target), this.getExtensionData());
            },
            updateGenderData: function(event) {
                this.postDemoData($(event.target), {gender: event.target.value});
            },
            updateLocaleData: function(event) {
                var targetElement = $(event.target);
                var selectedLocale = targetElement.find("option:selected");
                var data = {communication: [{
                    "language": {
                        "coding": [{"code": selectedLocale.val(), "display": selectedLocale.text(), "system": "urn:ietf:bcp:47"}]
                    }
                }]};
                this.postDemoData(targetElement, data);
                this.modules.tnthDates.clearSessionLocale();
                setTimeout(function() {window.location.reload(true);}, 1000);
            },
            updateIdentifierData: function(event) {
                this.postDemoData($(event.target), this.getIdentifierData());
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
            "reloadSendPatientEmailForm": function(userId) {
                if ($("#sendPatientEmailTabContent").length === 0) { return false; }
                var self = this;
                $("#sendPatientEmailTabContent").animate({opacity: 0}, function() {
                    $(this).css("opacity", 1);
                    setTimeout(function() {
                        var checkedOrgInput = $("#userOrgs input[name='organization']:checked");
                        if (checkedOrgInput.attr("id") === "noOrgs") {
                            return false;
                        }
                        if (self.settings.hasOwnProperty("ACCEPT_TERMS_ON_NEXT_ORG") &&
                            checkedOrgInput.attr("data-parent-name") === self.settings.ACCEPT_TERMS_ON_NEXT_ORG) {
                            $("#profileassessmentSendEmailContainer").addClass("active");  ////update registration and assessment status email tiles in communications section, needed when org changes
                            self.assessmentStatus(userId);
                        } else {
                            $("#profileassessmentSendEmailContainer").removeClass("active");
                        }
                    }, 500);
                });
            },
            "assessmentStatus": function(userId) {
                var self = this;
                this.modules.tnthAjax.patientReport(userId, {useWorker: true}, function(data) {
                    if (data.error || !data.user_documents) {
                        return false;
                    }
                    self.patientReport.data = data.user_documents;
                    var pcpReports = $.grep(data.user_documents, function(document) {
                        return /P3P/gi.test(document.filename);
                    });
                    self.patientReport.hasP3PReport = pcpReports && pcpReports.length > 0;
                    if (self.patientReport.hasP3PReport) {
                        $("#btnProfileSendassessmentEmail").hide();
                        $("#assessmentStatusContainer .email-selector-container").hide();
                    }
                });
            },
            getEmailContent: function(userId, messageId, callback) {
                callback = callback || function() {};
                $("#messageLoader_"+messageId).show();
                $("#messageLink_"+messageId).css("visibility", "hidden");
                this.modules.tnthAjax.emailLog(userId, false, function(data) {
                    setTimeout(function() {
                        $("#messageLoader_"+messageId).hide();
                        $("#messageLink_"+messageId).css("visibility", "visible");
                    }, 550);
                    if (!data.messages) {
                        callback(data);
                        return false;
                    }
                    var targetMessages = $.grep(data.messages, function(item) {
                        return parseInt(item.id) === parseInt(messageId);
                    });
                    targetMessages.forEach(function(item) {
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
                    });
                    callback(data);
                });
            },
            getEmailLog: function(userId, data) {
                if (!data.error) {
                    var self = this;
                    if (data.messages && data.messages.length > 0) {
                        (data.messages).forEach(function(item) {
                            item.sent_at = self.modules.tnthDates.formatDateString(item.sent_at, "iso");
                            item.subject = "<i id='messageLoader_" + item.id + "' class='message-loader fa fa-spinner fa-spin tnth-hide'></i>" +
                                           "<a id='messageLink_" + item.id + "' class='item-link' data-user-id='" + userId + "' data-item-id='" + item.id + "'><u>" + item.subject + "</u></a>";
                        });
                        $("#emailLogContent").html("<table id='profileEmailLogTable'></table>");
                        $("#profileEmailLogTable").bootstrapTable(this.setBootstrapTableConfig({
                            data: data.messages,
                            classes: "table table-responsive profile-email-log",
                            sortName: "sent_at",
                            sortOrder: "desc",
                            toolbar: "#emailLogTableToolBar",
                            columns: [{
                                field: "sent_at",
                                title: i18next.t("Date (GMT), Y-M-D"),
                                searchable: true,
                                sortable: true
                            }, {
                                field: "subject",
                                title: i18next.t("Subject"),
                                class: "message-subject",
                                searchable: true,
                                sortable: true
                            }, {
                                field: "recipients",
                                title: i18next.t("Email"),
                                sortable: true,
                                searchable: true,
                                width: "20%"
                            }]
                        }));
                        setTimeout(function() {
                            $("#lbEmailLog").addClass("active");
                            $("#profileEmailLogTable a.item-link").on("click", function() {
                                self.getEmailContent($(this).attr("data-user-id"), $(this).attr("data-item-id"));
                            });
                        }, 150);
                    } else {
                        $("#emailLogContent").html("<span class='text-muted'>" + i18next.t("No email log entry found.") + "</span>");
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
                $(".email-selector").off("change").on("change", function() {
                    self.messages.userInviteEmailErrorMessage = "";
                    self.messages.userInviteEmailInfoMessage = "";
                    var emailType = $(this).closest(".profile-email-container").attr("data-email-type");
                    var btnEmail = $("#btnProfileSend" + emailType + "Email");
                    if (String(this.value) !== "" && $("#email").val() !== "" && $("#erroremail").text() === "") {
                        var message = i18next.t("{emailType} email will be sent to {email}");
                        message = message.replace("{emailType}", $(this).children("option:selected").text())
                            .replace("{email}", $("#email").val());
                        self.messages.userInviteEmailInfoMessage = message;
                        btnEmail.attr("disabled", false).removeClass("disabled");
                    } else {
                        self.messages.userInviteEmailInfoMessage = "";
                        btnEmail.attr("disabled", true).addClass("disabled");
                    }
                });
                $("#email").on("change", function() {
                    self.messages.userInviteEmailInfoMessage = "";
                    self.messages.userInviteEmailErrorMessage = "";
                });
                $(".btn-send-email").off("click").on("click", function(event) {
                    event.preventDefault();
                    event.stopPropagation();
                    var emailType = $(this).closest(".profile-email-container").attr("data-email-type");
                    var emailTypeElem = $("#profile" + emailType + "EmailSelect"), selectedOption = emailTypeElem.children("option:selected");
                    var btnSelf = $(this);
                    if (selectedOption.val() === "") {
                        return false;
                    }
                    var emailUrl = selectedOption.attr("data-url"), email = $("#email").val(), subject = "", body = "", returnUrl = "";
                    var accessUrlError = "";
                    if (!emailUrl) {
                        self.messages.userInviteEmailErrorMessage = i18next.t("Url for email content is unavailable.");
                        return false;
                    }
                    var resetBtn = function(disabled, showLoading) {
                        disabled = disabled || false;
                        btnSelf.attr("disabled", disabled);
                        self.patientEmailForm.loading = showLoading;
                        if (!disabled) {
                            btnSelf.removeClass("disabled");
                        } else {
                            btnSelf.addClass("disabled");
                        }
                    };
                    resetBtn(true, true);
                    $.ajax({ //get email content via API
                        type: "GET",
                        url: emailUrl,
                        cache: false,
                        async: true
                    }).done(function(data) {
                        if (!data || !data.subject || !data.body) {
                            self.messages.userInviteEmailErrorMessage = "<div>" + i18next.t("Unable to send email. Missing content.") + "</div>";;
                            resetBtn();
                            return false;
                        }
                        subject = data.subject;
                        body = data.body;
                        if (selectedOption.val() === "invite" && emailType === "registration") {
                            returnUrl = self.getAccessUrl();
                            if (returnUrl) {
                                body = body.replace(/url_placeholder/g, decodeURIComponent(returnUrl));
                            } else {
                                accessUrlError = i18next.t("failed request to get email invite url");
                            }
                        }

                        self.messages.userInviteEmailErrorMessage = "";
                        if (accessUrlError) {
                            self.messages.userInviteEmailErrorMessage = accessUrlError;
                            resetBtn();
                            return false;
                        }
                        self.modules.tnthAjax.invite(self.subjectId, {
                            "subject": subject,
                            "recipients": email,
                            "body": body
                        }, function(data) {
                            if (data.error) {
                                self.messages.userInviteEmailErrorMessage = i18next.t("Error occurred while sending invite email.");
                                resetBtn();
                                return false;
                            }
                            self.messages.userInviteEmailInfoMessage = "<strong class='text-success'>" + i18next.t("{emailType} email sent to {emailAddress}").replace("{emailType}", selectedOption.text()).replace("{emailAddress}", email) + "</strong>";
                            emailTypeElem.val("");
                            self.modules.tnthAjax.emailLog(self.subjectId, {useWorker: true}, function(data) { //reload email audit log
                                setTimeout(function() {
                                    self.getEmailLog(self.subjectId, data);
                                }, 100);
                            });
                            resetBtn(true);
                        });
                    }).fail(function(xhr) { //report error
                        self.messages.userInviteEmailErrorMessage = i18next.t("Error occurred retreving email content via API.");
                        resetBtn();
                        self.modules.tnthAjax.reportError(self.subjectId, emailUrl, xhr.responseText);
                    });
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
                                    parentName = $(this).attr("data-parent-name") || $(this).closest(".org-container[data-parent-id]").attr("data-parent-name") ;
                                }
                            });
                        }
                        return parentName ? parentName : i18next.t("your clinic");
                    })();
                    $(this).addClass("disabled").attr("disabled", true);
                    $("#sendRegistrationEmailForm .loading-indicator").show();
                    $("#profileEmailErrorMessage").html("");
                    var btnRef = $(this);
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
                            if (data.error) {
                                $("#profileEmailErrorMessage").text(i18next.t("Error occurred while sending invite email."));
                            }
                        }
                        $("#sendRegistrationEmailForm .loading-indicator").hide();
                        btnRef.removeClass("disabled").attr("disabled", false);
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
                this.modules.tnthAjax.emailLog(subjectId, {useWorker: true}, function(data) {
                    setTimeout(function() { self.getEmailLog(subjectId, data); }, 100);
                });
            },
            initResetPasswordSection: function() {
                var self = this;
                $("#btnPasswordResetEmail").on("click", function(event) {
                    event.preventDefault();
                    event.stopImmediatePropagation(); //stop bubbling of events
                    var email = $("#email").val();
                    self.modules.tnthAjax.passwordReset(self.subjectId, function(data) {
                        if (!data.error) {
                            $("#passwordResetMessage").text(i18next.t("Password reset email sent to {email}").replace("{email}", email));
                        } else {
                            $("#passwordResetMessage").text(i18next.t("Unable to send email."));
                        }
                    });
                });
            },
            updateDeceasedSection: function(targetField) {
                var data = {}, isChecked = $("#boolDeath").is(":checked");
                var hasSuspendedConsent = $("#consentListTable .withdrawn-label").length;
                var confirmationRequired = isChecked && !hasSuspendedConsent && this.settings.LOCALIZED_AFFILIATE_ORG && this.topLevelOrgs.indexOf(this.settings.LOCALIZED_AFFILIATE_ORG) !== -1;
                $("#deceasedInfo").html("");
                if ($("#deathDate").val()) {
                    data.deceasedDateTime = $("#deathDate").val();
                }
                data.deceasedBoolean = isChecked;
                if (!confirmationRequired) {
                    this.postDemoData(targetField, data);
                    return;
                }
                var self = this, subjectId = this.subjectId;
                var setDisabledFields = function(disabledFlag) {
                    $("#boolDeath, #deathDate, #deathDay, #deathYear, #deathMonth").attr("disabled", disabledFlag);
                };
                var hidePopover = function() {
                    $("#deceasedConsentPopover").popover("hide");
                };
                var showPopover = function() {
                    if (!$("#deceasedConsentPopover").attr("aria-describedby")) {
                        $("#deceasedConsentPopover").popover("show");
                    }
                };
                var clearFields = function() {
                    if (!self.demo.data.deceasedDateTime) {
                        $("#deathDate, #deathDay, #deathYear, #deathMonth").val("");
                    }
                    if (!(String(self.demo.data.deceasedBoolean).toLowerCase() === "true")) {
                        $("#boolDeath").prop("checked", false);
                    }
                    hidePopover();
                };
                showPopover();
                $("#btnDeceasedConsentYes").off("click").on("click", function(e) { //selecting yes in the confirmation popover
                    e.stopPropagation();
                    setDisabledFields(true);
                    self.postDemoData(targetField, data, function(data) {
                        if (!data || data.error) {
                            setDisabledFields(false);
                            return false;
                        }
                        var orgTool = self.getOrgTool(), selectedOrgElement = orgTool.getSelectedOrg();
                        if (!selectedOrgElement.length) { //no need to continue if no affiliated org
                            setDisabledFields(false);
                            return;
                        }
                        self.modules.tnthAjax.withdrawConsent(subjectId, selectedOrgElement.val(), "", function(data) {
                            setDisabledFields(false);
                            if (data.error) {
                                $("#deceasedInfo").html(i18next.t("Error occurred suspending consent for subject."));
                                return;
                            }
                            hidePopover();
                            self.reloadConsentList(subjectId);
                        });
                    });
                });
                $("#btnDeceasedConsentNo").off("click").on("click", function(e) { //selecting no in the confirmation popover
                    e.stopPropagation();
                    clearFields();
                });
                $("#profileDeceasedSection .profile-item-edit-btn").on("click", function(e) {
                    e.stopPropagation();
                    clearFields();
                });
            },
            initDeceasedSection: function() {
                var self = this;
                $("#deathYear").val("");
                $("#deathMonth").val("");
                $("#deathDay").val("");
                $("#deathDate").val("");
                $("#boolDeath").prop("checked", false);
                if (this.demo.data.deceasedDateTime) {
                    $("#deathYear").val(this.demo.data.deceasedYear);
                    $("#deathMonth").val(this.demo.data.deceasedMonth);
                    $("#deathDay").val(this.demo.data.deceasedDay);
                    $("#deathDate").val(this.demo.data.deceasedMonth + "-" + this.demo.data.deceasedDay + "-" + this.demo.data.deceasedYear);
                    $("#boolDeath").prop("checked", true);
                }
                if (String(this.demo.data.deceasedBoolean).toLowerCase() === "true") {
                    $("#boolDeath").prop("checked", true);
                }
                this.__convertToNumericField($("#deathDay, #deathYear"));
                $("#boolDeath").on("click", function() {
                    if (!($(this).is(":checked"))) {
                        $("#deathYear").val("");
                        $("#deathDay").val("");
                        $("#deathMonth").val("");
                        $("#deathDate").val("");
                    }
                    self.updateDeceasedSection($("#boolDeathGroup"));
                });
                ["deathDay", "deathMonth", "deathYear"].forEach(function(fn) {
                    var fd = $("#" + fn);
                    var triggerEvent = fd.attr("type") === "text" ? "blur" : "change";
                    fd.on(triggerEvent, function() {
                        var d = $("#deathDay"), m = $("#deathMonth"), y = $("#deathYear");
                        if (d.val() && m.val() && y.val() && d.get(0).validity.valid && m.get(0).validity.valid && y.get(0).validity.valid) {
                            var errorMsg = self.modules.tnthDates.dateValidator(d.val(), m.val(), y.val(), true);
                            if (errorMsg === "") {
                                $("#deathDate").val(y.val() + "-" + m.val() + "-" + d.val());
                                $("#boolDeath").prop("checked", true);
                                $("#errorDeathDate").text("");
                                self.updateDeceasedSection($("#deceasedDateContainer"));
                            } else {
                                $("#errorDeathDate").text(errorMsg);
                            }
                        }
                    });
                });
            },
            initPatientReportSection: function() {
                var self = this;
                this.modules.tnthAjax.patientReport(self.subjectId, {useWorker: true}, function(data) {
                    if (!data.error) {
                        if (data.user_documents && data.user_documents.length > 0) {
                            var fData = [];
                            (data.user_documents).forEach(function(item) {
                                item.filename = self.escapeHtml(item.filename);
                                item.document_type = self.escapeHtml(item.document_type);
                                item.uploaded_at = self.modules.tnthDates.formatDateString(item.uploaded_at, "iso");
                                item.actions = '<a title="' + i18next.t("Download") + '" href="' + '/api/user/' + String(item.user_id) + '/user_documents/' + String(item.id) + '"><i class="fa fa-download"></i></a>';
                                fData.push(item);
                            });
                            self.patientReport.data = fData;
                            $("#profilePatientReportTable").bootstrapTable(self.setBootstrapTableConfig({
                                data: fData,
                                classes: "table table-responsive profile-patient-reports",
                                sortName: "uploaded_at",
                                sortOrder: "desc",
                                toolbar: "#prTableToolBar",
                                columns: [{field: "contributor", title: i18next.t("Type"), searchable: true, sortable: true},
                                    {field: "filename", title: i18next.t("Report Name"), searchable: true, sortable: true},
                                    {field: "uploaded_at", title: i18next.t("Generated (GMT)"), sortable: true, searchable: true, width: "20%"},
                                    {field: "document_type", title: i18next.t("Document Type"), sortable: true, visible: false},
                                    {field: "actions", title: i18next.t("Download"), sortable: false, searchable: false, visible: true, class: "text-center"}]
                            }));
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
                $("#assessmentListMessage").text(i18next.t("No questionnaire data found."));
                self.modules.tnthAjax.assessmentList(self.subjectId, {useWorker: true}, function(data) {
                    if (data.error) {
                        self.assessment.assessmentListError = i18next.t("Problem retrieving session data from server.");
                        return false;
                    }
                    self.assessment.assessmentListError = "";
                    var sessionUserId = $("#_session_user_id").val();
                    var entries = data.entry ? data.entry : null;
                    if (!entries || entries.length === 0) {
                        return false;
                    }
                    entries.forEach(function(entry, index) {
                        var reference = entry.questionnaire.reference;
                        var arrRefs = String(reference).split("/");
                        var instrumentId = arrRefs.length > 0 ? arrRefs[arrRefs.length - 1] : "";
                        if (!instrumentId) {
                            return false;
                        }
                        var authoredDate = String(entry.authored);
                        var reportLink = "/patients/session-report/" + sessionUserId + "/" + instrumentId + "/" + authoredDate;
                        self.assessment.assessmentListItems.push({
                            title: i18next.t("Click to view report"),
                            link: reportLink,
                            display: i18next.t(entry.questionnaire.display),
                            status: i18next.t(entry.status),
                            class: (index % 2 !== 0 ? "class='odd'" : "class='even'"),
                            date: self.modules.tnthDates.formatDateString(entry.authored, "iso")
                        });
                    });
                });
            },
            handleSelectedState: function(event) {
                var newValue = event.target.value;
                this.orgsSelector.selectedState = newValue;
            },
            initOrgsStateSelectorSection: function() {
                var self = this, orgTool = this.getOrgTool(), subjectId = this.subjectId;
                var stateDict={AL: i18next.t("Alabama"),AK: i18next.t("Alaska"), AS: i18next.t("American Samoa"),AZ: i18next.t("Arizona"),AR:i18next.t("Arkansas"),CA: i18next.t("California"),CO:i18next.t("Colorado"),CT:i18next.t("Connecticut"),DE:i18next.t("Delaware"),DC:i18next.t("District Of Columbia"),FM: i18next.t("Federated States Of Micronesia"),FL:i18next.t("Florida"),GA:i18next.t("Georgia"),GU:i18next.t("Guam"),HI:i18next.t("Hawaii"),ID:i18next.t("Idaho"),IL:i18next.t("Illinois"),IN:i18next.t("Indiana"),IA:i18next.t("Iowa"),KS:i18next.t("Kansas"),KY:i18next.t("Kentucky"),LA:i18next.t("Louisiana"),ME:i18next.t("Maine"),MH:i18next.t("Marshall Islands"),MD:i18next.t("Maryland"),MA:i18next.t("Massachusetts"),MI:i18next.t("Michigan"),MN:i18next.t("Minnesota"),MS:i18next.t("Mississippi"),MO:i18next.t("Missouri"),MT:i18next.t("Montana"),NE: i18next.t("Nebraska"),NV:i18next.t("Nevada"),NH:i18next.t("New Hampshire"),NJ:i18next.t("New Jersey"),NM:i18next.t("New Mexico"),NY:i18next.t("New York"),NC:i18next.t("North Carolina"),ND:i18next.t("North Dakota"),MP:i18next.t("Northern Mariana Islands"),OH:i18next.t("Ohio"),OK:i18next.t("Oklahoma"),OR:i18next.t("Oregon"),PW:i18next.t("Palau"),PA:i18next.t("Pennsylvania"),PR:i18next.t("Puerto Rico"),RI:i18next.t("Rhode Island"),SC:i18next.t("South Carolina"),SD:i18next.t("South Dakota"),TN:i18next.t("Tennessee"),TX:i18next.t("Texas"),UT:i18next.t("Utah"),VT:i18next.t("Vermont"),VI:i18next.t("Virgin Islands"),VA:i18next.t("Virginia"),WA:i18next.t("Washington"),WV:i18next.t("West Virginia"),WI:i18next.t("Wisconsin"),WY:i18next.t("Wyoming")};
                $("#stateSelector").on("change", function() {
                    var selectedState = $(this).find("option:selected"),
                        container = $("#" + selectedState.val() + "_container");
                    var defaultPrompt = i18next.t("What is your main clinic for prostate cancer care");
                    $("#userOrgsInfo").hide();
                    if (selectedState.val() !== "") {
                        if (selectedState.val() === "none") {
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

                var orgsList = this.orgsList, states = {}, contentHTML = "";
                var getParentState = function(o, states) {
                    if (!o) {
                        return "";
                    }
                    var s = "", found = false;
                    for (var state in states) {
                        if (!found) {
                            (states[state]).forEach(function(i) {
                                if (String(i) === String(o)) {
                                    s = state;
                                    found = true;
                                }
                            });
                        }
                    }
                    return s;
                };

                /**** draw state select element first to gather all states - assign orgs to each state in array ***/
                (this.orgsData).forEach(function(item) {
                    var __state = "";
                    if (!item.identifier) { return false; }
                    (item.identifier).forEach(function(region) {
                        if (String(region.system) === String(self.modules.SYSTEM_IDENTIFIER_ENUM.practice_region) && region.value) {
                            __state = (region.value).split(":")[1];
                            if (!states.hasOwnProperty(__state)) {
                                states[__state] = [item.id];
                                $("#userOrgs .main-state-container").prepend("<div id='" + __state + "_container' state='" + __state + "' class='state-container'></div>");
                            } else {
                                (states[__state]).push(item.id);
                            }
                            if ($("#stateSelector option[value='" + __state + "']").length === 0) {
                                $("#stateSelector").append("<option value='" + __state + "'>" + stateDict[__state] + "</option>");
                            }
                            orgsList[item.id].state = __state; //assign state for each item
                        }
                    });
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
                            if (a.name < b.name) {
                                return -1;
                            }
                            if (a.name > b.name) {
                                return 1;
                            }
                            return 0;
                        } else if (oo_1.children.length > 0 && oo_2.children.length === 0) {
                            return -1;
                        } else if (oo_2.children.length > 0 && oo_1.children.length === 0) {
                            return 1;
                        } else {
                            if (a.name < b.name) {
                                return -1;
                            }
                            if (a.name > b.name) {
                                return 1;
                            }
                            return 0;
                        }
                    } else {
                        return 0;
                    }
                });

                parentOrgs.forEach(function(item) {
                    var state = orgsList[item.id].state;
                    if ($("#" + state + "_container").length > 0) {
                        var oo = orgsList[item.id];
                        if (oo.children.length > 0) {
                            contentHTML = "<legend orgId='{orgId}'>{translatedOrgName}</legend>";
                            contentHTML += "<input class='tnth-hide' type='checkbox' name='organization' parent_org='true' data-org-name='{orgName}' ";
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
                    if (a.name < b.name) {
                        return 1;
                    }
                    if (a.name > b.name) {
                        return -1;
                    }
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
                        if (o.length > 0 && parseInt(o.val()) !== 0) {
                            o.closest(".state-container").show();
                            $(".clinic-prompt").show();
                        }
                    }, 150);
                    $("#userOrgs input[name='organization']").each(function() {
                        if (parseInt($(this).val()) !== 0) {
                            self.getDefaultModal(this);
                        }
                    });
                    orgTool.onLoaded(subjectId);
                    self.handleOrgsEvent();
                    self.setOrgsVis();
                } else { // if no states found, then need to draw the orgs UI
                    $("#userOrgs .selector-show").hide();
                    orgTool.onLoaded(subjectId, true);
                    self.handleOrgsEvent();
                    self.setOrgsVis(function() {
                        orgTool.filterOrgs(orgTool.getHereBelowOrgs());
                        orgTool.morphPatientOrgs();
                        $(".noOrg-container, .noOrg-container *").show();
                    });
                }
                if ($("#mainDiv.profile").length > 0) {
                    self.modules.tnthAjax.getConsent(subjectId, {useWorker: true}, function(data) {
                        self.getConsentList(data);
                    });
                }
                $("#clinics").attr("loaded", true);

            },
            initDefaultOrgsSection: function() {
                var subjectId = this.subjectId, orgTool = this.getOrgTool(), self = this;
                orgTool.onLoaded(subjectId, true);
                this.setOrgsVis(
                    function() {
                        if ((typeof leafOrgs !== "undefined") && leafOrgs) { /*global leafOrgs*/
                            orgTool.filterOrgs(leafOrgs);
                        }
                        if ($("#requireMorph").val()) {
                            orgTool.morphPatientOrgs();
                        }
                        self.handleOrgsEvent();
                        self.modules.tnthAjax.getConsent(subjectId, {useWorker: true}, function(data) {
                            self.getConsentList(data);
                        });
                        $("#clinics").attr("loaded", true);
                    });
            },
            setOrgsVis: function(callback) {
                callback = callback || function() {};
                var data = this.demo.data ? this.demo.data : null;
                if (!data || ! data.careProvider) { callback(); return false;}
                for (var i = 0; i < data.careProvider.length; i++) {
                    var val = data.careProvider[i];
                    var orgID = val.reference.split("/").pop();
                    if (parseInt(orgID) === 0) {
                        $("#userOrgs #noOrgs").prop("checked", true);
                        if ($("#stateSelector").length > 0) {
                            $("#stateSelector").find("option[value='none']").prop("selected", true).val("none");
                        }
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
                            if (ckOrg.length > 0) {
                                ckOrg.prop("checked", true);
                            } else {
                                var topLevelOrg = $("#fillOrgs").find("legend[orgid='" + orgID + "']");
                                if (topLevelOrg.length > 0) {
                                    topLevelOrg.attr("data-checked", "true");
                                }
                            }
                        }
                    }
                }
                callback(data);
            },
            handleOrgsEvent: function() {
                var self = this, orgTool = this.getOrgTool();
                $("#userOrgs input[name='organization']").each(function() {
                    $(this).attr("data-save-container-id", "userOrgs");
                    $(this).on("click", function() {
                        var userId = self.subjectId, parentOrg = orgTool.getElementParentOrg(this);
                        var orgsElements = $("#userOrgs input[name='organization']").not("[id='noOrgs']");
                        if ($(this).prop("checked")) {
                            if ($(this).attr("id") !== "noOrgs") {
                                $("#noOrgs").prop("checked", false);
                            } else {
                                orgsElements.prop("checked", false);
                            }
                        }
                        if (sessionStorage.getItem("noOrgModalViewed")) {
                            sessionStorage.removeItem("noOrgModalViewed");
                        }
                        $("#userOrgs .help-block").removeClass("error-message").text("");

                        if ($(this).attr("id") !== "noOrgs" && $("#fillOrgs").attr("patient_view")) {
                            if (self.modules.tnthAjax.hasConsent(userId, parentOrg)) {
                                self.updateOrgs($("#clinics"), true);
                            } else {
                                var __modal = self.getConsentModal(parentOrg);
                                if (__modal && __modal.length > 0) {
                                    setTimeout(function() { __modal.modal("show"); }, 50);
                                } else {
                                    self.setDefaultConsent(userId, parentOrg);
                                    setTimeout(function() { self.updateOrgs($("#clinics"), true);}, 500);
                                }
                            }
                        } else {
                            self.handleConsent($(this));
                            setTimeout(function() {
                                self.updateOrgs($("#clinics"),true);
                            }, 500);
                            self.reloadConsentList(userId);
                        }
                        self.handlePcaLocalized();
                        if ($("#locale").length > 0) {
                            self.modules.tnthAjax.getLocale(userId);
                        }
                        if ($("#profileassessmentSendEmailContainer").length > 0) {
                            setTimeout(function() {
                                self.reloadSendPatientEmailForm(self.subjectId);
                            }, 150);
                        }
                    });
                });
            },
            getNoOrgDisplay: function() {
                return "<p class='text-muted'>"+this.modules.i18next.t("No affiliated clinic")+"</p>";
            },
            getOrgsDisplay: function() {
                if (!this.demo.data.careProvider || this.demo.data.careProvider.length === 0) {
                    return this.getNoOrgDisplay();
                }
                /* example return from api demographics: [{ display: Duke, reference: "api/organization/1301"}, {"display":"Arvin George","reference":"api/practitioner/1851648521?system=http://hl7.org/fhir/sid/us-npi"}]
                 * NOTE: need to exclude displays other than organization */
                var self = this;
                var arrDisplay = this.demo.data.careProvider.map(function(item) {
                    if (String(item.reference) === "api/organization/0") { //organization id = 0
                        return self.getNoOrgDisplay();
                    }
                    return (item.reference.match(/^api\/organization/gi) ? "<p>"+item.display+"</p>": "");
                });

                return arrDisplay.join("");
            },
            updateOrgs: function(targetField, sync) {
                var demoArray = {"resourceType": "Patient"}, preselectClinic = $("#preselectClinic").val(), userId=this.subjectId;
                var self = this;
                if (preselectClinic) {
                    var parentOrg = $("#userOrgs input[name='organization'][value='" + preselectClinic + "']").attr("data-parent-id") || preselectClinic;
                    if (self.modules.tnthAjax.hasConsent(userId, parentOrg)) {
                        demoArray.careProvider = [{reference: "api/organization/" + preselectClinic}];
                    }
                } else {
                    var orgIDs = $("#userOrgs input[name='organization']:checked").map(function() {
                        return {reference: "api/organization/" + $(this).val()};
                    }).get();
                    if (orgIDs && orgIDs.length > 0) {
                        demoArray.careProvider = orgIDs;
                    }
                    /**** dealing with the scenario where user can be affiliated with top level org e.g. TrueNTH Global Registry, IRONMAN, via direct database addition **/
                    $("#fillOrgs legend[data-checked]").each(function() {
                        var tOrg = $(this).attr("orgid");
                        if (tOrg) {
                            demoArray.careProvider = demoArray.careProvider || [];
                            demoArray.careProvider.push({reference: "api/organization/" + tOrg});
                        }
                    });
                }
                if ($("#aboutForm").length === 0 && (!demoArray.careProvider)) { //don't update org to none if there are top level org affiliation above
                    demoArray.careProvider = [{reference: "api/organization/" + 0}];
                }
                this.modules.tnthAjax.putDemo(userId, demoArray, targetField, sync, this.setDemoData);
            },
            getConsentModal: function(parentOrg) {
                var orgTool = this.getOrgTool();
                parentOrg = parentOrg || orgTool.getElementParentOrg(orgTool.getSelectedOrg());
                if (!parentOrg) { return false; }
                var __modal = $("#" + parentOrg + "_consentModal");
                if (__modal.length > 0) {
                    return __modal;
                } else {
                    var __defaultModal = this.getDefaultModal(orgTool.getSelectedOrg());
                    if (__defaultModal && __defaultModal.length > 0) {
                        return __defaultModal;
                    }
                }
                return false;
            },
            "getDefaultAgreementUrl": function(orgId) {
                var stockConsentUrl = $("#stock_consent_url").val(), agreementUrl = "", orgElement = $("#" + orgId + "_org");
                if (stockConsentUrl && orgElement.length > 0) {
                    var orgName = orgElement.attr("data-parent-name") || orgElement.attr("data-org-name");
                    agreementUrl = stockConsentUrl.replace("placeholder", encodeURIComponent(orgName));
                }
                return agreementUrl;
            },
            "setDefaultConsent": function(userId, orgId) {
                if (!userId) { return false;}
                var agreementUrl = this.getDefaultAgreementUrl(orgId), self = this;
                if (!agreementUrl) {
                    $($("#consentContainer .error-message").get(0)).text(i18next.t("Unable to set default consent agreement"));
                    return false;
                }
                var params = self.modules.tnthAjax.consentParams;
                params.org = orgId;
                params.agreementUrl = agreementUrl;
                self.modules.tnthAjax.setConsent(userId, params, "default");
                setTimeout(function() { //need to remove all other consents associated w un-selected org(s)
                    self.removeObsoleteConsent();
                }, 100);
                self.reloadConsentList(userId);
                $($("#consentContainer .error-message").get(0)).text("");
            },
            removeObsoleteConsent: function() {
                var userId = this.subjectId, co = [], OT = this.getOrgTool();
                $("#userOrgs input[name='organization']").each(function() {
                    if ($(this).is(":checked")) {
                        co.push($(this).val());
                        var po = OT.getElementParentOrg(this);
                        if (po) { co.push(po);}
                    }
                });
                this.modules.tnthAjax.deleteConsent(userId, {org: "all", exclude: co.join(",")}); //exclude currently selected orgs
            },
            "handleConsent": function(obj) {
                var self = this, OT = this.getOrgTool(), userId = this.subjectId, cto = this.isConsentWithTopLevelOrg(), tnthAjax = self.modules.tnthAjax;
                $(obj).each(function() {
                    var parentOrg = OT.getElementParentOrg(this), orgId = $(this).val();
                    if ($(this).prop("checked")) {
                        if ($(this).attr("id") !== "noOrgs") {
                            var agreementUrl = $("#" + parentOrg + "_agreement_url").val();
                            if (String(agreementUrl) !== "") {
                                var params = self.CONSENT_ENUM.consented;
                                params.org = cto ? parentOrg : orgId;
                                params.agreementUrl = agreementUrl;
                                setTimeout(function() {
                                    tnthAjax.setConsent(userId, params, "all", true, function() {
                                        self.removeObsoleteConsent();
                                    });
                                }, 350);
                            } else {
                                self.setDefaultConsent(userId, parentOrg);
                            }
                        } else { //remove all valid consent if no org is selected
                            setTimeout(function() { tnthAjax.deleteConsent(userId, {"org": "all"});}, 350);
                        }
                    } else {
                        if (cto) {
                            var childOrgs = $("#userOrgs input[data-parent-id='" + parentOrg + "']");
                            if ($("#fillOrgs").attr("patient_view")) {
                                childOrgs = $("#userOrgs div.org-container[data-parent-id='" + parentOrg + "']").find("input[name='organization']");
                            }
                            var allUnchecked = !childOrgs.is(":checked");
                            if (allUnchecked) {
                                setTimeout(function() { tnthAjax.deleteConsent(userId, {"org": parentOrg});}, 350);
                            }
                        } else {
                            setTimeout(function() { tnthAjax.deleteConsent(userId, {"org": orgId});}, 350);
                        }
                    }
                });
            },
            getDefaultModal: function(o) {
                if (!o) { return false;}
                var orgTool = this.getOrgTool();
                var orgId = orgTool.getElementParentOrg(o), orgModalId = orgId + "_defaultConsentModal", orgElement = $("#"+orgModalId);
                if (orgElement.length > 0) { return orgElement; }
                var orgsList = orgTool.getOrgsList(), orgItem = orgsList.hasOwnProperty(orgId) ? orgsList[orgId]: null,
                    orgName = (orgItem && orgItem.shortname) ? orgItem.shortname : ($(o).attr("data-parent-name") || $(o).closest("label").text());
                var title = i18next.t("Consent to share information");
                var consentText = i18next.t("I consent to sharing information with <span class='consent-clinic-name'>{orgName}</span>.".replace("{orgName}", orgName));
                var orgModalElement = $("#defaultConsentModal").clone(true);
                var tempHTML = orgModalElement.html();
                tempHTML = tempHTML.replace(/\{orgId\}/g, orgId)
                    .replace(/\{close\}/g, i18next.t("Close"))
                    .replace(/\{yes\}/g, i18next.t("Yes"))
                    .replace(/\{no\}/g, i18next.t("No"))
                    .replace(/\{title\}/g, title)
                    .replace(/\{consentText\}/g, consentText);
                orgModalElement.html(tempHTML);
                orgModalElement.attr("id", orgModalId);
                $("#defaultConsentContainer").append(orgModalElement);
                return orgElement;
            },
            initConsentSection: function() {
                var __self = this, orgTool = this.getOrgTool(), modalElements = $("#consentContainer .modal, #defaultConsentContainer .modal");
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
                    var orgId = $(this).attr("data-org"), userId = __self.subjectId;
                    var postUpdate = function(orgId, errorMessage) {
                        if (errorMessage) {
                            $("#"+orgId+"_consentAgreementMessage").html(errorMessage);
                        } else {
                            $("#"+orgId+"_consentAgreementMessage").html("");
                            setTimeout(function() { modalElements.modal("hide"); __self.removeObsoleteConsent(); }, 250);
                            setTimeout(function() { __self.reloadConsentList(userId);}, 500);
                        }
                        $("#" + orgId + "_loader.loading-message-indicator").hide();
                        closeButtons.attr("disabled", false);
                    };
                    $("#" + orgId + "_loader.loading-message-indicator").show();
                    if ($(this).val() === "yes") {
                        var params = __self.CONSENT_ENUM.consented;
                        params.org = orgId;
                        params.agreementUrl = $("#" + orgId + "_agreement_url").val() || __self.getDefaultAgreementUrl(orgId);
                        setTimeout(function() {__self.modules.tnthAjax.setConsent(userId, params,"",false, function(data) {
                            postUpdate(orgId, data.error);
                        });}, 50);
                    } else {
                        __self.modules.tnthAjax.deleteConsent(userId, {"org": orgId});
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
                            __self.updateOrgs($("#clinics"), true);
                        }
                    });
                    $(this).on("show.bs.modal", function() {
                        var checkedOrg = $("#userOrgs input[name='organization']:checked");
                        var shortName = checkedOrg.attr("data-short-name") || checkedOrg.attr("data-org-name");
                        if (!shortName) {
                            shortName = orgTool.getShortName(checkedOrg.val());
                        }
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
            handlePcaLocalized: function() {
                if (!this.subjectId || !this.isPatient()) {
                    return false;
                }
                var parentOrg = this.orgTool.getSelectedOrgTopLevelParentOrg();
                if (!this.settings.LOCALIZED_AFFILIATE_ORG) {
                    return false; //don't set at all if config is not present, i.e. Truenth does not have this config
                }
                this.modules.tnthAjax.postClinical(this.subjectId,"pca_localized", this.isLocalizedAffiliatedOrg());

            },
            isLocalizedAffiliatedOrg: function() {
                var parentOrg = this.orgTool.getSelectedOrgTopLevelParentOrg();
                if (!parentOrg) {
                    return false;
                }
                return this.orgTool.getOrgName(parentOrg) === this.settings.LOCALIZED_AFFILIATE_ORG;
            },
            updateClinicalSection: function(data) {
                if (!data) { return false; }
                var self = this;
                var sortedArray = data.sort(function(a, b) {
                    return b.content.id - a.content.id;
                });
                for (var i = 0; i < sortedArray.length; i++) {
                    var val = sortedArray[i];
                    var clinicalItem = String(val.content.code.coding[0].display);
                    var clinicalValue = val.content.valueQuantity.value;
                    var clinicalUnit = val.content.valueQuantity.units;
                    var truesyValue = parseInt(clinicalValue) === 1 && !clinicalUnit;
                    var falsyValue = parseInt(clinicalValue) === 0 && !clinicalUnit;
                    var status = val.content.status;
                    if (clinicalItem === "PCa diagnosis") {
                        clinicalItem = "pca_diag";
                    } else if (clinicalItem === "PCa localized diagnosis") {
                        clinicalItem = "pca_localized";
                    }
                    var ci = $('div[data-topic="' + clinicalItem + '"]');
                    if (ci.length > 0) {
                        ci.fadeIn();
                    }
                    var $radios = $('input:radio[name="' + clinicalItem + '"]');
                    if ($radios.length > 0) {
                        if (!$radios.is(":checked")) {
                            if (String(status) === "unknown") {
                                $radios.filter('[data-status="unknown"]').prop("checked", true);
                            } else {
                                $radios.filter("[value=" + clinicalValue + "]").not("[data-status='unknown']").prop("checked", true);
                            }
                            if (truesyValue) {
                                $radios.filter("[value=true]").prop("checked", true);
                            } else if (falsyValue) {
                                $radios.filter("[value=false]").prop("checked", true);
                            }
                            if (clinicalItem === "biopsy") {
                                if (String(clinicalValue) === "true" || truesyValue) {
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
                            if (clinicalItem === "pca_diag") {
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
                    var hasCancerTreatment = String(treatmentCode) === String(this.modules.SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE);
                    $("#tx_yes").prop("checked", hasCancerTreatment);
                    $("#tx_no").prop("checked", !hasCancerTreatment);
                }
            },
            onBeforeInitClinicalQuestionsSection: function() {
                if (this.mode !== "profile") { return false; }
                if (!this.isProxy()) {
                    $("#clinicalQuestionsContainer .profile-item-edit-btn").removeClass("tnth-hide");
                }
                $("#patientQ").show();
                $("#patTx").remove(); //don't show treatment
                $("#patientQ hr").hide();
                $(".pat-q input:radio").off("click").on("click", function() {
                    var thisItem = $(this), toCall = thisItem.attr("name"), toSend = thisItem.val(); // Get value from div - either true or false
                    if (String(toSend) === "true" || String(toCall) === "pca_localized") {
                        thisItem.parents(".pat-q").nextAll().fadeIn();
                    } else {
                        thisItem.parents(".pat-q").nextAll().fadeOut();
                    }
                });
                var diag = $("#pca_diag_yes");
                if (diag.is(":checked")) {
                    diag.parents(".pat-q").nextAll().fadeIn();
                } else {
                    diag.parents(".pat-q").nextAll().fadeOut();
                }
                this.fillSectionView("clinical");
            },
            initClinicalQuestionsSection: function() {
                if (!this.subjectId) { return false; }
                var self = this;
                self.modules.tnthAjax.getTreatment(self.subjectId, {useWorker:true}, function(data) {
                    self.updateTreatment(data);
                    self.modules.tnthAjax.getClinical(self.subjectId, {useWorker:true}, function(data) {
                        self.updateClinicalSection(data.entry);
                        $("#patientQ").attr("loaded", "true");
                        self.onBeforeInitClinicalQuestionsSection();
                        $("#patientQ [name='biopsy']").on("click", function() {
                            var toSend = String($(this).val()), biopsyDate = $("#biopsyDate").val(), thisItem = $(this), userId = self.subjectId;
                            var toCall = thisItem.attr("name") || thisItem.attr("data-name"), targetField = $("#patientQ");
                            var arrQ = ["pca_diag", "pca_localized", "tx"];
                            if (toSend === "true") {
                                $("#biopsyDateContainer").show();
                                $("#biopsyDate").attr("skipped", "false");
                                arrQ.forEach(function(fieldName) {
                                    $("#patientQ input[name='" + fieldName + "']").attr("skipped", "false");
                                });
                                if (biopsyDate) {
                                    setTimeout(function() {
                                        self.modules.tnthAjax.postClinical(userId, toCall, toSend, "", targetField, {"issuedDate": biopsyDate});
                                    }, 50);
                                } else {
                                    $("#biopsy_day").focus();
                                }
                            } else {
                                $("#biopsyDate").attr("skipped", "true");
                                $("#biopsyDate, #biopsy_day, #biopsy_month, #biopsy_year").val("");
                                $("#biopsyDateError").text("");
                                $("#biopsyDateContainer").hide();
                                arrQ.forEach(function(fieldName) {
                                    var field = $("#patientQ input[name='" + fieldName + "']");
                                    field.prop("checked", false);
                                    field.attr("skipped", "true");
                                });
                                setTimeout(function() {
                                    self.modules.tnthAjax.postClinical(userId, toCall, "false", thisItem.attr("data-status"), targetField);
                                    self.modules.tnthAjax.postClinical(userId, "pca_diag", "false", "", targetField);
                                    self.modules.tnthAjax.postClinical(userId, "pca_localized", "false", "", targetField);
                                    self.modules.tnthAjax.deleteTreatment(userId);
                                }, 50);

                            }
                        });
                        self.__convertToNumericField($("#biopsy_day, #biopsy_year"));
                        $("#biopsy_day, #biopsy_month, #biopsy_year").on("change", function() {
                            var d = $("#biopsy_day"), m = $("#biopsy_month"), y = $("#biopsy_year");
                            var isValid = self.modules.tnthDates.validateDateInputFields(m, d, y, "biopsyDateError");
                            if (isValid) {
                                $("#biopsyDate").val(y.val()+"-"+m.val()+"-"+d.val());
                                $("#biopsyDateError").text("").hide();
                                $("#biopsy_yes").trigger("click");
                            } else {
                                $("#biopsyDate").val("");
                            }
                        });

                        $("#patientQ input[name='tx']").on("click", function() {
                            self.modules.tnthAjax.postTreatment(self.subjectId, (String($(this).val()) === "true"), "", $("#patientQ"));
                        });

                        $("#patientQ input[name='pca_localized']").on("click", function() {
                            var o = $(this);
                            setTimeout(function() {
                                self.modules.tnthAjax.postClinical(self.subjectId, o.attr("name"), o.val(), o.attr("data-status"), $("#patientQ"));
                            }, 50);
                        });

                        $("#patientQ input[name='pca_diag']").on("click", function() {
                            var toSend = String($(this).val()), userId = self.subjectId, o = $(this), targetField = $("#patientQ");
                            setTimeout(function() {
                                self.modules.tnthAjax.postClinical(userId, o.attr("name"), toSend, o.attr("data-status"), targetField);
                            }, 50);
                            if (toSend !== "true") {
                                ["pca_localized", "tx"].forEach(function(fieldName) {
                                    var field = $("#patientQ input[name='" + fieldName + "']");
                                    field.prop("checked", false);
                                    field.attr("skipped", "true");
                                });
                                setTimeout(function() {
                                    self.modules.tnthAjax.postClinical(userId, "pca_localized", "false", "", targetField);
                                    self.modules.tnthAjax.deleteTreatment(userId);
                                }, 50);
                            }
                        });
                    });
                });
            },
            manualEntryModalVis: function(hide) {
                if (hide) {
                    this.manualEntry.loading = true;
                } else {
                    this.manualEntry.loading = false;
                }
            },
            continueToAssessment: function(method, completionDate, assessment_url) {
                if (!assessment_url) {
                    this.manualEntry.errorMessage = i18next.t("The user does not have a valid assessment link.");
                    return false;
                }
                var self = this, still_needed = false, subjectId = this.subjectId;
                this.modules.tnthAjax.getStillNeededCoreData(subjectId, true, function(data) {
                    still_needed = data && data.still_needed && data.still_needed.length;
                }, method);
                if (/\?/.test(assessment_url)) { //passing additional query params
                    assessment_url += "&entry_method=" + method;
                } else {
                    assessment_url += "?entry_method=" + method;
                }
                if (method === "paper") {
                    assessment_url += "&authored=" + completionDate;
                }
                var winLocation = assessment_url;
                if (still_needed) {
                    winLocation = "/website-consent-script/" + $("#manualEntrySubjectId").val() + "?entry_method=" + method + "&subject_id=" + $("#manualEntrySubjectId").val() +
                    "&redirect_url=" + encodeURIComponent(assessment_url);
                }
                this.manualEntryModalVis(true);
                window.location = winLocation;
                setTimeout(function(callback) {
                    callback = callback || function() {};
                    if (callback) { callback(); }
                }, 1000, self.manualEntryModalVis);
            },
            initCustomPatientDetailSection: function() {
                var subjectId = this.subjectId, self = this;
                $(window).on("beforeunload", function() { //fix for safari
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
                    self.modules.tnthAjax.getConsent(subjectId, {sync: true}, function(data) { //get consent date
                        var dataArray = [];
                        if (!data || !data.consent_agreements || data.consent_agreements.length === 0) {
                            return false;
                        }
                        dataArray = data.consent_agreements.sort(function(a, b) {
                            return new Date(b.acceptance_date) - new Date(a.acceptance_date);
                        });
                        var items = $.grep(dataArray, function(item) { //filtered out non-deleted items from all consents
                            return !item.deleted && String(item.status) === "consented";
                        });
                        if (items.length > 0) { //consent date in GMT
                            self.manualEntry.consentDate = items[0].acceptance_date;
                        }
                    });
                    setTimeout(function() { self.manualEntry.initloading = false;}, 10);
                });

                $("input[name='entryMethod']").on("click", function() {
                    self.manualEntry.errorMessage = "";
                    self.manualEntry.method = $(this).val();
                    if ($(this).val() === "interview_assisted") {
                        self.manualEntry.todayObj = self.modules.tnthDates.getTodayDateObj(); //if method is interview assisted, reset completion date to GMT date/time for today
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
                        var td = todayObj.displayDay, tm = todayObj.displayMonth, ty = todayObj.displayYear;
                        var isValid = d.val() !== "" && m.val() !== "" && y.val() !== "" && d.get(0).validity.valid && m.get(0).validity.valid && y.get(0).validity.valid;
                        if (!isValid) {
                            $("#meSubmit").attr("disabled", true);
                        }
                        if (isValid) {
                            var errorMsg = tnthDates.dateValidator(d.val(), m.val(), y.val());
                            var consentDate = $("#manualEntryConsentDate").val();
                            var pad = function(n) { n = parseInt(n); return (n < 10) ? "0" + n : n; };
                            if (errorMsg || !consentDate) {
                                self.manualEntry.errorMessage = i18next.t("All date fields are required");
                                return false;
                            }

                            //check if date entered is today, if so use today's date/time
                            if (td + tm + ty === (pad(d.val()) + pad(m.val()) + pad(y.val()))) {
                                self.manualEntry.completionDate = todayObj.gmtDate;
                            } else {
                                var gmtDateObj = tnthDates.getDateObj(y.val(), m.val(), d.val(), 12, 0, 0);
                                self.manualEntry.completionDate = self.modules.tnthDates.getDateWithTimeZone(gmtDateObj);
                            }
                            //all date/time should be in GMT date/time
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
                            self.manualEntry.errorMessage = errorMsg;
                        }
                    });
                });
                $(document).delegate("#meSubmit", "click", function() {
                    var method = String(self.manualEntry.method), completionDate = $("#qCompletionDate").val();
                    var linkUrl = "/api/present-needed?subject_id=" + $("#manualEntrySubjectId").val();
                    if (method === "") { return false; }
                    if (method !== "paper") {
                        self.continueToAssessment(method, completionDate, linkUrl);
                        return false;
                    }
                    self.manualEntryModalVis(true);
                    self.modules.tnthAjax.getCurrentQB(subjectId, self.modules.tnthDates.formatDateString(completionDate, "iso-short"), null, function(data) {
                        if (data.error) {
                            return false;
                        }
                        //check questionnaire time windows
                        if (!(data.questionnaire_bank && Object.keys(data.questionnaire_bank).length > 0)) {
                            self.manualEntry.errorMessage = i18next.t("Invalid completion date. Date of completion is outside the days allowed.");
                            self.manualEntryModalVis();
                        } else {
                            self.manualEntry.errorMessage = "";
                            self.continueToAssessment(method, completionDate, linkUrl);
                        }
                    });
                });

                self.modules.tnthAjax.assessmentStatus(subjectId, function(data) {
                    if (!data.error && (data.assessment_status).toUpperCase() === "COMPLETED" &&
                        parseInt(data.outstanding_indefinite_work) === 0) {
                        $("#assessmentLink").attr("disabled", true);
                        $("#enterManualInfoContainer").text(i18next.t("All available questionnaires have been completed."));
                    }
                });
            },
            updateRolesData: function(event) {
                var roles = $("#rolesGroup input:checkbox:checked").map(function() {
                    return {name: $(this).val()};
                }).get();
                this.modules.tnthAjax.putRoles(this.subjectId, {"roles": roles}, $(event.target));
            },
            initUserRoles: function(params) {
                if (!this.subjectId) { return false; }
                var self = this;
                this.modules.tnthAjax.getRoles(this.subjectId, function(data) {
                    if (data.roles) {
                        self.userRoles = data.roles.map(function(role) {
                            return role.name;
                        });
                    }
                }, params);
            },
            initRolesListSection: function() {
                var self = this;
                this.modules.tnthAjax.getRoleList({useWorker:true}, function(data) {
                    if (!data.roles) { return false; }
                    self.roles.data = data.roles;
                });
                self.initUserRoles();
            },
            initAuditLogSection: function() {
                var self = this;
                this.modules.tnthAjax.auditLog(this.subjectId, {useWorker:true}, function(data) {
                    if (data.error) {
                        $("#profileAuditLogErrorMessage").text(i18next.t("Problem retrieving audit log from server."));
                        return false;
                    }
                    if (!data.audits || data.audits.length === 0) {
                        $("#profileAuditLogErrorMessage").text(i18next.t("No audit log item found."));
                        return false;
                    }
                    var ww = $(window).width(), fData = [], len = ((ww < 650) ? 20 : (ww < 800 ? 40 : 80));
                    (data.audits).forEach(function(item) {
                        item.by = item.by.reference || "-";
                        var r = /\d+/g;
                        var m = r.exec(String(item.by));
                        if (m) {
                            item.by = m[0];
                        }
                        item.lastUpdated = self.modules.tnthDates.formatDateString(item.lastUpdated, "iso");
                        item.comment = item.comment ? self.escapeHtml(item.comment) : "";
                        var c = String(item.comment);
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
                    $("#profileAuditLogTable").bootstrapTable(self.setBootstrapTableConfig({
                        data: fData,
                        classes: "table table-responsive profile-audit-log",
                        sortName: "lastUpdated",
                        sortOrder: "desc",
                        toolbar: "#auditTableToolBar",
                        columns: [{field: "by", title: i18next.t("User"), width: "5%", sortable: true, searchable: true},
                            {field: "comment", title: i18next.t("Comment"), searchable: true, sortable: true},
                            {field: "lastUpdated", title: i18next.t("Date/Time <span class='gmt'>{gmt}</span>").replace("{gmt}", "(GMT), Y-M-D"), sortable: true, searchable: true, width: "20%"},
                            {field: "version", title: i18next.t("Version"), sortable: true, visible: false}]
                    }));
                });
            },
            getConsentHeaderRow: function(header) {
                var content = "", h = header || this.consent.consentHeaderArray;
                h.forEach(function(title) {
                    if (String(title) !== "n/a") {
                        content += "<TH class='consentlist-header'>" + title + "</TH>";
                    }
                });
                return content;
            },
            getConsentRow: function(item) {
                if (!item) {return false;}
                var self = this, consentStatus = self.getConsentStatus(item), sDisplay = self.getConsentStatusHTMLObj(item).statusHTML;
                var isDisabled = this.isDisableField("consent_status");
                var LROrgId = item.organization_id;
                var topOrgID = (self.getOrgTool()).getTopLevelParentOrg(LROrgId);
                if (topOrgID && (String(topOrgID) !== String(LROrgId))) {
                    LROrgId = topOrgID;
                }
                var editorUrlEl = $("#" + LROrgId + "_editor_url"), cflag = this.getConsentStatusHTMLObj(item).statusText;
                var contentArray = [{
                    content: self.getConsentOrgDisplayName(item)
                }, {
                    content: sDisplay + (!isDisabled && self.isConsentEditable() && String(consentStatus) === "active" ? '&nbsp;&nbsp;<a data-toggle="modal" data-target="#profileConsentListModal" data-orgId="' + item.organization_id + '" data-agreementUrl="' + String(item.agreement_url).trim() + '" data-userId="' + self.subjectId + '" data-status="' + cflag + '"><span class="glyphicon glyphicon-pencil" aria-hidden="true" style="cursor:pointer; color: #000"></span></a>' : ""),
                    "_class": "indent"
                }, {
                    content: (function(item) {
                        var s = "<span class='agreement'><a href='" + item.agreement_url + "' target='_blank'><em>View</em></a></span>" +
                                ((editorUrlEl.length > 0 && editorUrlEl.val()) ? ("<div class='button--LR' " + (String(editorUrlEl.attr("data-show")) === "true" ? "data-show='true'" : "data-show='false'") + "><a href='" + editorUrlEl.val() + "' target='_blank'>" + i18next.t("Edit in Liferay") + "</a></div>") : "");
                        if (self.isDefaultConsent(item)) {
                            s = i18next.t("Sharing information with clinics ") + "<span class='agreement'>&nbsp;<a href='" + decodeURIComponent(item.agreement_url) + "' target='_blank'><em>" + i18next.t("View") + "</em></a></span>";
                        }
                        return s;
                    })(item)
                }, {
                    content: self.modules.tnthDates.formatDateString(item.acceptance_date) + (self.isConsentEditable() && self.isTestEnvironment() && String(consentStatus) === "active" ? '&nbsp;&nbsp;<a data-toggle="modal" data-target="#consentDateModal" data-orgId="' + item.organization_id + '" data-agreementUrl="' + String(item.agreement_url).trim() + '" data-userId="' + self.subjectId + '" data-status="' + cflag + '" data-signed-date="' + self.modules.tnthDates.formatDateString(item.acceptance_date, "d M y hh:mm:ss") + '"><span class="glyphicon glyphicon-pencil" aria-hidden="true" style="cursor:pointer; color: #000"></span></a>' : "")
                }];
                this.consent.consentDisplayRows.push(contentArray);
            },
            getConsentHistoryRow: function(item) {
                var self = this, sDisplay = self.getConsentStatusHTMLObj(item).statusHTML;
                var content = "<tr " + (item.deleted?"class='history'":"") + ">";
                var contentArray = [{
                    content: self.getConsentOrgDisplayName(item) + "<div class='smaller-text text-muted'>" + this.orgTool.getOrgName(item.organization_id) + "</div>"
                }, {
                    content: sDisplay
                }, {
                    content: self.modules.tnthDates.formatDateString(item.acceptance_date)

                },
                {
                    content: "<span class='text-danger'>" + (self.getRecordedDisplayDate(item)||"<span class='text-muted'>--</span>") + "</span>"
                }, {
                    content: (item.recorded && item.recorded.by && item.recorded.by.display ? item.recorded.by.display : "<span class='text-muted'>--</span>")
                }];

                contentArray.forEach(function(cell) {
                    content += "<td class='consentlist-cell'>" + cell.content + "</td>";
                });
                content += "</tr>";
                return content;
            },
            getConsentOrgDisplayName: function(item) {
                if (!item) {return "";}
                var orgId = item.organization_id, OT = this.getOrgTool(), currentOrg = OT.orgsList[orgId], orgName = currentOrg ? currentOrg.name : item.organization_id;
                if (!this.isConsentWithTopLevelOrg()) {
                    var topOrgID = OT.getTopLevelParentOrg(orgId), topOrg = OT.orgsList[topOrgID];
                    if (topOrg && topOrg.name) {
                        orgName = topOrg.name;
                    }
                }
                return orgName;
            },
            getConsentStatus: function(item) {
                item = item || {};
                if (item.deleted || String(item.status) === "deleted") { return "deleted"; }
                if (item.expired && this.modules.tnthDates.getDateDiff(String(item.expires)) > 0) {
                    return "expired";
                }
                return "active";
            },
            getRecordedDisplayDate: function(item) {
                if (!item) {return "";}
                var recordedDate = item.recorded? item.recorded.lastUpdated : "";
                return this.modules.tnthDates.formatDateString(recordedDate, "yyyy-mm-dd hh:mm:ss");
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
                    "deleted": "<span class='text-danger small-text'>" + consentLabels.deleted + "</span>",
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
                    if (String(item.status) === "deleted") {
                        sDisplay += "<span class='text-danger'> (</span>" + oDisplayText.deleted + "<span class='text-danger'>)</span>";
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
                        } else {
                            sDisplay = oDisplayText.consented;
                        }
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
                    var i18next = self.modules.i18next;
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
                                if (["subject website consent", "website terms of use"].indexOf(String(fType)) !== -1) {
                                    item.name = (org && org.name ? i18next.t(org.name) : "--");
                                    item.truenth_name = i18next.t("TrueNTH USA");
                                    item.accepted = self.modules.tnthDates.formatDateString(item.accepted); //format to accepted format D m y
                                    item.display_type = capitalize($.trim((item.type).toLowerCase().replace("subject", ""))); //for displaying consent type, note: this will remove text 'subject' from being displayed
                                    item.eproms_agreement_text = String(i18next.t("Agreed to {documentType}")).replace("{documentType}", capitalize(item.display_type));
                                    item.truenth_agreement_text = i18next.t("Agreed to terms");
                                    item.eproms_url_text = i18next.t(item.display_type);
                                    item.truenth_url_text = (String(i18next.t("{projectName} Terms of Use")).replace("{projectName}", "TrueNTH USA"));
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
                        $(this).attr({ "data-agreementUrl": agreementUrl, "data-userId": userId, "data-orgId": orgId});
                        if (String($(this).val()) === String(status)) {
                            $(this).prop("checked", true);
                        }
                    });
                    if (__self.isAdmin()) {
                        $(this).find(".admin-radio").show();
                    }
                });
                $("#profileConsentListModal input[class='radio_consent_input']").each(function() {
                    $(this).off("click").on("click", function() { //remove pre-existing events as when consent list is re-drawn
                        var o = __self.CONSENT_ENUM[$(this).val()];
                        __self.consent.saveLoading = true;
                        if (o) {
                            o.org = $(this).attr("data-orgId");
                            o.agreementUrl = $(this).attr("data-agreementUrl");
                        }
                        if (String($(this).val()) === "purged") {
                            __self.modules.tnthAjax.deleteConsent($(this).attr("data-userId"), {
                                org: $(this).attr("data-orgId")
                            });
                            __self.consent.saveLoading = false;
                            __self.reloadConsentList($(this).attr("data-userId"));
                        } else if (String($(this).val()) === "suspended") {
                            var modalElement = $("#profileConsentListModal"), self = $(this);
                            __self.modules.tnthAjax.withdrawConsent($(this).attr("data-userId"), $(this).attr("data-orgId"), null, function(data) {
                                modalElement.removeClass("fade").modal("hide");
                                __self.consent.saveLoading = false;
                                __self.reloadConsentList(self.attr("data-userId"));
                            });
                        } else {
                            var self = $(this);
                            __self.modules.tnthAjax.setConsent($(this).attr("data-userId"), o, $(this).val(), false, function(data) {
                                $("#profileConsentListModal").removeClass("fade").modal("hide");
                                __self.consent.saveLoading = false;
                                __self.reloadConsentList(self.attr("data-userId"));
                            });

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
                        var isValid = __self.modules.tnthDates.isValidDefaultDateFormat(d.val());
                        if (d.val() && !isValid) {
                            errorMessage += (errorMessage ? "<br/>" : "") + i18next.t("Date must in the valid format.");
                            d.datepicker("hide");
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
                        $("#consentDateModalError").html(errorMessage);
                    });
                });

                $("#consentDateModal .btn-submit").on("click", function() {
                    var ct = $("#consentDateModal_date"), o = __self.CONSENT_ENUM[ct.attr("data-status")];
                    if (!ct.val()) {
                        $("#consentDateModalError").text(i18next.t("You must enter a date/time"));
                        return false;
                    }
                    var h = $("#consentDateModal_hour").val()||"00",m = $("#consentDateModal_minute").val()||"00",s = $("#consentDateModal_second").val()||"00";
                    var dt = new Date(ct.val()); //2017-07-06T22:04:50 format
                    var cDate = dt.getFullYear()+"-"+(dt.getMonth() + 1)+"-"+dt.getDate()+"T"+pad(h)+":"+pad(m)+":"+pad(s);
                    o.org = ct.attr("data-orgId");
                    o.agreementUrl = ct.attr("data-agreementUrl");
                    o.acceptance_date = cDate;
                    o.testPatient = true;
                    setTimeout((function() { $("#consentDateContainer").hide();})(), 200);
                    setTimeout((function() {$("#consentDateLoader").show();})(), 450);
                    $("#consentDateModal button[data-dismiss]").attr("disabled", true); //disable close buttons while processing reques
                    setTimeout(__self.modules.tnthAjax.setConsent(ct.attr("data-userId"), o, ct.attr("data-status"), true, function(data) {
                        if (!data || data.error) {
                            $("#consentDateModalError").text(i18next.t("Error processing data.  Make sure the date is in the correct format."));
                            setTimeout(function() {
                                $("#consentDateContainer").show();
                                $("#consentDateLoader").hide();
                            }, 450);
                            $("#consentDateModal button[data-dismiss]").attr("disabled", false);
                            return false;
                        }
                        $("#consentDateModal").removeClass("fade").modal("hide");
                        __self.reloadConsentList(ct.attr("data-userId"));
                    }), 100);
                });
            },
            showConsentHistory: function() {
               return !this.consent.consentLoading && this.isConsentEditable() && this.hasConsentHistory();
            },
            hasConsentHistory: function() {
                return this.consent.historyItems.length > 0;
            },
            hasCurrentConsent: function() {
                return this.consent.currentItems.length > 0;
            },
            getConsentHistory: function(options) {
                if (!options) {options = {};}
                var self = this, content = "";
                content = "<div id='consentHistoryWrapper'><table id='consentHistoryTable' class='table-bordered table-condensed table-responsive' style='width: 100%; max-width:100%'>";
                content += this.getConsentHeaderRow(this.consent.consentHistoryHeaderArray);
                var items = this.consent.historyItems.sort(function(a, b) { //sort items by last updated date in descending order
                    return new Date(b.deleted.lastUpdated) - new Date(a.deleted.lastUpdated);
                });
                items = (this.consent.currentItems).concat(this.consent.historyItems); //combine both current and history items and display current items first;
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
                        self.modules.tnthAjax.getConsent(userId || self.subjectId, {sync: true}, function(data) {
                            self.getConsentList(data);
                        });
                    }, 1500);
                });
            },
            getConsentList: function(data) {
                if (!data) { return false; }
                if (data.error) {
                    this.consent.consentListErrorMessage = i18next.t("Error occurred retrieving consent list content.");
                    this.consent.consentLoading = false;
                    return false;
                }
                this.getTerms(); //get terms of use if any
                var self = this, dataArray = [];
                if (data.consent_agreements && (data.consent_agreements).length > 0) {
                    dataArray = data.consent_agreements;
                }
                this.consent.consentItems = dataArray;
                this.consent.consentDisplayRows = [];
                if (this.consent.consentItems.length === 0) {
                    clearInterval(self.consentListReadyIntervalId);
                    $("#consentListTable").animate({opacity: 1});
                    this.consent.consentLoading = false;
                    return false;
                }

                var existingOrgs = {};
                this.consent.currentItems = $.grep(this.consent.consentItems, function(item) {
                    return self.getConsentStatus(item) === "active";
                });
                this.consent.historyItems = $.grep(this.consent.consentItems, function(item) { //iltered out deleted items from all consents
                    return self.getConsentStatus(item) !== "active";
                });
                this.consent.currentItems.forEach(function(item, index) {
                    if (!(existingOrgs[item.organization_id]) && !(/null/.test(item.agreement_url))) {
                        self.getConsentRow(item, index);
                        existingOrgs[item.organization_id] = true;
                    }
                });
                this.consentListReadyIntervalId = setInterval(function() {
                    if ($("#consentListTable .consentlist-cell").length > 0) {
                        $("#consentListTable .button--LR[show='true']").addClass("show");
                        $("#consentListTable tbody tr").each(function(index) {
                            $(this).addClass(index % 2 !== 0 ? "even" : "odd");
                        });
                        if (!self.isConsentWithTopLevelOrg()) {
                            $("#consentListTable .agreement").each(function() { $(this).parent().hide(); });
                        }
                        if (self.isConsentEditable()) {
                            self.initConsentItemEvent();
                        }
                        if (self.isConsentEditable() && self.isTestEnvironment()) {
                            self.initConsentDateEvents();
                        }
                        $("#consentListTable").animate({opacity: 1}, 1500);
                        clearInterval(self.consentListReadyIntervalId);
                    }
                    if (self.showConsentHistory()) {
                        $("#viewConsentHistoryButton").on("click", function(e) {
                            e.preventDefault();
                            e.stopImmediatePropagation()
                            self.getConsentHistory();
                        });
                        setTimeout(function() {
                            $("#viewConsentHistoryButton").removeClass("tnth-hide");
                        }, 550);
                    }
                }, 50);
                this.consent.consentLoading = false;
            },
            __convertToNumericField: function(field) {
                if (field && ("ontouchstart" in window || (typeof(window.DocumentTouch) !== "undefined" && document instanceof window.DocumentTouch))) {
                    field.each(function() {$(this).prop("type", "tel");});
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

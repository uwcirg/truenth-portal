import tnthAjax from "./modules/TnthAjax.js";
import tnthDates from "./modules/TnthDate.js";
import OrgTool from "./modules/OrgTool.js";
import SYSTEM_IDENTIFIER_ENUM from "./modules/SYSTEM_IDENTIFIER_ENUM.js";
import ProcApp from "./modules/Procedures.js";
import Utility from "./modules/Utility.js";
import ClinicalQuestions from "./modules/ClinicalQuestions.js";
import Consent from "./modules/Consent.js";
import {sortArrayByField} from "./modules/Utility.js";
import {
    EPROMS_SUBSTUDY_ID,
    EPROMS_SUBSTUDY_TITLE,
    EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER,
    EPROMS_SUBSTUDY_SHORT_TITLE,
    EMPRO_POST_TX_QUESTIONNAIRE_IDENTIFIER,
    EMPRO_TRIGGER_UNPROCCESSED_STATES
} from "./data/common/consts.js";

/*
 * helper Object for initializing profile sections  TODO streamline this more
 */
export default (function() {
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
            Utility.VueErrorHandling(); /*global Utility VueErrorHandling */
            this.registerDependencies();
            this.getOrgTool();
            this.setUserSettings();
            this.setSubjectResearchStudies();
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
            subjectOrgs: [],
            subjectReseachStudies: [],
            subjectResearchStudyStatuses: {},
            userRoles: [],
            PIList: [],
            selectedClinicians: [],
            staffEditableRoles: ["clinician", "primary_investigator", "staff", "staff_admin"],
            userEmailReady: true,
            messages: {
                userEmailReadyMessage: "",
                userInviteEmailInfoMessage: "",
                userInviteEmailErrorMessage: "",
            },
            mode: "profile",
            demo: { //skeleton
                data: { resourceType:"Patient", email: "", name: {given: "",family: ""}, birthDay: "",birthMonth: "",birthYear: "", clinician: {}}
            },
            stateDict: {AL: i18next.t("Alabama"),AK: i18next.t("Alaska"), AS: i18next.t("American Samoa"),AZ: i18next.t("Arizona"),AR:i18next.t("Arkansas"),CA: i18next.t("California"),CO:i18next.t("Colorado"),CT:i18next.t("Connecticut"),DE:i18next.t("Delaware"),DC:i18next.t("District Of Columbia"),FM: i18next.t("Federated States Of Micronesia"),FL:i18next.t("Florida"),GA:i18next.t("Georgia"),GU:i18next.t("Guam"),HI:i18next.t("Hawaii"),ID:i18next.t("Idaho"),IL:i18next.t("Illinois"),IN:i18next.t("Indiana"),IA:i18next.t("Iowa"),KS:i18next.t("Kansas"),KY:i18next.t("Kentucky"),LA:i18next.t("Louisiana"),ME:i18next.t("Maine"),MH:i18next.t("Marshall Islands"),MD:i18next.t("Maryland"),MA:i18next.t("Massachusetts"),MI:i18next.t("Michigan"),MN:i18next.t("Minnesota"),MS:i18next.t("Mississippi"),MO:i18next.t("Missouri"),MT:i18next.t("Montana"),NE: i18next.t("Nebraska"),NV:i18next.t("Nevada"),NH:i18next.t("New Hampshire"),NJ:i18next.t("New Jersey"),NM:i18next.t("New Mexico"),NY:i18next.t("New York"),NC:i18next.t("North Carolina"),ND:i18next.t("North Dakota"),MP:i18next.t("Northern Mariana Islands"),OH:i18next.t("Ohio"),OK:i18next.t("Oklahoma"),OR:i18next.t("Oregon"),PW:i18next.t("Palau"),PA:i18next.t("Pennsylvania"),PR:i18next.t("Puerto Rico"),RI:i18next.t("Rhode Island"),SC:i18next.t("South Carolina"),SD:i18next.t("South Dakota"),TN:i18next.t("Tennessee"),TX:i18next.t("Texas"),UT:i18next.t("Utah"),VT:i18next.t("Vermont"),VI:i18next.t("Virgin Islands"),VA:i18next.t("Virginia"),WA:i18next.t("Washington"),WV:i18next.t("West Virginia"),WI:i18next.t("Wisconsin"),WY:i18next.t("Wyoming")},
            roles: {data: []},
            optionalCoreData: [],
            OrgsStateSelectorInitialized: false,
            consent: {
                consentHeaderArray: [ //html for consent header cell in array
                    i18next.t("Organization"),
                    `<span class="eproms-consent-status-header">${i18next.t("Consent Status")}</span><span class="truenth-consent-status-header">${i18next.t("Consent Status")}</span>`,
                    `<span class="agreement">${i18next.t("Agreement")}</span>`,
                    `<span class="eproms-consent-date-header">${i18next.t("Date")}</span><span class="truenth-consent-date-header">${i18next.t("Registration Date")}</span> <span class="gmt">(${i18next.t("GMT")})</span>`
                ],
                consentHistoryHeaderArray: [
                    i18next.t("Organization"),
                    `<span class="eproms-consent-status-header">${i18next.t("Consent Status")}</span><span class="truenth-consent-status-header">${i18next.t("Consent Status")}</span>`,
                    i18next.t("Consent Date"),
                    `${i18next.t("Last Updated")}<br/><span class='smaller-text'>${i18next.t("( GMT, Y-M-D )")}</span>`,
                    i18next.t("User")
                ],
                consentLabels: {
                    "default": i18next.t("Consented"),
                    "consented": i18next.t("Consented / Enrolled"),
                    "withdrawn": `<span data-eproms='true'>${i18next.t("Withdrawn - Suspend Data Collection and Report Historic Data")}</span><span data-truenth='true'>${i18next.t("Suspend Data Collection and Report Historic Data")}</span>`,
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
                errorMessage: null
            },
            patientEmailForm: {
                loading: false
            },
            postTxQuestionnaire: {
                questions: [],
                answers: [],
                loading: true
            },
            /*
             * based on trigger history
             * last triggers state
             */
            subStudyTriggers: {
                domains: [],
                date: "",
                state: "",
                data: {}
            },
            subStudyAssessment: {
                data: []
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
        computed: {
            propManualEntryErrorMessage: {
                set: function(newValue) {
                    this.manualEntry.message = newValue;
                },
                get: function() {
                    return this.manualEntry.message;
                }
            },
            computedIsSubStudyPatient: function() {
                //will re-compute when the dependent prop, this.subjectReseachStudies, updates
                return this.subjectReseachStudies.indexOf(EPROMS_SUBSTUDY_ID) !== -1;
            },
            computedUserEmail: function() {
                //will re-compute when email updates
                return this.demo.data.email;
            },
            computedTreatingClinician: function() {
                return this.demo.data.clinicians && this.demo.data.clinicians.length;
            },
            computedSubStudyTriggers: function() {
                return this.subStudyTriggers.domains;
            },
            computedSubStudyAssessmentData: function() {
                return this.subStudyAssessment.data;
            },
            computedSubStudyPostTxResponses: function() {
                return this.postTxQuestionnaire.answers;
            },
            computedOptionalCoreData: function() {
                return this.optionalCoreData;
            }
        },
        methods: {
            registerDependencies: function() {
                var self = this;
                if (!window.portalModules) {
                    window.portalModules = {};
                }
                window.portalModules.SYSTEM_IDENTIFIER_ENUM = SYSTEM_IDENTIFIER_ENUM;
                window.portalModules.tnthAjax = tnthAjax;
                window.portalModules.tnthDates = tnthDates;
                window.portalModules.orgTool = OrgTool;
                if (typeof i18next !== "undefined") {
                    window.portalModules.i18next = i18next;
                }
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
                var self = this;
                callback = callback || function() {};
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
            getCurrentUserOrgs: function() {
                if (!this.userOrgs || !this.userOrgs.length) {
                    return false;
                }
                return this.userOrgs;
            },
            setCurrentUserOrgs: function(params, callback){
                callback = callback || function() {};
                if (!this.currentUserId) {
                    callback({"error": "Current user id is required."});
                    return;
                }
                if (this.getCurrentUserOrgs()) {
                    callback(this.getCurrentUserOrgs());
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
                    self.userOrgs = orgTool.getOrgsByCareProvider(data.careProvider) || [];
                    var topLevelOrgs = orgTool.getUserTopLevelParentOrgs(self.userOrgs);
                    self.topLevelOrgs = topLevelOrgs.map(function(item) {
                        return orgTool.getOrgName(item);
                    });
                    callback(self.getCurrentUserOrgs());
                });
            },
            userHasNoEmail: function() {
                return !this.computedUserEmail;
            },
            isUserEmailReady: function() {
                return this.userEmailReady;
            },
            setUserEmailReady: function(params, callback) {
                callback = callback || function() {};
                params = params || {};
                if (this.mode !== "profile") { //setting email ready status only applies to profile page
                    callback();
                    return false;
                }
                var self = this;
                this.modules.tnthAjax.getEmailReady(this.subjectId, {data: params}, function(data) {
                    if (data.error) {
                        callback();
                        return false;
                    }
                    /*
                     * check for the presence of ignore_preference in parameters
                     */
                    if (params.ignore_preference) {
                        /*
                         * this will allow manual enabling of capacity to send email to user
                         */
                        callback(data);
                        return;
                    }
                    self.userEmailReady = data.ready;
                    self.messages.userEmailReadyMessage = data.reason || "";
                    callback(data);
                });
            },
            isDisableField: function(fieldId="") {
                return this.disableFields.indexOf(fieldId) !== -1;
            },
            handleMedidataRaveFields: function(params) {
                if (!this.settings.PROTECTED_FIELDS || !this.settings.PROTECTED_ORG) { //expected config example: PROTECTED_FIELDS = ['deceased', 'study_id', 'consent_status', 'dob', 'org'] and PROTECTED_ORG = 'IRONMAN'
                    return false;
                }
                var self = this;
                this.setCurrentUserOrgs(params, function() {
                    if (self.topLevelOrgs.indexOf(self.settings.PROTECTED_ORG) === -1) {
                        return false;
                    }
                    $.merge(self.disableFields, self.settings.PROTECTED_FIELDS);
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
            setDisableFields: function(params) {
                if (!this.currentUserId || this.isAdmin() || !this.isSubjectPatient()) {
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
                            m = self.pad(deceasedDateObj.getUTCMonth()+1);
                            d = deceasedDateObj.getUTCDate();
                            y = deceasedDateObj.getUTCFullYear();
                            deceasedDateObj = new Date(deceasedDateObj.toUTCString().slice(0, -4));
                            displayDeceasedDate = deceasedDateObj.toLocaleDateString("en-GB", { //use native date function
                                day: "numeric",
                                month: "short",
                                year: "numeric"
                            });
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
                        if (data.careProvider && data.careProvider.length) {
                            let clone = [...data.careProvider];
                            let clinicianFilteredSet = clone.filter(item => {
                                return item.reference.match(/^api\/clinician/gi);
                            });
                            self.demo.data.clinicians = clinicianFilteredSet.length? clinicianFilteredSet : [];
                            self.selectedClinicians = self.demo.data.clinicians;
                            self.subjectOrgs = self.getOrgTool().getOrgsByCareProvider(data.careProvider);
                        } else {
                            self.demo.data.clinicians = [];
                            self.subjectOrgs = [];
                        }
                    }
                    callback(data);
                });
            },
            setUserSettings: function() {
                if ($("#profileForm").length > 0) {
                    this.subjectId = document.querySelector("#profileUserId").value;
                    this.currentUserId = document.querySelector("#profileCurrentUserId").value;
                    this.mode = "profile";
                }
                if ($("#aboutForm").length > 0) {
                    this.subjectId = document.querySelector("#iq_userId").value;
                    this.currentUserId = document.querySelector("#iq_userId").value;
                    this.mode = "initialQueries";
                }
                var acoContainer = document.querySelector("#accountCreationContentContainer");
                if (acoContainer) {
                    this.currentUserId = document.querySelector("#currentStaffUserId").value;
                    this.mode = acoContainer.getAttribute("data-account") === "patient" ? "createPatientAccount": "createUserAccount";
                }
            },
            setSubjectResearchStudies: function() {
                let roleType = this.isSubjectPatient() ? "patient": "staff";
                this.modules.tnthAjax.getUserResearchStudies(this.subjectId, roleType, "", data => {
                    if (data) {
                        this.subjectResearchStudyStatuses = data;
                        this.subjectReseachStudies = Object.keys(data).map(item => parseInt(item));
                    }
                });
            },
            getOrgTool: function(callback) {
                callback = callback || function() {};
                if (!this.orgTool) {
                    var self = this;
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
                var isStaff = this.isStaff();
                var isCurrentUserPatient = this.currentUserRoles.indexOf("patient") !== -1;
                var isEditableByStaff = this.settings.hasOwnProperty("CONSENT_EDIT_PERMISSIBLE_ROLES") && this.settings.CONSENT_EDIT_PERMISSIBLE_ROLES.indexOf("staff") !== -1;
                var isEditableByPatient = this.settings.hasOwnProperty("CONSENT_EDIT_PERMISSIBLE_ROLES") && this.settings.CONSENT_EDIT_PERMISSIBLE_ROLES.indexOf("patient") !== -1;
                return !this.isDisableField("consent_status") && ((isStaff && isEditableByStaff) || (isCurrentUserPatient && isEditableByPatient));
            },
            isTestEnvironment: function() {
                return String(this.settings.SYSTEM_TYPE).toLowerCase() !== "production";
            },
            isAdmin: function() {
                return this.currentUserRoles.indexOf("admin") !== -1;
            },
            isSubjectPatient: function() {
                if (this.mode === "createPatientAccount" || $("#profileMainContent").hasClass("patient-view")) {
                    return true;
                }
                if (this.userRoles.length === 0) { //this is a blocking call if not cached, so avoid it if possible
                    this.initUserRoles({sync:true});
                }
                return this.userRoles.indexOf("patient") !== -1;
            },
            hasSubStudySubjectOrgs: function() {
                var orgTool = this.getOrgTool();
                //check via organization API
                return this.subjectOrgs.filter(orgId => {
                    return  orgTool.isSubStudyOrg(orgId);
                }).length;
            },
            /*
             * subject is ready to take EMPRO assessment
             */
            isSubStudyReadyPatient: function() {
                return this.isSubStudyPatient() && this.getResearchStudyStatus(EPROMS_SUBSTUDY_ID)["ready"];
            },
            isSubStudyPatient: function() {
                return this.computedIsSubStudyPatient;
            },
            hasSubStudyStatusErrors: function() {
                return this.hasResearchStudyStatusErrors(EPROMS_SUBSTUDY_ID);
            },
            getSubStudyStatusErrors: function() {
                return this.getResearchStudyStatusErrors(EPROMS_SUBSTUDY_ID);
            },
            getResearchStudyStatus: function(studyId) {
                return this.subjectResearchStudyStatuses[studyId];
            },
            /*
             * return any error associated with a research study status, e.g. patient withdrew
             */
            hasResearchStudyStatusErrors: function(studyId) {
                return this.subjectResearchStudyStatuses[studyId] &&
                this.subjectResearchStudyStatuses[studyId]["errors"].length;
            },
            getResearchStudyStatusErrors: function(studyId) {
                if (!this.hasResearchStudyStatusErrors(studyId)) {
                    return "";
                }
                return this.subjectResearchStudyStatuses[studyId]["errors"].join(", ");
            },
            isStaffAdmin: function() {
                return this.currentUserRoles.indexOf("staff_admin") !== -1;
            },
            isStaff: function() {
                return this.currentUserRoles.indexOf("staff") !== -1 ||  this.isStaffAdmin();
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
                    document.querySelector("#mainDiv").classList.add("profile");
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
                        setTimeout(function() {
                            self.clearSectionLoaders(); //clear section loaders after ajax calls completed, note this will account for failed/cancelled requests as well
                        }, 150);
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
                $("#loginAsButton, #btnLoginAs").removeClass("disabled").attr("disabled", false);
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
                            self.disableInputTextFields();
                            return;
                        }
                        /*  
                         * enable input text field when in edit view
                         */
                        self.enableInputTextField(container.find("input[type='text']"));
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
                        triggerEvent = triggerEvent + " change";
                        if ($(this).attr("type") === "text") {
                            $(this).attr("data-lpignore", true); //prevent lasspass icon be drawn inside of input field
                            $(this).on("keypress", function(e) {
                                e.stopPropagation();
                                if (e.keyCode === 13) { //account for hitting enter key when updating text field
                                    $(this).trigger(triggerEvent);
                                    return false;
                                }
                            });
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
            enableInputTextField: function(fields) {
                if (!fields) {
                    return false;
                }
                let self = this;
                fields.each(function() {
                    //do not enable fields that are designated to be disabled (e.g. protected fields as those from MedidataRave)
                    if (self.isDisableField($(this).attr("data-protected-fieldid"))) {
                        return true;
                    }
                    $(this).attr("disabled", false);
                });
            },
            disableInputTextFields: function(fields) {
                if (!fields) {
                    return false;
                }
                fields.each(function() {
                    /*
                     *  will not disable input field if marked as exempt from disabling
                     */
                    if (!$(this).attr("data-exempt-from-disabling")) {
                        $(this).attr("disabled", true);
                    }
                });
            },
            initSections: function(callback) {
                var self = this, sectionsInitialized = {}, initCount = 0;
                $("#mainDiv [data-profile-section-id]").each(function() {
                    var sectionId = $(this).attr("data-profile-section-id");
                    if (!sectionsInitialized[sectionId]) {
                        /*
                         * disabling input text fields within each section
                         */
                        self.disableInputTextFields($(this).find("input[type='text']"));
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
            setOptionalCoreData: function(data) {
                this.optionalCoreData = data;
            },
            hasOptionalCoreData: function() {
                return this.computedOptionalCoreData.length;
            },
            handleOptionalCoreData: function() {
                var targetSection = $("#profileDetailContainer"), self = this;
                if (targetSection.length > 0) {
                    var loadingElement = targetSection.find(".profile-item-loader");
                    loadingElement.show();
                    this.modules.tnthAjax.getOptionalCoreData(self.subjectId, {useWorker: true, cache: true}, function(data) { //cache this request as change is rare if ever for optional data
                        if (!data || !data.optional || !data.optional.length) {
                            return;
                        }
                        self.setOptionalCoreData(data.optional);
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
                case "identifier":
                    this.initIdentifierSection();
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
                case "treatingclinician":
                    this.initTreatingClinicianSection();
                    break;
                case "longitudinalreport":
                        this.initLongitudinalReportSection();
                        break;
                case "posttxquestionnaire":
                        this.initPostTxQuestionnaireSection();
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
                case "procedure":
                    this.initProcedureSection();
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
                    let field = $("#" + fn);
                    let y = $("#year"), m = $("#month"),d = $("#date");
                    field.on("keyup focusout", function() {
                        var isValid = self.modules.tnthDates.validateDateInputFields(m.val(), d.val(), y.val(), "errorbirthday");
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
                $("#email").on("keyup", function(e) {
                    e.stopPropagation();
                    $("#erroremail").html("");
                });
            
                $("#profileForm").on("change postEventUpdate", "#email", function(e) {
                    if (self.updateEmailVis()) { //should only update email if there is no validation error
                        self.postDemoData($(this), self.getTelecomData());
                    }
                });
            },
            updateEmailVis: function() {
                var hasError = $("#emailGroup").hasClass("has-error") || $("#erroremail").text();
                var emailValue = $("#email").val();
                if (!hasError) {
                    this.demo.data.email = emailValue;
                    $("#erroremail").html("");
                    $("#email_view").html("<p>" + (emailValue||i18next.t("not provided")) + "</p>"); //update email display /*global i18next */
                }
                return !hasError; //return appropriate indication that value/display has been updated if no error
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
            updateIdentifierData: function(target) {
                this.postDemoData($(target), this.getIdentifierData());
            },
            initIdentifierSection: function() {
                var self = this;
                $("#profileStudyId, #profileSiteId").on("update", function() {
                    self.updateIdentifierData(this);
                });
            },
            hasTreatingClinician: function() {
                return this.computedTreatingClinician;
            },
            isPI: function(reference) {
                if (!reference) return false;
                let referenceValue = this.getReferenceValue(reference);
                return this.PIList.filter(item => {
                    return item.identifier[0].value == referenceValue;
                }).length;
            },
            getReferenceValue: function(reference) {
                if (!reference) return "";
                return reference.split("/")[2];
            },
            getSelectedCliniciansDisplays: function() {
                if (!this.demo.data.clinicians || ! this.demo.data.clinicians.length) {
                    return "";
                }
                return this.demo.data.clinicians.map(item => {
                    return item.display;
                }).join(", ");
            },
            addClinician: function() {
                let selectedOption = $("#clinicianSelector option:selected");
                if (!selectedOption.length) return;
                let reference = `api/clinician/${selectedOption.val()}`;
                let exist = this.selectedClinicians.filter(item => {
                    return item.reference === reference;
                });
                if (exist.length) return;
                this.selectedClinicians.push({
                    "display": selectedOption.text(),
                    "reference": reference
                });
            },
            removeClinicianEvent: function(event) {
                event.stopPropagation();
                if (this.selectedClinicians.length === 1) {
                    $("#treatingClinicianContainer .select-list-error").text("You must add a clinician before removing the last.");
                    return;
                }
                let targetValue = $(event.target).closest(".clinician-item").attr("dataValue");
                if (!targetValue) return;
                this.removeClinicians(targetValue);
            },
            removeClinicians: function(targetValue) {
                if (!targetValue) return;
                let targetIndex = -1;
                this.selectedClinicians.forEach((item, index) => {
                    if (item.reference == targetValue) {
                        targetIndex = index;
                    }
                });
                if (targetIndex !== -1) {
                    $("#treatingClinicianContainer .select-list-error").text("");
                    this.selectedClinicians.splice(targetIndex, 1);
                    this.updateClinicians();
                }
            },
            updateClinicians: function() {
                if (!this.selectedClinicians || !this.selectedClinicians.length) {
                    return;
                }
                let postData = {"careProvider": []};
                if (this.demo.data.careProvider && this.demo.data.careProvider.length) {
                    postData.careProvider = [...this.demo.data.careProvider];
                    /*
                        * exclude pre-existing clinician reference
                        */
                    let filteredSet = (postData.careProvider).filter(item => {
                        return !item.reference.match(/^api\/clinician/gi);
                    });
                    postData.careProvider = filteredSet;
                }
                postData.careProvider = [...postData.careProvider, ...this.selectedClinicians];
                this.postDemoData($("#treatingClinicianContainer"), postData, () => {
                    /* reset selector value */
                    $("#clinicianSelector").val("");
                    /*
                        * set research study status after clinician is set
                        */
                    this.setSubjectResearchStudies();
                });
            },
            getPIIndicatorText: function() {
                return i18next.t("principal investigator");
            },
            initTreatingClinicianSection: function() {
                let self = this;
                this.modules.tnthAjax.getCliniciansList(this.subjectOrgs, function(data) {
                    if (!data || !data.entry || !data.entry.length) {
                        let errorMessage = i18next.t("No treating clinician available for this site");
                        $("#treatingClinicianContainer .select-list-error").text(errorMessage);
                        return;
                    }
                    let selectListHTML = `<select id="clinicianSelector" class="form-control">;
                                            <option value="">-- ${i18next.t("Add a Clinician")} --</option>`;
                    (data.entry).forEach(item => {
                        let cloneItem = JSON.parse(JSON.stringify(item));
                        let isPI = item.identifier.filter(i => {
                            return i.system == SYSTEM_IDENTIFIER_ENUM["primary_investigator"];
                        }).length;
                        if (isPI) {
                            /* gather a list of PI for use later */
                            self.PIList.push(cloneItem);
                        }
                        selectListHTML += `<option value="${item.identifier[0].value}" ${isPI.length ? "data-pi": ""}>${item.name[0].given} ${item.name[0].family}</option>`
                    });
                    selectListHTML += "</select>";

                    $("#treatingClinicianContainer .select-list").append(selectListHTML);
                    $( "#treatingClinicianContainer" ).delegate( "select", "change", function() {
                        if ($(this).val() === "") {
                            $("#treatingClinicianContainer .select-list-error").text(i18next.t("You must select a clinician"));
                            return false;
                        }
                        $("#treatingClinicianContainer .select-list-error").text("");
                        //add clinician
                        self.addClinician();
                        //update via api
                        self.updateClinicians();
                    });
                });
            },
            setSubStudyAssessmentData: function(data) {
                if (!data || !data.length) return;
                //latest first
                data = (data).sort(function(a, b) {
                    return new Date(b.authored) - new Date(a.authored);
                });
                this.subStudyAssessment.data = data;
            },
            hasSubStudyAsssessmentData: function() {
                return this.subStudyAssessment.data.length;
            },
            getSubStudyAssessmentStatus: function() {
                if (!this.hasSubStudyAsssessmentData()) return "";
                return String(this.subStudyAssessment.data[0].status).toLowerCase();
            },
            isSubStudyAssessmentCompleted: function() {
                return this.getSubStudyAssessmentStatus() === "completed";
            },
            getSubStudyAssessmentStatusDisplay: function() {
                return i18next.t("Last EMPRO questionnaire {status} on:").replace("{status}", this.getSubStudyAssessmentStatus());
            },
            getLastSubStudyAssessmentDate: function() {
                if (!this.subStudyAssessment.data || !this.subStudyAssessment.data.length) return "";
                return this.modules.tnthDates.formatDateString(this.subStudyAssessment.data[0].authored);
            },
            hasSubStudyAsssessmentData: function() {
                return this.computedSubStudyAssessmentData.length;
            },
            initLongitudinalReportSection: function() {
                if (!this.subjectId || !this.isSubStudyPatient()) return;
                let CONTAINER_ID = "longitudinalReportContainer";
                this.modules.tnthAjax.assessmentReport(this.subjectId, EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER,
                    data => {
                        if (!data || !data.entry || !data.entry.length) {
                            $(`#longitudinalReportSection`).hide();
                            return;
                        }
                        this.setSubStudyAssessmentData(data.entry);
                        $(`#${CONTAINER_ID}`).html(`<a href="/patients/${this.subjectId}/longitudinal-report/${EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER}" id="btnLongitudinalReport" class="btn btn-tnth-primary">${i18next.t("View {title} Report").replace("{title}", EPROMS_SUBSTUDY_SHORT_TITLE)}</a>`);
                });
            },
            setSubStudyTriggers: function(callback, params) {
                callback = callback || function() {};
                params = params || {};
                this.modules.tnthAjax.assessmentReport(this.subjectId, EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER,
                    data => {
                        if (!data || !data.entry || !data.entry.length) {
                            //if no assessment data, no need to set triggers
                            callback();
                            return;
                        }
                        this.setSubStudyAssessmentData(data.entry);
                        this.modules.tnthAjax.getTriggersHistory(this.subjectId, params, (data) => {
                            if (!data || !data.length) {
                                callback();
                                return;
                            }
                            let domains = new Array();
                            let lastTriggerItem = null;
                            for (var index = data.length-1; index >= 0; index--) {
                               if (EMPRO_TRIGGER_UNPROCCESSED_STATES.indexOf(String(data[index].state).toLowerCase()) === -1) {
                                    lastTriggerItem = data[index];
                                    break;
                               }
                            }
                            if (!lastTriggerItem || !lastTriggerItem.triggers) {
                                callback();
                                return false;
                            }
                            for (let topic in lastTriggerItem.triggers.domain) {
                                if (!Object.keys(lastTriggerItem.triggers.domain[topic]).length) {
                                    continue;
                                }
                                for (let q in lastTriggerItem.triggers.domain[topic]) {
                                    /*
                                     * HARD triggers ONLY 
                                     */
                                    if (lastTriggerItem.triggers.domain[topic][q] === "hard"
                                        && domains.indexOf(topic) === -1) {
                                        domains.push(topic);
                                    }
                                }
                            }
                            let completedDate = lastTriggerItem.triggers.source && lastTriggerItem.triggers.source.authored ? lastTriggerItem.triggers.source.authored : lastTriggerItem.timestamp;
                            [
                                this.subStudyTriggers.domains,
                                this.subStudyTriggers.date,
                                this.subStudyTriggers.state,
                                this.subStudyTriggers.data
                            ] = [
                                domains,
                                this.modules.tnthDates.formatDateString(completedDate),
                                lastTriggerItem.state,
                                lastTriggerItem.triggers];
                            callback();
                    });
                });
            },
            hasSubStudyTriggers: function() {
                return this.computedSubStudyTriggers.length;
            },
            hasPrevSubStudyPostTx: function() {
                return this.computedSubStudyPostTxResponses.length;
            },
            setPrevPostTxResponses: function(qnrId) {
                if (!qnrId) {
                    return;
                }
                this.modules.tnthAjax.getAssessmentByQNRId(this.subjectId, qnrId, false, (data) => {

                    if (!data.group || !data.group.question) {
                        return;
                    }
                   
                    this.postTxQuestionnaire.answers = data.group.question;
                     (this.postTxQuestionnaire.answers).forEach(item => {
                        let valueCoding = item.answer.filter(answer => {
                            return answer.valueCoding;
                        });
                        let valueString = item.answer.filter(answer => {
                            return answer.valueString;
                        });
                        let valueBoolean = item.answer.filter(answer => {
                            return answer.valueBoolean;
                        });
                        if (valueCoding.length) {
                            valueCoding.forEach(subItem => {
                                let fields = $(`#postTxQuestionnaireContainer [code="${subItem.valueCoding.code}"]`);
                                fields.each(function() {
                                    if ($(this).attr("dataType") === "open-choice") $(this).prop("checked", true);
                                    if ($(this).attr("dataType") === "choice") $(this).prop("selected", true);
                                    $(this).attr("answered", true);
                                });
                            });
                        }
                        if (valueBoolean.length) {
                            $(`#postTxQuestionnaireContainer [linkId="${item.linkId}"]`)
                            .prop("checked", valueBoolean[0].valueBoolean)
                            .attr("answered", true);
                            
                        }
                        if (valueString.length) {
                            valueString.forEach(subItem => {
                                $(`#postTxQuestionnaireContainer [linkId="${item.linkId}"][dataType="string"], #postTxQuestionnaireContainer [linkId="${item.linkId}"][dataType="date"]`).each(function() {
                                    if ($(`#postTxQuestionnaireContainer [linkId="${item.linkId}"][value="${subItem.valueString}"][dataType != "string"]`).length) {
                                        return true;
                                    }
                                    $(this).val(subItem.valueString)
                                    $(this).attr("answered", true);
                                });
                                
                            });
                        }
                        
                        $("#postTxResolutionContainer").text(i18next.t("Last updated on {authoredDate} GMT").replace("{authoredDate}",this.modules.tnthDates.formatDateString(data.authored, "iso")));
                     });
                });
            },
            shouldShowSubstudyPostTx: function() {
                return this.isSubStudyPatient() && ((!this.hasSubStudyStatusErrors() && this.isPostTxActionRequired()) || this.hasPrevSubStudyPostTx());
            },
            getPostTxActionStatus: function() {
                if (!this.subStudyTriggers.data || !this.subStudyTriggers.data.action_state) {
                    return "";
                }
                return String(this.subStudyTriggers.data.action_state).toLowerCase();
            },
            hasMissedPostTxAction: function() {
                return this.hasSubStudyTriggers() && this.getPostTxActionStatus() === "missed";
            },
            isPostTxActionRequired: function() {
                return this.subStudyTriggers.data &&
                (["due", "overdue", "required"].indexOf(this.getPostTxActionStatus()) !== -1
                );
            },
            isSubStudyTriggersResolved: function() {
                if (!this.subStudyTriggers.data) {
                    return true;
                }
                return this.getPostTxActionStatus() === "completed" || this.subStudyTriggers.data.resolution;
            },
            onResponseChangeFieldEvent: function(event) {
                let targetElement = $(event.target);
                let containerIdentifier = "#postTxQuestionnaireContainer";
                if (
                    targetElement.attr("type") === "checkbox" && targetElement.is(":checked") ||
                    (targetElement.attr("type") === "text" && targetElement.val()) ||
                    (event.target.tagName.toLowerCase() === "select" && targetElement.find("option:selected").val()) ||
                    (event.target.tagName.toLowerCase() === "textarea" && targetElement.val())
                ) {
                    targetElement.attr("answered", true);
                } else {
                    targetElement.removeAttr("answered");
                }
                //text for other field
                if (targetElement.hasClass("addl-text")) {
                    let code = targetElement.attr("code");
                    $(`${containerIdentifier} input[type="checkbox"][code="${code}"]`)
                    .prop("checked", targetElement.val()?true:false)
                }
                //other field
                if (targetElement.hasClass("other")) {
                    let code = targetElement.attr("code");
                    if (!targetElement.is(":checked")) {
                        $(`${containerIdentifier} textarea[code="${code}"]`).val("").removeAttr("answered");
                    }
                }
                let answeredNum = 0;
                $(`${containerIdentifier} .question`).each(function() {
                    if ($(this).find("[answered]").length) {
                        answeredNum++;
                    }
                });
                if (
                    $(`${containerIdentifier} .question`).length === answeredNum
                ) {
                    $(`${containerIdentifier} .btn-submit`).removeClass("disabled").removeAttr("disabled");
                    return;
                }
                $(`${containerIdentifier} .btn-submit`).addClass("disabled").attr("disabled", true);
            },
            shouldShowPostTxQuestionnaireSection: function() {
                return this.isSubStudyPatient() && this.hasSubStudyAsssessmentData();
            },
            initPostTxQuestionnaireSection: function(params) {
                if (!this.isSubStudyPatient()) {
                    return false;
                }
                let self = this;

                this.setSubStudyTriggers(() => {
                    if (!this.hasSubStudyAsssessmentData()) {
                        this.postTxQuestionnaire.loading = false;
                        return;
                    }
                    this.modules.tnthAjax.getInstrument(EMPRO_POST_TX_QUESTIONNAIRE_IDENTIFIER, false, (data) => {
                        let containerIdentifier = "#postTxQuestionnaireContainer";
                        setTimeout(function() {
                            this.postTxQuestionnaire.loading = false;
                        }.bind(this), 50);
                       
                        if (!data.item) {
                            $(`${containerIdentifier}`).hide();
                            return;
                        }
                        this.postTxQuestionnaire.questions = data.item;
                        Vue.nextTick(function() {
                            /*
                             *  if the triggers are considered proccessed. check to see if they have been resolved
                             */
                            if (
                                self.subStudyTriggers.data.resolution &&
                                self.subStudyTriggers.data.resolution.qnr_id
                            ){
                                self.setPrevPostTxResponses(self.subStudyTriggers.data.resolution.qnr_id);
                            }
                            if (self.isSubStudyTriggersResolved()) return;
                            //initialize datepicker
                            $(`${containerIdentifier} .data-datepicker`).datepicker(
                                {"format": "dd M yyyy","forceParse": false, "autoclose": true, endDate: new Date()}
                            ).on("changeDate", self.onResponseChangeFieldEvent);
                        });

                    });
                }, {...params, ...{clearCache: true}});
            },
            submitPostTxQuestionnaire: function(e) {
                e.preventDefault();
                let postData = {
                    entry: []
                };
                let answerSet = [], self = this;
                let containerElementIdentifier = "#postTxQuestionnaireContainer";
                $(`${containerElementIdentifier} .question`).each(function() {
                    let answers = [];
                    $(this).find("[dataType]").each(function() {
                        if ($(this).attr("dataType") === "date") {
                            answers.push({
                                "valueString": self.modules.tnthDates.formatDateString(new Date($(this).val()), "iso-short")
                            });
                        }
                        if ($(this).attr("dataType") === "choice") {
                            let selectedOption = $(this).find("option:selected");
                            if (selectedOption.length) {
                                answers.push({
                                    "valueString": selectedOption.val()
                                });
                                answers.push({
                                    "valueCoding": {
                                        "code": selectedOption.attr("code"),
                                        "system": `${location.origin}/api/codings/assessment`
                                    }
                                });
                            }
                        }
                        if ($(this).attr("dataType") === "open-choice" && $(this).is(":checked")) {
                            if ($(this).hasClass("other-text")) {
                                return true;
                            }
                            if ($(this).hasClass("other")) {
                                answers.push({
                                    "valueCoding": {
                                        "code": $(this).attr("code"),
                                        "system": `${location.origin}/api/codings/assessment`
                                    },
                                    "valueString": $(this).val()
                                });
                                let valueString = $(`#postTxQuestionnaireContainer .other-text[code="${$(this).attr("code")}"]`).val();
                                if (valueString) {
                                    answers.push({
                                        "valueString": valueString
                                    });
                                }
                                return true;
                            }
                            answers.push({
                                "valueString": $(this).val()
                            });
                            answers.push({
                                "valueCoding": {
                                    "code": $(this).attr("code"),
                                    "system": `${location.origin}/api/codings/assessment`
                                }
                            });
                        }
                        if ($(this).attr("dataType") === "boolean") {
                            answers.push({
                                "valueBoolean": $(this).is(":checked") ? true: false
                            });
                        }
                    });
                    answerSet.push({
                        "answer": answers,
                        "linkId": $(this).attr("linkId"),
                        "text": $(this).attr("text")
                    });
                });
                let patientReference = `${location.origin}/api/demographics/${this.subjectId}`;
                postData.entry.push({
                    "author":{
                        "display":"user info",
                        "reference":`${location.origin}/api/me/${this.currentUserId}`
                     },
                     "authored":this.modules.tnthDates.getTodayDateObj().gmtDate,
                     "group": {
                        "question": answerSet
                     },
                     "resourceType":"QuestionnaireResponse",
                     "questionnaire":{
                        "display":"EMPRO Post Intervention Questionnaire",
                        "reference":`${location.origin}/api/questionnaires/${EMPRO_POST_TX_QUESTIONNAIRE_IDENTIFIER}`
                     },
                     "source": {
                        "display": "user demographics",
                        "reference": `${location.origin}/api/demographics/${this.currentUserId}`
                    },
                     "subject":{
                        "display":"patient demographics",
                        "reference": patientReference
                     },
                     "status": "completed"
                });
                $(`${containerElementIdentifier} .error-message`).html("");
                $(`${containerElementIdentifier} .btn-submit`).addClass("disabled").attr("disabled", true);
                this.modules.tnthAjax.postAssessment(this.subjectId, postData.entry[0], {targetField:$("#postTxSubmitContainer")}, (data) => {
                    $(`${containerElementIdentifier} .btn-submit`).removeClass("disabled").removeAttr("disabled");
                    if (data && data.error) {
                        $(`${containerElementIdentifier} .error-message`).html(i18next.t("Error occurred submitting data, try again"));
                        return;
                    }
                    setTimeout(function() {
                        location.reload();
                    }.bind(this), 2000);
                });
                return false;
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
                            item.subject = `<i id="messageLoader_${item.id}" class="message-loader fa fa-spinner fa-spin tnth-hide"></i>
                                           <a id="messageLink_${item.id}" class="item-link" data-user-id="${userId}" data-item-id="${item.id}"><u>${item.subject}</u></a>`;
                        });
                        $("#emailLogContent").html("<table id='profileEmailLogTable'></table>");
                        //noting here that displaying sent_date date/time as is, in GMT
                        $("#profileEmailLogTable").bootstrapTable(this.setBootstrapTableConfig({
                            data: data.messages,
                            classes: "table table-responsive profile-email-log",
                            sortName: "id",
                            sortOrder: "desc",
                            toolbar: "#emailLogTableToolBar",
                            columns: [
                            { 
                                field: "id",
                                visible: false
                            },
                            {
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
                            self.setEmailContentLinkEvent();
                        }, 150);
                        //dealing with pagination, events dynamically attached to elements will need to be re-initiated
                        $("#profileEmailLogTable").on("reset-view.bs.table", function () {
                            self.setEmailContentLinkEvent();
                        });
                    } else {
                        $("#emailLogContent").html("<span class='text-muted'>" + i18next.t("No email log entry found.") + "</span>");
                        $(".communication-title").hide();
                    }
                } else {
                    $("#emailLogMessage").text(data.error);
                    $(".communication-title").hide();
                }
            },
            setEmailContentLinkEvent: function() {
                let self = this;
                $("#profileEmailLogTable a.item-link").on("click", function() {
                    self.getEmailContent($(this).attr("data-user-id"), $(this).attr("data-item-id"));
                });
            },
            allowSubStudyWelcomeEmail: function() {
                /*
                 *  to allow option for sub-study welcome email in the dropdown
                 *  the subject needs to have consented to the sub-study,
                 *  ready for EMPRO assessment, 
                 *  have a valid email and an assigned treating clinician
                 */
                return this.isSubStudyReadyPatient() && !this.userHasNoEmail() && this.hasTreatingClinician();
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
                    $(".profilePatientEmail__btn-msg-wrapper").addClass("tnth-hide");
                    if ($(this).val() === "") {
                        $("#profile"+emailType+"EmailBtnMsgWrapper").addClass("tnth-hide");
                    } else {
                        $("#profile"+emailType+"EmailBtnMsgWrapper").removeClass("tnth-hide");
                    }
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
                        btnSelf.attr("disabled", disabled).removeClass("opaque");
                        self.patientEmailForm.loading = showLoading;
                        if (!disabled) {
                            btnSelf.removeClass("disabled");
                        } else {
                            btnSelf.addClass("disabled");
                        }
                    };
                    resetBtn(true, true);
                    btnSelf.addClass("opaque");
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
                    $("#sendRegistrationEmailForm .loading-indicator").addClass("visible").removeClass("invisible");
                    self.modules.tnthAjax.invite(self.subjectId, {
                        "subject": subject,"recipients": email,"body": body}, function(data) {
                        if (!data.error) {
                            $("#profileEmailMessage").text(i18next.t("invite email sent to {email}").replace("{email}", email));
                            $("#btnProfileSendEmail").attr("disabled", true);
                            self.modules.tnthAjax.emailLog(self.subjectId, {useWorker: true}, function(data) { //reload email audit log
                                setTimeout(function() {
                                    self.getEmailLog(self.subjectId, data);
                                }, 100);
                            });
                        } else {
                            if (data.error) {
                                $("#profileEmailErrorMessage").text(i18next.t("Error occurred while sending invite email."));
                            }
                        }
                        $("#sendRegistrationEmailForm .loading-indicator").addClass("invisible").removeClass("visible");
                        btnRef.removeClass("disabled").attr("disabled", false);
                    });
                });
            },
            initCommunicationSection: function() {
                $("#communicationsContainer .tab-label").on("click", function(e) {
                    e.stopPropagation();
                    $(this).toggleClass("active");
                });
                $("#communicationsContainer .tab-label").last().addClass("active");
                $("#emailBodyModal").modal({"show": false});
                var subjectId = this.subjectId, self = this;
                this.modules.tnthAjax.emailLog(subjectId, {useWorker: true}, function(data) {
                    setTimeout(function() { self.getEmailLog(subjectId, data); }, 100);
                });
            },
            initResetPasswordSection: function() {
                var self = this;
                /*
                 *  ignore use preference so reset password email can still be sent as long as the API returns true for email readiness
                 */
                this.setUserEmailReady({"ignore_preference": true}, function(data) {
                    if (!data || data.error) {
                        return;
                    }
                    /*
                     * set approproiate UI display after call to API with param to ignore preference
                     */
                    if (data.ready) {
                        $("#btnPasswordResetEmail").attr("disabled", false);
                        $("#passwordResetMessage").html("").removeClass("text-warning");
                        return;
                    }
                    $("#btnPasswordResetEmail").attr("disabled", true);
                    $("#passwordResetMessage").html(data.reason).addClass("text-warning");
                });
                $("#btnPasswordResetEmail").on("click", function(event) {
                    event.preventDefault();
                    event.stopImmediatePropagation(); //stop bubbling of events
                    var email = $("#email").val();
                    $("#passwordResetErrorMessage").text("");
                    let setVis = (loading) => {
                        if (loading) {
                            $("#resetPasswordGroup .loading-indicator").removeClass("tnth-hide");
                            $("#btnPasswordResetEmail").addClass("disabled").attr("disabled", true);
                            return;
                        }
                        $("#resetPasswordGroup .loading-indicator").addClass("tnth-hide");
                        $("#btnPasswordResetEmail").removeClass("disabled").attr("disabled", false);
                    };
                    //loading
                    setVis(true);
                    self.modules.tnthAjax.passwordReset(self.subjectId, function(data) {
                        if (!data.error) {
                            $("#passwordResetMessage").text(i18next.t("Password reset email sent to {email}").replace("{email}", email));
                        } else {
                            $("#passwordResetErrorMessage").text(i18next.t("Unable to send email."));
                        }
                        setVis(false);
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
                        if (self.hasSubStudyConsent()) {
                            self.modules.tnthAjax.withdrawConsent(subjectId, selectedOrgElement.val(), {
                                research_study_id: EPROMS_SUBSTUDY_ID
                            });
                        }
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
                                item.actions = `<a title="${i18next.t("Download")}" href="${'/api/user/' + String(item.user_id) + '/user_documents/' + String(item.id)}"><i class="fa fa-download"></i></a>`;
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
            initTimeWarpUI: function() {
                let self = this;
                let containerId = "#timeWarpContainer";
                let modalId = "#timeWarpModal";
                let inputFieldId = "#timeWarpDays";
                let clearMessages = () => {
                    $(`${containerId} .info-message`).html("");
                    $(`${containerId} .error-message`).html("");
                };
                $(containerId).removeClass("tnth-hide");
                $(modalId).modal({
                    show: false
                });
                $(modalId).on("shown.bs.modal", function() {
                    $(`${containerId} .submit`).removeAttr("actionTaken");
                    $(inputFieldId).focus();
                });
                $(modalId).on("hidden.bs.modal", function(event) {
                    clearMessages();
                    $(inputFieldId).val("");
                    if (!$(`${containerId} .submit`).attr("actionTaken")) {
                        return;
                    }
                    setTimeout(() => {
                        location.reload();
                    }, 0);
                })
                $(`${containerId} .prompt`).on("click", function() {
                    $(modalId).modal("show");
                });
                $(inputFieldId).removeAttr("disabled");
                $(`${containerId} .submit`).on("click", function() {
                    $(this).addClass("disabled");
                    $(`${containerId} .loading-message`).show();
                    clearMessages();
                    self.modules.tnthAjax.timeWarpPatientData(self.subjectId, $(inputFieldId).val(), {"max_attempts": 1}, function(data) {
                        $(`${containerId} .loading-message`).hide();
                        $(`${containerId} .submit`).removeClass("disabled");
                        if (data && data.error) {
                            $(`${containerId} .error-message`).html("Unable to update data. Server error.");
                            return;
                        }
                        if (data && data.changed) {
                            $(`${containerId} .info-message`).html(`<b>Data changed</b>: <br/>${data.changed.join("<br/>")}`);
                        }
                        $(`${containerId} .submit`).attr("actionTaken", true);
                    });
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
                    //test/debug feature to allow time warping patient data
                    //non-production environment ONLY
                    self.initTimeWarpUI();
                    entries.forEach(function(entry, index) {
                        var reference = entry.questionnaire.reference;
                        if ((new RegExp(EMPRO_POST_TX_QUESTIONNAIRE_IDENTIFIER)).test(reference)) {
                            return true;
                        }
                        var arrRefs = String(reference).split("/");
                        var instrumentId = arrRefs.length > 0 ? arrRefs[arrRefs.length - 1] : "";
                        if (!instrumentId) {
                            return false;
                        }
                        var authoredDate = String(entry.authored);
                        var reportLink = "/patients/session-report/" + sessionUserId + "/" + instrumentId + "/" + authoredDate;
                        var getStatusString  = function(status) {
                            if (!status) {
                                return "";
                            }
                            return i18next.t(Utility.capitalize(String(status).replace(/[\-\_]/g, " ")));
                        };
                        var extensionStatus = "", visitName = "";
                        if (entry.extension && entry.extension.length) {
                            entry.extension.forEach(function(item) {
                                if (!extensionStatus && item.status) {
                                    extensionStatus = item.status;
                                }
                                if (!visitName && item.visit_name) {
                                    visitName = item.visit_name;
                                }
                            });
                        } 
                        /*
                         *  status as indicated in extension field should take precedence over regular status field
                         */
                        var visitStatus = extensionStatus ? extensionStatus: entry.status;
                        let displayName = entry.questionnaire.display;
                        if ((new RegExp(EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER)).test(reference)) {
                            displayName = i18next.t("EMPRO Questionnaire");
                        }
                        self.assessment.assessmentListItems.push({
                            title: i18next.t("Click to view report"),
                            link: reportLink,
                            display: displayName,
                            //title case the status to allow it to be translated correctly
                            status: getStatusString(visitStatus),
                            class: (index % 2 !== 0 ? "class='odd'" : "class='even'"),
                            visit: visitName,
                            date: self.modules.tnthDates.formatDateString(entry.authored, "iso")
                        });
                    });
                });
            },
            handleSelectedState: function(event) {
                var newValue = event.target.value;
                this.orgsSelector.selectedState = newValue;
            },
            getAcceptOnNextOrg: function(orgName) {
                if (!this.settings) {
                    return false;
                }
                return this.settings.ACCEPT_TERMS_ON_NEXT_ORG;
            },
            initOrgsStateSelectorSection: function() {
                var orgTool = this.getOrgTool(), self = this;
                orgTool.populateOrgsStateSelector(this.subjectId, [this.getAcceptOnNextOrg()], function() {
                    self.handleOrgsEvent();
                    orgTool.setOrgsVis(self.demo.data, function() {
                        if (!$("#stateSelector option").length) {
                            orgTool.filterOrgs(orgTool.getHereBelowOrgs());
                            orgTool.morphPatientOrgs();
                            $(".noOrg-container, .noOrg-container *").show();
                        }
                    });
                    self.modules.tnthAjax.getConsent(self.subjectId, {useWorker: true}, function(data) {
                        self.getConsentList(data);
                    });
                });
            },
            initDefaultOrgsSection: function() {
                var subjectId = this.subjectId, orgTool = this.getOrgTool(), self = this;
                orgTool.onLoaded(subjectId, true);
                orgTool.setOrgsVis(this.demo.data,
                    function() {
                        self.setCurrentUserOrgs(false, function(data) {
                            //admin staff can select any orgs (leaf orgs for patient)
                            var orgsToBeFiltered = self.isAdmin() ? orgTool.getTopLevelOrgs(): data;
                            if (self.isSubjectPatient()) {
                                //for patient, only leaf orgs are selectable
                                orgTool.filterOrgs(orgTool.getLeafOrgs(orgsToBeFiltered));
                                orgTool.morphPatientOrgs();
                            } else {
                                //others e.g. staff
                                orgTool.filterOrgs(orgTool.getHereBelowOrgs(orgsToBeFiltered));
                            }
                            self.handleOrgsEvent();
                            self.modules.tnthAjax.getConsent(subjectId, {useWorker: true}, function(data) {
                                self.getConsentList(data);
                            });
                            $("#clinics").attr("loaded", true);
                        });
                    });
            },
            handleOrgsEvent: function() {
                var self = this, orgTool = this.getOrgTool();
                orgTool.handleOrgsEvent(this.subjectId, this.isConsentWithTopLevelOrg());
                $("#clinics").on("updated", function() {
                    self.setDemoData("", function(){
                        self.setView().setContent($("#userOrgs_view"), self.getOrgsDisplay());
                    }); 
                    self.reloadConsentList(self.subjectId);
                    self.handlePcaLocalized();
                    if ($("#locale").length > 0) {
                        self.modules.tnthAjax.getLocale(self.subjectId);
                    }
                    if ($("#profileassessmentSendEmailContainer").length > 0) {
                        setTimeout(function() {
                            self.reloadSendPatientEmailForm(self.subjectId);
                        }, 150);
                    }
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
            initConsentSection: function() {
                Consent.initFieldEvents(this.subjectId);
            },
            handlePcaLocalized: function() {
                if (!this.subjectId || !this.isSubjectPatient()) {
                    return false;
                }
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
                ClinicalQuestions.update(this.subjectId, function() {
                    self.onBeforeInitClinicalQuestionsSection();
                    ClinicalQuestions.initFieldEvents(self.subjectId);
                });
            },
            initProcedureSection: function() {
                ProcApp.initViaTemplate();
            },
            manualEntryModalVis: function(hide) {
                if (hide) {
                    /*
                     * TODO, need to find out why IE is raising vue error here
                     */
                    this.manualEntry.loading = true;
                    $("#manualEntryLoader").show();
                    $("#manualEntryButtonsContainer").hide();
                } else {
                    this.manualEntry.loading = false;
                    $("#manualEntryLoader").hide();
                    $("#manualEntryButtonsContainer").show();
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
                }, 5000, self.manualEntryModalVis);
            },
            setManualEntryDateToToday: function() {
                this.manualEntry.todayObj = this.modules.tnthDates.getTodayDateObj();
                //set initial completion date as GMT date/time for today based on user timezone
                this.manualEntry.completionDate = this.manualEntry.todayObj.gmtDate;
            },
            setInitManualEntryCompletionDate: function() {
                //set initial completion date as GMT date/time for today based on user timezone
                this.setManualEntryDateToToday();
                //comparing consent date to completion date without the time element
                if (this.modules.tnthDates.formatDateString(this.manualEntry.consentDate, "iso-short") === 
                    this.modules.tnthDates.formatDateString(this.manualEntry.completionDate, "iso-short")) {
                    //set completion date/time to consent date/time if equal
                    this.manualEntry.completionDate = this.manualEntry.consentDate;
                }
            },
            resetManualEntryFormValidationError: function() {
                //reset error message to null
                this.manualEntry.errorMessage = null;
                //reset bootstrap form validation error
                $("#manualEntryCompletionDateContainer").removeClass("has-error");
                $("#manualEntryMessageContainer").html("").removeClass("with-errors");
            },
            setManualEntryErrorMessage: function(message) {
                if (!message) {
                    return;
                }
                $("#manualEntryMessageContainer").html(message);
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
                    self.resetManualEntryFormValidationError();
                });
                $("#manualEntryModal").on("shown.bs.modal", function() {
                    self.manualEntry.method = "";
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
                        if (items.length) { 
                            //consent date in GMT
                            self.manualEntry.consentDate = self.modules.tnthDates.formatDateString(items[0].acceptance_date, "system");
                        }
                        //to reach here patient might have withdrawn?
                        //do check for that
                        const withdrawnItem = $.grep(dataArray, function(item) {
                            //filtered out non-deleted items from all consents
                            return !item.deleted && String(item.status) === "suspended";
                        });
                        if (withdrawnItem.length) {
                            //use PREVIOUSLY valid consent date
                            var consentItems = $.grep(dataArray, function(item) {
                                return item.deleted && Consent.hasConsentedFlags(item);
                            });
                            if (consentItems.length) {
                                self.manualEntry.consentDate = self.modules.tnthDates.formatDateString(consentItems[0].acceptance_date, "system");
                            }
                        }
                        //set completion date once consent date/time has been set
                        self.setInitManualEntryCompletionDate();
                    });
                    setTimeout(function() { self.manualEntry.initloading = false;}, 10);
                });

                $("input[name='entryMethod']").on("click", function() {
                    self.resetManualEntryFormValidationError();
                    self.manualEntry.method = $(this).val();
                    if ($(this).val() === "interview_assisted") {
                        //if method is interview assisted, reset completion date to GMT date/time for today
                        self.setManualEntryDateToToday();
                        return;
                    }
                    //paper entry
                    self.setInitManualEntryCompletionDate();
                });

                self.__convertToNumericField($("#qCompletionDay, #qCompletionYear"));

                ["qCompletionDay", "qCompletionMonth", "qCompletionYear"].forEach(function(fn) {
                    var fd = $("#" + fn),
                        tnthDates = self.modules.tnthDates;

                    fd.on("change", function(e) {
                        e.stopImmediatePropagation();

                        //reset error
                        self.resetManualEntryFormValidationError();
                        $("#meSubmit").attr("disabled", false);
                    
                        var d = $("#qCompletionDay");
                        var m = $("#qCompletionMonth");
                        var y = $("#qCompletionYear");

                        //add true boolean flag to check for future date entry
                        var errorMessage = tnthDates.dateValidator(d.val(), m.val(), y.val(), true);
                        if (errorMessage) {
                            self.manualEntry.errorMessage = errorMessage;
                            self.setManualEntryErrorMessage(errorMessage);
                            $("#meSubmit").attr("disabled", true);
                            return false;
                        }
            
                        var gmtDateObj = tnthDates.getDateObj(y.val(), m.val(), d.val(), 12, 0, 0);
                        self.manualEntry.completionDate = self.modules.tnthDates.getDateWithTimeZone(gmtDateObj, "system");

                        //add check for consent date
                        if (!self.manualEntry.consentDate) {
                            return false;
                        }

                        //check completion date against consent date
                        //all date/time should be in GMT date/time
                        var completionDate = new Date(self.manualEntry.completionDate);
                        //noting here that date/time in ISO date with added hours, minutes and seconds separated by T is converted again to UTC by firefox 
                        //so need to use non-ISO date/time format for comparison to avoid additional conversion
                        var cConsentDate = new Date(self.modules.tnthDates.formatDateString(self.manualEntry.consentDate, "mm/dd/yyyy hh:mm:ss"));
                        //Get a copy of the consent date
                        //NB: NEED to make a deep copy here because: Date object in javascript is MUTABLE
                        //Changing the hour, minute and second in the subsequent code will ACTUALLY change the reference as well
                        var oConsentDate = new Date(cConsentDate.getTime());
                        var nCompletionDate = completionDate.setHours(0, 0, 0, 0);
                        var nConsentDate = cConsentDate.setHours(0, 0, 0, 0);
            
                        /*
                         * set completion date/time to consent date/time IF the two dates are the same 
                         */
                        if (nCompletionDate === nConsentDate) {
                            //set completion date to system format, recognized by backend
                            self.manualEntry.completionDate = self.modules.tnthDates.formatDateString(oConsentDate, "system"); 
                        }
                    });
                });
                $(document).delegate("#meSubmit", "click", function() {
                    var method = String(self.manualEntry.method), completionDate = self.manualEntry.completionDate;
                    var linkUrl = "/api/present-needed?subject_id=" + $("#manualEntrySubjectId").val();
                    if (method === "") { return false; }
                    if (method !== "paper") {
                        self.continueToAssessment(method, completionDate, linkUrl);
                        return false;
                    }
                    self.manualEntryModalVis(true);
                    self.modules.tnthAjax.getCurrentQB(subjectId, completionDate, null, function(data) {
                        var errorMessage = "";
                        if (data.error) {
                            errorMessage = i18next.t("Server error occurred checking questionnaire window");
                        }
                        //check questionnaire time windows
                        if (!data.questionnaire_bank || !Object.keys(data.questionnaire_bank).length) {
                            errorMessage = i18next.t("Invalid completion date. Date of completion is outside the days allowed.");
                        }
                        if (errorMessage) {
                            self.setManualEntryErrorMessage(errorMessage);
                            self.manualEntryModalVis();
                            //use computed property to assign value to error message here, 
                            //IE is throwing error if it is not done this way, not exactly sure why still
                            self.propManualEntryErrorMessage = errorMessage;
                            return false;
                        }
                        self.resetManualEntryFormValidationError();
                        self.continueToAssessment(method, completionDate, linkUrl);
                    });
                });

                /* disabling this to accomodate entry of survey responses on paper */
                // self.modules.tnthAjax.assessmentStatus(subjectId, function(data) {
                //     if (!data.error && (data.assessment_status).toUpperCase() === "COMPLETED" &&
                //         parseInt(data.outstanding_indefinite_work) === 0) {
                //         $("#assessmentLink").attr("disabled", true);
                //         $("#enterManualInfoContainer").text(i18next.t("All available questionnaires have been completed."));
                //     }
                // });
            },
            updateRolesData: function(event) {
                var roles = $("#rolesGroup input:checkbox:checked").map(function() {
                    return {name: $(this).val()};
                }).get();
                /*
                 * check if a role is selected
                 */
                if (!roles.length) {
                    //make sure at least one role is selected
                    //admin, staff admin functionality
                    $(".put-roles-error").html("A role must be selected.");
                    return false;
                }
                $(".put-roles-error").html("");
                this.modules.tnthAjax.putRoles(this.subjectId, {"roles": roles}, $(event.target));
                /*
                 * refresh user roles list since it has been uploaded
                 */
                this.initUserRoles({clearCache: true});
            },
            updateRolesUI: function(roles) {
                if (!roles) return;
                roles.forEach(role => {
                    $("#rolesGroup input[value='"+role+"']").attr("checked", true);
                });
            },
            initUserRoles: function(params) {
                if (!this.subjectId) { return false; }
                var self = this;
                this.modules.tnthAjax.getRoles(this.subjectId, function(data) {
                    if (data.roles) {
                        self.userRoles = data.roles.map(function(role) {
                            return role.name;
                        });
                        Vue.nextTick(() => {
                            self.updateRolesUI(self.userRoles);
                        });
                    }
                }, params);
            },
            initRolesListSection: function() {
                var self = this;
                this.modules.tnthAjax.getRoleList({useWorker:true}, function(data) {
                    if (!data.roles) { return false; }
                    let roles = data.roles || [];
                    if (!self.isAdmin() && self.isStaffAdmin()) {
                        /*
                         * admin staff should not be able to edit role(s) for a user that contains other roles
                         */
                        let diffRoles = self.userRoles.filter(item => !self.staffEditableRoles.includes(item));
                        if (diffRoles.length) {
                            $("#rolesGroup").closest(".profile-item-container").hide();
                        } else {
                            /*
                             * filter down editable roles for a staff
                             */
                            roles = roles.filter(item => {
                                return self.staffEditableRoles.indexOf(item.name) >= 0
                            });
                        }
                    }

                    /*
                     * alphabetize role list by the name property of each item in the array
                     * for ease of viewing and selection
                     */
                    self.roles.data = sortArrayByField(roles, "name");
                    setTimeout(self.initUserRoles, 50);  
                });
            },
            initAuditLogSection: function() {
                var self = this, errorMessage = "";
                $("#profileAuditLogTable").html(Utility.getLoaderHTML());
                $("#profileAuditLogTable .loading-message-indicator").show();
                this.modules.tnthAjax.auditLog(this.subjectId, {useWorker:true}, function(data) {
                    if (data.error) {
                        errorMessage = i18next.t("Error retrieving data from server");
                    }
                    if (!data.audits || data.audits.length === 0) {
                        errorMessage = i18next.t("no data returned");
                    }
                    if (errorMessage) {
                        $("#profileAuditLogTable").html("");
                        $("#profileAuditLogErrorMessage").text(errorMessage);
                        //report error if loading audit log results in error
                        self.modules.tnthAjax.reportError(self.subjectId, "/api/user/" + self.subjectId + "/audit", errorMessage);
                        return false;
                    }
                    var ww = $(window).width(), fData = [], len = ((ww < 650) ? 20 : (ww < 800 ? 40 : 80)), errorMessage="";
                    (data.audits).forEach(function(item) {
                        item.by = item.by.reference || "-";
                        var r = /\d+/g;
                        var m = r.exec(String(item.by));
                        if (m) {
                            item.by = m[0];
                        }
                        item.lastUpdated = self.modules.tnthDates.formatDateString(item.lastUpdated, "iso");
                        item.comment = item.comment ? String(item.comment) : "";
                        //noting here that comment is already escaped.  just need to display it as is, no need to decode it
                        var c = String(item.comment);
                        item.comment = c.length > len ? (c.substring(0, len + 1) + "<span class='second hide'>" + (c.substr(len + 1)) + "</span><br/><sub onclick='{showText}' class='pointer text-muted'>" + i18next.t("More...") + "</sub>") : item.comment;
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
                    $("#profileAuditLogTable").html("");
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
            getConsentEditDisplayIconHTML: function(item="", targetElementId="") {
                return `&nbsp;&nbsp;<a data-toggle="modal" data-target="#${targetElementId}" data-orgId="${item.organization_id}" data-agreementUrl="${item.agreement_url}" data-userId="${this.subjectId}" data-status="${item.statusText || this.getConsentStatusHTMLObj(item).statusText}" data-signed-date="${this.modules.tnthDates.formatDateString(item.acceptance_date, "system")}" data-researchStudyId="${item.research_study_id}"><span class="glyphicon glyphicon-pencil edit-icon" aria-hidden="true"></span></a>`;
            },
            getLREditIconHTML: function(item) {
                var LROrgId = (this.getOrgTool()).getTopLevelParentOrg(item.organization_id);
                var editorUrlEl = $("#" + LROrgId + "_editor_url");
                if (!editorUrlEl.val()) {
                    return "";
                }
                var dataShow = String(editorUrlEl.attr("data-show")) === "true";
                return `<div class="button--LR" data-show="${dataShow}"><a href="${editorUrlEl.val()}" target="_blank">${i18next.t("Edit in Liferay")}</a></div>`
            },
            isConsentStatusEditable: function(item) {
               return this.isConsentEditable() && String(this.getConsentStatus(item)) === "active";
            },
            isConsentDateEditable: function(item) {
                //consent date is editable only if the field is not disabled (e.g. as related to MedidataRave), consent is editable (e.g., Eproms), current user is a staff and subject is a patient
                return (this.isTestEnvironment() && !this.isSubjectPatient()) || (this.isConsentStatusEditable(item) && this.isSubjectPatient() && this.isStaff());
            },
            /*
             * stub row in the consent table for sub-study if the subject hasn't consented to the substudy but already consented to the main study
             */
            getSubStudyConsentUnknownRow: function() {
                if (!this.hasCurrentConsent()) {
                    return;
                }
                let currentConsentItem = this.consent.currentItems[0];
                this.consent.consentDisplayRows.push(
                    [{
                        content: EPROMS_SUBSTUDY_TITLE
                    },
                    {
                        content: i18next.t("Not consented") + 
                                this.getConsentEditDisplayIconHTML({
                                    organization_id: currentConsentItem.organization_id,
                                    statusText: "unknown",
                                    agreement_url: currentConsentItem.agreement_url,
                                    research_study_id: EPROMS_SUBSTUDY_ID
                                }
                        , "profileConsentListModal"),
                        "_class": "indent"
                    }, {content: `<span class="agreement">&nbsp;</span>`}, {content: "&nbsp;"}]
                );
            },
            getConsentRow: function(item) {
                if (!item) {return false;}
                var self = this, sDisplay = self.getConsentStatusHTMLObj(item).statusHTML;
                var contentArray = [{
                    content: self.getConsentOrgDisplayName(item)
                }, {
                    content: sDisplay + (self.isConsentStatusEditable(item) ? self.getConsentEditDisplayIconHTML(item, "profileConsentListModal") : ""),
                    "_class": "indent"
                }, {
                    content: (function(item) {
                        var viewLinkHTML = `<span class="agreement">&nbsp;&nbsp;<a href="${decodeURIComponent(item.agreement_url)}" target="_blank"><em>${i18next.t("View")}</em></a></span>`;
                        var s = viewLinkHTML + self.getLREditIconHTML(item);
                        if (self.isDefaultConsent(item)) {
                            s = i18next.t("Sharing information with clinics") + viewLinkHTML;
                        }
                        return s;
                    })(item)
                }, {
                    content: self.modules.tnthDates.formatDateString(item.acceptance_date) + (self.isConsentDateEditable(item) ? self.getConsentEditDisplayIconHTML(item, "consentDateModal") : "&nbsp;")
                }];
                this.consent.consentDisplayRows.push(contentArray);
            },
            getConsentHistoryRow: function(item) {
                var self = this, sDisplay = self.getConsentStatusHTMLObj(item).statusHTML;
                var content = `<tr ${(item.deleted?"class='history'":"")}>`;
                var contentArray = [{
                    content: `${self.getConsentOrgDisplayName(item)}<div class="smaller-text text-muted">${this.orgTool.getOrgName(item.organization_id)}</div>`
                }, {
                    content: sDisplay
                }, {
                    content: self.modules.tnthDates.formatDateString(item.acceptance_date)

                },
                {
                    content: `<span class="text-danger">${self.getRecordedDisplayDate(item)||'<span class="text-muted">--</span>'}</span>`
                }, {
                    content: (item.recorded && item.recorded.by && item.recorded.by.display ? item.recorded.by.display : "<span class='text-muted'>--</span>")
                }];

                contentArray.forEach(function(cell) {
                    content += `<td class="consentlist-cell">${cell.content}</td>`;
                });
                content += "</tr>";
                return content;
            },
            isSubStudyConsent: function(item) {
                if (!item) {
                    return false;
                }
                return parseInt(item.research_study_id) === EPROMS_SUBSTUDY_ID;
            },
            getConsentOrgDisplayName: function(item) {
                if (!item) {return "";}
                if (this.isSubStudyConsent(item)) {
                    return EPROMS_SUBSTUDY_TITLE;
                }
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
                let recordedDate;
                if (item.deleted) {
                    recordedDate = item.deleted.lastUpdated;
                }
                if (!recordedDate && item.recorded) {
                    recordedDate = item.recorded.lastUpdated;
                } 
                return recordedDate ? this.modules.tnthDates.formatDateString(recordedDate, "yyyy-mm-dd hh:mm:ss") : "";
            },
            isDefaultConsent: function(item) {
                return item && /stock\-org\-consent/.test(item.agreement_url);
            },
            getConsentStatusHTMLObj: function(item) {
                var consentStatus = this.getConsentStatus(item), sDisplay = "", cflag = "";
                var se = item.staff_editable, sr = item.send_reminders, ir = item.include_in_reports;
                var consentLabels = this.consent.consentLabels;
                var oDisplayText = {
                    "default": `<span class='text-success small-text'>${consentLabels.default}</span>`,
                    "consented": `<span class='text-success small-text'>${consentLabels.consented}</span>`,
                    "withdrawn": `<span class='text-warning small-text withdrawn-label'>${consentLabels.withdrawn}</span>`,
                    "deleted": `<span class='text-danger small-text'>${consentLabels.deleted}</span>`,
                    "purged": `<span class='text-danger small-text'>${consentLabels.purged}</span>`,
                    "expired": `<span class='text-warning'>&#10007; <br><span>(${i18next.t("expired")}</span>`,
                };
                switch (consentStatus) {
                case "deleted":
                    if (Consent.hasConsentedFlags(item)) {
                        sDisplay = oDisplayText.consented;
                    } else if (se && ir && !sr || (!se && ir && !sr)) {
                        sDisplay = oDisplayText.withdrawn;
                    } else if (!se && !ir && !sr) {
                        sDisplay = oDisplayText.purged;
                    } else {
                        sDisplay = oDisplayText.consented;
                    }
                    if (String(item.status) === "deleted") {
                        sDisplay += `<span class="text-danger"> (</span>${oDisplayText.deleted}<span class="text-danger">)</span>`;
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
                            data.tous = (data.tous).sort(function(a, b) {
                                return new Date(a.accepted) - new Date(b.accepted);
                            });
                            let websiteConsentTerms = [
                                ["website terms of use",
                                "subject website consent"],
                                ["empro website terms of use"]
                            ];
                            (data.tous).forEach(function(item) {
                                let fType = $.trim(item.type).toLowerCase();
                                let exists = (self.consent.touObj).filter(tou => {
                                    return tou.agreement_url === item.agreement_url;
                                });
                                if (exists.length) {
                                    return true;
                                }
                                let org = orgsList[item.organization_id];
                                let matchedTermTypes = websiteConsentTerms.filter(o => {
                                    return o.indexOf(String(fType)) !== -1;
                                });
                                if (matchedTermTypes.length) {
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
                var self = this;
                Consent.initConsentListModalEvent();
                $("#profileConsentListModal").on("show.bs.modal", function() {
                    if (self.isAdmin()) {
                        $(this).find(".admin-radio").removeClass("tnth-hide").show();
                    }
                });
                $("#profileConsentListModal input[class='radio_consent_input']").on("click", function() {
                    self.consent.saveLoading = true;
                });
                $("#profileConsentListModal").on("updated", function() {
                    self.consent.saveLoading = false;
                    setTimeout(function() {
                        self.reloadConsentList(self.subjectId);
                    }, 150);

                });
            },
            initConsentDateEvents: function() {
                var self = this;
                Consent.initConsentDateFieldEvents();
                $("#consentDateModal").on("updated", function() {
                    setTimeout(function() {
                        self.reloadConsentList($("#consentDateModal_date").attr("data-userId"));
                    }, 150);
                });
            },
            showConsentHistory: function() {
               return !this.consent.consentLoading && this.isConsentEditable() && this.hasConsentHistory();
            },
            hasConsentHistory: function() {
                return this.consent.historyItems.length > 0;
            },
            hasSubStudyConsent: function() {
                return this.hasCurrentConsent() && this.consent.currentItems.filter(item => item.research_study_id === EPROMS_SUBSTUDY_ID).length;
            },
            showSubStudyConsentAddElement: function() {
                //check to see if user organization is in substudy
                if (!this.hasSubStudySubjectOrgs()) {
                    return false;
                }
                //adding a test substudy consent should only be allowed in Test environment
                if (!this.isTestEnvironment()) {
                    return false;
                }
                //should only show add substudy consent row if the subject is a patient and the user is a staff/staff admin
                return this.hasCurrentConsent() && !this.hasSubStudyConsent() && this.isSubjectPatient() && this.isStaff();
            },
            hasCurrentConsent: function() {
                return this.consent.currentItems.length > 0;
            },
            getConsentHistory: function(options) {
                if (!options) {options = {};}
                var self = this, content = "";
                content = "<div id='consentHistoryWrapper'><table id='consentHistoryTable' class='table-bordered table-condensed table-responsive' style='width: 100%; max-width:100%'>";
                content += this.getConsentHeaderRow(this.consent.consentHistoryHeaderArray);
                items = (this.consent.currentItems).concat(this.consent.historyItems); //combine both current and history items and display current items first;
                var items = items.sort(function(a, b) { 
                    //sort items by last updated date in descending order
                    let bLastUpdated = b.deleted ? b.deleted.lastUpdated : b.recorded.lastUpdated;
                    let aLastUpdated = a.deleted ? a.deleted.lastUpdated : a.recorded.lastUpdated;
                    return new Date(bLastUpdated) - new Date(aLastUpdated);
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
                        self.modules.tnthAjax.getConsent(userId || self.subjectId, {sync: true}, function(data) {
                            self.getConsentList(data);
                            self.setSubjectResearchStudies();
                            self.setDemoData();
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
                this.consent.historyItems = $.grep(this.consent.consentItems, function(item) { //filtered out deleted items from all consents
                    return self.getConsentStatus(item) !== "active";
                });
                this.consent.currentItems.forEach(function(item, index) {
                    if (!(existingOrgs[item.organization_id+"_"+item.research_study_id]) && !(/null/.test(item.agreement_url))) {
                        self.getConsentRow(item, index);
                        existingOrgs[item.organization_id+"_"+item.research_study_id] = true;
                    }
                });
                if (this.showSubStudyConsentAddElement()) {
                     this.getSubStudyConsentUnknownRow();
                }
                clearInterval(this.consentListReadyIntervalId);
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
                            Consent.initConsentListModalEvent();
                            self.initConsentItemEvent();
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
                }, 150);
                this.consent.consentLoading = false;
            },
            pad : function(n) { n = parseInt(n); return (n < 10) ? "0" + n : n; },
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
    return ProfileObj;
})();

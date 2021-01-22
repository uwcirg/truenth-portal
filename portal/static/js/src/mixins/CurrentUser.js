import tnthAjax from "../modules/TnthAjax.js";
import OrgTool from "../modules/OrgTool.js";
/*
 * reusable Vue mixin component for retrieving current user information, e.g. organizations, roles
 * used by Vue instances as component or non-Vue instances as object
 */
var CurrentUser = { /* global $ i18next */
    data: function(){
        return {
            userId: null,
            orgTool: null,
            isAdmin: false,
            userResearchStudyIds: [],
            userRoles: [],
            userOrgs: [],
            topLevelOrgs: [],
            leafOrgs: [],
            hereBelowOrgs: []
        };
    },
    methods: {
        initCurrentUser: function(callback, doPopulateOrgsUI, orgElementsContainerId) { /* init method for populating properties for current user */
            var self = this;
            callback = callback || function() {};
            this.setUserId(function() {
                if (!self.getUserId()) {
                    callback({error: true});
                    return false;
                }
                self.setUserRoles(function() { /* set user roles */
                    self.setUserResearchStudies(function() {
                        self.setUserOrgs(self.getUserId());
                        self.initOrgsList(function() { /* set user orgs */
                            callback();
                        }, doPopulateOrgsUI, orgElementsContainerId);
                    });
                });
            });
        },
        getUserId: function() {
            return this.userId;
        },
        setUserId: function(callback) {
            callback = callback || function() {};
            if (this.userId) {
                callback();
                return true;
            }
            var self = this;
            tnthAjax.getCurrentUser(function(data) {
                if (data && data.id) {
                    self.userId = data.id;
                }
                callback();
            });
        },
        getUserRoles: function (callback) {
            callback = callback || function () {};
            if (this.userRoles && this.userRoles.length) {
                callback(this.userRoles);
                return;
            }
            this.setUserRoles(callback);
        },
        setUserRoles: function (callback) {
            callback = callback || function () {};
            if (this.userRoles && this.userRoles.length) {
                callback();
                return;
            }
            var self = this;
            tnthAjax.getRoles(this.userId, function (data) {
                if (!data || data.error) {
                    callback({
                        "error": i18next.t("Error occurred setting user roles")
                    });
                    return false;
                }
                self.userRoles = data.roles.map(function (item) {
                    return item.name;
                });
                self.setAdminUser();
                callback();
            });
        },
        setAdminUser: function() {
            this.isAdmin = this.userRoles.indexOf("admin") !== -1;
        },
        isAdminUser: function() {
            return this.isAdmin;
        },
        isPatientUser: function() {
            return this.userRoles.indexOf("patient") !== -1
        },
        setUserResearchStudies: function(callback) {
            callback = callback || function() {};
            if (this.isPatientUser()) {
                this.setPatientResearchStudies(callback);
                return;
            }
            this.setStaffResearchStudies(callback);
        },
        setStaffResearchStudies: function(callback) {
            callback = callback || function() {};
            tnthAjax.getStaffResearchStudies(this.userId, "", data => {
                if (data && data.research_study) {
                    this.userResearchStudyIds = data.research_study.map(item => item.id);
                }
                callback();
            });
        },
        setPatientResearchStudies: function(callback) {
            callback = callback || function() {};
            let self = this;
            tnthAjax.getPatientResearchStudies(this.userId, "", data => {
                if (data && data.research_study) {
                    this.userResearchStudyIds = Object.keys(data.research_study).map(item => parseInt(item));
                }
                callback();
            });
        },
        getUserOrgs: function () {
            if (this.userOrgs.length === 0) {
                this.setUserOrgs(this.userId);
            }
            return this.userOrgs;
        },
        setUserOrgs: function () {
            if (!this.userId) {
                return false;
            }
            var self = this;
            $.ajax({
                type: "GET",
                async: false,
                url: "/api/demographics/" + this.userId
            }).done(function (data) {
                if (data && data.careProvider) {
                    let orgFilteredSet = self.getOrgTool().getOrgsByCareProvider(data.careProvider);
                    self.userOrgs = orgFilteredSet;
                }
            }).fail(function () {
                alert(i18next.t("Error occurred setting user organizations"));
            });
        },
        hasTopLevelOrgs: function() {
            return this.topLevelOrgs && this.topLevelOrgs.length;
        },
        setTopLevelOrgs: function () {
            var self = this;
            this.topLevelOrgs = (this.userOrgs).map(function (orgId) {
                return self.orgTool.getOrgName(self.orgTool.getTopLevelParentOrg(orgId));
            });
            let redux = (names) => names.filter((v,i) => names.indexOf(v) === i);
            this.topLevelOrgs = redux(this.topLevelOrgs);
        },
        setLeafOrgs: function() {
            this.leafOrgs = this.orgTool.getLeafOrgs(this.getUserOrgs());
        },
        getLeafOrgs: function() {
            return this.leafOrgs;
        }, 
        setHereBelowOrgs: function() {
            this.hereBelowOrgs = this.orgTool.getHereBelowOrgs(this.getUserOrgs());
        },
        getHereBelowOrgs: function() {
            return this.hereBelowOrgs;
        },
        getSelectedOrgHereBelowOrgs: function(orgId) {
            return this.orgTool.getHereBelowOrgs([orgId]);
        },
        getOrgTool: function () {
            if (!this.orgTool) {
                this.orgTool = new OrgTool();
            }
            return this.orgTool;
        },
        filterOrgs: function() {
            this.orgTool.filterOrgs(this.getHereBelowOrgs());
        },
        initOrgsList: function (callback, doPopulate, containerId) {
            callback = callback || function() {};
            var self = this;
            this.getOrgTool();
            this.orgTool.init(function (data) {
                if (data.error) {
                    return false;
                }
                self.setTopLevelOrgs();
                self.setHereBelowOrgs();
                self.setLeafOrgs();
                if (doPopulate) {
                    self.orgTool.populateUI(); //populate orgs dropdown UI
                    self.filterOrgs();
                }
                callback();
            }, containerId);
        },
        __copy: function() {
            var self = this, CurrentUserObj = {};
            for (var prop in self) {
                CurrentUserObj[prop] = self[prop];
            }
            return CurrentUserObj;
        }
    }
};

export default CurrentUser; //Vue mixin component
export var CurrentUserObj = CurrentUser.methods.__copy(); //exposing it as a regular object


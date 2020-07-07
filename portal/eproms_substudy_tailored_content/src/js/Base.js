import {sendRequest, initI18next} from "./Utility";
export default {
    mounted: function() {
        var self = this;
        Promise.all([
            sendRequest(self.settingsURL).catch(error => { return error }),
            sendRequest(self.meURL).catch(error => { return error }),
        ]).then(responses => {
            try {
                this.setSettings(JSON.parse(responses[0]));
            } catch(e) {
                self.setErrorMessage(`Error parsing data ${e}`);
            }
            try {
                self.userInfo = JSON.parse(responses[1]);
            } catch(e) {
                self.setErrorMessage(`Error parsing data ${e}`);
            }
            self.initApp();
            console.log("settings? ", self.settings);
            console.log("user? ", self.userInfo)
        }).catch(error => {
            self.setErrorMessage(`Error in promises ${error}`);
            self.initApp();
        });
    },
    /*
     * methods available to the application
     */
    methods: {
        isLoading: function() {
            return this.loading;
        },
        isInitialized: function() {
            return this.initialized;
        },
        initApp: function() {
            let self = this;
            this.setSettings(this.settings);
            this.setLRBaseURL(this.settings?this.settings["LR_ORIGIN"]:"");
            this.setUserID(this.userInfo?this.userInfo["id"]:0);
            this.initialized = true;
            Promise.all([
                 //TODO init user domains, call api based on user id
                sendRequest(`/api/demographics/${this.getUserID()}`).catch(error => { return error }),
            ]).then(responses => {
                try {
                    this.setLocale(JSON.parse(responses[0]));
                } catch(e) {
                    self.setErrorMessage(`Error parsing data ${e}`);
                }
                console.log("user locale? ", this.getLocale())
                //get welcome page
                //TODO filter content based on user's domains?
                //each domain link on the intro/welcome page should have a representative attribute or css class
                //that denote which domain it represents
                self.getIntroContent();
                self.setInitView();
            }).catch(error => {
                self.setErrorMessage(`Error in promises ${error}`);
                self.setInitView();
            });
        },
        setInitView: function() {
            let self = this;
            Vue.nextTick(
                function() {
                    setTimeout(function() {
                        this.setCurrentView("intro");
                        this.loading = false;
                    }.bind(self), 350);
                }
            );
        },
        hasError: function() {
            return this.errorMessage !== "";
        },
        resetError: function() {
            this.setErrorMessage("");
        },
        setErrorMessage: function(message) {
            this.errorMessage += (this.errorMessage?"<br/>": "") + message;
        },
        getUserID: function() {
            return this.userId;
        },
        setUserID: function(id) {
            this.userId = id;
        },
        getLocale: function() {
            return this.locale.replace('_', '-');
        },
        setLocale: function(data) {
            let self = this;
            if (!data || !data.communication) {
                return false;
            }
            data.communication.forEach(function(item) {
                if (item.language) {
                    self.locale = item.language.coding[0].code;
                }
            });
            console.log("Locale ", this.locale);
        },
        getSettings: function() {
            return this.settings;
        },
        setSettings: function(data) {
            if (data) {
                this.settings = data;
            }
        },
        getUserInfo: function() {
            return this.userInfo;
        },
        setUserInfo: function(data) {
            if (data) {
                this.userInfo = data;
            }
        },
        getLRBaseURL: function() {
            return this.LifeRayBaseURL;
        },
        setLRBaseURL: function(data) {
            if (data) {
                this.LifeRayBaseURL = data;
            }
        },
        getCurrentView: function() {
            return this.currentView;
        },
        setCurrentView: function(viewId) {
            viewId = viewId || "intro";
            this.currentView = viewId;
        },
        isCurrentView: function(viewId) {
            return !this.hasError() && !this.isLoading() && this.isMatchView(viewId);
        },
        isMatchView: function(viewId) {
            return this.currentView === viewId;
        },
        goToView: function(viewId) {
            Vue.nextTick(
                function() {
                    self.resetError();
                    self.setCurrentView(viewId);
                }
            );
        },
        getSelectedDomain: function() {
           return this.activeDomain;
        },
        getSearchURL: function() {
            //TODO use current domain name as tag
            //pass in locale info
            return `/api/asset/tag/${this.getSelectedDomain()}?locale_code=${this.getLocale()}`;
            //CORS issue with querying LR directly, TODO: uncomment this when resolves
            //return  `${this.getLRBaseURL()}//c/portal/truenth/asset/query?content=true&anyTags=exercise?languageId=${this.getLocale}`;
        },
        getIntroContent: function() {
            if (this.introContent) {
                //already populated
                return this.introContent;
            }
            sendRequest(this.getSearchURL()).then(response => {
                this.setIntroContent(response);
                this.setCurrentView("intro");
            }).catch(e => {
                this.setErrorMessage(`Error occurred retrieving content: ${e.responseText}`);
            });
        },
        setIntroContent: function(data) {
            this.introContent = data;
        },
        goHome: function() {
            this.goToView("intro");
        }
    }
};

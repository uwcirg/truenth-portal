import NavMethods from "./Nav";
import VideoMethods from "./Video";
import {checkIE, getUrlParameter, tryParseJSON} from "./Utility";
export default {
    mounted: function() {
        Promise.all([
            this.$http(this.settingsURL).catch(error => { return error }),
            this.$http(this.meURL).catch(error => { return error }),
        ]).then(responses => {
            try {
                this.setSettings(JSON.parse(responses[0]));
            } catch(e) {
                this.setErrorMessage(`Error parsing data ${e}`);
            }
            try {
                this.userInfo = JSON.parse(responses[1]);
            } catch(e) {
                this.setErrorMessage(`Error parsing data ${e}`);
            }
            this.initApp();
            //console.log("settings? ", this.settings);
            //console.log("user? ", this.userInfo)
        }).catch(error => {
            this.setErrorMessage(`Error in promises ${error}`);
            this.initApp();
        });
    },
    watch: {
        $route(to, from) {
            /*
             * watch for manual hash change
             */
            if (to && to.params) {
                if (!to.params.topic) {
                    location.reload();
                    return false;
                }
                if (this.domains.indexOf(to.params.topic) !== -1) {
                    location.reload();
                    return false;
                }
            }
        }
    },
    mixins: [NavMethods, VideoMethods],
    /*
     * methods available to the application
     */
    methods: {
        isLoading() {
            return this.loading;
        },
        isInitialized() {
            return this.initialized;
        },
        initApp() {
            this.setSettings(this.settings);
            this.setLRBaseURL(this.settings?this.settings["LR_ORIGIN"]:"");
            this.setUserID(this.userInfo?this.userInfo["id"]:0);
            this.initialized = true;
            if (!this.getUserID()) {
                this.setSelectedDomain();
                this.getDomainContent();
                return;
            }
            Promise.all([
                 //TODO init user domains, call api based on user id
                this.$http(`/api/demographics/${this.getUserID()}`).catch(error => { return error }),
                this.$http("//geoip.cirg.washington.edu/json/")
            ]).then(responses => {
                try {
                    this.setLocale(JSON.parse(responses[0]));
                } catch(e) {
                    this.setErrorMessage(`Error parsing locale data ${e}`);
                }
                try {
                    this.setCountryCode(JSON.parse(responses[1]));
                } catch(e) {
                    this.setErrorMessage(`Error parsing country code data ${e}`);
                }

                //console.log("user locale? ", this.getLocale())
                //get welcome page
                //TODO filter content based on user's domains?
                //each domain link on the intro/welcome page should have a representative attribute or css class
                this.setSelectedDomain();
                //that denote which domain it represents
                this.getDomainContent();
               // self.setInitView();
            }).catch(error => {
                this.setErrorMessage(`Error in promises ${error}`);
                this.setInitView();
            });
        },
        setInitView() {
            //TODO if selected domain is default domain, need to filter content based on topics for subject
            Vue.nextTick(() => {
                    setTimeout(function() {
                        this.goToTop();
                        this.setCurrentView("domain");
                        this.loading = false;
                    }.bind(this), 350);
                }
            );
        },
        hasError() {
            return this.errorMessage !== "";
        },
        resetError() {
            this.setErrorMessage("");
        },
        setErrorMessage(message) {
            this.errorMessage += (this.errorMessage?"<br/>": "") + message;
        },
        getUserID() {
            return this.userId;
        },
        setUserID(id) {
            this.userId = id;
        },
        getLocale() {
            return this.locale.replace('_', '-');
        },
        setLocale(data) {
            //let self = this;
            if (!data || !data.communication) {
                return false;
            }
            data.communication.forEach(item => {
                if (item.language &&
                    item.language.coding &&
                    item.language.coding.length) {
                    this.locale = item.language.coding[0].code;
                }
            });
            console.log("Locale ", this.locale);
        },
        getCountryCode() {
           return this.countryCode;
         //return "GB";
         //return "CA";
        },
        setCountryCode(data) {
            if (!data || !data.country_code) return false;
            this.countryCode = data.country_code;
        },
        getEligibleCountryCodes() {
            return this.eligibleCountryCodes;
        },
        isEligibleCountryCode(countryCode) {
            if (!countryCode) return false;
            return this.eligibleCountryCodes.filter(item => {
                return item.code === countryCode.toUpperCase()
                
            }).length;
        },
        getSettings() {
            return this.settings;
        },
        setSettings(data) {
            if (data) {
                this.settings = data;
            }
        },
        getUserInfo() {
            return this.userInfo;
        },
        setUserInfo(data) {
            if (data) {
                this.userInfo = data;
            }
        },
        getLRBaseURL() {
            return this.LifeRayBaseURL;
        },
        setLRBaseURL(url) {
            if (url) {
                this.LifeRayBaseURL = url;
            }
        },
        getCurrentView() {
            return this.currentView;
        },
        setCurrentView(viewId) {
            viewId = viewId || "domain";
            this.currentView = viewId;
        },
        isCurrentView(viewId) {
            return !this.isLoading() && this.isMatchView(viewId);
        },
        isMatchView(viewId) {
            return this.currentView === viewId;
        },
        goToTop() {
            document.body.scrollTop = 0; // For Safari
            document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
        },
        goToView(viewId) {
            Vue.nextTick(
                () => {
                    this.resetError();
                    this.setCurrentView(viewId);
                }
            );
        },
        setCollapsible() {
            let collapsibleElements = document.querySelectorAll(".collapsible");
            collapsibleElements.forEach(el => {
                el.addEventListener('click', event => {
                    let parentEl = event.target.parentElement;
                    let collapsibleItems = parentEl.querySelectorAll(".collapsible");
                    collapsibleItems.forEach(item => {
                        if (item === event.target) return true;
                        item.classList.remove("open");
                    });
                    if (event.target.classList.contains("open")) {
                        event.target.classList.remove("open");
                        return;
                    }
                    event.target.classList.add("open");
                });
            })
        },
        setTileLinkEvent() {
            let tileElements = document.querySelectorAll(".tiles-container .tile");
            tileElements.forEach(el => {
                let anchorLink = el.querySelector("a");
                if (anchorLink && anchorLink.getAttribute("href")) {
                    el.addEventListener("click", function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        window.open(anchorLink.getAttribute("href"), anchorLink.getAttribute("data-location")? 
                        ("_"+anchorLink.getAttribute("data-location").replace("_", "")): "_blank");
                        return false;
                    });
                }
            });
        },
        initRouterEvents() {
            if (checkIE()) {
                 window.addEventListener("hashchange", () => {
                    let routerTopic = this.getRouterTopic();
                    if (routerTopic) {
                        window.location.reload();
                        return false;
                    }
                    return false;
                });
            }
        },
        getRouterTopic() {

           if (checkIE()) { // detect it's IE11
                var currentPath = window.location.hash.slice(1)
                if (this.$route.path !== currentPath) {
                    this.$router.push(currentPath)
                }
            }

            if (this.$route &&
                this.$route.params && 
                this.$route.params.topic &&
                this.domains.indexOf(this.$route.params.topic.toLowerCase()) !== -1) {
                return this.$route.params.topic;
            }
            let arrHashText = String(location.hash).split("#");
            if (arrHashText && arrHashText[1]) {
                let matchText = arrHashText[1].replace("/", "");
                if (this.domains.indexOf(matchText.toLowerCase()) !== -1) {
                    return matchText;
                }
                return "";
            } 
            return "";
        },
        setSelectedDomain() {
            let routerTopic = this.getRouterTopic();
            let queryTopic = getUrlParameter("topic") || getUrlParameter("domain");
            if (queryTopic) {
                this.activeDomain = queryTopic;
                return;
            }
            if (routerTopic) {
                this.activeDomain = routerTopic;
                return;
            }
            //TODO this should be the default landing topic/tag
            this.activeDomain = "default_domain";
        },
        getSelectedDomain() {
            //example URL that works: 
            //https://amy-dev.cirg.washington.edu/substudy-tailored-content#/insomnia
            //https://amy-dev.cirg.washington.edu/substudy-tailored-content?topic=hot_flashes
            return this.activeDomain;
         },
         getSearchURL(searchTag) {
             searchTag = searchTag || this.getSelectedDomain();
             //TODO use current domain name as tag
             //pass in locale info
             return `/api/asset/tag/${searchTag}?locale_code=${this.getLocale()}`;
             //CORS issue with querying LR directly, TODO: uncomment this when resolves
            //  return  `${this.getLRBaseURL()}/c/portal/truenth/asset/query?content=true&anyTags=${this.getSelectedDomain()}&languageId=${this.getLocale()}`;
         },
        onDomainContentDidLoad() {
            setTimeout(function() {
                this.setInitView();
                this.setCurrentView("domain");
            }.bind(this), 150);
            this.setResourcesByCountry();
            this.initNav();
            this.initRouterEvents();
            this.setCollapsible();
            this.initVideo();
            this.setTileLinkEvent();
            this.initDebugModeEvent();
        
        },
        getDomainContent() {
            if (this.domainContent) {
                //already populated
                this.setInitView();
                return this.domainContent;
            }
            this.$http(this.getSearchURL()).then(response => {
                if (response) {
                    this.setDomainContent(response);
                    Vue.nextTick()
                    .then(() => {
                        // DOM updated
                        this.onDomainContentDidLoad();
                    });
                    
                } else {
                    this.setErrorMessage(`Error occurred retrieving content: no content returned.`);
                    this.setInitView(true);
                }
            }).catch(e => {
                console.log("failed? ", e)
                this.getContentAttempt++;
                if (this.getContentAttempt <= 2) {
                    this.getDomainContent();
                    return;
                } else {
                    this.getContentAttempt = 0;
                }
                this.setErrorMessage(`Error occurred retrieving content: ${e.statusText}`);
                this.loading = false;
               // this.setInitView();
            });
        },
        setDomainContent: function(data) {
            let content = tryParseJSON(data);
            if (content) {
                this.domainContent = content["results"][0]["content"];
                return;
            }
            this.domainContent = data;
        },
        setResourcesByCountry(countryCode) {
            let resourceSection = document.querySelector(".resource-section");
            if (!resourceSection) {
                return;
            }
            countryCode = countryCode ||this.getCountryCode();
            if (!this.isEligibleCountryCode(countryCode)) {
                return;
            }
            if (!this.debugMode && (countryCode === this.defaultCountryCode || !countryCode)) return;
            if (this.debugMode && countryCode === this.defaultCountryCode) {
                location.reload();
                return;
            }
            this.$http(this.getSearchURL(`resources_${this.getSelectedDomain()}_${countryCode}`)).then(response => {
                if (response) {
                    resourceSection.querySelector(".content").innerHTML = response;
                    
                } else {
                    this.setErrorMessage(`Error occurred retrieving content: no content returned.`);
                    this.setInitView(true);
                }
            }).catch(e => {
                console.log(`error fetching resources for country code ${countryCode} `, e)
            });
           
        },
        goHome: function() {
            this.goToView("domain");
        },
        initDebugModeEvent: function() {
            /*
             * activating debugging tool by pressing Ctrl + Shift + d
             */
            document.addEventListener("keydown", event => {
                if (event.ctrlKey && 
                    event.shiftKey &&
                    event.key.toLowerCase() === "d")
                this.debugMode = true;
            });
        },
        isDebugMode: function() {
            return this.debugMode;
        }
    }
};

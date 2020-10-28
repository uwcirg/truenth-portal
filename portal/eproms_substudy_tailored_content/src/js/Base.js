import NavMethods from "./Nav";
import VideoMethods from "./Video";
import {checkIE, getUrlParameter, tryParseJSON, PromiseAllSettledPolyfill} from "./Utility";

export default {
    created() {
        PromiseAllSettledPolyfill();
    },
    mounted() {
        Promise.allSettled([
            this.$http(this.settingsURL).catch(error => { return error }),
            this.$http(this.meURL).catch(error => { return error }),
            this.$http(this.geoIPURL),
            this.$http(this.domainMappingsURL),
        ]).then(responses => {
            try {
                //set config settings
                this.setSettings(JSON.parse(responses[0].value));
            } catch(e) {
                //log error to console
                this.setErrorMessage(`Error parsing data ${e}`);
            }
            try {
                //set user email and id
                this.userInfo = JSON.parse(responses[1].value);
            } catch(e) {
                //log error to console
                this.setErrorMessage(`Error parsing user data ${e}`);
            }
            try {
                //set country code
                this.setCountryCode(JSON.parse(responses[2].value));
            } catch(e) {
                //log error to console
                this.setErrorMessage(`Error parsing country code data ${e}`);
            }
            try {
                //set domain mappings
                this.domainMappings = JSON.parse(responses[3].value);
            } catch(e) {
                //log error to console
                this.setErrorMessage(`Error parsing domain mapping data ${e}`);
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
            Promise.allSettled(
                this.getUserID()?
                [
                    this.$http(`/api/demographics/${this.getUserID()}`).catch(error => { return error }),
                    this.$http(`/api/user/${this.getUserID()}/triggers`)
                ] :
                [new Promise((resolve, reject) => setTimeout(() => reject(new Error("No user Id found.")), 0))]
            ).then(responses => {
                try {
                    this.setLocale(JSON.parse(responses[0].value));
                } catch(e) {
                    //log error to console
                    this.setErrorMessage(`Error parsing locale data ${e}`);
                }
                //TODO get user domains based on trigger API
                try {
                    this.setUserDomains(JSON.parse(responses[1].value));
                } catch(e) {
                    //log error to console
                    this.setErrorMessage(`Error parsing trigger data ${e}`);
                }
                this.setSelectedDomain();
                //populate domain content
                this.getDomainContent();
            }).catch(error => {
                this.setErrorMessage(`Error in promises ${error}`);
                this.setInitView();
            });
        },
        setInitView() {
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
            this.errorMessage += (this.errorMessage?"\n": "") + message;
            //error will be log to console
            console.error(this.errorMessage);
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
            //console.log("Locale ", this.locale);
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
        getUserDomains() {
            return this.userDomains;
        },
        setUserDomains(data) {
            if (!data || !data.triggers || !data.triggers.domain) {
                return false;
            }
            let hardTriggerDomains = (data.triggers.domain).filter(item => {
                let entry = Object.entries(item);
                return entry[0] && entry[0][1] && entry[0][1].indexOf("hard") !== -1;
            });
            this.userDomains = (hardTriggerDomains).map(item => {
                return this.domainMappings[Object.keys(item)[0]];
            });
            this.userDomains = this.userDomains.filter((d, index) => {
                return this.userDomains.indexOf(d) === index;
            });
            //console.log("user domain? ", this.userDomains);
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
            this.activeDomain = this.defaultDomain;
        },
        getSelectedDomain() {
            //example URL that works: 
            //https://amy-dev.cirg.washington.edu/substudy-tailored-content#/insomnia
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
                this.getContentAttempt++;
                if (this.getContentAttempt <= 2) {
                    this.getDomainContent();
                    return;
                } else {
                    this.getContentAttempt = 0;
                }
                this.setErrorMessage(`Error occurred retrieving content: ${e.statusText}`);
                this.loading = false;
            });
        },
        setDomainContent: function(data) {
            let content = tryParseJSON(data);
            if (content) {
                this.domainContent = content["results"][0]["content"];
                return;
            }
            this.domainContent = data;
            //filter content of default landing page based on user trigger-based domains
            if (this.getSelectedDomain() === this.defaultDomain) {
                Vue.nextTick()
                    .then(() => {
                        // DOM updated
                        this.processDefaultDomainContent();
                    });
                
            }
        },
        processDefaultDomainContent() {
            if (!this.getUserDomains().length) return;
            let hardTriggerTiles = document.querySelectorAll("#hardTriggerTopicsContainer .tile");
            hardTriggerTiles.forEach(item => {
                if (this.getUserDomains().indexOf(item.getAttribute("data-topic")) === -1) {
                    item.classList.add("hide");
                }
            });

            document.querySelector("#hardTriggerTopicsContainer").classList.add("show");
            
            let otherTopicTiles = document.querySelectorAll("#otherTopicsContainer .tile");
            otherTopicTiles.forEach(item => {
                if (this.getUserDomains().indexOf(item.getAttribute("data-topic")) !== -1) {
                    item.classList.add("hide");
                }
            });
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
                    //log error to console
                    this.setErrorMessage(`Error occurred retrieving content: no content returned.`);
                    this.setInitView(true);
                }
            }).catch(e => {
                this.setErrorMessage(`error fetching resources for country code ${countryCode} `, e)
            });
           
        },
        goHome: function() {
            this.goToView("domain");
        },
        initDebugModeEvent: function() {
            /*
             * activating debugging tool by pressing Ctrl + Shift + d
             */
            if (document) {
                document.addEventListener("keydown", event => {
                    if (event.ctrlKey && 
                        event.shiftKey &&
                        event.key.toLowerCase() === "d") {
                        this.debugMode = true;
                        console.log("current data ", this.$data);
                        return false;
                    }
                    
                });
            }
        },
        isDebugMode: function() {
            return this.debugMode;
        }
    }
};


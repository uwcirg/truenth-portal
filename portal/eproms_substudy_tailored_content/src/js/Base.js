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
                if (this.domains.indexOf(to.params.topic) !== -1 ||
                    this.mainPageIdentifiers.indexOf(to.params.topic) !== -1) {
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
                  //this.$http(`/static/files/substudy_test_triggers_new.json`)
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
        getDefaultDomains() {
            return Object.keys(this.domainMappings);
        },
        getUserDomains() {
            return this.userDomains;
        },
        setUserDomains(data) {
            this.userDomains = [];
            if (!data || !data.triggers || !data.triggers.domain) {
                return false;
            }
            let self = this;
            for (let key in data.triggers.domain) {
                for (let q in data.triggers.domain[key]) {
                    if (["hard", "soft"].indexOf(data.triggers.domain[key][q]) !== -1) {
                        if (self.domainMappings[key]) {
                            self.userDomains.push(self.domainMappings[key]);
                        }
                        if (self.getDefaultDomains().indexOf(key) !== -1) {
                            self.userDomains.push(key);
                        }
                    }
                }
            }
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
                (this.domains.indexOf(this.$route.params.topic.toLowerCase()) !== -1 ||
                 this.mainPageIdentifiers.indexOf(this.$route.params.topic.toLowerCase()) !== -1
                )) {
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
            this.initNav();
            this.initRouterEvents();
            this.setCollapsible();
            this.setTileLinkEvent();
            this.setVideoByDomainTopic();
            this.setResourcesByCountry();
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
            let triggerElements = document.querySelectorAll(".trigger");
            if (!this.getUserDomains().length) {
                triggerElements.forEach(el => {
                    el.classList.remove("show");
                    el.classList.add("hide");
                })
                return;
            }
            let hardTriggerTiles = document.querySelectorAll("#hardTriggerTopicsContainer .tile");
            hardTriggerTiles.forEach(item => {
                item.classList.remove("hide");
                if (this.getUserDomains().indexOf(item.getAttribute("data-topic")) === -1) {
                    item.classList.add("hide");
                }
            });

            document.querySelector("#hardTriggerTopicsContainer").classList.add("show");
            
            let otherTopicTiles = document.querySelectorAll("#otherTopicsContainer .tile");
            otherTopicTiles.forEach(item => {
                item.classList.remove("hide");
                if (this.getUserDomains().indexOf(item.getAttribute("data-topic")) !== -1) {
                    item.classList.add("hide");
                }
            });
            triggerElements.forEach(el => {
                el.classList.add("show");
            })
        },
        setResourcesByCountry(countryCode) {

            let resourceSections = document.querySelectorAll(`.resource-section`);
            if (!resourceSections.length) {
                return;
            }
            countryCode = countryCode ||this.getCountryCode();
            if (!this.isEligibleCountryCode(countryCode)) {
                return;
            }
            resourceSections.forEach(resourceSection => {
                let topic = resourceSection.getAttribute("data-topic");
                if (!topic) {
                    return true;
                }
                this.$http(this.getSearchURL(`resources_${topic}_${countryCode.toLowerCase()}`)).then(response => {
                    if (!response) {
                         //log error to console
                         this.setErrorMessage(`Error occurred retrieving ${countryCode} resource content: no content returned.`);
                         return;
                    }
                    if (!resourceSection.querySelector(".content")) {
                        let div = document.createElement("div");
                        div.classList.add("content");
                        resourceSection.append(div);
                    }
                    resourceSection.querySelector(".content").innerHTML = response;
                }).catch(e => {
                    this.setErrorMessage(`error fetching resources for country code ${countryCode} `, e)
                });
            });
        },
        setVideoByDomainTopic() {
            let videoSections = document.querySelectorAll(`.video-section`);
            if (!videoSections.length) {
                return;
            }
            videoSections.forEach(videoSection => {
                if (videoSection.querySelector(".video")) {
                    this.initVideo();
                    return true;
                }
                let videoTopic = videoSection.getAttribute("data-topic");
                if (!videoTopic) {
                    return true;
                }
                this.$http(this.getSearchURL(`video_${videoTopic}`)).then(response => {
                    if (!response) {
                         //log error to console
                         this.setErrorMessage(`Error occurred retrieving ${videoTopic} video content: no content returned.`);
                         return;
                    }
                    videoSection.innerHTML = response;
                    Vue.nextTick()
                    .then(() => {
                        // DOM updated
                        this.initVideo();
                    });
                }).catch(e => {
                    this.setErrorMessage(`error fetching video for ${videoTopic} `, e);
                });
            });
            this.initVideoEvents();
        },
        goHome() {
            this.goToView("domain");
        },
        initDebugModeEvent() {
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
        submitTestTriggers() {
            let testChkElements = document.querySelectorAll("#debugContainer .trigger-checkbox");
            let testData = {
                triggers: {
                    domain: {}
                }
            };
            testChkElements.forEach(el => {
                if (el.checked) {
                    testData.triggers.domain[el.value] = {"ironman_ss": "hard"}
                }
            });
            //log test data to console for debugging
            console.log("test data? ", testData);
            this.setUserDomains(testData);
            this.processDefaultDomainContent();
            //log updated date to console for debugging
            console.log("updated data ", this.$data);
        },
        isDebugMode () {
            return this.debugMode;
        },
        unsetDebugMode() {
            this.debugMode = false;
        }
    }
};

